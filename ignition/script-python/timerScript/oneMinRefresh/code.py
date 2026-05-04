import system
import traceback

logger = system.util.getLogger("app.mes.oee.shiftCounts")


def buildCanaryHistoryPath(lineRootPath, counterRelativePath, canaryProviderPrefix, canaryTagRootPrefix):
	"""
	Builds the Canary history tag path.

	Example inputs:
	  lineRootPath          = "[default]GPA/Site/Area/L1"
	  counterRelativePath   = "MachineInput/outfeed"
	  canaryProviderPrefix  = "[Canary/ignition-elev8-script-prod-gw:default]"
	  canaryTagRootPrefix   = "Canary8-LaTech/Mes"

	Output:
	  [Canary/...]Canary8-LaTech/Mes/GPA/Site/Area/L1/MachineInput/outfeed
	"""
	if lineRootPath is None or lineRootPath == "":
		raise Exception("lineRootPath is required")

	if counterRelativePath is None or counterRelativePath == "":
		raise Exception("counterRelativePath is required")

	linePathNoProvider = str(lineRootPath)
	if linePathNoProvider.startswith("["):
		rightBracketIndex = linePathNoProvider.find("]")
		if rightBracketIndex >= 0:
			linePathNoProvider = linePathNoProvider[rightBracketIndex + 1:]

	linePathNoProvider = linePathNoProvider.strip("/")
	counterRelativePath = str(counterRelativePath).strip("/")

	canaryProviderPrefix = str(canaryProviderPrefix).strip()
	canaryTagRootPrefix = str(canaryTagRootPrefix).strip("/")

	return "%s%s/%s/%s" % (canaryProviderPrefix, canaryTagRootPrefix, linePathNoProvider, counterRelativePath)


def readGoodValue(tagPath):
	qualifiedValue = system.tag.readBlocking([tagPath])[0]
	if not qualifiedValue.quality.isGood():
		return None
	return qualifiedValue.value


def getDatasetTimestampColumnName(historyDataset):
	columnNames = list(historyDataset.getColumnNames())
	if "t_stamp" in columnNames:
		return "t_stamp"
	return columnNames[0]


def getDatasetValueColumnName(historyDataset, fullHistoryPath):
	columnNames = list(historyDataset.getColumnNames())
	if fullHistoryPath in columnNames:
		return fullHistoryPath
	if len(columnNames) >= 2:
		return columnNames[1]
	return None


def calculateTotalIncrementFromHistory(historyDataset, valueColumnName):
	"""
	Sums counter increases across the dataset.

	Reset/rollover handling:
	- If current < previous, treat as reset and add current (best-effort without knowing max rollover)
	"""
	if historyDataset is None:
		return 0

	rowCount = historyDataset.getRowCount()
	if rowCount <= 0:
		return 0

	if valueColumnName is None:
		return 0

	totalIncrement = 0.0
	previousValue = None

	for rowIndex in range(rowCount):
		currentValue = historyDataset.getValueAt(rowIndex, valueColumnName)

		if currentValue is None:
			continue

		try:
			currentValue = float(currentValue)
		except:
			continue

		if previousValue is None:
			previousValue = currentValue
			continue

		if currentValue >= previousValue:
			totalIncrement += (currentValue - previousValue)
		else:
			# Counter reset/rollover (unknown max): treat as reset and add the new value.
			totalIncrement += currentValue

		previousValue = currentValue

	if totalIncrement < 0:
		totalIncrement = 0

	return totalIncrement


def updateShiftGoodCountForLine(lineRootPath,
                               shiftStartTimeTagPath,
                               shiftIdTagPath,
                               goodCountTagPath,
                               counterRelativePath="MachineInput/outfeed",
                               canaryProviderPrefix="[Canary/ignition-elev8-script-prod-gw:default]",
                               canaryTagRootPrefix="Canary8-LaTech/Mes"):
	"""
	Computes shift good count from Canary history and writes it to the GoodCount memory tag.

	lineRootPath should be the line folder, e.g.
	  [default]GPA/Site/Area/L1
	"""
	try:
		shiftIdValue = readGoodValue(shiftIdTagPath)
		if shiftIdValue is None:
			# No active shift, do not overwrite (you can choose to zero it instead)
			return

		shiftStartTime = readGoodValue(shiftStartTimeTagPath)
		if shiftStartTime is None:
			return

		endTime = system.date.now()

		historyPath = buildCanaryHistoryPath(
			lineRootPath=lineRootPath,
			counterRelativePath=counterRelativePath,
			canaryProviderPrefix=canaryProviderPrefix,
			canaryTagRootPrefix=canaryTagRootPrefix
		)

		historyDataset = system.tag.queryTagHistory(
			paths=[historyPath],
			startDate=shiftStartTime,
			endDate=endTime,
			returnFormat="Wide",
			returnSize=-1,                 # as-changed
			includeBoundingValues=True,
			noInterpolation=True,
			ignoreBadQuality=False
		)

		valueColumnName = getDatasetValueColumnName(historyDataset, historyPath)
		totalGood = calculateTotalIncrementFromHistory(historyDataset, valueColumnName)

		# If you want whole parts only:
		totalGoodInt = int(round(totalGood, 0))

		system.tag.writeBlocking([goodCountTagPath], [totalGoodInt])

	except Exception as error:
		logger.error("updateShiftGoodCountForLine failed for %s: %s\n%s" %
		             (str(lineRootPath), str(error), traceback.format_exc()))