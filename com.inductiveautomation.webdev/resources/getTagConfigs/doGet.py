def doGet(request, session):


	import system

	params = request.get('params', {})
	pathParam = params.get('path')

	if not pathParam:
		return {
			"json": {
				"error": "Missing required parameter 'path'. Example: ?path=[default]GPA/Site/Area/L6"
			}
		}

	recursive = str(params.get('recursive', 'false')).lower() == 'true'

	try:
		configs = system.tag.getConfiguration(pathParam, recursive)

		tags = []
		for i, config in enumerate(configs):
			tagInfo = {}

			for key in ['name', 'fullPath', 'tagType', 'dataType', 'valueSource',
			            'opcItemPath', 'opcServer', 'expression',
			            'historyEnabled', 'historyScanclass', 'historyProvider',
			            'historyMaxAge', 'historyMaxAgeUnits',
			            'engUnit', 'tooltip', 'enabled', 'readOnly']:
				try:
					val = config.get(key)
					if val is not None:
						if isinstance(val, (bool, int, float, str)):
							tagInfo[key] = val
						else:
							tagInfo[key] = str(val)
				except:
					pass

			# Construct fullPath from input if not returned by config
			fullPath = tagInfo.get('fullPath', '')
			if not fullPath:
				name = tagInfo.get('name', '')
				if name:
					fullPath = pathParam if i == 0 and name in pathParam else pathParam.rstrip('/') + '/' + name
				tagInfo['fullPath'] = fullPath

			tagType = tagInfo.get('tagType', '')

			# Read value and infer type for atomic tags
			if fullPath and tagType not in ('Folder', 'UdtType', 'UdtInstance', 'Provider', ''):
				try:
					qv = system.tag.readBlocking([fullPath])[0]
					tagInfo['value'] = qv.value
					tagInfo['quality'] = str(qv.quality)
					if qv.value is not None:
						tagInfo['inferredType'] = type(qv.value).__name__
				except:
					pass

			tags.append(tagInfo)

		return {
			"json": {
				"path": pathParam,
				"count": len(tags),
				"tags": tags
			}
		}

	except Exception as ex:
		import traceback
		return {
			"json": {
				"error": str(ex),
				"traceback": traceback.format_exc(),
				"path": pathParam
			}
		}