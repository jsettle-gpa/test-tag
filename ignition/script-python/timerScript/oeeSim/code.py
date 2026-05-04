# tagEvent/oeeSimRunner.py
import system
import random

log = system.util.getLogger("tagEvent.oeeSimRunner")

def toInt(v, d=0):
	try:
		if v is None:
			return int(d)
		return int(v)
	except:
		return int(d)

def toLong(v, d=0):
	try:
		if v is None:
			return long(d)
		return long(v)
	except:
		return long(d)

def toFloat(v, d=0.0):
	try:
		if v is None:
			return float(d)
		return float(v)
	except:
		return float(d)

def normText(v):
	try:
		if v is None:
			return ""
		return str(v).strip()
	except:
		return ""

#def buildBlocks(plannedSeconds, availability, runChunkSeconds, downChunkSeconds):
#	planned = int(plannedSeconds)
#	avail = float(availability)
#
#	runTarget = int(round(planned * avail))
#	if runTarget < 0:
#		runTarget = 0
#	if runTarget > planned:
#		runTarget = planned
#	downTarget = planned - runTarget
#
#	runChunk = int(runChunkSeconds)
#	downChunk = int(downChunkSeconds)
#	if runChunk <= 0:
#		runChunk = 1
#	if downChunk <= 0:
#		downChunk = 1
#
#	blocks = []
#	runRemaining = runTarget
#	downRemaining = downTarget
#
#	while runRemaining > 0 or downRemaining > 0:
#		if runRemaining > 0:
#			sec = runChunk if runRemaining >= runChunk else runRemaining
#			blocks.append({"state": 1, "seconds": sec})
#			runRemaining -= sec
#
#		if downRemaining > 0:
#			sec = downChunk if downRemaining >= downChunk else downRemaining
#			blocks.append({"state": 5, "seconds": sec})
#			downRemaining -= sec
#
#	return blocks

def buildBlocks(plannedSeconds, availability, runChunkSeconds, downChunkSeconds):
	"""Builds alternating run/down blocks for the simulator.
	Run blocks use state 1 (Running). Down blocks randomly pick
	from the Manufacturing Line downtime states so the dashboard
	shows varied reasons instead of always "Unplanned Downtime".

	Downtime states (from state group 1067):
	  2 = Idle           (waiting)   - weight 15
	  3 = Changeover     (setup)     - weight 20
	  5 = Unplanned Down (faulted)   - weight 10
	  6 = Starved        (waiting)   - weight 20
	  7 = Blocked        (waiting)   - weight 15
	  8 = Material Change(setup)     - weight 10
	  9 = Quality Hold   (held)      - weight 10
	"""
	planned = int(plannedSeconds)
	avail = float(availability)

	runTarget = int(round(planned * avail))
	if runTarget < 0:
		runTarget = 0
	if runTarget > planned:
		runTarget = planned
	downTarget = planned - runTarget

	runChunk = int(runChunkSeconds)
	downChunk = int(downChunkSeconds)
	if runChunk <= 0:
		runChunk = 1
	if downChunk <= 0:
		downChunk = 1

	# Weighted downtime states -- higher weight = more likely to be picked.
	# Changeover and Starved are most common in manufacturing.
	downStates = [
		(2, 15),   # Idle
		(3, 20),   # Changeover
		(5, 10),   # Unplanned Downtime
		(6, 20),   # Starved
		(7, 15),   # Blocked
		(8, 10),   # Material Change
		(9, 10)    # Quality Hold
	]

	# Build a weighted list to pick from
	weightedStates = []
	for stateCode, weight in downStates:
		weightedStates.extend([stateCode] * weight)

	blocks = []
	runRemaining = runTarget
	downRemaining = downTarget

	while runRemaining > 0 or downRemaining > 0:
		if runRemaining > 0:
			sec = runChunk if runRemaining >= runChunk else runRemaining
			blocks.append({"state": 1, "seconds": sec})
			runRemaining -= sec

		if downRemaining > 0:
			# Vary the down chunk duration slightly (50% to 150% of base)
			variedChunk = int(downChunk * (0.5 + random.random()))
			if variedChunk <= 0:
				variedChunk = 1
			sec = variedChunk if downRemaining >= variedChunk else downRemaining

			# Pick a random downtime state
			downState = random.choice(weightedStates)
			blocks.append({"state": downState, "seconds": sec})
			log.info("buildBlocks: down block state={} for {} sec".format(downState, sec))
			downRemaining -= sec

	log.info("buildBlocks: built {} blocks, avail={}, runChunk={}, downChunk={}".format(
		len(blocks), availability, runChunkSeconds, downChunkSeconds))
	return blocks

