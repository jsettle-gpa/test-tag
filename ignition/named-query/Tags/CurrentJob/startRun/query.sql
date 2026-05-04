SELECT
	wor.run_id,
	wor.work_order_id,
	wor.planned_qty AS requiredQuantity,
	wor.asset_id,
	CAST(wor.planned_start_at AS datetime2) AS planned_start_at,
	CAST(wor.planned_end_at AS datetime2) AS planned_end_at,
	wo.item_id,
	i.item_name AS productName,
	wo.bom_id,
	ba.run_rate AS idealRunRate,
	ba.setup_time_seconds
FROM product.work_order_run wor
JOIN product.work_order wo
	ON wo.work_order_id = wor.work_order_id
LEFT JOIN product.item i
	ON i.item_id = wo.item_id
	AND i.is_deleted = 0
	AND i.is_enabled = 1
LEFT JOIN product.bom_asset ba
	ON ba.bom_id = wo.bom_id
	AND ba.asset_id = wor.asset_id
	AND ba.is_deleted = 0
	AND ba.is_enabled = 1
WHERE wor.run_id = :runId
	AND wor.is_deleted = 0
	AND wor.is_enabled = 1;