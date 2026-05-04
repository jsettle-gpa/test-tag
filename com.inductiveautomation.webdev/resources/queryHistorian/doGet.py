def doGet(request, session):
# queryHistorian WebDev endpoint
# deploy on Tag Gateway (172.16.150.37)
#
# usage examples:
#   ?path=[default]GPA/Site/Area/L1/MachineInput/state&minutes=100
#   ?path=[default]GPA/Site/Area/L1/MachineInput/state&minutes=100&aggregationMode=DurationOn&aggregationValue=1&returnSize=1


	params = request.get("params", {})
	path = params.get("path", "")
	minutes = int(params.get("minutes", "60"))
	aggregationMode = params.get("aggregationMode", None)
	aggregationValue = params.get("aggregationValue", None)
	returnSize = int(params.get("returnSize", "0"))

	if not path:
		return {"json": {"error": "path parameter required"}}

	end = system.date.now()
	start = system.date.addMinutes(end, -minutes)

	# build query args
	queryArgs = {
		"paths": [path],
		"startDate": start,
		"endDate": end,
		"returnSize": returnSize,
		"returnFormat": "Wide"
	}

	# add aggregation if specified
	if aggregationMode:
		queryArgs["aggregationMode"] = aggregationMode
	if aggregationValue is not None:
		queryArgs["aggregationValue"] = int(aggregationValue)

	data = system.tag.queryTagHistory(**queryArgs)

	result = []
	for row in range(data.rowCount):
		result.append({
			"timestamp": str(data.getValueAt(row, 0)),
			"value": data.getValueAt(row, 1)
		})

	return {"json": {"count": len(result), "data": result}}