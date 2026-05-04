# tagEvent/jobStateTracking.py
logger = system.util.getLogger("tagEvent.jobStateTracking")

def toInt(value, defaultValue=0):
	try:
		if value is None:
			return int(defaultValue)
		return int(value)
	except:
		return int(defaultValue)

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

def isRunningState(statesDs, stateCode):
	if statesDs is None:
		return False
	try:
		stateCode = int(stateCode)
	except:
		return False

	for r in range(statesDs.getRowCount()):
		try:
			if int(statesDs.getValueAt(r, "reasonCode")) == stateCode:
				return normText(statesDs.getValueAt(r, "stateCategory")) == "running"
		except:
			pass
	return False


def handleStateValueChanged(tagPathStr, previousValue, currentValue, initialChange, missedEvents, configStatesPath=None):
	if initialChange:
		return
	if currentValue is None or not currentValue.quality.isGood():
		return

	jobRoot = str(tagPathStr).rsplit("/", 2)[0]
	lineRoot = str(tagPathStr).rsplit("/", 3)[0]
	if not lineRoot.endswith("/"):
		lineRoot += "/"

	activeQv = system.tag.readBlocking([jobRoot + "/activeRun"])[0]
	if (not activeQv.quality.isGood()) or (not bool(activeQv.value)):
		return

	eventTime = currentValue.timestamp
	newState = toInt(currentValue.value, 0)

	shiftStatesRoot = lineRoot + "CurrentShift/shiftStates/"

	lastStatePath   = shiftStatesRoot + "lastState"
	lastTimePath    = shiftStatesRoot + "lastStateChangeTime"
	dsPath          = shiftStatesRoot + "stateChangeDS"

	downSecPath     = shiftStatesRoot + "totalDownSeconds"
	runSecPath      = shiftStatesRoot + "totalRunningSeconds"
	microSecPath    = shiftStatesRoot + "microStopSeconds"
	microCntPath    = shiftStatesRoot + "microStopCount"
	isRunningPath   = shiftStatesRoot + "isRunning"

	ictPath = lineRoot + "CurrentShift/OEE/Inputs/ICTSeconds"

	if configStatesPath is None:
		mesRoot = jobRoot.rsplit("/", 1)[0]
		configStatesPath = mesRoot + "/Config/states"

	qv = system.tag.readBlocking([
		lastStatePath, lastTimePath, dsPath,
		downSecPath, runSecPath, microSecPath, microCntPath,
		ictPath, configStatesPath
	])

	oldState = qv[0].value
	oldTime  = qv[1].value
	ds       = qv[2].value

	downSec  = qv[3].value
	runSec   = qv[4].value
	microSec = qv[5].value
	microCnt = qv[6].value

	ictSec   = toFloat(qv[7].value, 0.0)
	statesDs = qv[8].value

	if downSec is None:  downSec  = 0
	if runSec is None:   runSec   = 0
	if microSec is None: microSec = 0
	if microCnt is None: microCnt = 0

	# First-time init: just store current state/time and isRunning
	if oldTime is None or oldState is None:
		newIsRunning = isRunningState(statesDs, newState)
		system.tag.writeBlocking(
			[lastStatePath, lastTimePath, downSecPath, runSecPath, microSecPath, microCntPath, isRunningPath],
			[newState, eventTime, long(downSec), long(runSec), long(microSec), int(microCnt), bool(newIsRunning)]
		)
		return

	# Duration in previous state
	durationMs = system.date.millisBetween(oldTime, eventTime)
	if durationMs < 0:
		durationMs = 0
	durationSec = long(durationMs / 1000)

	# Trace dataset (optional)
	cols = ["startTime", "endTime", "state", "durationSec", "isRunning", "isMicro"]
	if ds is None:
		ds = system.dataset.toDataSet(cols, [])
	else:
		try:
			if list(ds.getColumnNames()) != cols:
				ds = system.dataset.toDataSet(cols, [])
		except:
			ds = system.dataset.toDataSet(cols, [])

	oldWasRunning = isRunningState(statesDs, oldState)

	isMicro = False
	if oldWasRunning:
		runSec = long(runSec) + durationSec
	else:
		# classify micro if ICT is available
		if ictSec > 0 and durationSec < long(ictSec):
			isMicro = True
			microSec = long(microSec) + durationSec
			microCnt = int(microCnt) + 1
		else:
			downSec = long(downSec) + durationSec

	ds = system.dataset.addRow(ds, [oldTime, eventTime, toInt(oldState, 0), durationSec, bool(oldWasRunning), bool(isMicro)])

	# Live isRunning based on NEW state
	newIsRunning = isRunningState(statesDs, newState)

	# Write back new state/time and accumulators
	system.tag.writeBlocking(
		[lastStatePath, lastTimePath, dsPath, downSecPath, runSecPath, microSecPath, microCntPath, isRunningPath],
		[newState, eventTime, ds, long(downSec), long(runSec), long(microSec), int(microCnt), bool(newIsRunning)]
	)