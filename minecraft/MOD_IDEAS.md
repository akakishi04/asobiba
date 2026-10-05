# AsobibaTweaks idea pool

Rule: small features, independently switchable, and no feature may become a hard dependency for another feature.

## Accepted / in implementation

### Growing item mining-tier mutations
Pickaxes can rarely improve their effective harvest tier when leveling. This makes some early-game tools become unusual keepers instead of making every old tool mandatory to retain.

### Daily Favor
One small activity receives a mild bonus each Minecraft day. It should influence today's choice, not become a chore list.

### Universal Bond
Every Mob can participate in a generic Bond system. Common follow/stay/friendly-owner behavior is shared; species-specific pet abilities are optional later extensions.

## World oddities

### Sleep roulette
Sleeping can roll a temporary next-day rule: low gravity, stronger knockback, fast crops, fragile tools, unusually social animals, etc.

### Weather fronts
Rare local weather modifiers: strong wind bends projectiles, warm rain accelerates crops, meteor-shower nights create tiny surface finds.

### Strange chunks
A tiny fraction of chunks receive a deterministic quirk from world seed + chunk coordinate: weak gravity, echoing sounds, fast plants, strange slime behavior.

### Minor anomalies
Very rare harmless events: a village bell rings with nobody there, nearby sheep all stare in one direction, torches flicker, bats suddenly leave a cave.

### Seasonal micro-rules
Not full seasons. Every few Minecraft days, one subtle environmental modifier rotates: mushrooms spread slightly more, snow lingers, bees work longer, etc.

## Exploration

### Forgotten camp
Very small procedural abandoned camps: campfire, one container, signs of what happened. No giant structure system.

### Wanderer's cache
Maps can occasionally point to a tiny buried cache with mostly mundane supplies and one odd named object.

### Landmark memory
The game remembers first visits to distinctive places and can later generate tiny callbacks: "You first reached a cherry grove 37 days ago."

### Echo trail
After a long expedition, returning through previously traveled chunks can occasionally reveal tiny visual traces of the old journey.

### Cartographer rumors
Cartographers sometimes sell vague rumors rather than exact structure maps: "something unusual lies north beyond a cold biome."

## Mob systems

### Mob grudges
A hostile Mob that survives repeated encounters may remember the player, gain a name and a small personality modifier.

### Pet personality
Bonded mobs can roll traits such as brave, cowardly, greedy, curious, sleepy, territorial or clingy.

### Pet jobs
Simple optional roles rather than automation factories: pick up nearby drops, warn about enemies, sit near crops, carry a tiny inventory.

### Unlikely friendships
Two nearby bonded mobs can slowly form a relationship; friends prefer staying near each other and may react if one is hurt.

### Wild curiosity
Some normally neutral/passive mobs occasionally inspect placed blocks, dropped items or unusual player actions.

### Herd memory
Repeatedly feeding or protecting a local herd makes that herd less skittish around the player without individually taming every animal.

## Items and inventory

### Item personality
Growing items gain traits at milestones: stubborn, careful, lucky, bloodthirsty, sentimental, etc.

### Tool scars
Important events leave purely descriptive history on an item: first diamond mined, dragon fight survived, 10,000th block broken.

### Lucky junk
Rare worthless-looking items get strange tiny properties. Example: a bowl that occasionally refuses to leave the hotbar, or a stick that glows near bees.

### Inheritance
Retiring a highly grown item can pass one small trait or a fraction of growth into a replacement, avoiding permanent starter-tool lock-in.

### Last chance durability
A beloved high-growth tool at 1 durability can very rarely refuse to break once, gaining a permanent "survivor" scar.

## Player / daily life

### Micro quests
Tiny contextual challenges: mine 16 blocks without taking damage, return home before sunset, cook three different foods. Rewards stay small.

### Habit tracker
The game notices repeated habits ("you fish every rainy morning") and occasionally acknowledges them without turning them into achievements.

### Home comfort
Frequently used areas slowly become recognized as "home"; sleeping/eating there may give tiny comfort effects, with no claim/protection system.

### Travel fatigue
Repeated sprinting over huge distances gives a very small reason to stop at camps, beds or villages. Must remain optional and non-annoying.

### Personal rituals
A repeated unusual sequence of actions can become a tiny self-created ritual with cosmetic feedback. Example: ring bell -> sleep -> eat bread.

## Death and risk

### Death echo
Deaths leave a lightweight echo containing cause/time/location. Revisiting it can provide a tiny recovery opportunity or just history.

### Near-death memory
Surviving below one heart can mark the held item or bonded pet with a descriptive memory.