def reset(simRoot):
	"""
	Resets internal state, lifetime, and outputs for the given sim profile root.
	Example simRoot: "[default]Sim/GoodOEE"
	"""
	simRoot = simRoot.rstrip("/")
	settingsRoot = simRoot + "/Settings"
	lifeRoot = simRoot + "/Lifetime"
	outRoot = simRoot + "/Outputs"

	paths = [
		settingsRoot + "/tickNumber",
		settingsRoot + "/partCarry",
		settingsRoot + "/rejectCarry",
		settingsRoot + "/blockIndex",
		settingsRoot + "/blockRemainingSeconds",

		lifeRoot + "/good",
		lifeRoot + "/reject",
		lifeRoot + "/totalSeconds",
		lifeRoot + "/runSeconds",
		lifeRoot + "/downSeconds",

		outRoot + "/infeed",
		outRoot + "/outfeed",
		outRoot + "/reject",
		outRoot + "/state"
	]

	values = [0, 0.0, 0.0, 0, 0,  0, 0, 0, 0, 0,  0, 0, 0, 0]
	system.tag.writeBlocking(paths, values)
	log.info("reset: sim profile {} reset".format(simRoot))

def stepActiveProfile(activeProfileTagPath="[default]Sim/ActiveProfile"):
	"""
	Reads ActiveProfile and steps only that profile.
	ActiveProfile should contain folder name: GoodOEE / BadOEE / PerfectOEE
	"""
	qv = system.tag.readBlocking([activeProfileTagPath])[0]
	if not qv.quality.isGood():
		log.warn("stepActiveProfile: bad quality on ActiveProfile tag")
		return

	name = normText(qv.value)
	if name == "":
		log.warn("stepActiveProfile: ActiveProfile is empty")
		return

	log.trace("stepActiveProfile: stepping profile '{}'".format(name))
	simRoot = "[default]Sim/" + name
	step(simRoot)

