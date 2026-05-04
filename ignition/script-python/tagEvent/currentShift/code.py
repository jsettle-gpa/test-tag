import system
import traceback


log = system.util.getLogger("tagEvent.currentShift")

referenceAssetTagPath = "[default]reference/Core/AssetLineCell"
lineTypeId = 4
currentShiftUdtTypeId = "MES/CurrentShift"

def normalizeAssetPath(assetPath):
	p = (assetPath or "").strip().strip("/")
	if p == "" or ".." in p or "\\" in p:
		raise Exception("Invalid assetPath: %r" % assetPath)
	return p


def ensureFolder(folderPath):
	parts = folderPath.split("/")
	if len(parts) < 2:
		return

	current = parts[0] 
	for name in parts[1:]:
		nextPath = current + "/" + name
		if not system.tag.exists(nextPath):
			log.info("Creating folder: %s" % nextPath)
			system.tag.configure(current, [{"name": name, "tagType": "Folder"}], "a")
		current = nextPath

def ensureCurrentShiftUdt(assetPath):
	ap = normalizeAssetPath(assetPath)

	assetRoot = "[default]/" + ap

	ensureFolder(assetRoot)

	udtRoot = assetRoot + "/CurrentShift"
	if not system.tag.exists(udtRoot):
		log.info("Creating UDT instance: %s (typeId=%s)" % (udtRoot, currentShiftUdtTypeId))
		system.tag.configure(
			assetRoot,
			[{"name": "CurrentShift", "tagType": "UdtInstance", "typeId": currentShiftUdtTypeId}],
			"a"
		)

	return udtRoot

def readAssetLineCell():
	log.info("Reading AssetLineCell: %s" % referenceAssetTagPath)
	qv = system.tag.readBlocking([referenceAssetTagPath])[0]
	log.info("AssetLineCell quality=%s type=%s" % (qv.quality, type(qv.value)))

	if not qv.quality.isGood():
		raise Exception("Bad quality reading %s: %s" % (referenceAssetTagPath, qv.quality))

	val = qv.value
	if val is None:
		raise Exception("AssetLineCell is None")
		
	if isinstance(val, (str, unicode)):
		obj = system.util.jsonDecode(val)
		colNames = [c["name"] for c in obj["columns"]]
		return system.dataset.toDataSet(colNames, obj["rows"])

	return val

def iterLineAssets(ds):
	for r in system.dataset.toPyDataSet(ds):
		if r["typeId"] == lineTypeId:
			yield int(r["assetId"]), str(r["assetPath"])

def writeNoShift(udtRoot):
	system.tag.writeBlocking(
		[udtRoot + "/shiftId", udtRoot + "/shiftStartTime", udtRoot + "/shiftEndTime", udtRoot + "/plannedProductionTime"],
		["NO_SHIFT", None, None, 0]
	)

def writeShift(udtRoot, shift):
	startJava = isoToJavaDate(shift.get("startDatetime"))
	endJava   = isoToJavaDate(shift.get("endDatetime"))

	paths = [
		udtRoot + "/shiftId",
		udtRoot + "/shiftStartTime",
		udtRoot + "/shiftEndTime",
		udtRoot + "/plannedProductionTime"
	]
	vals = [
		str(shift.get("shiftTemplateId", "")),
		startJava,
		endJava,
		int(shift.get("durationMinutesRemaining", 0))
	]

	qcs = system.tag.writeBlocking(paths, vals)
	log.info("writeShift %s qc=%s start=%s end=%s" %
	         (udtRoot, [str(q) for q in qcs], str(startJava), str(endJava)))
	        
def refresh():
	log.info("CurrentShift refresh starting")
	try:
		ds = readAssetLineCell()

		count = 0
		for assetId, assetPath in iterLineAssets(ds):
			count += 1
			log.info("Refreshing assetId=%s assetPath=%s" % (assetId, assetPath))

			udtRoot = ensureCurrentShiftUdt(assetPath)

			res = mes.shift.whatShift.getShiftForAsset(assetId)
			if not res or not res.get("success"):
				writeNoShift(udtRoot)
				continue

			shift = res.get("shift")
			if not shift:
				writeNoShift(udtRoot)
			else:
				writeShift(udtRoot, shift)

		log.info("CurrentShift refresh done. Lines processed=%d" % count)

	except Exception as e:
		log.error("CurrentShift refresh failed: %s\n%s" % (str(e), traceback.format_exc()))

def handleManualRefresh():
	print "tagEvent.currentShift manual refresh invoked"
	log.info("manual refresh invoked")
	refresh()