### Revenge target
The Mob that killed the player can rarely become marked and persist for a while, creating an emergent revenge objective.

## Resource / building tweaks

### Resource fatigue
Repeatedly harvesting one resource in a short period can cause harmless weirdness: sounds, particles, temporary quirks or a tiny chance for ore to shift.

### Builder's momentum
Placing many blocks of the same palette gives cosmetic rhythm feedback, not speed buffs strong enough to automate building.

### Aging builds
Player-placed blocks can optionally accumulate only cosmetic age metadata over very long periods, enabling subtle moss/dust overlays later.

### Mining resonance
Long uninterrupted mining sometimes reveals audio hints about nearby caves or ore clusters rather than directly highlighting blocks.

## Weird but promising
### Moon Toss / Lunar Offering
On full-moon nights, throwing selected items high enough into the open sky can cause them to vanish as a lunar offering. Several Minecraft days later, the world may return a thematically related, strange, or deliberately disproportionate package from the sky. The exchange table should be world-seed-influenced, not fully disclosed, and configurable. This is accepted as a future implementation candidate.


### Object superstition
The game invents meaningless-but-consistent folklore for a world seed, such as "red beds are lucky during thunderstorms", with tiny cosmetic confirmation.

### Moon moods
Certain full moons slightly alter Mob behaviors rather than simply buffing spawn rates.

### World nicknames
Frequently visited places can acquire generated nicknames based on events that happened there.

### Lost-and-found
Mobs may occasionally carry mundane named objects implying a tiny story; returning/keeping them has no major balance effect.

### Rumor system
Villagers generate short claims about local events. Some are true, some exaggerated, some completely wrong.

## Avoid for AsobibaTweaks

- Large tech trees.
- New dimensions.
- Massive content packs.
- Anything requiring AsobibaTweaks to keep a world loadable.
- Systems whose optimal use becomes mandatory busywork.

Those should become separate mods.

## World Folklore implementation candidate

Accepted as a future implementation family rather than immediate v0.1 scope.

Core direction:

- Seed-specific hidden folklore rules that differ per world.
- Some rumors are true, some are false, and some are incomplete versions of a real condition.
- Repeated player habits can become recognized rituals with tiny cosmetic or mechanical effects.
- Important locations can accumulate local memory and folklore over time.
- The world may slowly adapt tiny behaviors to long-term player habits without exposing a visible progression meter.

Design constraint: folklore should feel discoverable and arguable, not like a checklist or achievement system. Exact rules should not be dumped directly into normal UI.

## Accepted movement / interaction tweaks

The following are promoted to planned implementation candidates:

### Wall Kick
A lightweight wall-jump: jump against a wall and kick away once before landing. No equipment requirement. Intended for traversal, cave movement and combat repositioning.

### Sliding
While sprinting, crouch to enter a short slide. The initial goal is movement feel and fitting through low gaps, not combat DPS.

### Ledge Climb
Allow the player to catch and climb short ledges that are just out of normal jump reach. Keep the reachable height conservative so ladders/scaffolding remain useful.

### Field Repair
Permit crude direct repairs without an anvil by consuming matching material. This must be less efficient than proper repair systems and should be useful mainly while away from base.

### Weapon Throwing
Allow selected melee weapons such as swords and axes to be thrown, land as recoverable objects, and be picked back up. Balance around giving up the held weapon temporarily rather than making it a superior ranged attack.

### Torch Throwing
Allow torches to be thrown as lightweight utility projectiles. A valid impact on a floor or wall can place the torch, making cave scouting and vertical exploration less menu-like. Prefer sharing a generic throwable-item foundation with weapon throwing.

### Carry Small Mobs
Allow the player to pick up and carry small mobs directly. Carrying occupies the player's hands and slows or otherwise constrains movement. Bonded or injured mobs may receive slightly more permissive handling. Some dangerous small mobs should remain risky rather than being made harmless while carried.

Design constraint: both features should feel physical and immediate, not like opening a transport or placement GUI.

Design constraint: these features should extend vanilla interaction vocabulary without becoming a mandatory movement/combat overhaul.


## Accepted village / world simulation tweaks

### Mob-Used Buildings
Mobs should recognize and make lightweight use of player- or village-built spaces: shelter from rain, gathering around campfires, using benches/tables heuristically, preferring bridges and doors, and treating sensible interiors differently from open terrain. This is not a claim/protection system.

### Regional Trade Value
Some goods become more valuable when moved far from where they are common. Snow-region goods can fetch more in deserts, cactus/desert goods more in cold regions, etc. Keep the model simple and visible enough to reward actual transport without turning trade into an opaque economy simulator.

