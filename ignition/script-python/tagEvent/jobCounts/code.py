# mes/jobCounts.py
# Ignition Jython 2.7 script library

import system
import tagUtils

logger = system.util.getLogger("mes.jobCounts")

def toLong(v, defaultValue=0):
	try:
		if v is None:
			return long(defaultValue)
		return long(v)
	except:
		return long(defaultValue)

def computeDelta(currentValue, previousValue, initialChange, allowResetToCurrent=True):
	if initialChange:
		return 0

	cur = toLong(getattr(currentValue, "value", None), None)
	prev = toLong(getattr(previousValue, "value", None), None)

	if cur is None or prev is None:
		return 0

	delta = cur - prev
	if delta < 0:
		delta = cur if allowResetToCurrent else 0

	return toLong(delta, 0)

def addToTag(tagPath, delta):
	delta = toLong(delta, 0)
	if delta <= 0:
		return 0

	currentTotal = tagUtils.readTag(tagPath)
	currentTotal = toLong(currentTotal, 0)

	newTotal = currentTotal + delta
	tagUtils.writeTag(tagPath, newTotal)
	return delta

def updateAccumulator(currentValue, previousValue, initialChange, accumulatorPath, allowResetToCurrent=True):
	delta = computeDelta(
		currentValue=currentValue,
		previousValue=previousValue,
		initialChange=initialChange,
		allowResetToCurrent=allowResetToCurrent
	)
	return addToTag(accumulatorPath, delta)

def updateInfeed(jobRoot, currentValue, previousValue, initialChange, allowResetToCurrent=True):
	countsRoot = jobRoot.rstrip("/") + "/runCounts"
	return updateAccumulator(
		currentValue=currentValue,
		previousValue=previousValue,
		initialChange=initialChange,
		accumulatorPath=countsRoot + "/derivedInfeed",
		allowResetToCurrent=allowResetToCurrent
	)

def updateOutfeed(jobRoot, currentValue, previousValue, initialChange, allowResetToCurrent=True):
	countsRoot = jobRoot.rstrip("/") + "/runCounts"
	return updateAccumulator(
		currentValue=currentValue,
		previousValue=previousValue,
		initialChange=initialChange,
		accumulatorPath=countsRoot + "/derivedOutfeed",
		allowResetToCurrent=allowResetToCurrent
	)

def updateReject(jobRoot, currentValue, previousValue, initialChange, allowResetToCurrent=True):
	countsRoot = jobRoot.rstrip("/") + "/runCounts"
	return updateAccumulator(
		currentValue=currentValue,
		previousValue=previousValue,
		initialChange=initialChange,
		accumulatorPath=countsRoot + "/derivedReject",
		allowResetToCurrent=allowResetToCurrent
	)