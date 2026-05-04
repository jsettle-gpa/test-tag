# mes/shiftCounts.py

import system
import tagUtils
from tagEvent.jobCounts import toLong, computeDelta

logger = system.util.getLogger("mes.shiftCounts")


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

def updateOutfeed(shiftRoot, currentValue, previousValue, initialChange, allowResetToCurrent=True):
	countsRoot = shiftRoot.rstrip("/") + "/shiftCounts"
	return updateAccumulator(currentValue, previousValue, initialChange, countsRoot + "/GoodCount", allowResetToCurrent)

def updateReject(shiftRoot, currentValue, previousValue, initialChange, allowResetToCurrent=True):
	countsRoot = shiftRoot.rstrip("/") + "/shiftCounts"
	return updateAccumulator(currentValue, previousValue, initialChange, countsRoot + "/RejectCount", allowResetToCurrent)