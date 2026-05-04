# ported 2025-02-09 - hunter

from java.util import Date
from java.sql import Timestamp
from java.text import SimpleDateFormat
from java.util import TimeZone
from datetime import datetime


# ================================================================
# DATETIME HANDLING STRATEGY
# ================================================================
#
# we deal with three different layers that each want dates in
# different formats and this can get messy fast
#
# 1) Ignition Perspective frontend uses java.util.Date
# 2) Domain logic in Jython works best with Python datetime
# 3) Database uses datetimeoffset(0) for timestamps and
#    plain date type for things like recurrence_end_date
#
# the approach here is to keep Python datetime as the internal
# representation inside our domain objects since thats what
# works best for comparisons and calculations in Jython
#
# then i provide explicit accessors for each context so you
# always know what youre getting back
#
#   .startDatetime        -> Python datetime for domain logic
#   .startAsJavaDate      -> java.util.Date for Perspective
#   .startAsIsoString     -> ISO string for database writes
#   .toDateString         -> YYYY-MM-DD for date columns
#
# The DateTimeConverter class handles all the messy conversion
# stuff in one place so we dont have conversion code scattered
# everywhere and i can actually test it properly
#
# When creating objects via new() you can pass in whatever
# format you have and it figures it out
#
# When rebuilding from the database the reconstitute()
# method knows what format to expect from each column type
#
# IMPORTANT:
# If you make changes in this area, all existing tests must
# continue to pass. Date handling bugs are subtle and tend
# to surface later in production if we are not strict here.
#
# ALSO NOTE:
# If you are using the Ignition script console to test changes,
# make sure to reset the script console between runs. The
# datetime library can get into a weird state and break
# unpredictably, and trying to troubleshoot that usually
# leads to internal Ignition issues rather than real bugs.
# Ask me how i know. - hunter
#
# ================================================================

class DateTimeConverter:
	"""
	Centralized datetime conversion for Jython/Ignition.
	
	Handles conversions between:
	  - Java Date/Timestamp (frontend, Ignition)
	  - Python datetime (domain logic)
	  - ISO-8601 strings (serialization, API)
	  - SQL date strings (database date columns)
	"""
	
	# thread safe formatters would be better, works for now
	_ISO_FORMAT = "yyyy-MM-dd'T'HH:mm:ssXXX"
	_DATE_FORMAT = "yyyy-MM-dd"
	
	@classmethod
	def toDatetime(cls, value):
		"""
		Convert any supported type to Python datetime.
		
		Accepts: Java Date, Timestamp, millis (long), ISO string, Python datetime
		Returns: Python datetime or None
		"""
		if value is None or value == "":
			return None
		
		if isinstance(value, datetime):
			return value
		
		# java Date or Timestamp -> millis -> datetime
		if isinstance(value, (Date, Timestamp)):
			millis = value.getTime()
			return datetime.utcfromtimestamp(millis / 1000.0)
		
		# millis as long/int
		if isinstance(value, (int, long)):
			return datetime.utcfromtimestamp(value / 1000.0)
		
		# ISO string
		if isinstance(value, basestring):
			return cls._parseIsoString(value)
		
		raise ValueError("Cannot convert %s to datetime" % type(value).__name__)
	
	@classmethod
	def toJavaDate(cls, value):
		"""
		Convert any supported type to java.util.Date.
		
		Accepts: Python datetime, ISO string, millis, Java Date
		Returns: java.util.Date or None
		"""
		if value is None or value == "":
			return None
		
		if isinstance(value, Date):
			return value
		
		if isinstance(value, Timestamp):
			return Date(value.getTime())
		
		if isinstance(value, datetime):
			import calendar
			millis = long(calendar.timegm(value.timetuple()) * 1000)
			return Date(millis)
		
		if isinstance(value, (int, long)):
			return Date(long(value))
		
		if isinstance(value, basestring):
			dt = cls._parseIsoString(value)
			return cls.toJavaDate(dt) if dt else None
		
		raise ValueError("Cannot convert %s to Java Date" % type(value).__name__)
	
	@classmethod
	def toIsoString(cls, value):
		"""
		Convert any supported type to ISO-8601 UTC string.
		
		Returns: "2026-01-01T05:00:00+00:00" or None
		"""
		if value is None or value == "":
			return None
		
		if isinstance(value, basestring):
			dt = cls._parseIsoString(value)
			if dt is None:
				raise ValueError("Invalid ISO string: %s" % value)
			return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
		
		dt = cls.toDatetime(value)
		if dt is None:
			return None
		
		return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
	
	@classmethod
	def toDateString(cls, value):
		"""
		Convert any supported type to date-only string (YYYY-MM-DD).
		
		For database 'date' columns like recurrence_end_date.
		Returns: "2026-01-01" or None
		"""
		if value is None or value == "":
			return None
		
		# uf already a date string, extract date portion
		if isinstance(value, basestring):
			if "T" in value:
				return value.split("T")[0]
			# assume it's already YYYY-MM-DD
			if len(value) == 10 and value[4] == "-" and value[7] == "-":
				return value
			# try to parse and convert
			dt = cls._parseIsoString(value)
			if dt:
				return dt.strftime("%Y-%m-%d")
			raise ValueError("Invalid date string: %s" % value)
		
		dt = cls.toDatetime(value)
		if dt is None:
			return None
		
		return dt.strftime("%Y-%m-%d")
	
	@classmethod
	def _parseIsoString(cls, value):
		"""Parse ISO-8601 string to Python datetime."""
		if not value:
			return None
		
		# handle various ISO formats
		# remove timezone for parsing, assume UTC
		clean = value
		if clean.endswith("Z"):
			clean = clean[:-1]
		if "+" in clean:
			clean = clean.split("+")[0]
		if clean.count("-") > 2:  # has negative timezone like -05:00
			# find the timezone portion after the time
			if "T" in clean:
				parts = clean.split("T")
				timePart = parts[1]
				if "-" in timePart:
					timePart = timePart.split("-")[0]
				clean = parts[0] + "T" + timePart
		
		# try common formats
		formats = [
			"%Y-%m-%dT%H:%M:%S",
			"%Y-%m-%dT%H:%M:%S.%f",
			"%Y-%m-%d %H:%M:%S",
			"%Y-%m-%d",
		]
		
		for fmt in formats:
			try:
				return datetime.strptime(clean, fmt)
			except ValueError:
				continue
		
		raise ValueError("Cannot parse datetime string: %s" % value)

