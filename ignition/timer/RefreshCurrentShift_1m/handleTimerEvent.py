def handleTimerEvent():
	logger = system.util.getLogger('shiftUDTUpdate')
	try:
		mes.shift.shift.getAllActiveShiftDS()
		#logger.info('Tag GW > RefreshCurrentShift_1m > shift UDT updated')
	except Exception as e:
		logger.error('Tag GW > RefreshCurrentShift_1m > shift UDT update failed: %s' % str(e))