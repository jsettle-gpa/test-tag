# tagEvent/shiftLifeCycle.py
import traceback

from mes.util.tagPathBuilder import LineTagPaths

logger = system.util.getLogger("tagEvent.shiftLifeCycle")

DS_COLS = [
	"startTime",
	"endTime",
	"durationSec",
	"reasonCode",
	"stateDescription",
	"color",
	"icon",
	"stateCategory",
	"isMicro"
]


def toInt(v, d=0):
	try:
		if v is None:
			return int(d)
		return int(v)
	except:
		return int(d)


def toLong(v, d=0):
	try:
		if v is None:
			return long(d)
		return long(v)
	except:
		return long(d)


def normText(v):
	try:
		if v is None:
			return ""
		return str(v).strip().lower()
	except:
		return ""


def emptyStateChangeDS():
	return system.dataset.toDataSet(DS_COLS, [])


def lookupStateMeta(statesDs, stateCode):
	"""
	statesDs expected columns:
	- reasonCode
	- stateDescription
	- color
	- icon
	- stateCategory

	returns:
	(stateDescription, color, icon, stateCategory)
	"""
	if statesDs is None:
		return ("", "", "", "")

	code = toInt(stateCode, -1)

	try:
		for r in range(statesDs.getRowCount()):
			try:
				if toInt(statesDs.getValueAt(r, "reasonCode"), -999) == code:
					desc = statesDs.getValueAt(r, "stateDescription")
					color = statesDs.getValueAt(r, "color")
					icon = statesDs.getValueAt(r, "icon")
					cat = statesDs.getValueAt(r, "stateCategory")

					return (
						"" if desc is None else str(desc),
						"" if color is None else str(color),
						"" if icon is None else str(icon),
						"" if cat is None else str(cat)
					)
			except:
				pass
	except:
		pass

	return ("", "", "", "")


def isRunningState(statesDs, stateCode):
	_, _, _, cat = lookupStateMeta(statesDs, stateCode)
	return normText(cat) == "running"


def summarizeValue(v):
	"""
	Keep logs readable. Avoid dumping huge dataset contents.
	"""
	try:
		if hasattr(v, "getRowCount") and hasattr(v, "getColumnCount"):
			return "Dataset(rows=%s, cols=%s)" % (v.getRowCount(), v.getColumnCount())
		if isinstance(v, basestring):
			if len(v) > 200:
				return v[:200] + "...(%s chars)" % len(v)
			return v
		return str(v)
	except:
		return "<unprintable>"


def handleShiftChange(tagPathString, previousValue, currentValue, initialChange, missedEvents):
	if initialChange:
		return
	if currentValue is None or (not currentValue.quality.isGood()):
		return

	try:
		newShiftId = currentValue.value
		if newShiftId is None or str(newShiftId) == "NO_SHIFT":
			return

		prevShiftId = previousValue.value if (previousValue is not None and previousValue.quality.isGood()) else None
		if prevShiftId is not None and str(prevShiftId) == str(newShiftId):
			return

		paths = LineTagPaths.fromTagPath(tagPathString)

		readPaths = [
			paths.currentShift.shiftStartTime,
			paths.machine.state,
			paths.config.states
		]

		qv = system.tag.readBlocking(readPaths)

		# Log bad reads with path-level detail
		readBads = []
		for i in range(len(qv)):
			if not qv[i].quality.isGood():
				readBads.append("%s => %s" % (readPaths[i], str(qv[i].quality)))

		if readBads:
			logger.warn(
				"shiftLifeCycle read quality issues"
				"\ntriggerTag=%s"
				"\nprevShiftId=%s"
				"\nnewShiftId=%s"
				"\nreadFailures:\n%s" % (
					str(tagPathString),
					str(prevShiftId),
					str(newShiftId),
					"\n".join(readBads)
				)
			)

		shiftStart = qv[0].value if qv[0].quality.isGood() else None
		currentStateCode = toInt(qv[1].value if qv[1].quality.isGood() else None, 0)
		statesDs = qv[2].value if qv[2].quality.isGood() else None

		nowTs = system.date.now()
		seedStart = shiftStart if shiftStart is not None else nowTs

		durMs = system.date.millisBetween(seedStart, nowTs)
		if durMs < 0:
			durMs = 0
		durSec = long(durMs / 1000)

		stateDescription, color, icon, stateCategory = lookupStateMeta(statesDs, currentStateCode)
		isMicro = False

		rowToAdd = [
			seedStart,
			nowTs,
			durSec,
			currentStateCode,
			stateDescription,
			color,
			icon,
			stateCategory,
			bool(isMicro)
		]

		dsValue = emptyStateChangeDS()
		dsValue = system.dataset.addRow(dsValue, rowToAdd)

		running = isRunningState(statesDs, currentStateCode)

		seedRunSec = long(durSec) if running else long(0)
		seedDownSec = long(0) if running else long(durSec)

		writePaths = [
			paths.currentShift.counts.good,
			paths.currentShift.counts.reject,
			paths.currentShift.productsProduced,
			paths.currentShift.states.totalDownSeconds,
			paths.currentShift.states.totalRunningSeconds,
			paths.currentShift.states.microStopSeconds,
			paths.currentShift.states.microStopCount,
			paths.currentShift.states.lastState,
			paths.currentShift.states.lastStateChangeTime,
			paths.currentShift.states.isRunning,
			paths.currentShift.states.stateChangeDS
		]

		writeVals = [
			0,
			0,
			0,
			seedDownSec,
			seedRunSec,
			long(0),
			int(0),
			currentStateCode,
			seedStart,
			bool(running),
			dsValue
		]

		results = system.tag.writeBlocking(writePaths, writeVals)

		bads = []
		for i in range(len(results)):
			if not results[i].isGood():
				bads.append(
					"path=%s | value=%s | result=%s" % (
						writePaths[i],
						summarizeValue(writeVals[i]),
						str(results[i])
					)
				)

		if bads:
			logger.warn(
				"shiftLifeCycle bad writes"
				"\ntriggerTag=%s"
				"\nprevShiftId=%s"
				"\nnewShiftId=%s"
				"\nseedStart=%s"
				"\nnowTs=%s"
				"\ndurSec=%s"
				"\ncurrentStateCode=%s"
				"\nstateDescription=%s"
				"\nstateCategory=%s"
				"\nrunning=%s"
				"\nwriteFailures:\n%s" % (
					str(tagPathString),
					str(prevShiftId),
					str(newShiftId),
					str(seedStart),
					str(nowTs),
					str(durSec),
					str(currentStateCode),
					str(stateDescription),
					str(stateCategory),
					str(running),
					"\n".join(bads)
				)
			)
# DEBUG
#		else:
#			logger.info(
#				"shiftLifeCycle success"
#				"\ntriggerTag=%s"
#				"\nprevShiftId=%s"
#				"\nnewShiftId=%s"
#				"\ncurrentStateCode=%s"
#				"\nrunning=%s" % (
#					str(tagPathString),
#					str(prevShiftId),
#					str(newShiftId),
#					str(currentStateCode),
#					str(running)
#				)
#			)

	except Exception as e:
		logger.error(
			"shiftLifeCycle failed"
			"\ntriggerTag=%s"
			"\npreviousValue=%s"
			"\ncurrentValue=%s"
			"\nerror=%s"
			"\n%s" % (
				str(tagPathString),
				str(previousValue.value if previousValue is not None else None),
				str(currentValue.value if currentValue is not None else None),
				str(e),
				traceback.format_exc()
			)
		)