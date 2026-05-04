def doGet(request, session):

	params = request.get('params', {})
	path = params.get('path', '')

	if not path:
		return {'json': {'error': 'path parameter required', 'example': '/getUdtTypes?path=[MES]_types_/MES/Config'}}

	try:
		# Get the UDT configuration
		config = system.tag.getConfiguration(path, True)

		if not config:
			return {'json': {'path': path, 'error': 'Not found or empty'}}

		# Convert to serializable dict
		result = {
			'path': path,
			'count': len(config),
			'types': []
		}

		for item in config:
			typeInfo = {
				'name': str(item.get('name', '')),
				'tagType': str(item.get('tagType', ''))
			}

			# Get parameters - handle as Ignition config object
			if 'parameters' in item:
				typeInfo['parameters'] = {}
				paramDict = item.get('parameters')
				if paramDict:
					for pName in paramDict:
						pConfig = paramDict[pName]
						typeInfo['parameters'][str(pName)] = {
							'dataType': str(pConfig.get('dataType', '')) if hasattr(pConfig, 'get') else str(pConfig),
							'value': pConfig.get('value') if hasattr(pConfig, 'get') else None
						}

			# Get member tags
			if 'tags' in item:
				typeInfo['tags'] = []
				for tag in item.get('tags', []):
					typeInfo['tags'].append({
						'name': str(tag.get('name', '')),
						'tagType': str(tag.get('tagType', '')),
						'value': tag.get('value') if 'value' in tag else None
					})

			result['types'].append(typeInfo)

		return {'json': result}

	except Exception as ex:
		import traceback
		return {'json': {'error': str(ex), 'traceback': traceback.format_exc(), 'path': path}} 