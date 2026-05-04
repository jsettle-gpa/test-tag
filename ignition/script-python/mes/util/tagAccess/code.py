# mes/util/tagAccess.py

"""
Centralized tag read/write helpers.

Goals:
- Keep all system.tag calls in one place.
- Provide consistent quality/default handling.
- Support bulk operations cleanly for performance (readBlocking/writeBlocking).
"""


logger = system.util.getLogger("mes.util.tagAccess")


def readBlocking(tagPaths):
	"""
	Thin wrapper around system.tag.readBlocking.
	Returns list of QualifiedValue.
	"""
	if not tagPaths:
		return []
	return system.tag.readBlocking(tagPaths)


def writeBlocking(tagPaths, values):
	"""
	Thin wrapper around system.tag.writeBlocking.
	Returns list of QualityCode.
	"""
	if not tagPaths:
		return []
	if values is None:
		values = []
	return system.tag.writeBlocking(tagPaths, values)


def tagExists(tagPath):
	"""
	Safe exists check.
	"""
	try:
		return system.tag.exists(tagPath)
	except Exception:
		return False


def readValue(tagPath, defaultValue=None):
	"""
	Read a single tag value with default fallback on bad quality.
	"""
	qualifiedValue = readBlocking([tagPath])[0]
	if not qualifiedValue.quality.isGood():
		return defaultValue
	return qualifiedValue.value


def readValues(tagPaths, defaultValue=None):
	"""
	Read multiple tag values. Returns list aligned to tagPaths.
	Any bad quality returns defaultValue (default None).
	"""
	if not tagPaths:
		return []

	qualifiedValues = readBlocking(tagPaths)

	values = []
	for qualifiedValue in qualifiedValues:
		if qualifiedValue.quality.isGood():
			values.append(qualifiedValue.value)
		else:
			values.append(defaultValue)

	return values


def readQualityValues(tagPaths):
	"""
	Read multiple tags and return list of (value, quality, timestamp).
	Useful for debugging/logging or advanced logic.
	"""
	if not tagPaths:
		return []

	qualifiedValues = readBlocking(tagPaths)

	results = []
	for qualifiedValue in qualifiedValues:
		results.append((qualifiedValue.value, qualifiedValue.quality, qualifiedValue.timestamp))

	return results


def writeValue(tagPath, value):
	"""
	Write a single value.
	"""
	return writeBlocking([tagPath], [value])


def writeValues(tagPaths, values):
	"""
	Write multiple values.
	"""
	return writeBlocking(tagPaths, values)


def writeValuesIfExists(tagPaths, values):
	"""
	Write only to tag paths that exist, preserving alignment.
	Returns (writtenPaths, qualityCodes)
	"""
	if not tagPaths:
		return ([], [])

	writablePaths = []
	writableValues = []

	for index in range(len(tagPaths)):
		tagPath = tagPaths[index]
		if tagExists(tagPath):
			writablePaths.append(tagPath)
			writableValues.append(values[index])

	if not writablePaths:
		return ([], [])

	qualityCodes = writeBlocking(writablePaths, writableValues)
	return (writablePaths, qualityCodes)