## tests for DateTimeConverter

from java.time import Instant
from java.util import Date
from datetime import datetime

def test_toDatetime_FromJavaDate():
	dateObj = Date(1767243600000L)
	result = DateTimeConverter.toDatetime(dateObj)
	assert isinstance(result, datetime), "Expected Python datetime"
	assert result.year == 2026
	assert result.month == 1
	assert result.day == 1
	assert result.hour == 5
	assert result.minute == 0

def test_toDatetime_FromMillis():
	millis = 1767243600000L
	result = DateTimeConverter.toDatetime(millis)
	assert isinstance(result, datetime), "Expected Python datetime"
	assert result.year == 2026
	assert result.month == 1
	assert result.day == 1

def test_toDatetime_FromIsoString():
	iso = "2026-01-01T05:00:00+00:00"
	result = DateTimeConverter.toDatetime(iso)
	assert isinstance(result, datetime), "Expected Python datetime"
	assert result.year == 2026
	assert result.month == 1
	assert result.day == 1
	assert result.hour == 5

def test_toDatetime_FromIsoStringZ():
	iso = "2026-01-01T05:00:00Z"
	result = DateTimeConverter.toDatetime(iso)
	assert isinstance(result, datetime), "Expected Python datetime"
	assert result.hour == 5

def test_toDatetime_FromPythonDatetime():
	dt = datetime(2026, 1, 1, 5, 0, 0)
	result = DateTimeConverter.toDatetime(dt)
	assert result is dt, "Should return same object"

def test_toDatetime_None():
	assert DateTimeConverter.toDatetime(None) is None
	assert DateTimeConverter.toDatetime("") is None

def test_toJavaDate_FromPythonDatetime():
	dt = datetime(2026, 1, 1, 5, 0, 0)
	result = DateTimeConverter.toJavaDate(dt)
	assert isinstance(result, Date), "Expected Java Date"
	assert result.getTime() == 1767243600000L

def test_toJavaDate_FromMillis():
	millis = 1767243600000L
	result = DateTimeConverter.toJavaDate(millis)
	assert isinstance(result, Date), "Expected Java Date"
	assert result.getTime() == millis

def test_toJavaDate_FromIsoString():
	iso = "2026-01-01T05:00:00+00:00"
	result = DateTimeConverter.toJavaDate(iso)
	assert isinstance(result, Date), "Expected Java Date"
	assert result.getTime() == 1767243600000L

