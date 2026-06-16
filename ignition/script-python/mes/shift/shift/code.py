from dateutil.rrule import rrulestr
from datetime import timedelta
from mes.domain.timeutil import DateTimeConverter


class AssetActiveShiftTemplateRow:
	def __init__(self, row):
		self.assetShiftAssignmentId = row['asset_shift_assignment_id']
		self.assetId = row['asset_id']
		self.shiftTemplateId = row['shift_template_id']
		self.assetPath = row['asset_path']
		self.title = row['title']
		self.startDatetimeUtc = row['start_datetime_utc']
		self.endDatetimeUtc = row['end_datetime_utc']
		self.durationMinutes = row['duration_minutes']
		self.rrule = row['rrule']
		self.recurrenceEndDate = row['recurrence_end_date']
		self.templateMetadata = row['template_metadata']
		self.assignmentMetadata = row['assignment_metadata']


class CurrentShift(object):
	COLUMNS = [
		"assetId",
		"assetPath",
		"shiftTemplateId",
		"title",
		"shiftStartTime",
		"shiftEndTime",
		"plannedProductionTime",
		"shiftInstanceId"
	]
	def __init__(self, assetId, assetPath, shiftTemplateId, title,
				 shiftStartTime, shiftEndTime, plannedProductionTime,
				 shiftInstanceId):
		self.assetId = assetId
		self.assetPath = assetPath
		self.shiftTemplateId = shiftTemplateId
		self.title = title
		self.shiftStartTime = shiftStartTime
		self.shiftEndTime = shiftEndTime
		self.plannedProductionTime = plannedProductionTime
		self.shiftInstanceId = shiftInstanceId

	def toRow(self):
		return [
			self.assetId,
			self.assetPath,
			self.shiftTemplateId,
			self.title,
			self.shiftStartTime,
			self.shiftEndTime,
			self.plannedProductionTime,
			self.shiftInstanceId
		]

	def __repr__(self):
		return "CurrentShift(asset={}, title='{}', start={}, end={})".format(
			self.assetId, self.title, self.shiftStartTime, self.shiftEndTime
		)


def _fetchPlannedDowntime(assignmentIds, shiftDate):
	"""
	Bulk fetch planned downtime events for a set of assignment IDs on a given date.
	Returns a dict of {asset_shift_assignment_id: total_downtime_minutes}.
	"""
	if not assignmentIds:
		return {}

	placeholders = ", ".join(["?" for _ in assignmentIds])
	query = """
		SELECT asset_shift_assignment_id, SUM(duration_minutes) AS total_downtime
		FROM operation.planned_downtime_event
		WHERE asset_shift_assignment_id IN ({})
		AND event_date = ?
		GROUP BY asset_shift_assignment_id
	""".format(placeholders)

	params = list(assignmentIds) + [shiftDate]
	data = system.db.runPrepQuery(query, params)
	rows = system.dataset.toPyDataSet(data)

	return {row['asset_shift_assignment_id']: row['total_downtime'] for row in rows}

def _upsertShiftInstances(resolvedShifts):
	"""
	Bulk upsert shift instances for all resolved shifts.
	Returns a dict of {(asset_shift_assignment_id, shiftStartIso): shift_instance_id}
	"""
	if not resolvedShifts:
		return {}
	candidates = []
	for template, shiftStart, shiftEnd, assets in resolvedShifts:
		shiftStartIso = DateTimeConverter.toIsoString(shiftStart)
		shiftEndIso = DateTimeConverter.toIsoString(shiftEnd)
		for assetRow in assets:
			candidates.append((assetRow.assetShiftAssignmentId, shiftStartIso, shiftEndIso))
	if not candidates:
		return {}
	insertQuery = """
		INSERT INTO operation.shift_instance (asset_shift_assignment_id, actual_start_time, actual_end_time)
		SELECT vals.assignment_id, vals.start_time, vals.end_time
		FROM (VALUES {}) AS vals(assignment_id, start_time, end_time)
		WHERE NOT EXISTS (
			SELECT 1 FROM operation.shift_instance si
			WHERE si.asset_shift_assignment_id = vals.assignment_id
			AND si.actual_start_time = vals.start_time
			AND si.is_deleted = 0
		)
	""".format(", ".join(["(?, ?, ?)" for _ in candidates]))

	insertParams = [val for row in candidates for val in row]
	system.db.runPrepUpdate(insertQuery, insertParams, "db")

	placeholders = ", ".join(["?" for _ in candidates])
	assignmentIds = [row[0] for row in candidates]
	startTimes = [row[1] for row in candidates]

	selectQuery = """
		SELECT asset_shift_assignment_id,
		       CONVERT(VARCHAR(25), actual_start_time, 127) AS actual_start_time_iso,
		       shift_instance_id
		FROM operation.shift_instance
		WHERE asset_shift_assignment_id IN ({})
		AND CAST(actual_start_time AS DATE) >= CAST(DATEADD(day, -1, SYSUTCDATETIME()) AS DATE)
		AND is_deleted = 0
	""".format(placeholders)

	data = system.db.runPrepQuery(selectQuery, assignmentIds, "db")
	rows = system.dataset.toPyDataSet(data)

	startTimeSet = set(startTimes)
	return {
		(row['asset_shift_assignment_id'], row['actual_start_time_iso'].replace('Z', '+00:00')): row['shift_instance_id']
		for row in rows
		if row['actual_start_time_iso'].replace('Z', '+00:00') in startTimeSet
	}

