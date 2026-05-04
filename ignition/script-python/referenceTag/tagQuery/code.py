# tag/tagQuery.py

def state():
	return """
		SELECT
			s.state_id as stateId ,
			s.state_group_id as stateGroupId,
			s.reason_code as reasonCode,
			s.state_description as stateDescription,
			s.state_category as stateCategory,
			JSON_VALUE(s.metadata, '$.color') AS color,
			JSON_VALUE(s.metadata, '$.icon')  AS icon
		FROM core.state s
		WHERE s.is_deleted = 0
		  AND s.is_enabled = 1
	"""


def assetLineCell():
	return """
		SELECT
			a.asset_id   AS assetId,
			a.asset_name AS assetName,
			a.asset_path AS assetPath,
			a.parent_id  AS parentId,
			a.type_id AS typeId,
			m.state_group_id AS stateGroupId
		FROM core.asset a
		LEFT JOIN core.asset_state_group_mapping m
		  ON m.asset_id = a.asset_id
		 AND m.is_deleted = 0
		 AND m.is_enabled = 1
		WHERE a.is_deleted = 0
		  AND a.is_enabled = 1
		  AND a.type_id IN (4, 5)
	"""


def fetchAll():
	"""
	Fetch all reference datasets in a single transaction
	using the DEFAULT database connection.
	"""
	tx = system.db.beginTransaction(timeout=60000)
	try:
		out = {
			"State": system.db.runPrepQuery(state(), [], tx=tx),
			"AssetLineCell": system.db.runPrepQuery(assetLineCell(), [], tx=tx),
		}
		system.db.commitTransaction(tx)
		return out
	except:
		system.db.rollbackTransaction(tx)
		raise
	finally:
		system.db.closeTransaction(tx)