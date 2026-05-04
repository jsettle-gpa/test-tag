"""
Tag path builder utilities for line-scoped MES tags.

Refactor goals:
- Keep CurrentJob and CurrentShift as first-class objects
- Reduce duplicated path-builder boilerplate
- Make adding new tags/folders easier
- Preserve convenient bulk helpers for read/write operations

Usage:
	from mes.util.tagPathBuilder import LineTagPaths

	paths = LineTagPaths("[default]GPA/Site/Area/L2")

	system.tag.readBlocking([paths.currentJob.activeRun])
	system.tag.writeBlocking(paths.currentJob.startRunTriggerTags(), [1234, True])

	outfeedTargets = paths.currentJob.outfeedAccumulatorTargets()
"""


class _TagNode(object):
	"""
	Base helper for building tag paths from a root.
	"""

	def __init__(self, root):
		self.root = str(root).rstrip("/")

	def _tag(self, name):
		return self.root + "/" + str(name)

	def _group(self, folder, cls=None):
		groupRoot = self._tag(folder)
		if cls is None:
			return TagGroup(groupRoot)
		return cls(groupRoot)


class TagGroup(_TagNode):
	"""
	Generic folder/group node.

	Use this when you want a lightweight container for paths without
	needing a custom class for every single nested folder.
	"""

	def __init__(self, root, tags=None):
		_TagNode.__init__(self, root)
		self._tags = tags or []

	def all(self):
		return [self._tag(name) for name in self._tags]


class OeeInputTagGroup(TagGroup):
	def __init__(self, root):
		TagGroup.__init__(self, root, ["ICTSeconds", "PPTSeconds"])
		self.ICTSeconds = self._tag("ICTSeconds")
		self.PPTSeconds = self._tag("PPTSeconds")


class OeeMetricTagGroup(TagGroup):
	def __init__(self, root):
		TagGroup.__init__(self, root, ["A", "P", "Q", "OEE"])
		self.availability = self._tag("A")
		self.performance = self._tag("P")
		self.quality = self._tag("Q")
		self.oee = self._tag("OEE")


class OeeTagGroup(_TagNode):
	def __init__(self, root):
		_TagNode.__init__(self, root)
		self.inputs = OeeInputTagGroup(self._tag("Inputs"))
		self.metrics = OeeMetricTagGroup(self._tag("Metrics"))


class JobCountTagGroup(TagGroup):
	def __init__(self, root):
		TagGroup.__init__(self, root, [
			"derivedInfeed",
			"derivedOutfeed",
			"derivedReject",
			"totalCount"
		])
		self.infeed = self._tag("derivedInfeed")
		self.outfeed = self._tag("derivedOutfeed")
		self.reject = self._tag("derivedReject")
		self.totalCount = self._tag("totalCount")

	def resettable(self):
		return [
			self.infeed,
			self.outfeed,
			self.reject
		]


class JobStateTagGroup(TagGroup):
	def __init__(self, root):
		TagGroup.__init__(self, root, [
			"lastState",
			"lastStateChangeTime",
			"stateChangeDS",
			"totalRunningSeconds",
			"totalDownSeconds",
			"microStopSeconds",
			"microStopCount",
			"isRunning"
		])
		self.lastState = self._tag("lastState")
		self.lastStateChangeTime = self._tag("lastStateChangeTime")
		self.stateChangeDS = self._tag("stateChangeDS")
		self.totalRunningSeconds = self._tag("totalRunningSeconds")
		self.totalDownSeconds = self._tag("totalDownSeconds")
		self.microStopSeconds = self._tag("microStopSeconds")
		self.microStopCount = self._tag("microStopCount")
		self.isRunning = self._tag("isRunning")

	def resettable(self):
		return self.all()


class JobMachineInputRefTagGroup(TagGroup):
	def __init__(self, root):
		TagGroup.__init__(self, root, ["outfeed", "infeed", "reject", "state"])
		self.outfeed = self._tag("outfeed")
		self.infeed = self._tag("infeed")
		self.reject = self._tag("reject")
		self.state = self._tag("state")


