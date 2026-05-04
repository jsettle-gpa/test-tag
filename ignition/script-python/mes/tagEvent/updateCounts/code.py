# mes/tagEvent/updateCounts.py
"""
Generic delta-based accumulator updater.

Responsibilities:
- Resolve line paths from the event tag path
- Compute delta once from a tag event
- Apply the same delta to one or more accumulator tags
- Keep event scripts minimal
"""

from mes.util.tagPathBuilder import LineTagPaths
from mes.util import tagAccess

logger = system.util.getLogger("tagEvent.updateCounts")


def tryToLong(value):
	try:
		if value is None:
			return None
		return long(value)
	except:
		return None


def summarizeValue(value):
	try:
		if value is None:
			return "None"
		return str(value)
	except:
		return "<unprintable>"


def computeDelta(tagPath, currentValue, previousValue, initialChange, allowResetToCurrent=True):
	"""
	Compute a positive counter delta from a tag valueChanged event.

	Returns:
		(delta, errorMessage)
	"""
	if initialChange:
		return (0, "initialChange=True")

	if currentValue is None or not currentValue.quality.isGood():
		return (0, "currentValue quality bad or missing")

	if previousValue is None or not previousValue.quality.isGood():
		return (0, "previousValue quality bad or missing")

	currentRaw = getattr(currentValue, "value", None)
	previousRaw = getattr(previousValue, "value", None)

	currentNumber = tryToLong(currentRaw)
	previousNumber = tryToLong(previousRaw)

	if currentNumber is None:
		return (0, "currentValue not numeric: %s" % summarizeValue(currentRaw))

	if previousNumber is None:
		return (0, "previousValue not numeric: %s" % summarizeValue(previousRaw))

	delta = currentNumber - previousNumber
	if delta < 0:
		delta = currentNumber if allowResetToCurrent else 0

	return (long(delta), None)


def applyDeltaBulk(accumulatorTagPaths, delta, defaultValue=0):
	"""
	Add the same delta to all accumulator tags using one bulk read and one bulk write.
	Returns the applied delta.
	"""
	deltaNumber = tryToLong(delta)
	if deltaNumber is None:
		logger.warn(
			"applyDeltaBulk skipped"
			"\nreason=delta not numeric"
			"\ndelta=%s" % summarizeValue(delta)
		)
		return 0

	if deltaNumber <= 0 or not accumulatorTagPaths:
		return 0

	qvs = tagAccess.readBlocking(accumulatorTagPaths)

	newValues = []
	readIssues = []

	defaultNumber = tryToLong(defaultValue)
	if defaultNumber is None:
		defaultNumber = 0

	for i in range(len(qvs)):
		qv = qvs[i]
		tagPath = accumulatorTagPaths[i]

		if not qv.quality.isGood():
			currentTotal = defaultNumber
			readIssues.append(
				"path=%s | reason=bad quality | quality=%s | fallback=%s" % (
					tagPath,
					str(qv.quality),
					str(defaultNumber)
				)
			)
		else:
			currentTotal = tryToLong(qv.value)
			if currentTotal is None:
				currentTotal = defaultNumber
				readIssues.append(
					"path=%s | reason=value not numeric | value=%s | fallback=%s" % (
						tagPath,
						summarizeValue(qv.value),
						str(defaultNumber)
					)
				)

		newValues.append(currentTotal + deltaNumber)

	if readIssues:
		logger.warn("applyDeltaBulk read fallbacks:\n%s" % "\n".join(readIssues))

	qs = tagAccess.writeBlocking(accumulatorTagPaths, newValues)

	bads = []
	for i in range(len(qs)):
		if not qs[i].isGood():
			bads.append(
				"path=%s | value=%s | result=%s" % (
					accumulatorTagPaths[i],
					summarizeValue(newValues[i]),
					str(qs[i])
				)
			)

	if bads:
		logger.warn("applyDeltaBulk write issues:\n%s" % "\n".join(bads))

	return deltaNumber


