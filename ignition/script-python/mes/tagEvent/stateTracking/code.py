# mes/tagEvent/stateTracking.py
"""
Shared state tracking for CurrentShift and CurrentJob.

Responsibilities:
- On machine state change:
  - close the previous state interval
  - append a row to the state-change dataset
  - accumulate running/down/microstop seconds
  - write the new current state markers

Scope rules:
- Shift writes only when CurrentShift/shiftId is valid
- Job writes only when CurrentJob/activeRun is True
"""

import traceback

from mes.util.tagPathBuilder import LineTagPaths

logger = system.util.getLogger("tagEvent.stateTracking")

NO_SHIFT = "NO_SHIFT"

STATE_DS_COLUMNS = [
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

STATE_CATEGORY_RUNNING = "running"


def toInt(value, defaultValue=0):
	try:
		if value is None:
			return int(defaultValue)
		return int(value)
	except:
		return int(defaultValue)


def toLong(value, defaultValue=0):
	try:
		if value is None:
			return long(defaultValue)
		return long(value)
	except:
		return long(defaultValue)


def toFloat(value, defaultValue=0.0):
	try:
		if value is None:
			return float(defaultValue)
		return float(value)
	except:
		return float(defaultValue)


def normText(value):
	try:
		if value is None:
			return ""
		return str(value).strip().lower()
	except:
		return ""


def ensureStateEventDataset(dsValue):
	"""
	Ensure the state dataset exists and matches the expected schema.
	"""
	if dsValue is None:
		return system.dataset.toDataSet(STATE_DS_COLUMNS, [])

	try:
		if list(dsValue.getColumnNames()) != STATE_DS_COLUMNS:
			return system.dataset.toDataSet(STATE_DS_COLUMNS, [])
	except:
		return system.dataset.toDataSet(STATE_DS_COLUMNS, [])

	return dsValue


def lookupStateMeta(statesDs, stateCode):
    """
    Find description/category/color/icon for a state code from Config/states dataset.
    Returns (description, category, color, icon).
    """
    if statesDs is None:
        return ("", "", "", "")

    code = toInt(stateCode, -1)

    try:
        for r in range(statesDs.getRowCount()):
            try:
                if toInt(statesDs.getValueAt(r, "reasonCode"), -999) == code:
                    desc  = statesDs.getValueAt(r, "stateDescription")
                    cat   = statesDs.getValueAt(r, "stateCategory")

                    try:
                        color = statesDs.getValueAt(r, "color")
                    except:
                        color = None

                    try:
                        icon = statesDs.getValueAt(r, "icon")
                    except:
                        icon = None

                    return (
                        "" if desc  is None else str(desc),
                        "" if cat   is None else str(cat),
                        "" if color is None else str(color),
                        "" if icon  is None else str(icon)
                    )
            except:
                pass
    except:
        pass

    return ("", "", "", "")


def isRunningState(statesDs, stateCode):
	"""
	True when the state code maps to a running category.
	"""
	if statesDs is None:
		return False

	code = toInt(stateCode, -1)

	try:
		for r in range(statesDs.getRowCount()):
			try:
				if toInt(statesDs.getValueAt(r, "reasonCode"), -999) == code:
					return normText(statesDs.getValueAt(r, "stateCategory")) == STATE_CATEGORY_RUNNING
			except:
				pass
	except:
		pass

	return False


def writeBlockingChecked(paths, values):
	qs = system.tag.writeBlocking(paths, values)

	bads = []
	for i in range(len(qs)):
		if not qs[i].isGood():
			bads.append("%s => %s" % (paths[i], str(qs[i])))

	if bads:
		logger.warn("stateTracking write issues:\n%s" % "\n".join(bads))

	return qs


def writeStateScope(
	lastStatePath,
	lastTimePath,
	dsPath,
	runSecPath,
	downSecPath,
	microSecPath,
	microCntPath,
	isRunningPath,
	ictPath,
	configStatesPath,
	eventTime,
	newStateCode
):
	"""
	Generic state accumulator used for both shift and job scopes.
	"""
	readPaths = [
		lastStatePath,
		lastTimePath,
		dsPath,
		runSecPath,
		downSecPath,
		microSecPath,
		microCntPath,
		isRunningPath,
		ictPath,
		configStatesPath
	]

	qv = system.tag.readBlocking(readPaths)

	oldStateValue = qv[0].value if qv[0].quality.isGood() else None
	oldTimeValue = qv[1].value if qv[1].quality.isGood() else None
	dsValue = qv[2].value if qv[2].quality.isGood() else None

	runSec = toLong(qv[3].value if qv[3].quality.isGood() else 0, 0)
	downSec = toLong(qv[4].value if qv[4].quality.isGood() else 0, 0)
	microSec = toLong(qv[5].value if qv[5].quality.isGood() else 0, 0)
	microCnt = toInt(qv[6].value if qv[6].quality.isGood() else 0, 0)

	ictSec = toFloat(qv[8].value if qv[8].quality.isGood() else 0.0, 0.0)
	statesDs = qv[9].value if qv[9].quality.isGood() else None

	dsValue = ensureStateEventDataset(dsValue)

	if oldTimeValue is None or oldStateValue is None:
		newIsRunning = isRunningState(statesDs, newStateCode)
		writeBlockingChecked(
			[lastStatePath, lastTimePath, isRunningPath],
			[newStateCode, eventTime, bool(newIsRunning)]
		)
		return

	oldStateCode = toInt(oldStateValue, 0)
	oldTime = oldTimeValue

	durationMs = system.date.millisBetween(oldTime, eventTime)
	if durationMs < 0:
		durationMs = 0

	durationSec = long(durationMs / 1000)

	stateDescription, stateCategory, stateColor, stateIcon = lookupStateMeta(statesDs, oldStateCode)
	oldWasRunning = isRunningState(statesDs, oldStateCode)

	isMicro = (not oldWasRunning) and (ictSec > 0) and (float(durationSec) < float(ictSec))

	dsValue = system.dataset.addRow(
		dsValue,
		[
			oldTime,
			eventTime,
			durationSec,
			oldStateCode,
			stateDescription,
			stateColor,
			stateIcon,
			stateCategory,
			bool(isMicro)
		]
	)

	if oldWasRunning:
		runSec += durationSec
	elif isMicro:
		microSec += durationSec
		microCnt += 1
	else:
		downSec += durationSec

	newIsRunning = isRunningState(statesDs, newStateCode)

	writeBlockingChecked(
		[
			lastStatePath,
			lastTimePath,
			dsPath,
			runSecPath,
			downSecPath,
			microSecPath,
			microCntPath,
			isRunningPath
		],
		[
			newStateCode,
			eventTime,
			dsValue,
			long(runSec),
			long(downSec),
			long(microSec),
			int(microCnt),
			bool(newIsRunning)
		]
	)


def writeCurrentShiftState(paths, eventTime, newStateCode):
	"""
	Write state accumulation to CurrentShift when a valid shift exists.
	"""
	shiftIdQV = system.tag.readBlocking([paths.currentShift.shiftId])[0]
	shiftId = shiftIdQV.value if shiftIdQV.quality.isGood() else None

	if shiftId is None or str(shiftId) == NO_SHIFT:
		return

	writeStateScope(
		lastStatePath=paths.currentShift.states.lastState,
		lastTimePath=paths.currentShift.states.lastStateChangeTime,
		dsPath=paths.currentShift.states.stateChangeDS,
		runSecPath=paths.currentShift.states.totalRunningSeconds,
		downSecPath=paths.currentShift.states.totalDownSeconds,
		microSecPath=paths.currentShift.states.microStopSeconds,
		microCntPath=paths.currentShift.states.microStopCount,
		isRunningPath=paths.currentShift.states.isRunning,
		ictPath=paths.currentShift.oee.inputs.ICTSeconds,
		configStatesPath=paths.config.states,
		eventTime=eventTime,
		newStateCode=newStateCode
	)


def writeCurrentJobState(paths, eventTime, newStateCode):
	"""
	Write state accumulation to CurrentJob when activeRun is True.
	"""
	activeRunQV = system.tag.readBlocking([paths.currentJob.activeRun])[0]
	activeRun = bool(activeRunQV.value) if activeRunQV.quality.isGood() else False

	if not activeRun:
		return

	writeStateScope(
		lastStatePath=paths.currentJob.states.lastState,
		lastTimePath=paths.currentJob.states.lastStateChangeTime,
		dsPath=paths.currentJob.states.stateChangeDS,
		runSecPath=paths.currentJob.states.totalRunningSeconds,
		downSecPath=paths.currentJob.states.totalDownSeconds,
		microSecPath=paths.currentJob.states.microStopSeconds,
		microCntPath=paths.currentJob.states.microStopCount,
		isRunningPath=paths.currentJob.states.isRunning,
		ictPath=paths.currentJob.oee.inputs.ICTSeconds,
		configStatesPath=paths.config.states,
		eventTime=eventTime,
		newStateCode=newStateCode
	)


def handleStateValueChanged(tagPathString, previousValue, currentValue, initialChange, missedEvents):
	"""
	Attach to MachineInput/state valueChanged.
	Writes both shift-scoped and job-scoped state accumulation using shared logic.
	"""
	if initialChange:
		return

	if currentValue is None or (not currentValue.quality.isGood()):
		return

	try:
		paths = LineTagPaths.fromTagPath(tagPathString)
		eventTime = currentValue.timestamp
		newStateCode = toInt(currentValue.value, 0)

		writeCurrentShiftState(paths, eventTime, newStateCode)
		writeCurrentJobState(paths, eventTime, newStateCode)

	except Exception as error:
		logger.error("handleStateValueChanged failed: %s\n%s" % (str(error), traceback.format_exc()))