### Fire as a Village Emergency
Large fires in or near settlements become an event. Villagers, golems and bonded helpers can flee, alert others, move valuables and attempt simple firefighting with nearby water or available containers. Fire should become a local incident rather than passive background destruction.

### Autonomous Village Growth
Villages can slowly expand using resources they actually possess or gather.

Initial scope:
- Villagers recognize a bounded village work area.
- Simple worker behaviors gather renewable/local materials such as logs, crops, stone/cobble and selected common blocks.
- Harvested resources enter village storage instead of appearing from nowhere.
- Builders consume those stored materials to construct from a small pool of vanilla-like templates.
- Expansion is gated by population, beds, stored resources and a long cooldown measured in Minecraft days.
- Workers replant crops and saplings where practical.
- Natural resource gathering must avoid obvious player structures and never indiscriminately strip the entire area.
- Existing paths/buildings influence where new structures are placed.
- New houses/workspaces should be incremental additions, not instant village regeneration.

Design constraint: the system should make villages feel self-sustaining and capable of modest growth, not become a colony-management game or fully autonomous megacity builder.


### Carpenter Villager Profession
Add a dedicated carpenter/builder villager profession as the visible executor for village construction.

Initial responsibilities:
- Read village build jobs created by the autonomous-growth planner.
- Pull required blocks from village storage rather than spawning materials.
- Carry a small work inventory for the current construction step.
- Walk to the build site and place blocks progressively.
- Repair damaged village structures using stored materials.
- Help with post-fire reconstruction.
- Prefer nearby safe scaffolding/path positions and stop work at night or during danger.

Possible workstation:
- A vanilla-adjacent workstation should be preferred where practical; otherwise add one very small carpenter workbench block rather than a whole machine system.

Possible trades:
- Buy logs, planks, stone, bricks and common construction materials.
- Sell scaffolding, ladders, doors, fences, signs and small batches of building blocks.
- Higher levels can sell decorative building materials or village-style blueprint/map items without bypassing exploration.

Design constraint: carpenter AI should execute construction jobs, not independently decide village strategy. Planning stays in a village-level system so individual villagers remain simple and debuggable.


## Village simulation scope — accepted

Village simulation is now an accepted feature family. The goal is a lightweight, observable settlement simulation built from real resources and actual villager actions, not invisible structure spawning.

### Village professions and logistics
- Carpenter: executes construction and repair jobs, including post-fire reconstruction.
- Quartermaster: manages shared village storage and exposes shortages/surpluses.
- Forester: harvests wood conservatively and replants saplings.
- Quarry worker: gathers stone from bounded/recognized quarry areas instead of free-form underground strip mining.
- Porter: moves resources between farms, quarries, forests, storage and build sites; later may use llamas/donkeys.
- Fire responder role: maintains access to water and prioritizes emergency response when fires occur.

### Autonomous village growth
- Villages gather real local/renewable materials.
- Gathered resources enter actual village storage.
- Construction consumes stored resources.
- Growth is gated by population, beds, food, resources, available land and long cooldowns.
- Buildings appear progressively as carpenters work, not instantly.
- Construction pauses during night, attacks or emergencies.
- Existing roads/buildings influence placement.
- Player structures and protected/obviously artificial areas should not be harvested or bulldozed.

### Outposts and satellite sites
Villages may establish small functional sites away from the core settlement:
- forester huts
- quarries
- fishing huts
- satellite farms
- grazing areas
- temporary work camps

These sites should remain linked to the parent settlement through logistics rather than becoming free resource generators.

### Roads and bridges
- New buildings should tend to receive paths connecting them to the settlement.
- Satellite sites may gradually gain roads.
- Terrain can create public-works jobs.
- Small rivers/gaps can trigger bridge construction.
- Roads/bridges consume real materials and should be built incrementally.

### Building recognition and occupancy
Villagers can recognize plausible player-built structures using lightweight heuristics such as:
- roof/cover
- usable interior space
- door/access
- bed or relevant workstation
- lighting
- path connectivity

Valid empty structures may become homes/workspaces without requiring a special claim block.

### Building culture
Village architecture can drift over time based on:
- biome
- locally available materials
- materials repeatedly supplied by the player
- established local building palette
- carpenter skill

A plains village repeatedly supplied with spruce and stone brick may gradually develop a visibly different architectural identity.

### Imperfect construction
Less experienced builders may make harmless aesthetic mistakes:
- asymmetric windows
- mixed roof materials
- missing decorative fence
- unusual door placement
- minor substitutions when exact materials run out

Construction mistakes must not make buildings unusable.

### Carpenter progression
Carpenters can gain practical experience:
- faster work
- less material waste
- access to more complex templates
- better repair behavior
- fewer cosmetic mistakes

