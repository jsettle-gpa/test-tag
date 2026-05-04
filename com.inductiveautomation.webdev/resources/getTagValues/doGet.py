def doGet(request, session):


	import system

	params = request.get('params', {})

	# Get tag path(s) - can be single path or comma-separated
	pathParam = params.get('path') or params.get('paths')

	if not pathParam:
		return {
			"json": {
				"error": "Missing required parameter 'path'. Example: ?path=[default]MyTag or ?path=[default]Tag1,[default]Tag2"
			}
		}

	# Split by comma if multiple paths
	paths = [p.strip() for p in pathParam.split(',') if p.strip()]

	# Read tag values
	results = []
	qualifiedValues = system.tag.readBlocking(paths)

	for i, qv in enumerate(qualifiedValues):
		val = qv.value

		# handle DataSet values
		if hasattr(val, 'getRowCount') and hasattr(val, 'getColumnCount'):
			cols = list(val.getColumnNames())
			rows = []
			for r in range(val.getRowCount()):
				row = {}
				for c in cols:
					cellVal = val.getValueAt(r, c)
					if cellVal is not None and hasattr(cellVal, 'getTime'):
						row[c] = str(cellVal)
					else:
						row[c] = cellVal
				rows.append(row)
			val = {"columns": cols, "rowCount": val.getRowCount(), "rows": rows}

		results.append({
			"path": paths[i],
			"value": val,
			"quality": str(qv.quality),
			"timestamp": str(qv.timestamp)
		})

	return {
		"json": {
			"count": len(results),
			"tags": results
		}
	}