import system
import traceback

def readTag(path):
	return system.tag.readBlocking([path])[0].value

def writeTag(path, value):
	system.tag.writeBlocking([path], [value])

def writeTags(paths, values):
	system.tag.writeBlocking(paths, values)

def parentPath(tagPath, levels):
	p = str(tagPath)
	for i in range(levels):
		p = p.rsplit("/", 1)[0]
	return p


logger = system.util.getLogger("app.util.tag")

def getParentPath(tagPathString):
	"""
	Returns the parent folder path for a tag path string.
	Example:
	  [default]GPA/Site/Area/L6/CurrentShift/shiftId
	becomes:
	  [default]GPA/Site/Area/L6/CurrentShift
	"""
	if tagPathString is None:
		return None
	pathText = str(tagPathString)
	if "/" not in pathText:
		return pathText
	return pathText.rsplit("/", 1)[0]

def joinTagPath(basePath, childPath):
	"""
	Joins tag paths safely.
	If childPath is already a full provider path ([default]...), returns childPath.
	"""
	if childPath is None or childPath == "":
		return basePath
	if childPath.startswith("["):
		return childPath
	if basePath is None:
		return childPath
	if basePath.endswith("/"):
		return basePath + childPath
	return basePath + "/" + childPath

def tagExists(tagPath):
	try:
		return system.tag.exists(tagPath)
	except Exception as error:
		logger.error("tagExists failed tagPath=%r error=%s\n%s" % (tagPath, str(error), traceback.format_exc()))
		return False

def readBlocking(tagPaths):
	"""
	Wrapper for system.tag.readBlocking with consistent error logging.
	Returns list of QualifiedValue.
	"""
	try:
		return system.tag.readBlocking(tagPaths)
	except Exception as error:
		logger.error("readBlocking failed tagPaths=%r error=%s\n%s" % (tagPaths, str(error), traceback.format_exc()))
		raise

def writeBlocking(tagPaths, values):
	"""
	Wrapper for system.tag.writeBlocking with consistent error logging.
	Returns list of QualityCode.
	"""
	try:
		return system.tag.writeBlocking(tagPaths, values)
	except Exception as error:
		logger.error("writeBlocking failed tagPaths=%r error=%s\n%s" % (tagPaths, str(error), traceback.format_exc()))
		raise

def readTagValueOrDefault(tagPath, defaultValue):
	"""
	Reads a tag and returns defaultValue when quality is bad or value is None.
	"""
	qualityValue = readBlocking([tagPath])[0]
	if qualityValue.quality.isGood() and qualityValue.value is not None:
		return qualityValue.value
	return defaultValue

def readBoolean(tagPath, defaultValue):
	value = readTagValueOrDefault(tagPath, defaultValue)
	return bool(value)

def readLong(tagPath, defaultValue):
	value = readTagValueOrDefault(tagPath, defaultValue)
	try:
		return long(value)
	except:
		return long(defaultValue)

def writeValuesByPath(pathValuePairs):
	"""
	Writes a list of (path, value) pairs.
	"""
	paths = []
	values = []
	for pair in pathValuePairs:
		paths.append(pair[0])
		values.append(pair[1])
	writeBlocking(paths, values)

def getLineRootPathFromCurrentShiftTag(tagPathString):
	"""
	Given a tag path inside CurrentShift (commonly shiftId), returns the line root.
	Example:
	  .../L6/CurrentShift/shiftId -> .../L6
	"""
	currentShiftRootPath = getParentPath(tagPathString)   # .../CurrentShift
	if currentShiftRootPath is None:
		return None
	return getParentPath(currentShiftRootPath)

def getCurrentShiftRootPathFromShiftIdTag(tagPathString):
	"""
	Given a shiftId tag path, returns the CurrentShift root path.
	"""
	return getParentPath(tagPathString)

def getLineRootPathFromMachineInputCounterTag(tagPathString):
	"""
	Expects: .../<Line>/MachineInput/<counterName>
	Returns: .../<Line>
	"""
	machineInputRootPath = getParentPath(tagPathString)   # .../MachineInput
	if machineInputRootPath is None:
		return None
	return getParentPath(machineInputRootPath)