def getAllActiveShifts():
	"""
	Queries all active shift template assignments, expands rrule
	recurrences, and returns a list of CurrentShift objects for
	any asset currently in a shift window.
	"""
	now = system.date.now()
	try:
		data = system.db.execQuery("App/Schedule/vAssetActiveShiftTemplates", {})
		rows = [AssetActiveShiftTemplateRow(row) for row in system.dataset.toPyDataSet(data)]
		if not rows:
			return []

		templateGroups = {}
		for row in rows:
			tid = row.shiftTemplateId
			if tid not in templateGroups:
				templateGroups[tid] = {
					'template': row,
					'assets': []
				}
			templateGroups[tid]['assets'].append(row)

		nowUtc = DateTimeConverter.toDatetime(now.getTime())

		# resolve shift windows and collect what we need for the bulk query
		resolvedShifts = []  # list of (template, shiftStart, shiftEnd, assets)

		for tid, group in templateGroups.items():
			template = group['template']
			templateStart = DateTimeConverter.toDatetime(long(template.startDatetimeUtc))
			if not templateStart:
				continue

			shiftStart = None
			shiftEnd = None

			if not template.rrule:
				templateEnd = DateTimeConverter.toDatetime(long(template.endDatetimeUtc))
				if templateStart and templateEnd and templateStart <= nowUtc < templateEnd:
					shiftStart = templateStart
					shiftEnd = templateEnd
			else:
				rule = rrulestr(template.rrule, dtstart=templateStart)
				lookback = nowUtc - timedelta(hours=48)
				lookahead = nowUtc + timedelta(hours=48)
				occurrences = list(rule.between(lookback, lookahead, inc=True))
				for occ in occurrences:
					occEnd = occ + timedelta(minutes=template.durationMinutes)
					if occ <= nowUtc < occEnd:
						shiftStart = occ
						shiftEnd = occEnd
						break

			if shiftStart is None:
				continue

			resolvedShifts.append((template, shiftStart, shiftEnd, group['assets']))

		if not resolvedShifts:
			return []

		dateToAssignmentIds = {}
		for template, shiftStart, shiftEnd, assets in resolvedShifts:
			shiftDate = shiftStart.date()
			for assetRow in assets:
				dateToAssignmentIds.setdefault(shiftDate, set()).add(assetRow.assetShiftAssignmentId)

		# downtimeLookup: {(asset_shift_assignment_id, date): total_downtime_minutes}
		downtimeLookup = {}
		for shiftDate, assignmentIds in dateToAssignmentIds.items():
			dailyDowntime = _fetchPlannedDowntime(assignmentIds, shiftDate)
			for assignmentId, totalMinutes in dailyDowntime.items():
				downtimeLookup[(assignmentId, shiftDate)] = totalMinutes
				
		
		instanceLookup = _upsertShiftInstances(resolvedShifts)

		# build CurrentShift objects with adjusted plannedProductionTime
		activeShifts = []
		for template, shiftStart, shiftEnd, assets in resolvedShifts:
			shiftStartJava = DateTimeConverter.toJavaDate(shiftStart)
			shiftEndJava = DateTimeConverter.toJavaDate(shiftEnd)
			shiftDate = shiftStart.date()
			shiftStartIso = DateTimeConverter.toIsoString(shiftStart)

			for assetRow in assets:
				plannedDowntime = downtimeLookup.get((assetRow.assetShiftAssignmentId, shiftDate), 0)
				plannedProductionTime = max(0, template.durationMinutes - plannedDowntime)
				shiftInstanceId = instanceLookup.get((assetRow.assetShiftAssignmentId, shiftStartIso))

				activeShifts.append(CurrentShift(
					assetId=assetRow.assetId,
					assetPath=assetRow.assetPath,
					shiftTemplateId=template.shiftTemplateId,
					title=template.title,
					shiftStartTime=shiftStartJava,
					shiftEndTime=shiftEndJava,
					plannedProductionTime=plannedProductionTime,
					shiftInstanceId=shiftInstanceId
				))

		return activeShifts

	except Exception as e:
		logger = system.util.getLogger("mes.shift.activeShifts")
		logger.error("Error retrieving active shifts: " + str(e))
		import traceback
		logger.error(traceback.format_exc())
		return []


def getAllActiveShiftDS():
	activeShifts = getAllActiveShifts()
	headers = CurrentShift.COLUMNS
	rows = [s.toRow() for s in activeShifts]
	dataset = system.dataset.toDataSet(headers, rows)
	system.tag.writeBlocking(['[default]reference/Operation/CurrentShift'], [dataset])
	return dataset