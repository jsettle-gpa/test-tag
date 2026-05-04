def toLong(value, defaultValue=0):
	"""
	Coerce to long safely.
	"""
	try:
		if value is None:
			return long(defaultValue)
		return long(value)
	except:
		return long(defaultValue)