class CurrentJob(_TagNode):
	"""
	Full path builder for CurrentJob tags.
	"""

	def __init__(self, assetPath):
		_TagNode.__init__(self, str(assetPath).rstrip("/") + "/CurrentJob")

		# Identity / header tags
		self.runId = self._tag("runId")
		self.activeRun = self._tag("activeRun")
		self.bomId = self._tag("bomId")
		self.productId = self._tag("productId")
		self.requiredQuantity = self._tag("requiredQuantity")
		self.idealRunRate = self._tag("idealRunRate")
		self.runPlannedStartTime = self._tag("runPlannedStartTime")
		self.runPlannedEndTime = self._tag("runPlannedEndTime")
		self.productName = self._tag("productName")

		# Nested groups
		self.counts = JobCountTagGroup(self._tag("runCounts"))
		self.states = JobStateTagGroup(self._tag("runStates"))
		self.oee = OeeTagGroup(self._tag("OEE"))
		self.machineRef = JobMachineInputRefTagGroup(self._tag("MachineInputRef"))

	def startRunTriggerTags(self):
		return [
			self.runId,
			self.activeRun
		]

	def endRunTriggerTags(self):
		return [
			self.activeRun
		]

	def identityTags(self):
		return [
			self.runId,
			self.bomId,
			self.productId,
			self.requiredQuantity,
			self.idealRunRate,
			self.runPlannedStartTime,
			self.runPlannedEndTime
		]

	def outfeedAccumulatorTargets(self):
		return [self.counts.outfeed]

	def rejectAccumulatorTargets(self):
		return [self.counts.reject]

	def infeedAccumulatorTargets(self):
		return [self.counts.infeed]


class ShiftCountTagGroup(TagGroup):
	def __init__(self, root):
		TagGroup.__init__(self, root, ["GoodCount", "RejectCount", "totalCount"])
		self.good = self._tag("GoodCount")
		self.reject = self._tag("RejectCount")
		self.totalCount = self._tag("totalCount")


class ShiftStateTagGroup(TagGroup):
	def __init__(self, root):
		TagGroup.__init__(self, root, [
			"lastState",
			"lastStateChangeTime",
			"stateChangeDS",
			"totalRunningSeconds",
			"totalDownSeconds",
			"microStopSeconds",
			"microStopCount",
			"isRunning"
		])
		self.lastState = self._tag("lastState")
		self.lastStateChangeTime = self._tag("lastStateChangeTime")
		self.stateChangeDS = self._tag("stateChangeDS")
		self.totalRunningSeconds = self._tag("totalRunningSeconds")
		self.totalDownSeconds = self._tag("totalDownSeconds")
		self.microStopSeconds = self._tag("microStopSeconds")
		self.microStopCount = self._tag("microStopCount")
		self.isRunning = self._tag("isRunning")


class CurrentShift(_TagNode):
	"""
	Full path builder for CurrentShift tags.
	"""

	def __init__(self, assetPath):
		_TagNode.__init__(self, str(assetPath).rstrip("/") + "/CurrentShift")

		# Identity / header tags
		self.shiftId = self._tag("shiftId")
		self.shiftName = self._tag("shiftName")
		self.shiftStartTime = self._tag("shiftStartTime")
		self.shiftEndTime = self._tag("shiftEndTime")
		self.plannedProductionTime = self._tag("plannedProductionTime")
		self.productsProduced = self._tag("metrics/productsProduced")

		# Nested groups
		self.counts = ShiftCountTagGroup(self._tag("shiftCounts"))
		self.states = ShiftStateTagGroup(self._tag("shiftStates"))
		self.oee = OeeTagGroup(self._tag("OEE"))

	def identityTags(self):
		return [
			self.shiftId,
			self.shiftName,
			self.shiftStartTime,
			self.shiftEndTime,
			self.plannedProductionTime
		]


class MachineInputTagPaths(TagGroup):
	"""
	Full path builder for MachineInput tags.
	"""

	def __init__(self, assetPath):
		TagGroup.__init__(self, str(assetPath).rstrip("/") + "/MachineInput", [
			"outfeed",
			"infeed",
			"reject",
			"state"
		])
		self.outfeed = self._tag("outfeed")
		self.infeed = self._tag("infeed")
		self.reject = self._tag("reject")
		self.state = self._tag("state")


class ConfigTagPaths(TagGroup):
	"""
	Full path builder for Config tags under a line.
	"""

	def __init__(self, assetPath):
		TagGroup.__init__(self, str(assetPath).rstrip("/") + "/Config", [
			"states",
			"assetId"
		])
		self.states = self._tag("states")
		self.assetId = self._tag("assetId")


