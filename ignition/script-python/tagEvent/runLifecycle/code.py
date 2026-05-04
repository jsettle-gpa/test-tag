# mes/runLifecycle.py

import tagUtils
from tagEvent import jobCounts

logger = system.util.getLogger("mes.runLifecycle")

def onJobActiveChange(tagPath, currentValue, previousValue, initialChange):
	"""
	Call from Tag Change Script on jobActive.
	When job starts (rising edge), reset job counts.
	"""
	if initialChange:
		return

	isStarting = bool(currentValue.value) and not bool(previousValue.value)
	if not isStarting:
		return

	jobRoot = tagUtils.parentPath(tagPath, 1)
	jobCounts.resetCounts(jobRoot)
	