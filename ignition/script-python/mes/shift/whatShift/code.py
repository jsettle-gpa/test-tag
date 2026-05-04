import json
from mes.domain.timeutil import DateTimeConverter
from dateutil.rrule import rrulestr
from datetime import timedelta

class ShiftTemplate:
	def __init__(self, row):
		"""
		Initialize ShiftTemplate from a dataset row
		
		Args:
			row: A row from the query result dataset
		"""
		self.shiftTemplateId = row['shiftTemplateId']
		self.title = row['title']
		self.startDatetimeUtc = row['startDatetimeUtc']
		self.endDatetimeUtc = row['endDatetimeUtc']
		self.durationMinutes = row['durationMinutes']
		self.rrule = row['rrule']
		self.recurrenceEndDate = row['recurrenceEndDate']
		self.metadata = row['metadata']
		self.assetId = row['assetId']
		self.assetShiftAssignmentId = row['assetShiftAssignmentId']
	
	def getShiftAt(self, queryDatetime, referenceNow=None):
		"""
		Calculate which shift was/is active at a given time
		
		Args:
			queryDatetime: The time to check what shift was active (Java Date)
			referenceNow: Optional "now" reference for calculating remaining time (Java Date).
						 If None, uses queryDatetime as reference.
			
		Returns:
			dict: Shift details or None if no shift was active
		"""
		try:
			# Convert string timestamps to Python datetime (UTC)
			startMillis = long(self.startDatetimeUtc)
			endMillis = long(self.endDatetimeUtc)
			
			templateStartUtc = DateTimeConverter.toDatetime(startMillis)
			templateEndUtc = DateTimeConverter.toDatetime(endMillis)
			
			if not templateStartUtc or not templateEndUtc:
				return None
			
			# Convert query datetime (Java Date) to UTC Python datetime
			queryMillis = queryDatetime.getTime()
			queryDatetimeUtc = DateTimeConverter.toDatetime(queryMillis)
			
			# Convert reference "now" if provided, otherwise use queryDatetime
			if referenceNow is not None:
				referenceMillis = referenceNow.getTime()
				referenceNowUtc = DateTimeConverter.toDatetime(referenceMillis)
			else:
				referenceNowUtc = queryDatetimeUtc
			
			# Parse the recurrence rule
			rrule = rrulestr(self.rrule, dtstart=templateStartUtc)
			
			# Get occurrences around the query time
			lookbackTime = queryDatetimeUtc - timedelta(hours=48)
			lookaheadTime = queryDatetimeUtc + timedelta(hours=48)
			
			occurrences = list(rrule.between(lookbackTime, lookaheadTime, inc=True))
			
			# Check each occurrence to see if query time falls within that shift
			for occurrence in occurrences:
				shiftStartUtc = occurrence
				shiftEndUtc = shiftStartUtc + timedelta(minutes=self.durationMinutes)
				
				# Check if query time falls within this shift
				if shiftStartUtc <= queryDatetimeUtc < shiftEndUtc:
					# Convert to Java Date for local display
					shiftStartLocal = DateTimeConverter.toJavaDate(shiftStartUtc)
					shiftEndLocal = DateTimeConverter.toJavaDate(shiftEndUtc)
					
					# Calculate remaining/elapsed time relative to referenceNow
					remainingSeconds = (shiftEndUtc - referenceNowUtc).total_seconds()
					durationMinutesRemaining = int(remainingSeconds / 60)
					
					# Calculate elapsed time
					elapsedSeconds = (referenceNowUtc - shiftStartUtc).total_seconds()
					durationMinutesElapsed = int(elapsedSeconds / 60)
					
					# Determine if shift is in past, current, or future
					if referenceNowUtc < shiftStartUtc:
						shiftStatus = "future"
					elif referenceNowUtc >= shiftEndUtc:
						shiftStatus = "past"
					else:
						shiftStatus = "current"
					
					return {
						'assetShiftAssignmentId': self.assetShiftAssignmentId,
						'assetId': self.assetId,
						'shiftTemplateId': self.shiftTemplateId,
						'title': self.title,
						'startDatetime': DateTimeConverter.toIsoString(shiftStartLocal),
						'endDatetime': DateTimeConverter.toIsoString(shiftEndLocal),
						'durationMinutes': self.durationMinutes,
						'durationMinutesRemaining': max(0, durationMinutesRemaining),  # Never negative
						'durationMinutesElapsed': max(0, durationMinutesElapsed),
						'shiftStatus': shiftStatus,
						'metadata': self.metadata
					}
			
			return None
			
		except Exception as e:
			logger = system.util.getLogger("mes.shift.whatShift")
			logger.error("Error calculating shift for template {}: {}".format(self.shiftTemplateId, str(e)))
			import traceback
			logger.error(traceback.format_exc())
			return None


def getShiftForAsset(assetId, datetime=None):
	"""
	Get the shift that was/is active for a given asset at a specific time.
	
	Args:
		assetId: The asset ID to query shifts for
		datetime: The time to query (DateTimeConverter-able object). If None, uses current time.
		
	Returns:
		dict: Dictionary with success status and shift info
		
	Example:
		# Get current shift
		result = getShiftForAsset(59)
		
		# Get historical shift
		result = getShiftForAsset(59, datetime='2026-02-02T19:00:00+00:00')
		
		if result['success']:
			shift = result['shift']
			if shift:
				print shift['title']  # "Day Shift"
				print shift['shiftStatus']  # "past", "current", or "future"
				print shift['durationMinutesRemaining']  # 0 if past
	"""
	try:
		# Parse the query datetime
		if datetime is None:
			queryDatetime = system.date.now()
		elif isinstance(datetime, (str, unicode)):
			try:
				pythonDt = DateTimeConverter.toDatetime(datetime)
				import calendar
				millis = long(calendar.timegm(pythonDt.timetuple()) * 1000)
				queryDatetime = system.date.fromMillis(millis)
			except:
				queryDatetime = system.date.now()
		else:
			queryDatetime = datetime
		
		# Always use actual "now" as reference for calculating remaining time
		referenceNow = system.date.now()
		
		# Validate assetId is provided
		if assetId is None:
			return {
				'success': False,
				'error': 'assetId parameter is required'
			}
		
		# Execute query
		data = system.db.runNamedQuery('App/Schedule/whatShift', {'assetId': assetId})
		
		# Convert to ShiftTemplate objects
		shiftTemplates = [ShiftTemplate(row) for row in system.dataset.toPyDataSet(data)]
		
		# Find the shift active at the query time
		shift = None
		for template in shiftTemplates:
			foundShift = template.getShiftAt(queryDatetime, referenceNow)
			if foundShift is not None:
				shift = foundShift
				break
		
		# Return the shift
		return {
			'success': True,
			'assetId': assetId,
			'queryDatetime': str(queryDatetime),
			'currentDatetime': str(referenceNow),
			'shift': shift
		}
	
	except Exception as e:
		# Log the error
		logger = system.util.getLogger("mes.shift.whatShift")
		logger.error("Error retrieving shift: " + str(e))
		import traceback
		logger.error(traceback.format_exc())
		
		# Return error response
		return {
			'success': False,
			'error': str(e)
		}

def getActiveShifts(datetime=None, siteId=None):
	pass