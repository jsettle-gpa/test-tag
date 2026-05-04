def doGet(request, session):
# listProjects WebDev Endpoint
#
# Setup in Ignition Designer:
# 1. Create WebDev resource with mount point "elev8"
# 2. Create endpoint named "listProjects"
# 3. Paste this into doGet.py
#
# URL: http://172.16.150.37:8088/system/webdev/elev8/listProjects

	import system
	from java.io import File

	logger = system.util.getLogger("webdev.listProjects")

	ctx = request['context']

	# Get data directory
	dataDir = str(ctx.systemManager.dataDir.absoluteFile).replace('\\', '/')
	projectsRoot = dataDir + '/projects'

	logger.info("Listing projects from: " + projectsRoot)

	projects = []

	try:
		rootDir = File(projectsRoot)
		items = rootDir.listFiles()
		logger.debug("Found %d items in projects folder" % (len(items) if items else 0))

		if items:
			for item in items:
				itemPath = str(item.getAbsolutePath()).replace('\\', '/')
				if item.isDirectory():
					projectName = item.getName()
					logger.debug("Processing project: " + projectName)

					# Check what resources exist
					hasViews = File(itemPath + '/com.inductiveautomation.perspective/views').exists()
					hasScripts = File(itemPath + '/ignition/script-python').exists()
					hasNamedQueries = File(itemPath + '/ignition/named-query').exists()

					# Check for project.json to get inheritance info
					projectJsonPath = itemPath + '/project.json'
					parent = None
					title = None
					projectJsonFile = File(projectJsonPath)
					if projectJsonFile.exists():
						try:
							content = system.file.readFileAsString(projectJsonPath)
							projectJson = system.util.jsonDecode(content)
							parent = projectJson.get('parent')
							title = projectJson.get('title')
							logger.debug("  - title: %s, parent: %s" % (title, parent))
						except Exception as ex:
							logger.warn("Failed to parse project.json for %s: %s" % (projectName, str(ex)))

					projects.append({
						"name": projectName,
						"title": title,
						"parent": parent,
						"hasViews": hasViews,
						"hasScripts": hasScripts,
						"hasNamedQueries": hasNamedQueries
					})

		logger.info("Found %d projects" % len(projects))

	except Exception as ex:
		import traceback
		logger.error("Error listing projects: " + str(ex))
		logger.error(traceback.format_exc())
		return {
			"json": {
				"error": str(ex),
				"traceback": traceback.format_exc(),
				"projectsRoot": projectsRoot
			}
		}

	return {
		"json": {
			"projectsRoot": projectsRoot,
			"count": len(projects),
			"projects": projects
		}
	}