def doGet(request, session):
	# browseProjects WebDev Endpoint
	#
	# Setup in Ignition Designer:
	# 1. Create WebDev resource with mount point "elev8"
	# 2. Create endpoint named "browseProjects"
	# 3. Paste this into doGet.py
	#
	# URL: http://172.16.150.37:8088/system/webdev/elev8/browseProjects
	# Params: ?project=<name>&path=<subpath>
	
	import system
	from java.io import File

	ctx = request['context']
	params = request.get('params', {})

	projectName = params.get('project') or 'elev8_MES'
	subPath = params.get('path') or ''

	# Build the full path
	dataDir = str(ctx.systemManager.dataDir.absoluteFile).replace('\\', '/')
	projectRoot = dataDir + '/projects/' + projectName

	if subPath:
		fullPath = projectRoot + '/' + subPath.strip('/')
	else:
		fullPath = projectRoot

	targetFile = File(fullPath)

	# Check if path exists
	if not targetFile.exists():
		return {
			"json": {
				"error": "Path not found",
				"path": fullPath
			}
		}

	# If it's a file, return its contents
	if targetFile.isFile():
		try:
			content = system.file.readFileAsString(fullPath)

			# Try to parse as JSON
			try:
				jsonContent = system.util.jsonDecode(content)
				return {
					"json": {
						"type": "file",
						"path": fullPath,
						"isJson": True,
						"content": jsonContent
					}
				}
			except:
				return {
					"json": {
						"type": "file",
						"path": fullPath,
						"isJson": False,
						"content": content
					}
				}
		except Exception as ex:
			return {
				"json": {
					"error": "Failed to read file: " + str(ex),
					"path": fullPath
				}
			}

	# It's a directory - list contents
	try:
		items = targetFile.listFiles()
		contents = []

		if items:
			for item in items:
				itemName = item.getName()
				isDir = item.isDirectory()

				info = {
					"name": itemName,
					"isDirectory": isDir
				}

				if not isDir:
					info["size"] = item.length()

				contents.append(info)

		# Sort: directories first, then files
		contents.sort(key=lambda x: (not x['isDirectory'], x['name'].lower()))

		return {
			"json": {
				"type": "directory",
				"project": projectName,
				"path": subPath or "/",
				"fullPath": fullPath,
				"count": len(contents),
				"contents": contents
			}
		}

	except Exception as ex:
		return {
			"json": {
				"error": str(ex),
				"path": fullPath
			}
		}