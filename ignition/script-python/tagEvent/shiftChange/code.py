import system
import traceback
import tagUtils as tagUtil

logger = system.util.getLogger("app.shift.currentShift")

def writeShiftCountersCleared(currentShiftRootPath):
	paths = [
		currentShiftRootPath + "/Counts/baseline/baselineOutfeed",
		currentShiftRootPath + "/Counts/baseline/baselineInfeed",
		currentShiftRootPath + "/Counts/baseline/baselineReject",
		currentShiftRootPath + "/Counts/GoodCount",
		currentShiftRootPath + "/Counts/RejectCount",
		currentShiftRootPath + "/derived/runSeconds",
		currentShiftRootPath + "/derived/downSeconds"
	]
	values = [0, 0, 0, 0, 0, 0, 0]

	activeShiftIdPath = currentShiftRootPath + "/derived/activeShiftId"
	if tagUtil.tagExists(activeShiftIdPath):
		paths.append(activeShiftIdPath)
		values.append(-1)

	tagUtil.writeBlocking(paths, values)

def writeShiftCountersInitialized(currentShiftRootPath, lineRootPath, newShiftIdValue,
                                 outfeedRelativePath, infeedRelativePath, rejectRelativePath):
	outfeedPath = tagUtil.joinTagPath(lineRootPath, outfeedRelativePath)
	infeedPath  = tagUtil.joinTagPath(lineRootPath, infeedRelativePath)
	rejectPath  = tagUtil.joinTagPath(lineRootPath, rejectRelativePath)

	outfeedValue = tagUtil.readTagValueOrDefault(outfeedPath, 0)
	infeedValue  = tagUtil.readTagValueOrDefault(infeedPath, 0)
	rejectValue  = tagUtil.readTagValueOrDefault(rejectPath, 0)

	paths = [
		currentShiftRootPath + "/Counts/baseline/baselineOutfeed",
		currentShiftRootPath + "/Counts/baseline/baselineInfeed",
		currentShiftRootPath + "/Counts/baseline/baselineReject",
		currentShiftRootPath + "/Counts/GoodCount",
		currentShiftRootPath + "/Counts/RejectCount",
		currentShiftRootPath + "/derived/runSeconds",
		currentShiftRootPath + "/derived/downSeconds"
	]
	values = [
		outfeedValue,
		infeedValue,
		rejectValue,
		0,
		0,
		0,
		0
	]

	activeShiftIdPath = currentShiftRootPath + "/derived/activeShiftId"
	if tagUtil.tagExists(activeShiftIdPath):
		paths.append(activeShiftIdPath)
		values.append(int(newShiftIdValue))

	tagUtil.writeBlocking(paths, values)

def handleShiftIdValueChanged(tagPathString, previousShiftIdValue, currentShiftIdValue,
                             currentQualityValue,
                             outfeedRelativePath="MachineInput/outfeed",
                             infeedRelativePath="MachineInput/infeed",
                             rejectRelativePath="MachineInput/reject"):
	try:
		if currentQualityValue is not None and hasattr(currentQualityValue, "isGood"):
			if not currentQualityValue.isGood():
				return

		currentShiftRootPath = tagUtil.getCurrentShiftRootPathFromShiftIdTag(tagPathString)
		if currentShiftRootPath is None:
			return

		lineRootPath = tagUtil.getLineRootPathFromCurrentShiftTag(tagPathString)
		if lineRootPath is None:
			return

		if currentShiftIdValue is None:
			writeShiftCountersCleared(currentShiftRootPath)
			logger.info("Shift cleared because shiftId is None. currentShiftRootPath=%s" % currentShiftRootPath)
			return

		if previousShiftIdValue != currentShiftIdValue:
			writeShiftCountersInitialized(
				currentShiftRootPath=currentShiftRootPath,
				lineRootPath=lineRootPath,
				newShiftIdValue=currentShiftIdValue,
				outfeedRelativePath=outfeedRelativePath,
				infeedRelativePath=infeedRelativePath,
				rejectRelativePath=rejectRelativePath
			)
			logger.info("Shift initialized. previous=%r current=%r currentShiftRootPath=%s" %
			            (previousShiftIdValue, currentShiftIdValue, currentShiftRootPath))
			return

	except Exception as error:
		logger.error("handleShiftIdValueChanged failed: %s\n%s" % (str(error), traceback.format_exc()))