class LineTagPaths(object):
	"""
	Entry point for all line-scoped tag paths.

	Args:
		assetPath (str): Full line root path, for example:
			'[default]GPA/Site/Area/L2'
	"""

	KNOWN_ANCHORS = [
		"/CurrentJob",
		"/CurrentShift",
		"/MachineInput",
		"/Config"
	]

	def __init__(self, assetPath):
		self.assetPath = str(assetPath).rstrip("/")

		self.currentJob = CurrentJob(self.assetPath)
		self.currentShift = CurrentShift(self.assetPath)
		self.machine = MachineInputTagPaths(self.assetPath)
		self.config = ConfigTagPaths(self.assetPath)

		# Backward compatibility aliases
		self.job = self.currentJob
		self.shift = self.currentShift

	@classmethod
	def fromTagPath(cls, tagPath):
		fullPath = str(tagPath)

		for anchor in cls.KNOWN_ANCHORS:
			idx = fullPath.find(anchor)
			if idx > -1:
				return cls(fullPath[:idx])

		return cls(fullPath)

	def debugDump(self):
		return {
			"assetPath": self.assetPath,

			"currentJob.root": self.currentJob.root,
			"currentJob.runId": self.currentJob.runId,
			"currentJob.activeRun": self.currentJob.activeRun,
			"currentJob.bomId": self.currentJob.bomId,
			"currentJob.productId": self.currentJob.productId,
			"currentJob.requiredQuantity": self.currentJob.requiredQuantity,
			"currentJob.idealRunRate": self.currentJob.idealRunRate,
			"currentJob.runPlannedStartTime": self.currentJob.runPlannedStartTime,
			"currentJob.runPlannedEndTime": self.currentJob.runPlannedEndTime,
			"currentJob.counts.infeed": self.currentJob.counts.infeed,
			"currentJob.counts.outfeed": self.currentJob.counts.outfeed,
			"currentJob.counts.reject": self.currentJob.counts.reject,
			"currentJob.counts.totalCount": self.currentJob.counts.totalCount,
			"currentJob.states.lastState": self.currentJob.states.lastState,
			"currentJob.states.lastStateChangeTime": self.currentJob.states.lastStateChangeTime,
			"currentJob.states.stateChangeDS": self.currentJob.states.stateChangeDS,
			"currentJob.states.totalRunningSeconds": self.currentJob.states.totalRunningSeconds,
			"currentJob.states.totalDownSeconds": self.currentJob.states.totalDownSeconds,
			"currentJob.states.microStopSeconds": self.currentJob.states.microStopSeconds,
			"currentJob.states.microStopCount": self.currentJob.states.microStopCount,
			"currentJob.states.isRunning": self.currentJob.states.isRunning,
			"currentJob.oee.inputs.ICTSeconds": self.currentJob.oee.inputs.ICTSeconds,
			"currentJob.oee.inputs.PPTSeconds": self.currentJob.oee.inputs.PPTSeconds,
			"currentJob.oee.metrics.A": self.currentJob.oee.metrics.availability,
			"currentJob.oee.metrics.P": self.currentJob.oee.metrics.performance,
			"currentJob.oee.metrics.Q": self.currentJob.oee.metrics.quality,
			"currentJob.oee.metrics.OEE": self.currentJob.oee.metrics.oee,

			"currentShift.root": self.currentShift.root,
			"currentShift.shiftId": self.currentShift.shiftId,
			"currentShift.shiftName": self.currentShift.shiftName,
			"currentShift.shiftStartTime": self.currentShift.shiftStartTime,
			"currentShift.shiftEndTime": self.currentShift.shiftEndTime,
			"currentShift.plannedProductionTime": self.currentShift.plannedProductionTime,
			"currentShift.counts.good": self.currentShift.counts.good,
			"currentShift.counts.reject": self.currentShift.counts.reject,
			"currentShift.counts.totalCount": self.currentShift.counts.totalCount,
			"currentShift.states.lastState": self.currentShift.states.lastState,
			"currentShift.states.lastStateChangeTime": self.currentShift.states.lastStateChangeTime,
			"currentShift.states.stateChangeDS": self.currentShift.states.stateChangeDS,
			"currentShift.states.totalRunningSeconds": self.currentShift.states.totalRunningSeconds,
			"currentShift.states.totalDownSeconds": self.currentShift.states.totalDownSeconds,
			"currentShift.states.microStopSeconds": self.currentShift.states.microStopSeconds,
			"currentShift.states.microStopCount": self.currentShift.states.microStopCount,
			"currentShift.states.isRunning": self.currentShift.states.isRunning,
			"currentShift.oee.inputs.ICTSeconds": self.currentShift.oee.inputs.ICTSeconds,
			"currentShift.oee.inputs.PPTSeconds": self.currentShift.oee.inputs.PPTSeconds,
			"currentShift.oee.metrics.A": self.currentShift.oee.metrics.availability,
			"currentShift.oee.metrics.P": self.currentShift.oee.metrics.performance,
			"currentShift.oee.metrics.Q": self.currentShift.oee.metrics.quality,
			"currentShift.oee.metrics.OEE": self.currentShift.oee.metrics.oee,

			"machine.root": self.machine.root,
			"machine.outfeed": self.machine.outfeed,
			"machine.infeed": self.machine.infeed,
			"machine.reject": self.machine.reject,
			"machine.state": self.machine.state,

			"config.root": self.config.root,
			"config.states": self.config.states,
			"config.assetId": self.config.assetId
		}