### Adaptive plans
Village-level planning can reprioritize or revise construction when conditions change:
- housing shortage
- food shortage
- storage shortage
- fire damage
- population spike
- new outpost need

Avoid full procedural architecture editing in the first version; modular template stages are acceptable.

### Public works requests
Real village shortages/public works can generate requests visible to the player:
- deliver stone for a bridge
- supply lumber for housing
- restore food reserves
- bring materials for fire reconstruction

These are not arbitrary quests; they should originate from actual simulation needs.

### Refugees and migration
Villagers can relocate after severe local failure:
- repeated raids
- major fires
- food collapse
- loss of housing
- settlement destruction

Survivors may move to nearby villages, causing secondary housing/food pressure there.

### Village fission / new settlements
A mature or failing settlement may eventually send a small group to establish a new settlement elsewhere.
- Requires population and supplies.
- New group should physically travel where practical.
- New settlement begins small.
- Avoid uncontrolled exponential expansion via hard cooldowns/caps.

### Village relocation
If a location remains chronically nonviable, part of the population may abandon it rather than endlessly rebuilding.
This is a rare high-level outcome, not a frequent behavior.

### Villager breeding overhaul
Replace the purely bed/food-shaped feel with settlement-aware reproduction.

Candidate rules:
- couples/households are not required, but repeated proximity and shared home usage can influence pairing.
- reproduction rate considers food reserves, free beds, housing quality, recent disasters and village population pressure.
- severe shortages suppress births naturally.
- abundant food and stable housing allow gradual population growth.
- newborns should create real future resource demand rather than appearing as free population.
- population caps scale with available housing/infrastructure, not merely raw bed count.
- post-disaster recovery can temporarily increase willingness to repopulate once food/housing recover.
- avoid explicit genetic/eugenic mechanics; the feature is demographic simulation, not trait breeding.

### Forest regeneration
Forests can recover slowly without requiring every sapling to be manually placed.
- mature forest edges can very slowly seed nearby viable ground
- player-heavy clearcut areas recover over long timescales
- foresters accelerate and organize regeneration
- avoid rapid spreading or uncontrolled tree spam

### Rivers as infrastructure
Settlements can treat rivers as useful geography rather than only pathfinding obstacles:
- water source
- fishing area
- settlement boundary
- transport corridor
- bridge location
- possible later boat logistics

### Regional economy integration
Regional trade value, village logistics and autonomous growth should interact:
- scarce construction goods are worth more locally
- player imports can unblock construction
- surplus goods can support caravans later
- material flow should visibly affect village development

### Fire emergency integration
Major settlement fires can:
- trigger alarms
- interrupt normal work
- cause evacuation
- start firefighting behavior
- damage housing/storage capacity
- create reconstruction jobs
- deplete real material reserves

### Mob-use-of-buildings integration
Village and player-built spaces should support lightweight contextual use by mobs:
- shelter from rain
- gathering around campfires
- use of benches/tables heuristically
- preference for doors/bridges/covered routes
- occupancy of recognized interiors

Design constraint: this feature family should stop before becoming a full colony-management game. The player may influence villages through building, trade and supply, but should not need to micromanage schedules, worker assignment or production graphs.


## Accepted utility / interaction tweaks

### Expanded Fishing Rod
Treat the fishing rod as a lightweight remote-interaction tool rather than only a fishing item.
Planned uses may include:
- pulling dropped items
- tugging mobs
- retrieving thrown weapons
- interacting with selected simple world objects at range where sensible
- pulling dangerous or useful objects toward the player

Keep this physical and imperfect; it should not become a universal remote-control wand.

### Extinguish Primed Creepers
Allow a currently ignited creeper to be interrupted by a fast player action, such as hitting it with a water bottle or another explicit extinguishing interaction. The goal is a skillful emergency save, not a permanent creeper nerf.

### Temporary Ender Pearl Return Point
Allow an ender pearl to be placed/anchored temporarily instead of immediately thrown. A later action can consume or activate it to return to that point. The anchor expires and must remain limited enough that beds, lodestones and normal travel still matter.

### Firework Propulsion for Objects
Allow firework rockets to be attached to or used on selected entities/objects to create temporary uncontrolled propulsion.
Potential targets:
- boats
- dropped items
- small mobs
- TNT
- minecarts where safe enough

This feature should preserve a meaningful risk of bad outcomes rather than becoming precision transportation.


### High-Speed Minecarts and Collision Damage
Promote minecarts from mostly transportation objects into true momentum-based vehicles.