def updateCount(tagPath, accumulatorTagPaths, currentValue, previousValue, initialChange, allowResetToCurrent=True):
	delta, errorMessage = computeDelta(tagPath, currentValue, previousValue, initialChange, allowResetToCurrent)

	if errorMessage is not None:
		logger.warn(
			"Skipping count update"
			"\ntagPath=%s"
			"\nreason=%s"
			"\npreviousValue=%s"
			"\ncurrentValue=%s" % (
				str(tagPath),
				errorMessage,
				summarizeValue(getattr(previousValue, "value", None) if previousValue is not None else None),
				summarizeValue(getattr(currentValue, "value", None) if currentValue is not None else None)
			)
		)
		return 0

	if delta <= 0:
		return 0

	return applyDeltaBulk(accumulatorTagPaths, delta)


def resetBulk(tagPathsToReset, resetValue=0):
	"""
	Bulk reset helper for any list of tags.
	"""
	if not tagPathsToReset:
		return

	values = [resetValue for unused in tagPathsToReset]
	qs = tagAccess.writeBlocking(tagPathsToReset, values)

	bads = []
	for i in range(len(qs)):
		if not qs[i].isGood():
			bads.append("%s => %s" % (tagPathsToReset[i], str(qs[i])))

	if bads:
		logger.warn("resetBulk write issues:\n%s" % "\n".join(bads))


def getInfeedTargetsFromTagPath(tagPath):
	"""
	Build infeed accumulator targets from an event tag path.
	Infeed is currently job-only.
	"""
	paths = LineTagPaths.fromTagPath(tagPath)
	return [
		paths.currentJob.counts.infeed
	]


def getOutfeedTargetsFromTagPath(tagPath):
	"""
	Build outfeed accumulator targets from an event tag path.
	Outfeed updates:
	- CurrentJob/runCounts/derivedOutfeed
	- CurrentShift/shiftCounts/GoodCount
	"""
	paths = LineTagPaths.fromTagPath(tagPath)
	return [
		paths.currentJob.counts.outfeed,
		paths.currentShift.counts.good
	]


def getRejectTargetsFromTagPath(tagPath):
	"""
	Build reject accumulator targets from an event tag path.
	Reject updates:
	- CurrentJob/runCounts/derivedReject
	- CurrentShift/shiftCounts/RejectCount
	"""
	paths = LineTagPaths.fromTagPath(tagPath)
	return [
		paths.currentJob.counts.reject,
		paths.currentShift.counts.reject
	]


def handleInfeedValueChanged(tagPath, previousValue, currentValue, initialChange, missedEvents, allowResetToCurrent=True):
	try:
		targets = getInfeedTargetsFromTagPath(tagPath)
		return updateCount(tagPath, targets, currentValue, previousValue, initialChange, allowResetToCurrent)
	except Exception as e:
		logger.error(
			"Infeed count update failed"
			"\ntagPath=%s"
			"\npreviousValue=%s"
			"\ncurrentValue=%s"
			"\nerror=%s" % (
				str(tagPath),
				summarizeValue(getattr(previousValue, "value", None) if previousValue is not None else None),
				summarizeValue(getattr(currentValue, "value", None) if currentValue is not None else None),
				str(e)
			)
		)
		return 0


def handleOutfeedValueChanged(tagPath, previousValue, currentValue, initialChange, missedEvents, allowResetToCurrent=True):
	try:
		targets = getOutfeedTargetsFromTagPath(tagPath)
		return updateCount(tagPath, targets, currentValue, previousValue, initialChange, allowResetToCurrent)
	except Exception as e:
		logger.error(
			"Outfeed count update failed"
			"\ntagPath=%s"
			"\npreviousValue=%s"
			"\ncurrentValue=%s"
			"\nerror=%s" % (
				str(tagPath),
				summarizeValue(getattr(previousValue, "value", None) if previousValue is not None else None),
				summarizeValue(getattr(currentValue, "value", None) if currentValue is not None else None),
				str(e)
			)
		)
		return 0


def handleRejectValueChanged(tagPath, previousValue, currentValue, initialChange, missedEvents, allowResetToCurrent=True):
	try:
		targets = getRejectTargetsFromTagPath(tagPath)
		return updateCount(tagPath, targets, currentValue, previousValue, initialChange, allowResetToCurrent)
	except Exception as e:
		logger.error(
			"Reject count update failed"
			"\ntagPath=%s"
			"\npreviousValue=%s"
			"\ncurrentValue=%s"
			"\nerror=%s" % (
				str(tagPath),
				summarizeValue(getattr(previousValue, "value", None) if previousValue is not None else None),
				summarizeValue(getattr(currentValue, "value", None) if currentValue is not None else None),
				str(e)
			)
		)
		return 0