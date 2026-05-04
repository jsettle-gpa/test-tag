# tag/referenceData.py
import system
import json
from referenceTag import utils
from referenceTag import tagQuery


def datasetTagPaths(root):
	return {
		"State":         utils.tagPath(root, "Core/State"),
		"AssetLineCell": utils.tagPath(root, "Core/AssetLineCell"),
		"StatesByGroup": utils.tagPath(root, "Core/StatesByGroup"),
	}


def readSystemState(root):
	paths = utils.systemTagPaths(root)
	values = system.tag.readBlocking([
		paths["RefreshTrigger"],
		paths["LastRefreshUtc"],
		paths["RefreshStatus"],
	])
	return values[0].value, values[1].value, values[2].value




def getStatesForGroup(stateGroupId, statesDs=None):
	"""
	Return a dataset of states for a given stateGroupId.

	stateGroupId: int (or str that can be cast)
	statesDs: optional dataset (pass in if you already have it to avoid a tag read)
	"""
	try:
		gid = int(stateGroupId)
	except:
		gid = -1

	# If caller didn't pass the master dataset, read it from the reference tag.
	if statesDs is None:
		statesDs = system.tag.readBlocking(["[default]reference/Core/State"])[0].value

	if statesDs is None or statesDs.getRowCount() == 0:
		# Return an empty dataset with the expected columns
		headers = ["stateId","stateGroupId","reasonCode","stateDescription","stateCategory","color","icon"]
		return system.dataset.toDataSet(headers, [])

	headers = list(statesDs.getColumnNames())
	out = []

	for row in system.dataset.toPyDataSet(statesDs):
		try:
			if int(row["stateGroupId"]) == gid:
				out.append([row[h] for h in headers])
		except:
			continue

	return system.dataset.toDataSet(headers, out)

def buildStatesByGroup(stateDs):
	"""
	Build a dataset with:
	  stateGroupId (Integer), statesJson (String)
	One row per state_group_id, with statesJson being a JSON array of states.
	"""
	headers = ["stateGroupId", "statesJson"]
	if stateDs is None:
		return system.dataset.toDataSet(headers, [])

	groups = {}
	for s in system.dataset.toPyDataSet(stateDs):
		gid = s["stateGroupId"]
		if gid is None:
			continue
		gid = int(gid)

		groups.setdefault(gid, []).append({
			"stateId": s["stateId"],
			"stateGroupId": s["stateGroupId"],
			"reasonCode": s["reasonCode"],
			"stateDescription": s["stateDescription"],
			"stateCategory": s["stateCategory"],
			"color": s["color"],
			"icon": s["icon"],
		})

	rows = []
	for gid in sorted(groups.keys()):
		rows.append([gid, json.dumps(groups[gid])])

	return system.dataset.toDataSet(headers, rows)


def publish(root, datasets):
	dpaths = datasetTagPaths(root)
	spaths = utils.systemTagPaths(root)

	system.tag.writeBlocking(
		[
			dpaths["State"],
			dpaths["AssetLineCell"],
			dpaths["StatesByGroup"],  
			spaths["LastRefreshUtc"],
			spaths["RefreshStatus"],
			spaths["LastError"],
		],
		[
			datasets["State"],
			datasets["AssetLineCell"],
			datasets["StatesByGroup"], 
			utils.now(),
			"OK",
			"",
		]
	)


def refresh(referenceRoot="[default]reference", force=False):
	if not utils.refreshLock.tryLock():
		return
	try:
		utils.ensureReferenceStructure(referenceRoot)

		trigger, lastRefreshUtc, status = readSystemState(referenceRoot)

		if not force and status not in (None, "", "INIT", "ERROR"):
			return

		utils.setStatus(referenceRoot, "REFRESHING")

		datasets = tagQuery.fetchAll()

		datasets["StatesByGroup"] = buildStatesByGroup(datasets.get("State"))

		publish(referenceRoot, datasets)

	except Exception as e:
		utils.setStatus(referenceRoot, "ERROR", str(e))
	finally:
		utils.refreshLock.unlock()

def refreshStatesOnly():
	"""refreshes state and statesByGroup reference datasets"""
	root = "[default]reference"
	stateDs = system.db.runPrepQuery(tagQuery.state(), [])
	statesByGroupDs = buildStatesByGroup(stateDs)
	paths = datasetTagPaths(root)
	system.tag.writeBlocking(
		[paths["State"], paths["StatesByGroup"]],
		[stateDs, statesByGroupDs]
	)
		
# ---- entry points ----

def handleTimerEvent():
	# Gateway timer script (every 30 minutes)
	refresh(referenceRoot="[default]reference", force=False)


def handleStartup():
	# Gateway startup
	refresh(referenceRoot="[default]reference", force=True)


def handleManualRefresh():
	# Manual UI action
	refresh(referenceRoot="[default]reference", force=True)