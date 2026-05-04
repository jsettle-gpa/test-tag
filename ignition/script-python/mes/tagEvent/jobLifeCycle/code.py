# mes/tagEvent/jobLifeCycle.py
"""
CurrentJob lifecycle handlers.

Responsibilities:
- On activeRun False -> True:
  - read runId
  - hydrate CurrentJob fields from DB
  - populate OEE input tags
- On activeRun True -> False:
  - reset CurrentJob counts/state/OEE input tags

This module reacts to CurrentJob/activeRun changes.
"""

import traceback

from mes.util.tagPathBuilder import LineTagPaths

logger = system.util.getLogger("tagEvent.jobLifeCycle")

NQ_GET_RUN_CONTEXT = "Tags/CurrentJob/startRun"

STATE_DS_COLUMNS = [
	"startTime",
	"endTime",
	"durationSec",
	"reasonCode",
	"stateDescription",
	"stateCategory",
	"isMicro"
]


def toBool(value, defaultValue=False):
	try:
		if value is None:
			return bool(defaultValue)
		if isinstance(value, bool):
			return value

		s = str(value).strip().lower()
		if s in ["true", "1", "yes", "y", "on"]:
			return True
		if s in ["false", "0", "no", "n", "off"]:
			return False

		return bool(value)
	except:
		return bool(defaultValue)


def secondsBetween(startValue, endValue):
	try:
		if startValue is None or endValue is None:
			return 0
		return max(0, int(system.date.secondsBetween(startValue, endValue)))
	except:
		return 0


def emptyStateDataset():
	return system.dataset.toDataSet(STATE_DS_COLUMNS, [])


def firstRow(ds):
	"""
	Convert the first dataset row to a dict.
	Returns None if dataset is empty.
	"""
	if ds is None or ds.getRowCount() <= 0:
		return None

	row = {}
	for col in list(ds.getColumnNames()):
		row[col] = ds.getValueAt(0, col)
	return row


def writeBlockingChecked(paths, values):
	qs = system.tag.writeBlocking(paths, values)

	bads = []
	for i in range(len(qs)):
		if not qs[i].isGood():
			bads.append("%s => %s" % (paths[i], str(qs[i])))

	return bads


def buildResetPathsAndValues(paths):
	"""
	Build the reset write set for CurrentJob tags.
	"""
	writePaths = [
		# Counts
		paths.currentJob.counts.infeed,
		paths.currentJob.counts.outfeed,
		paths.currentJob.counts.reject,

		# State
		paths.currentJob.states.totalRunningSeconds,
		paths.currentJob.states.totalDownSeconds,
		paths.currentJob.states.microStopSeconds,
		paths.currentJob.states.microStopCount,
		paths.currentJob.states.lastState,
		paths.currentJob.states.lastStateChangeTime,
		paths.currentJob.states.stateChangeDS,
		paths.currentJob.states.isRunning,

		# Planned time / OEE inputs
		paths.currentJob.runPlannedStartTime,
		paths.currentJob.runPlannedEndTime,
		paths.currentJob.oee.inputs.PPTSeconds,

		# Identity/config hydrated at run start
		paths.currentJob.bomId,
		paths.currentJob.productId,
		paths.currentJob.requiredQuantity,
		paths.currentJob.idealRunRate,
		paths.currentJob.productName
	]

	writeValues = [
		0, 0, 0,
		0, 0, 0, 0, None, None, emptyStateDataset(), False,
		None, None, 0,
		None, None, 0, 0, None
	]

	return writePaths, writeValues


def buildStartPathsAndValues(paths, row):
    ictPerPart = float(row.get("ict_per_part_sec") or 0)
    totalIct   = float(row.get("total_ict_sec")    or 0)
    idealRunRate = round(3600.0 / ictPerPart, 4) if ictPerPart > 0 else 0.0

    requiredQuantity = row.get("requiredQuantity") or 0
    productName      = row.get("productName")      or ""

    # PPT = total ideal time for this run (replaces planned start/end window)
    pptSeconds = totalIct if totalIct > 0 else 0

    writePaths = [
        paths.currentJob.productName,
        paths.currentJob.requiredQuantity,
        paths.currentJob.idealRunRate,
        paths.currentJob.oee.inputs.PPTSeconds,
        # Write ICTSeconds to CurrentShift so micro-stop classification stays correct
        paths.currentShift.oee.inputs.ICTSeconds,
    ]

    writeValues = [
        productName,
        requiredQuantity,
        idealRunRate,
        pptSeconds,
        ictPerPart,
    ]

    return writePaths, writeValues


def resetCurrentJob(tagPathString, previousValue, currentValue, initialChange, missedEvents):
	"""
	Attach to CurrentJob/activeRun valueChanged.
	On True -> False, clears CurrentJob run-scoped tags.
	"""
	if initialChange:
		return
	if currentValue is None or not currentValue.quality.isGood():
		return

	try:
		prevActive = toBool(previousValue.value if previousValue is not None and previousValue.quality.isGood() else None, False)
		newActive = toBool(currentValue.value, False)

		if not (prevActive and (not newActive)):
			return

		paths = LineTagPaths.fromTagPath(tagPathString)
		writePaths, writeValues = buildResetPathsAndValues(paths)

		bads = writeBlockingChecked(writePaths, writeValues)
		if bads:
			logger.warn("resetCurrentJob had bad writes:\n%s" % "\n".join(bads))
		else:
			logger.info("resetCurrentJob complete for %s" % paths.assetPath)

	except Exception as e:
		logger.error("resetCurrentJob failed: %s\n%s" % (str(e), traceback.format_exc()))


def startRun(tagPathString, previousValue, currentValue, initialChange, missedEvents):
	"""
	Attach to CurrentJob/activeRun valueChanged.
	On False to True, reads runId and calls DB to get values for CurrentJob UDT.
	"""
	if initialChange:
		return
	if currentValue is None or not currentValue.quality.isGood():
		return

	try:
		prevActive = toBool(previousValue.value if previousValue is not None and previousValue.quality.isGood() else None, False)
		newActive = toBool(currentValue.value, False)

		if not ((not prevActive) and newActive):
			return

		paths = LineTagPaths.fromTagPath(tagPathString)

		runIdQV = system.tag.readBlocking([paths.currentJob.runId])[0]
		if not runIdQV.quality.isGood():
			logger.warn("startRun: runId quality bad for %s" % paths.currentJob.runId)
			return

		runId = runIdQV.value
		if runId is None:
			logger.warn("startRun: runId is None for %s" % paths.assetPath)
			return

		ds = system.db.execQuery(NQ_GET_RUN_CONTEXT, {"runId": runId})
		row = firstRow(ds)
		if row is None:
			logger.warn("startRun: no query row for runId=%s" % str(runId))
			return

		writePaths, writeValues = buildStartPathsAndValues(paths, row)

		bads = writeBlockingChecked(writePaths, writeValues)
		if bads:
			logger.warn("startRun had bad writes for runId=%s:\n%s" % (str(runId), "\n".join(bads)))
		else:
			logger.info("startRun hydrated CurrentJob for runId=%s assetPath=%s" % (str(runId), paths.assetPath))

	except Exception as e:
		logger.error("startRun failed: %s\n%s" % (str(e), traceback.format_exc()))