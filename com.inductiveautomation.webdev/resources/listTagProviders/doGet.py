def doGet(request, session):

	import system

	# Browse the root to get all tag providers
	try:
		browseResults = system.tag.browse("", {})

		providers = []
		for result in browseResults.getResults():
			name = str(result['name'])
			fullPath = str(result['fullPath'])
			tagType = str(result['tagType'])

			providers.append({
				"name": name,
				"path": fullPath,
				"tagType": tagType
			})

		return {
			"json": {
				"count": len(providers),
				"providers": providers
			}
		}

	except Exception as ex:
		return {
			"json": {
				"error": str(ex)
			}
		}