Planned behavior:
- Remove the normal artificial top-speed ceiling for minecarts.
- Final speed should emerge from powered rail input, slopes, friction and braking rather than a fixed vanilla-style cap.
- Collision damage / knockback scales with actual minecart speed.
- High-speed carts can become dangerous to mobs and players.
- Rail design, braking distance and track geometry therefore matter.
- Keep minecart contents/passengers intact where possible rather than treating high speed as automatic destruction.
- At extreme speed, prioritize safe handling of unloaded chunks and invalid collision states instead of silently clamping velocity.
- Configurable collision lethality and derail/crash behavior can be added separately; speed itself should not be arbitrarily capped by default.

Design constraint: preserve the fun of absurd engineering. Safety logic may prevent simulation corruption, but should not turn into another hidden speed limit.


### Blast / Slipstream Wind Pressure
Add short-lived wind-pressure impulses from high-energy events rather than a global weather simulation.

Potential sources:
- large explosions
- extremely fast minecarts
- dragon wing beats / large flying entities
- selected high-speed projectiles or machinery later

Effects:
- push dropped items and lightweight entities
- stronger impulses on small mobs, weaker on large/heavy mobs
- players can be displaced but should retain meaningful control
- nearby loose decorations may react where appropriate
- magnitude falls off strongly with distance and obstruction

### Wind Pressure Resistance Enchantment
Add an armor enchantment that reduces forced displacement from wind-pressure impulses.
- stacks across armor pieces with diminishing returns
- does not reduce ordinary melee knockback unless explicitly configured
- does not grant full immunity at normal levels
- intended for high-speed rail work, explosive engineering and dangerous environments

Design constraint: wind pressure should create readable physical consequences without becoming a constant annoyance or replacing vanilla knockback rules.


## Accepted enchantment-system tweaks

### Growing Enchantments
Enchantments can accumulate their own use history separately from the item's ordinary growth level.

Core direction:
- Each enchantment on an item can gain hidden or visible mastery through relevant use.
- Mastery should usually improve behavior quality, consistency, or unlock a side-grade rather than simply increasing the vanilla enchantment level forever.
- A heavily used enchantment may develop a small specialization based on how it was used.
- Moving/replacing the item should not trivially duplicate mastery.
- Vanilla enchanting remains useful; this system extends enchantments after acquisition instead of replacing enchanting tables/books/anvils.
- Growth pace must be slow enough that a fresh enchantment and a veteran enchantment feel different without making early enchant rolls worthless.

Examples:
- Unbreaking mastery slightly improves its chance distribution.
- Efficiency mastery may reduce the penalty on difficult blocks rather than raw speed stacking forever.
- Feather Falling mastery may improve recovery after very large falls.
- Loyalty mastery may return thrown weapons along a cleaner/safer trajectory.
- Mending mastery may waste less XP when only tiny repairs are needed.

Design constraint: enchantment growth should create attachment and specialization, not infinite vertical power scaling.


### Enchantment Growth Branches
At major mastery milestones, selected enchantments can specialize into side-grade branches rather than only increasing their vanilla level.
Examples include Feather Falling becoming safer landing, impact landing, or aerial recovery; Fortune becoming ore-, crop-, or high-variance-focused.
Branches should change play style more than raw DPS/mining output.

### Curse Growth
Curses also accumulate mastery/history and may mutate through long-term use.
The curse remains a meaningful drawback, but veteran cursed gear can develop unusual compensating behavior instead of remaining pure trash.
Examples may include Binding becoming harder to lose on death, or Vanishing evolving into a delayed-return behavior.

### Mutually Exclusive Enchantment Switching
Permit selected normally-exclusive enchantments to coexist on one item while only one is active at a time.
Example: Fortune and Silk Touch can both be stored, but only the selected mode applies.
Switching may require XP, cooldown, anvil work, or another explicit cost so one item does not become a free universal solution.

### Enchantment Mastery Inheritance
Retiring/sacrificing veteran enchanted gear can transfer only part of an enchantment's mastery/history to a replacement.
The enchantment itself and the mastery are separate resources: inheritance should preserve attachment without making gear upgrades free.

### Uncapped Anvil Experience Cost
Remove the hard anvil experience ceiling / "Too Expensive!" rejection for normal survival use.
- High-cost operations remain expensive.
- Prior-work and enchantment combination costs may continue to scale.
- If the player actually has the required levels, the operation should be allowed.
- This is required for high-mastery enchantment transfer, switching and late-game item history systems.
- Any separate anti-abuse limits should be explicit configuration, not a hidden vanilla-style hard stop.

Design constraint: anvil changes should remove arbitrary rejection, not make merging/repairing cheap.
