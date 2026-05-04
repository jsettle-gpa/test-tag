def doGet(request, session):

	import system

	# --- 1) Get request params ---
	ctx    = request['context']
	params = request.get('params', {})

	# project param is optional, default to 'elev8' for your dev project
	projectName = params.get('project') or 'elev8'
	viewPath    = params.get('viewPath')

	if not viewPath:
		# Missing viewPath => return simple JSON error
		return {
			"json": {
				"error": "Missing required query parameter 'viewPath'. Example: ?viewPath=Main/Overview"
			}
		}

	# --- 2) Build the on-disk path to the view JSON ---

	# Base Ignition data directory, e.g.
	#   C:/Program Files/Inductive Automation/Ignition/data
	dataDir = str(ctx.systemManager.dataDir.absoluteFile).replace('\\', '/')

	# Your actual layout: data/projects/<projectName>/com.inductiveautomation.perspective/views/<viewPath>/
	projectsRoot = dataDir + '/projects'

	# Normalise the view path (e.g. "Main/Overview")
	normViewPath = viewPath.strip('/').replace('\\', '/')

	# Folder that should contain the view resource
	viewFolder = (
		projectsRoot + '/' + projectName +
		'/com.inductiveautomation.perspective/views/' +
		normViewPath
	)

	# Try common filenames in order
	viewJsonPath = None
	for name in ['view.json', 'config.json']:
		candidatePath = viewFolder + '/' + name
		if system.file.fileExists(candidatePath):
			viewJsonPath = candidatePath
			break

	# If we didn't find any JSON file at all
	if not viewJsonPath:
		return {
			"json": {
				"error": "View not found (no view.json or config.json)",
				"project": projectName,
				"viewPath": viewPath,
				"expectedFolder": viewFolder
			}
		}

	# --- 3) Read and parse the JSON file ---

	try:
		viewJsonStr = system.file.readFileAsString(viewJsonPath)
		viewJsonObj = system.util.jsonDecode(viewJsonStr)
	except Exception, ex:
		return {
			"json": {
				"error": "Failed to read or parse view JSON",
				"message": str(ex),
				"viewJsonPath": viewJsonPath
			}
		}

	# --- 4) Extract custom props and params ---

	# This corresponds to view.custom in Perspective
	viewCustom = viewJsonObj.get('custom', {})

	# Top-level view params (view.params in Perspective)
	viewParams = viewJsonObj.get('params', {})

	# --- 5) Collect button event scripts ---

	buttonScripts = []

	def walkComponent(node, pathParts):
		"""
		Recursively walk the component tree, collecting scripts
		from button components.
		"""
		if not isinstance(node, dict):
			return

		meta = node.get('meta') or {}
		name = meta.get('name') or ''

		if name:
			pathParts = pathParts + [name]

		compType = node.get('type', '') or ''
		lowerType = compType.lower()

		events = node.get('events') or {}

		# Heuristic: treat anything with 'button' in the type as a button
		if 'button' in lowerType:
			for category, catEvents in events.items():
				if not isinstance(catEvents, dict):
					continue
				for eventName, evt in catEvents.items():
					cfg    = (evt.get('config') or {}) if isinstance(evt, dict) else {}
					script = cfg.get('script')
					scope  = evt.get('scope') if isinstance(evt, dict) else None

					if script:
						buttonScripts.append({
							"componentPath": "/".join(pathParts),
							"componentType": compType,
							"category": category,       # e.g. "component"
							"eventName": eventName,     # e.g. "onActionPerformed"
							"scope": scope,             # e.g. "G"
							"script": script
						})

		# Recurse into children
		children = node.get('children') or []
		for child in children:
			walkComponent(child, pathParts)

	rootNode = viewJsonObj.get('root', {}) or {}
	walkComponent(rootNode, [])

	# --- 6) Return result as JSON ---

	return {
		"json": {
			"project": projectName,
			"viewPath": viewPath,
			"viewJsonPath": viewJsonPath,
			"viewCustom": viewCustom,
			"viewParams": viewParams,
			"buttonScripts": buttonScripts
		}
	}