# tag/utils.py

from java.util.concurrent.locks import ReentrantLock

refreshLock = ReentrantLock()


def now():
	return system.date.now()


def tagPath(root, rel):
	return "%s/%s" % (root, rel)


def systemTagPaths(root):
	return {
		"RefreshTrigger": tagPath(root, "System/RefreshTrigger"),
		"LastRefreshUtc": tagPath(root, "System/LastRefreshUtc"),
		"RefreshStatus":  tagPath(root, "System/RefreshStatus"),
		"LastError":      tagPath(root, "System/LastError"),
	}


def setStatus(root, status, errorText=""):
	paths = systemTagPaths(root)
	system.tag.writeBlocking(
		[paths["RefreshStatus"], paths["LastError"]],
		[status, errorText or ""]
	)
	

def ensureReferenceStructure(referenceRoot):
	"""
	Create reference root, Core/System folders, and required tags if missing.
	Root folder creation is isolated to avoid race conditions.
	"""

	providerEnd = referenceRoot.find("]")
	provider = referenceRoot[:providerEnd + 1]          # "[default]"
	rootName = referenceRoot[providerEnd + 1:].lstrip("/")  # "reference"

	def exists(path):
		return system.tag.exists(path)

	# -------------------------
	# Root folder (ONLY)
	# -------------------------
	if not exists(referenceRoot):
		system.tag.configure(
			provider,
			[{
				"name": rootName,
				"tagType": "Folder"
			}],
			"m"
		)
		# IMPORTANT: stop here, let next execution create children
		return

	# -------------------------
	# Child folders
	# -------------------------
	for child in ("Core", "System"):
		path = referenceRoot + "/" + child
		if not exists(path):
			system.tag.configure(
				referenceRoot,
				[{
					"name": child,
					"tagType": "Folder"
				}],
				"m"
			)

	# -------------------------
	# System tags
	# -------------------------
	systemTags = [
		("RefreshTrigger", "Int4"),
		("LastRefreshUtc", "DateTime"),
		("RefreshStatus", "String"),
		("LastError", "String"),
	]

	systemDefs = []
	for name, dataType in systemTags:
		path = referenceRoot + "/System/" + name
		if not exists(path):
			systemDefs.append({
				"name": name,
				"tagType": "AtomicTag",
				"dataType": dataType,
				"valueSource": "memory",
				"value": "INIT" if name == "RefreshStatus" else None
			})

	if systemDefs:
		system.tag.configure(referenceRoot + "/System", systemDefs, "m")

	# -------------------------
	# Core dataset tags
	# -------------------------
	coreDefs = []
	for name in ("State", "AssetLineCell"):
		path = referenceRoot + "/Core/" + name
		if not exists(path):
			coreDefs.append({
				"name": name,
				"tagType": "AtomicTag",
				"dataType": "DataSet",
				"valueSource": "memory"
			})

	if coreDefs:
		system.tag.configure(referenceRoot + "/Core", coreDefs, "m")