def step(simRoot):
	"""
	Deterministic OEE sim engine.
	- repeating run/down blocks based on availability + chunk sizes
	- produces only during running (state 1)
	- deterministic rejects based on quality fraction carry
	- stops when targetGood reached (if targetGood > 0)
	"""
	read = system.tag.readBlocking
	write = system.tag.writeBlocking

	simRoot = simRoot.rstrip("/")
	settingsRoot = simRoot + "/Settings"
	lifeRoot = simRoot + "/Lifetime"
	outRoot = simRoot + "/Outputs"

	paths = [
		settingsRoot + "/running",
		settingsRoot + "/tickSeconds",
		settingsRoot + "/rolloverCount",
		settingsRoot + "/targetGood",

		settingsRoot + "/plannedSeconds",
		settingsRoot + "/availability",
		settingsRoot + "/performance",
		settingsRoot + "/quality",

		# NOTE: keep tag name for now, but interpret as "seconds per part"
		settingsRoot + "/idealRatePerMin",

		settingsRoot + "/runChunkSeconds",
		settingsRoot + "/downChunkSeconds",

		settingsRoot + "/tickNumber",
		settingsRoot + "/partCarry",
		settingsRoot + "/rejectCarry",
		settingsRoot + "/blockIndex",
		settingsRoot + "/blockRemainingSeconds",

		lifeRoot + "/good",
		lifeRoot + "/reject",
		lifeRoot + "/totalSeconds",
		lifeRoot + "/runSeconds",
		lifeRoot + "/downSeconds",

		outRoot + "/infeed",
		outRoot + "/outfeed",
		outRoot + "/reject",
		outRoot + "/state"
	]

	qv = read(paths)
	v = [x.value for x in qv]

	running = bool(v[0])
	if not running:
		return

	tickSeconds = max(1, toInt(v[1], 1))
	rollover = max(1, toInt(v[2], 32767))
	targetGood = max(0, toLong(v[3], 0))

	plannedSeconds = max(1, toInt(v[4], 3600))
	availability = min(1.0, max(0.0, toFloat(v[5], 1.0)))
	performance = min(1.5, max(0.0, toFloat(v[6], 1.0)))
	quality = min(1.0, max(0.0, toFloat(v[7], 1.0)))

	# INTERPRET THIS AS SECONDS PER PART
	idealSecondsPerPart = max(0.0, toFloat(v[8], 0.0))

	runChunkSeconds = max(1, toInt(v[9], 600))
	downChunkSeconds = max(1, toInt(v[10], 120))

	tickNumber = toLong(v[11], 0)
	partCarry = toFloat(v[12], 0.0)
	rejectCarry = toFloat(v[13], 0.0)
	blockIndex = toInt(v[14], 0)
	blockRemaining = toInt(v[15], 0)

	lifeGood = toLong(v[16], 0)
	lifeReject = toLong(v[17], 0)
	lifeTotal = toLong(v[18], 0)
	lifeRun = toLong(v[19], 0)
	lifeDown = toLong(v[20], 0)

	infeed = toLong(v[21], 0)
	outfeed = toLong(v[22], 0)
	reject = toLong(v[23], 0)
	stateVal = toInt(v[24], 0)

	log.trace("step: tick={}, blockIdx={}, blockRemain={}, state={}, infeed={}, outfeed={}".format(
		tickNumber, blockIndex, blockRemaining, stateVal, infeed, outfeed))

	# stop on targetGood
	if targetGood > 0 and lifeGood >= targetGood:
		log.info("step: targetGood reached ({}/{}), stopping".format(lifeGood, targetGood))
		write([settingsRoot + "/running", outRoot + "/state"], [False, 0])
		return

	# stop if planned window complete
	if lifeTotal >= plannedSeconds:
		log.info("step: planned window complete ({}/{}), stopping".format(lifeTotal, plannedSeconds))
		write([settingsRoot + "/running", outRoot + "/state"], [False, 0])
		return

	# build schedule blocks (repeat run/down chunks, but clipped to planned)
	blocks = buildBlocks(plannedSeconds, availability, runChunkSeconds, downChunkSeconds)

	# initialize / advance block if needed
	if blockRemaining <= 0:
		if blockIndex >= len(blocks):
			log.info("step: all blocks exhausted, stopping")
			write([settingsRoot + "/running", outRoot + "/state"], [False, 0])
			return
		blockRemaining = int(blocks[blockIndex]["seconds"])
		stateVal = int(blocks[blockIndex]["state"])
		log.info("step: entering block {} - state={} for {} sec".format(
			blockIndex, stateVal, blockRemaining))

	# advance time
	tickNumber += 1
	lifeTotal += tickSeconds
	blockRemaining = max(0, blockRemaining - tickSeconds)

	isRun = (stateVal == 1)
	if isRun:
		lifeRun += tickSeconds
	else:
		lifeDown += tickSeconds

	partsThisTick = 0
	rejectsThisTick = 0
	goodThisTick = 0

	# production only while running
	if isRun and idealSecondsPerPart > 0.0:
		# parts/sec = performance / (sec/part)
		actualRatePerSec = performance / idealSecondsPerPart

		rawParts = (actualRatePerSec * tickSeconds) + partCarry
		partsThisTick = int(rawParts)
		partCarry = rawParts - partsThisTick  # IMPORTANT: keep fractional carry

		rejectRate = 1.0 - quality
		if rejectRate < 0.0:
			rejectRate = 0.0
		if rejectRate > 1.0:
			rejectRate = 1.0

		rawRejects = (partsThisTick * rejectRate) + rejectCarry
		rejectsThisTick = int(rawRejects)
		rejectCarry = rawRejects - rejectsThisTick

		if rejectsThisTick > partsThisTick:
			rejectsThisTick = partsThisTick

		goodThisTick = partsThisTick - rejectsThisTick

		# clamp to targetGood
		if targetGood > 0 and (lifeGood + goodThisTick) > targetGood:
			goodThisTick = int(targetGood - lifeGood)
			if goodThisTick < 0:
				goodThisTick = 0
			partsThisTick = goodThisTick + rejectsThisTick
			if partsThisTick < goodThisTick:
				partsThisTick = goodThisTick

		# update outputs (counts stop during down)
		infeed = (infeed + partsThisTick) % rollover
		outfeed = (outfeed + goodThisTick) % rollover
		reject = (reject + rejectsThisTick) % rollover

		lifeGood += goodThisTick
		lifeReject += rejectsThisTick

	# advance block pointer if block finished
	if blockRemaining <= 0:
		blockIndex += 1
		log.info("step: block finished, advancing to block {}".format(blockIndex))

	write(
		[
			settingsRoot + "/tickNumber",
			settingsRoot + "/partCarry",
			settingsRoot + "/rejectCarry",
			settingsRoot + "/blockIndex",
			settingsRoot + "/blockRemainingSeconds",

			lifeRoot + "/good",
			lifeRoot + "/reject",
			lifeRoot + "/totalSeconds",
			lifeRoot + "/runSeconds",
			lifeRoot + "/downSeconds",

			outRoot + "/infeed",
			outRoot + "/outfeed",
			outRoot + "/reject",
			outRoot + "/state"
		],
		[
			tickNumber,
			partCarry,
			rejectCarry,
			blockIndex,
			blockRemaining,

			lifeGood,
			lifeReject,
			lifeTotal,
			lifeRun,
			lifeDown,

			infeed,
			outfeed,
			reject,
			stateVal
		]
	)