def test_toJavaDate_FromJavaDate():
	dateObj = Date(1767243600000L)
	result = DateTimeConverter.toJavaDate(dateObj)
	assert result is dateObj, "Should return same object"

def test_toJavaDate_None():
	assert DateTimeConverter.toJavaDate(None) is None
	assert DateTimeConverter.toJavaDate("") is None

def test_toIsoString_FromJavaDate():
	dateObj = Date(1767243600000L)
	result = DateTimeConverter.toIsoString(dateObj)
	assert isinstance(result, basestring), "Expected string"
	assert result == "2026-01-01T05:00:00+00:00"

def test_toIsoString_FromPythonDatetime():
	dt = datetime(2026, 1, 1, 5, 0, 0)
	result = DateTimeConverter.toIsoString(dt)
	assert result == "2026-01-01T05:00:00+00:00"

def test_toIsoString_FromMillis():
	millis = 1767243600000L
	result = DateTimeConverter.toIsoString(millis)
	assert result == "2026-01-01T05:00:00+00:00"

def test_toIsoString_Normalization():
	# input with Z should normalize to +00:00
	result = DateTimeConverter.toIsoString("2026-01-01T05:00:00Z")
	assert result.endswith("+00:00"), "Should normalize to +00:00 format"

def test_toIsoString_None():
	assert DateTimeConverter.toIsoString(None) is None
	assert DateTimeConverter.toIsoString("") is None

def test_toDateString_FromPythonDatetime():
	dt = datetime(2026, 1, 1, 5, 0, 0)
	result = DateTimeConverter.toDateString(dt)
	assert result == "2026-01-01"

def test_toDateString_FromIsoString():
	iso = "2026-01-01T05:00:00+00:00"
	result = DateTimeConverter.toDateString(iso)
	assert result == "2026-01-01"

def test_toDateString_FromDateString():
	# already a date string should pass through
	result = DateTimeConverter.toDateString("2026-01-01")
	assert result == "2026-01-01"

def test_toDateString_FromJavaDate():
	dateObj = Date(1767243600000L)
	result = DateTimeConverter.toDateString(dateObj)
	assert result == "2026-01-01"

def test_toDateString_None():
	assert DateTimeConverter.toDateString(None) is None
	assert DateTimeConverter.toDateString("") is None

def test_roundtrip_JavaDate():
	# Java Date -> datetime -> Java Date
	original = Date(1767243600000L)
	dt = DateTimeConverter.toDatetime(original)
	back = DateTimeConverter.toJavaDate(dt)
	assert back.getTime() == original.getTime()

def test_roundtrip_IsoString():
	# ISO string -> datetime -> ISO string
	original = "2026-01-01T05:00:00+00:00"
	dt = DateTimeConverter.toDatetime(original)
	back = DateTimeConverter.toIsoString(dt)
	assert back == original

def run_datetime_converter_tests():
	tests = [
		test_toDatetime_FromJavaDate,
		test_toDatetime_FromMillis,
		test_toDatetime_FromIsoString,
		test_toDatetime_FromIsoStringZ,
		test_toDatetime_FromPythonDatetime,
		test_toDatetime_None,
		test_toJavaDate_FromPythonDatetime,
		test_toJavaDate_FromMillis,
		test_toJavaDate_FromIsoString,
		test_toJavaDate_FromJavaDate,
		test_toJavaDate_None,
		test_toIsoString_FromJavaDate,
		test_toIsoString_FromPythonDatetime,
		test_toIsoString_FromMillis,
		test_toIsoString_Normalization,
		test_toIsoString_None,
		test_toDateString_FromPythonDatetime,
		test_toDateString_FromIsoString,
		test_toDateString_FromDateString,
		test_toDateString_FromJavaDate,
		test_toDateString_None,
		test_roundtrip_JavaDate,
		test_roundtrip_IsoString,
	]
	
	passed = 0
	failed = 0
	
	for test in tests:
		try:
			test()
			print "PASS: %s" % test.__name__
			passed += 1
		except AssertionError as e:
			print "FAIL: %s - %s" % (test.__name__, str(e))
			failed += 1
		except Exception as e:
			print "ERROR: %s - %s" % (test.__name__, str(e))
			failed += 1
	
	print "\n%d passed, %d failed" % (passed, failed)