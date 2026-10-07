# AsobibaTweaks idea pool

Rule: small features, independently switchable, and no feature may become a hard dependency for another feature.

> Implementation status: accepted candidates have MVP code paths. See `asobiba-tweaks/IMPLEMENTATION_STATUS.md` for the code mapping and validation state.

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


### Villager Welfare and Confinement

Villagers track a lightweight persistent welfare state derived from their actual living conditions over time.

Accepted direction:
- do not use a crude room-size or single-block "trading hall" detector
- each villager has a persistent **Welfare score from 0 to 100**
- welfare is based on observed living-condition history rather than on one instantaneous enclosure check
- welfare degrades gradually when a villager is chronically unable to move, sleep, reach a workstation, access reasonable open space, or participate in normal village life
- short-term confinement, transport, emergencies, work shifts and temporary pathfinding failures should not immediately penalize the player
- good living conditions recover welfare gradually
- the initial welfare bands are:
  - **80-100: Good** — no welfare trade penalty
  - **60-79: Normal** — no welfare trade penalty
  - **40-59: Strained** — approximately **+10% trade price**
  - **20-39: Poor** — approximately **+25% trade price** plus visible mild weakness/exhaustion-like feedback
  - **0-19: Severe** — approximately **+50% trade price** plus stronger visible weakness/exhaustion-like feedback
- the welfare score should be driven by several independent life-history signals rather than any one requirement:
  - whether the villager has actually been able to move through a reasonable local area
  - whether it has successfully slept during normal sleep opportunities
  - whether it can reach/use its workstation during work periods
  - whether it periodically reaches open or meaningfully non-confined space
  - whether it can participate in ordinary village/social activity with other villagers
- one failed signal does not immediately make a villager unhealthy; persistent failure across Minecraft days is what matters
- normal transport in boats/minecarts, temporary holding cells, raids, fire evacuation, brief construction blockage and transient pathfinding failure must remain effectively penalty-free
- meaningful welfare decline should require roughly **one or more Minecraft days** of sustained poor conditions, with deeper penalties requiring several days rather than minutes
- welfare recovery is also gradual so briefly releasing a chronically confined villager does not instantly erase long-term neglect
- severe long-term neglect may raise prices sharply enough that maintaining healthy villagers is economically preferable to permanent one-block imprisonment
- welfare penalties apply per villager and persist across reloads
- the system should remain compatible with autonomous village housing, work, migration and emergency behavior
- percentage thresholds and timing values are initial tuning defaults and may be adjusted after playtesting without changing the welfare model
- special trade-only progression materials such as the Arcane Bookshelf material participate in the same welfare-adjusted pricing


Additional anti-trading-hall rules:
- welfare evaluation uses a weighted life-history model rather than a room-size detector
- initial weighting target:
  - **Mobility / usable local movement: 30%**
  - **Sleep access and successful sleep: 20%**
  - **Workstation access/use: 20%**
  - **Open-space / non-confined access: 15%**
  - **Social/village participation: 15%**
- a villager can miss one category temporarily without severe consequences, but chronic failure in several categories drives welfare down reliably
- ordinary compact houses remain valid as long as the villager can actually leave its sleeping/work position, move around, reach required points and participate in village life
- permanent 1x1 / 1x2 immobilized cells, workstation cages and equivalent layouts are expected to fail Mobility, Open-space and Social participation over time even if bed/workstation reachability is technically present
- after sustained severe confinement, the villager enters a **Refusal** state once Welfare is below **20**
- while in Refusal, the villager **will not restock trades and will not open normal trading interaction**
- Refusal clears only after Welfare recovers to at least **40**, preventing brief release/reset exploits
- existing offers and villager profession data are retained while refusing; this is not a profession reset or trade deletion
- welfare recovery requires actual successful life activity over time, not merely opening a door or enlarging the cell for a few seconds
- moving a villager through transport or temporarily sheltering it during danger does not count as chronic confinement because the system evaluates history across Minecraft days
- layouts that function as a normal village marketplace are allowed: villagers may work at assigned stalls during the day provided they can leave them, sleep normally, move through shared spaces and participate in village life
- the design goal is specifically to make **permanently immobilized trading halls non-viable**, not to ban organized trading districts or compact villages

Design constraint: discourage permanent immobilized trading halls without punishing normal houses, compact villages, temporary containment, transport or emergency shelter.

### Fire as a Village Emergency
Large fires in or near settlements become an event. Villagers, golems and bonded helpers can flee, alert others, move valuables and attempt simple firefighting with nearby water or available containers. Fire should become a local incident rather than passive background destruction.

Accepted initial behavior:
- a single isolated fire block does not trigger a village-wide emergency
- the initial event threshold is roughly **3-4 active fire blocks** within the village or near its boundary that persist for a short continuous window rather than disappearing immediately
- once the threshold is met, nearby villagers temporarily suspend ordinary routines and enter fire-emergency behavior
- children, unemployed/non-combat villagers and other vulnerable villagers prioritize evacuation toward recognized safe village space
- Iron Golems and suitable bonded helpers may assist with evacuation / path clearing rather than treating fire itself as an enemy
- Carpenter villagers may participate in containment, simple firefighting and later structural repair
- firefighting should consume available village resources where appropriate, such as nearby water access or stored filled containers, rather than spawning free resources
- after the fire ends, damaged recognized village structures may generate repair work that consumes stored construction materials
- the exact persistence window and 3-vs-4 fire threshold are initial tuning values; the event should ignore trivial sparks while reacting quickly to a genuine spreading fire

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
- Quarry worker: gathers stone from bounded/recognized quarry areas instead of free-form underground strip mining. Village quarrying is intentionally shallow: autonomous workers should normally remain at **Y >= 0** and must not dig into negative-Y deep-slate/deep-cave layers.
- Porter: moves resources between farms, quarries, forests, storage and build sites; later may use llamas/donkeys.
- Fire responder role: maintains access to water and prioritizes emergency response when fires occur.

### Village activity boundary

Accepted direction:
- each village uses a **dynamic activity boundary** rather than one permanently fixed spherical radius
- the village center is derived from the local concentration of recognized village anchors such as bells, occupied beds, active workstations and shared storage
- the initial ordinary village activity radius is approximately **48 blocks**
- the boundary may expand gradually in directions where recognized homes, workplaces, farms, roads and other continuously used village infrastructure already exist
- isolated distant structures are not immediately absorbed into the main village simply because a villager can path to them
- distant functional sites become Outposts / Satellite Sites once they are linked to the parent settlement through recognized roads/logistics
- the ordinary village core should normally stop expanding at roughly **128 blocks from its effective center**; activity beyond that is handled as a linked satellite site rather than unlimited core growth
- player-built structures are not automatically treated as village property merely because they fall inside the boundary
- harvesting, construction placement, welfare context and logistics use this activity boundary as a common spatial reference so village AI does not expand or gather without limit
- the boundary may be asymmetric and follow actual settlement growth rather than remaining a perfect circle

### Autonomous village growth
- Villages gather real local/renewable materials.
- Gathered resources enter actual village storage.
- Construction consumes stored resources.
- Growth is gated by population, beds, food, resources, available land and long cooldowns.
- Buildings appear progressively as carpenters work, not instantly.
- Construction pauses during night, attacks or emergencies.
- Existing roads/buildings influence placement.
- Player structures and protected/obviously artificial areas should not be harvested or bulldozed.

### Village shared storage and logistics

Accepted direction:
- village resources are backed by **real item containers** rather than an abstract infinite resource counter
- recognized village storage uses actual Chests, Barrels and other explicitly supported container blocks
- the contents of those containers are the source of truth for village resources
- a lightweight **Village Resource Ledger** may cache totals for planner performance, but it must be reconciled against real container contents
- villagers physically deposit gathered resources into recognized storage and physically withdraw materials for construction, repair and other work
- player-added items immediately become usable village resources once placed into recognized village storage
- player-removed items are genuinely gone from village supply; there is no hidden replacement inventory
- initial logical storage categories may include:
  - Food
  - Construction
  - General
  - Emergency
- category-specific storage is optional; General storage remains a valid fallback so villages do not require a rigid warehouse-management minigame
- Emergency storage is preferred for firefighting / disaster-response supplies when available
- construction and repair jobs reserve required materials in the village ledger before work starts so multiple jobs do not simultaneously claim the same physical stock
- reserved items remain physically present until withdrawn, but other village jobs treat the reserved quantity as unavailable
- reservations are reduced as materials are actually collected and are released if the associated job is cancelled
- when recognized storage approaches practical capacity limits, the village may create a storage-expansion need:
  1. add storage to a suitable existing storage building
  2. expand an existing warehouse/storage structure
  3. build a new storage building
- Outposts and Satellite Sites may maintain small local storage
- resources gathered at remote sites must be transported into the parent village logistics network rather than teleporting directly into the central stockpile
- Porters move goods between farms, forests, quarries, satellite storage, village storage and active work sites
- later transport upgrades may use donkeys, llamas or other suitable pack animals without changing the underlying physical-resource model
- storage is not a claim/protection system: players may use, remove, add or destroy recognized village containers normally, and the simulation reacts to the resulting real inventory state

Design constraint: real containers are authoritative; the ledger exists for efficient planning, reservations and visibility, never as a hidden source of free materials.

### Resource-site assignment and bounded gathering

Accepted direction:
- autonomous gathering is **site-based** rather than free-form resource chasing
- the village planner first designates a recognized work site, then assigns suitable workers to that site
- workers may gather only inside their assigned site's boundary
- workers do not continue following a resource vein/tree line/crop patch beyond the assigned boundary
- if a site becomes depleted or unsuitable, workers stop and the planner must approve a replacement or new site
- gathering is demand-driven: when the relevant village stockpile is at or above its target reserve, ordinary gathering for that resource pauses
- player structures, recognized roads, occupied buildings and clearly artificial/protected-use areas are excluded from autonomous harvesting
- remote sites may become linked Outposts / Satellite Sites and use the established logistics system rather than teleporting resources

#### Forestry sites
- Foresters operate only inside recognized **Forestry Sites**
- an initial Forestry Site should usually cover roughly a **24-32 block radius**
- normal tree logs are the main target
- leaves are normally left to natural decay unless a specific cleanup action is needed
- after harvesting, Foresters replant a compatible/same-family sapling whenever practical
- the site should retain enough standing trees and/or planted saplings to avoid deliberate clear-cutting
- the same patch is not harvested continuously without allowing meaningful regrowth
- logs that appear to be part of player/village structures, roofs, pillars, bridges or other artificial construction are not harvested
- unusually complex/giant trees may be skipped if safe complete harvesting cannot be performed without leaving severe floating remnants
- Forestry Sites are intended to behave as renewable managed woodland rather than disposable forest removal zones

#### Quarry sites
- Quarry workers operate only inside recognized **Quarry Sites**
- sites prefer exposed stone, cliffs, hillsides and shallow stone deposits
- autonomous quarrying remains at **Y >= 0**
- ordinary quarry depth should stay roughly **8-16 blocks below the site's initial working surface**, while still respecting the Y>=0 hard floor
- workers do not follow natural caves, ravines or ore veins beyond the Quarry Site boundary
- quarrying does not intentionally tunnel beneath recognized homes, roads or village infrastructure
- major uncontrolled water/lava ingress causes the affected work face to be suspended rather than blindly excavated through
- the primary purpose is construction material such as stone/cobblestone and related common blocks
- coal, iron or other useful ore exposed naturally inside the approved quarry may be collected as a byproduct
- workers do not deepen or extend the quarry specifically to pursue ore

#### Village farms
- Farmers harvest only recognized **Village Farm** areas
- mature crops are harvested and normally replanted with the same crop
- required seeds/planting items may be drawn from village storage when available
- crop mix may gradually respond to actual village food/resource demand rather than remaining permanently fixed
- arbitrary nearby player farms are not harvested
- a player-built farm may later be adopted as a Village Farm only when it lies within village use context and has been intentionally/consistently used as village agricultural infrastructure
- temporary crop shortages do not authorize farmers to harvest outside recognized farm boundaries

Design constraint: workers gather from places the settlement has explicitly decided to use, not from every reachable resource in the loaded world.

### Outpost creation and lifecycle

Accepted direction:
- Outposts / Satellite Sites are created only for **persistent remote work needs**, not merely because a resource happens to exist outside the village core
- suitable candidates include approved Forestry, Quarry, Farm, Fishing or similar work sites that are expected to remain useful for multiple Minecraft days
- an Outpost requires:
  - an actual village resource/work demand
  - a recognized remote work site
  - a safe practical route back to the parent village
  - enough real stored construction/maintenance resources
  - expected sustained use rather than one-off gathering
- distance guidance:
  - up to roughly **96 blocks** from the effective village center: ordinary commuting is preferred where practical
  - roughly **96-192 blocks**: a small lodging/logistics Outpost becomes a normal option
  - beyond roughly **192 blocks**: establishment should be uncommon and require stronger sustained value/logistics justification
- an Outpost begins small and purpose-built rather than as a second full village
- an initial Outpost may contain:
  - one small work/rest building
  - small local storage
  - 1-2 beds where overnight work is justified
  - the required profession/work equipment
  - lighting/basic safety
  - a recognized route/road link to the parent settlement
- workers commute when distance allows; only the number of workers actually needed for the site should stay overnight or operate from the Outpost
- Outposts remain explicitly linked to a **parent village**
- ordinary Outposts do not independently:
  - create unlimited new housing
  - run unrestricted population growth
  - create further Outposts on their own
  - behave as free independent resource generators
- their normal functions are remote work, temporary worker accommodation, local buffering/storage and logistics back to the parent village
- continued use may grow a work site from a minimal shelter into a more established Outpost, but major permanent population growth requires a separate **Satellite Settlement / settlement-fission** decision rather than silent Outpost expansion
- when the underlying resource demand disappears or the site becomes depleted/nonviable, the Outpost may enter an inactive/abandoned state
- on shutdown, workers return to the parent village and logistics stop
- recoverable stored resources may be transported back to the parent village when practical
- abandoned Outpost buildings normally remain physically in the world as settlement history rather than being automatically deleted

Design constraint: Outposts extend a village's working reach without becoming uncontrolled self-replicating villages.


### Roads and bridges
Accepted direction:
- roads are created from **actual movement/logistics demand**, not by connecting every structure immediately
- important path nodes include village center/bell, housing clusters, workplaces, shared storage, farms, resource sites, satellite sites and existing recognized road junctions
- the village planner uses a road-building cost map rather than straight-line placement
- preferred terrain order is roughly: **existing road -> flat ground -> gentle slope -> minor grading -> steep slope -> water crossing -> major excavation**
- routes should bend around difficult terrain when that is cheaper and more natural than forcing a direct line
- ordinary village paths are usually **1-2 blocks wide**
- primary village roads are normally **2 blocks wide**
- heavily used logistics routes may later widen toward **3 blocks** when justified by traffic
- road materials follow biome/local building palette and available resources
- roads may mature over time, for example **dirt path -> gravel -> stone/cobblestone paving**, with every upgrade consuming real materials
- road construction and upgrades are performed progressively by Carpenter/public-works jobs rather than appearing instantly
- existing player-built paths/bridges that are recognized as usable infrastructure should be preferred and integrated instead of duplicated or overwritten

Traffic / demand behavior:
- one incidental traversal does not create a road
- repeated villager movement, frequent Porter routes, new occupied buildings and active satellite logistics increase route demand
- once demand crosses the planning threshold, the route becomes a public-works candidate
- road quality may improve as sustained traffic increases
- abandoned/rarely used routes do not need continual upgrading

Bridge decisions:
- bridges are considered only when a planned route encounters water, ravines, gaps or similar obstacles
- the planner compares the bridge cost against the practical detour cost
- relatively short crossings, initially around **2-12 blocks**, are suitable bridge candidates when a detour would be materially longer
- if a short safe detour exists, the planner should prefer the detour rather than constructing an unnecessary bridge
- initial bridge families may include:
  - simple wooden bridge for minor crossings
  - standard wood/stone bridge for normal village roads
  - more substantial stone bridge for mature/high-traffic settlements
- bridge width should normally match the road it serves
- bridge construction is phased, such as supports/piers where required -> deck -> railings -> road connection
- bridges consume real stored materials and are physically built by Carpenter/public-works workers
- bridge placement must validate safe foundations/support positions and avoid obviously impossible spans

Elevation handling:
- minor height changes use normal path blocks/terrain adaptation
- moderate slopes may use stairs and short graded sections
- steep slopes should prefer switchbacks or alternate routing
- cliffs or terrain requiring excessive excavation should usually cause rerouting instead of forced construction

Design constraint: roads should emerge because the settlement actually uses a route, and bridges should exist because they solve a real movement problem rather than as decorative automatic generation.


### Workstation placement and building function

Accepted direction:
- workstation placement is driven by **building function first**, not by placing job-site blocks into arbitrary empty cells
- the planning order is:
  1. village planner determines which profession / function is needed
  2. building planner chooses reuse, expansion or a suitable building type
  3. the building template exposes semantic placement anchors
  4. a placement validator confirms that the chosen workstation position is actually usable by villagers
- building templates may define semantic anchors such as:
  - `WORKSTATION_PRIMARY`
  - `WORKSTATION_SECONDARY`
  - `BED`
  - `STORAGE`
  - `DOOR`
  - `WINDOW`
  - `DECORATION`
- the actual workstation block placed into a workstation anchor depends on the profession/function selected for that building
- workstation anchors should prefer positions that are indoors, have valid floor/headroom, leave a usable standing position in front of the block, remain path-reachable from the building entrance and do not obstruct doors, stairs or major circulation paths
- invalid placements such as doorways, stair traffic cells, unsafe drops, submerged positions or unreachable interaction faces are rejected
- existing recognized/player-built structures may receive workstations later if a valid semantic/use position can be found without damaging the structure
- retrofit candidate positions are scored by shelter, floor/headroom, path reachability, circulation safety and compatibility with nearby related facilities
- buildings have practical workstation-capacity limits; the system should prefer several plausible workplaces over packing arbitrarily many identical job-site blocks into one room
- related professions may share a larger functional building when appropriate, such as multiple smithing professions in one smithy
- large numbers of the same profession should be distributed across suitable buildings rather than creating dense workstation rows
- multi-story mixed-use buildings are valid:
  - ground floor may serve as shop/workspace
  - upper floors may serve as bedrooms, storage or secondary work/living space
- workstation/home proximity is allowed and often desirable, but villagers must still be able to leave the building and participate in ordinary village movement/social life for welfare purposes
- a workstation does not count as valid village capacity until its pathing and interaction-space validation succeeds

Design constraint: decide what a building is for before deciding exactly where its workstation block goes.

### Building recognition and occupancy

Accepted direction:
- building recognition uses **lightweight functional heuristics**, not a strict sealed-room flood fill and not a special claim block
- the system asks whether a structure contains a stable, reachable, sheltered space that villagers can actually use
- recognition is limited to structures within the village activity context or directly connected to recognized village roads / sites; the village does not scan the entire loaded world for buildings
- candidate structures are evaluated when relevant blocks change and through infrequent background validation rather than expensive full-volume scans every tick

Core recognition signals:
- meaningful roof / weather cover over the usable area
- walkable interior floor area
- at least one usable entrance / access route
- sufficient headroom for villager navigation
- safe path connectivity from the village road / local circulation network
- basic lighting / absence of persistently dangerous darkness where practical
- absence of obvious hazards such as open lava, unavoidable deep drops or blocked entrances
- semantic contents such as beds, workstations, storage, seating/common-space features or other recognized functional anchors
- one signal alone is insufficient; the classifier combines several signals into a practical usability score

Interior / usable-space rules:
- a building does **not** need to be perfectly airtight or geometrically rectangular
- porches, open workshops, market stalls with roofs and partially open structures may still count when they provide a safe usable work/shelter space
- caves, overhangs or raw terrain are not automatically buildings merely because they are covered
- tiny decorative boxes and inaccessible sealed rooms do not count as usable buildings
- multi-story structures are evaluated by reachable floor regions; upper floors count only when stairs/ladders/approved access actually connect them
- separate connected rooms may belong to one building when they share practical circulation and one coherent exterior footprint

Initial functional classification:
- **Residential**: usable beds/home space dominate the function
- **Workshop / Profession Building**: one or more valid workstations plus usable worker standing/path space
- **Storage**: recognized village containers and practical loading/access space dominate
- **Public / Common Building**: sheltered shared space, bell/common facilities, meeting/seating-type use or other public anchors
- **Mixed-use**: multiple strong functions coexist, such as shop/workshop below and residence above
- **Generic Shelter / Unassigned**: structurally usable but lacking enough semantic anchors for a stronger classification
- classification may change later when beds, workstations, storage or other functional blocks are added/removed

Occupancy:
- recognized capacity is based on **usable reachable spaces**, not raw block counts
- beds/workstations that cannot be path-reached do not contribute capacity
- a Residential building contributes only beds and home spaces that pass navigation/safety checks
- a Workshop contributes only workstations with a valid interaction position
- occupancy assignments prefer nearby available buildings before creating unnecessary new construction
- villagers may share larger buildings where the template/recognized space has enough actual capacity
- overcrowding beyond validated capacity is discouraged and feeds into the existing housing/welfare systems

Player-built structures:
- valid player-built structures may be recognized and used without requiring a claim/registration block
- recognition does **not** transfer ownership, lock the structure, protect it, or prevent the player from editing it
- ordinary recognition is non-destructive: villagers may occupy/use valid anchors, but do not demolish or rewrite arbitrary player construction merely because it was recognized
- an empty player-built house inside the village may therefore become housing if it has valid beds/access
- a player-built warehouse may become recognized storage if its containers are intentionally integrated into village use
- a player-built workshop may be adopted if its workstation is reachable and compatible
- later non-destructive retrofit may add explicitly approved workstation/storage/decorative elements only to validated free anchor positions; existing player blocks are not blindly replaced
- if player edits make a structure unusable, its capacity/classification is revalidated and may be reduced or removed without deleting the physical building

Structure identity / persistence:
- once recognized, a building receives a lightweight persistent structure record containing its footprint/bounds, entrances, usable floors, functional anchors, classification and current validation state
- the record is a cache/reference for simulation; the physical world remains authoritative
- significant edits trigger local revalidation rather than rebuilding the entire village model
- destroyed or heavily damaged structures become Invalid/Damaged and may generate repair demand if they are village-owned/planned infrastructure
- merely recognized player buildings are not automatically scheduled for reconstruction after the player intentionally changes/removes them

Design constraint: villagers should understand and use plausible spaces built by either the game or the player, while recognition remains cheap, non-destructive and grounded in actual navigability rather than ownership flags or perfect-room geometry.

### Building culture
Village architecture can drift over time based on:
- biome
- locally available materials
- materials repeatedly supplied by the player
- established local building palette
- carpenter skill

A plains village repeatedly supplied with spruce and stone brick may gradually develop a visibly different architectural identity.

### Housing demand and new-house decisions

Accepted direction:
- village housing construction is driven by a **housing-pressure score** rather than by raw bed count alone
- the planner reevaluates housing demand periodically, not every tick; an initial cadence of roughly **once per Minecraft day** is sufficient
- housing pressure considers:
  - current population versus recognized usable sleeping capacity
  - number of genuinely free beds / usable home spaces
  - recent and expected population growth
  - villagers repeatedly failing to secure normal sleeping/home access
  - welfare pressure caused specifically by overcrowding or inadequate housing
  - homes lost or made unusable by fire, raids or other damage
- a village should normally maintain a small reserve rather than waiting for every bed to be occupied
- initial target reserve is approximately **15-25% spare usable housing capacity**, with a practical minimum of about **2 spare villager spaces** for established villages
- housing construction becomes a normal candidate when usable housing capacity falls below roughly **110% of current population**
- it becomes high priority when capacity is at or below current population, or when multiple villagers repeatedly fail to sleep because no valid home space is available
- one transient bad night, temporary bed obstruction or visiting/moving villager does not immediately create a construction job
- new construction requires sufficient stored food stability and required building materials; the planner does not create blocks or ignore a food crisis merely to satisfy the housing target
- after completing a normal house, the village waits at least about **2-3 Minecraft days** before starting another discretionary housing expansion unless there is an acute housing loss/emergency
- emergency replacement after fire/destruction may bypass the ordinary housing-growth cooldown
- before creating an entirely new detached building, the planner may choose among:
  1. repair/reoccupy an existing recognized but damaged/unused home
  2. expand a suitable existing structure
  3. add an upper floor where the template/building supports it
  4. construct a new detached house
- repair/reuse is preferred when it is materially cheaper and still produces valid housing
- vertical expansion becomes more attractive when suitable road-adjacent land is scarce or the village's established architecture favors multi-story construction
- detached new construction is preferred when land is available and vertical expansion would make navigation or architecture awkward
- a new house is not considered complete housing capacity until its access, interior navigation, required beds and basic safety checks pass
- unfinished construction does not count toward population capacity
- the planner should avoid speculative overbuilding: housing projects are tied to real current/near-term demand rather than endlessly increasing spare capacity
- abandoned or chronically unused houses may remain part of the architectural village but do not count as fully usable housing unless pathing and occupancy checks still pass

Initial priority model:
- **Acute shortage:** no spare usable capacity / villagers cannot sleep -> housing priority very high
- **Growing pressure:** reserve below target and population/resources are stable -> normal housing project candidate
- **Healthy reserve:** reserve at or above target -> no new housing project
- **Oversupply:** substantially more housing than expected demand -> suppress housing expansion and prefer other public works

Design constraint: villages should build homes because people actually need them, while keeping a small believable reserve and avoiding bed-count-driven construction spam.

### Multi-story village buildings

Accepted direction:
- village construction is not limited to single-story templates
- the building template pool may include **two-story houses, workshops and mixed-use structures**
- vertical construction becomes more likely as the village matures, land near existing roads becomes constrained, or the local building culture already contains taller structures
- multi-story buildings must remain fully navigable by villagers: stairs, doors, headroom, beds/workstations and path access must be validated before the structure is considered usable
- upper floors may contain bedrooms, storage or secondary work/living space while the ground floor remains accessible from the village road/path network
- builders construct upper stories progressively rather than spawning a completed multi-floor structure at once
- multi-story templates still consume real stored materials and may use safe scaffolding/work positions during construction
- early villages should prefer simpler one-story structures; experienced carpenters and mature settlements may unlock more complex vertical templates
- do not require every village to become vertically dense; biome, available land, local material palette and established architecture influence whether the village grows outward or upward

### Imperfect construction
Less experienced builders may make harmless aesthetic mistakes:
- asymmetric windows
- mixed roof materials
- missing decorative fence
- unusual door placement
- minor substitutions when exact materials run out

Construction mistakes must not make buildings unusable.

### Progressive village construction execution

Accepted direction:
- village buildings are **not spawned instantly as completed structures**
- the village planner selects a building need/type and placement, then converts the selected template into an ordered construction plan
- Carpenter villagers execute that plan by physically transporting and placing real blocks
- building templates are modular/semantic plans rather than a single opaque paste operation; they may define foundation, walls, floors, roof, stairs, doors, windows, beds, storage, workstations and decorative anchors
- templates may support rotation, mirroring and approved material substitutions based on local village palette/resources without becoming unrestricted procedural architecture
- before construction starts, the site is validated for terrain, water, cliffs, existing structures, roads, player-built areas and unsafe voids/cavities
- small terrain differences may be handled with limited excavation, fill, foundations or support pillars; village AI must not perform large-scale terrain flattening merely to force a template to fit
- construction proceeds in explicit phases, for example:
  1. site preparation
  2. foundation
  3. structural frame / ground floor
  4. walls
  5. upper floors where applicable
  6. stairs / internal access
  7. roof
  8. doors / windows
  9. beds / workstations / storage
  10. decoration
  11. final validation
- Carpenter villagers withdraw reserved materials from real village storage, carry a bounded work inventory and place blocks only from reachable/safe work positions
- upper-story and roof work may use temporary Scaffolding or another explicitly allowed temporary construction aid; temporary construction blocks are removed/recovered after the relevant phase
- multiple Carpenters may cooperate on one larger project by claiming independent work units / placement tasks so they do not fight over the same block positions
- material shortage pauses the affected construction phase rather than spawning replacement materials
- incomplete buildings remain visibly incomplete until missing materials arrive and work resumes
- raids, fire emergencies, night/danger states, loss of the assigned Carpenter, unsafe terrain changes or player edits may pause construction
- when the world has changed since the plan was created, the site/remaining work is revalidated before continuing
- player-placed blocks are not blindly overwritten; conflicting changes may cause local replanning or project cancellation
- a building is not registered as usable housing/workspace merely because its visual shell is complete
- final validation must confirm usable entrances, navigation between required floors, reachable beds/workstations, adequate headroom and absence of obvious unsafe gaps before the structure contributes functional village capacity
- if final validation fails, the building remains incomplete/invalid and may generate repair/rework tasks
- the execution layer is intentionally separate from village strategy: the planner decides **what/where** to build, while Carpenter AI handles **how to carry out the approved construction plan**

Design constraint: templates describe intended structures, but the visible world change should come from villagers actually building them with real resources over time.

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

Accepted direction:
- an Outpost does not become an independent settlement merely because it grows physically; independence requires an explicit village-level **fission / founding decision**
- normal Satellite Settlement candidacy requires roughly:
  - parent-village distance of about **192+ blocks**
  - at least **7 Minecraft days** of stable Outpost operation
  - a sustained need for roughly **4+ resident/regular workers**
  - at least **6 usable housing spaces**
  - about **3 days of food reserve**
  - independent shared storage
  - minimum viable food/water/living infrastructure
  - a safe recognized road/logistics connection
  - no recent major collapse such as severe fire, raid loss or food failure
- meeting the threshold creates a founding candidate rather than an instant new village
- the parent village physically allocates a founding group, initially around **4-6 villagers**, plus real food, beds, construction materials and required profession equipment
- the group must physically establish a minimum viable settlement; failure through losses, missing resources or invalid infrastructure may abort the founding attempt
- a new Village ID is created only after the founding site successfully validates housing, storage, food support and required work access
- once independent, the settlement has its own population, housing pressure, welfare, storage ledger and construction planning while retaining roads/trade/logistics relationships with the parent
- the former Outpost may remain recorded as the new settlement's founding site/history
- ordinary fission is restricted to mature settlements, initially around **12-16+ population**, and is blocked while the parent village itself has serious food/housing instability
- a parent village has roughly a **30 Minecraft day** cooldown after successfully founding a new settlement
- a newly founded settlement should itself wait roughly **30 Minecraft days** before becoming eligible to found another settlement
- newly founded independent villages should normally be separated by at least roughly **256 blocks**, unless terrain/history provides a strong exceptional reason
- these limits exist to prevent exponential self-replication

Emergency founding:
- a second path exists for **Refugee Settlement** formation after severe repeated raids, major fire, housing destruction, food collapse or comparable long-term failure
- refugee founding may relax some normal prosperity requirements when survival requires relocation
- an existing stable Outpost is the preferred emergency destination when available
- emergency founding still requires real people/resources and may fail; it is not a free teleport/rebuild mechanic


### Village relocation
If a location remains chronically nonviable, part of the population may abandon it rather than endlessly rebuilding.
This is a rare high-level outcome, not a frequent behavior.

### Village merge / district integration

Accepted direction:
- two villages may merge when their lived settlement networks have effectively become one community
- geographic proximity alone is **not** sufficient
- merge candidacy considers sustained evidence such as:
  - overlapping/continuous occupied building areas
  - villagers routinely crossing the old boundary for work, sleep or social activity
  - regular Porter/resource logistics between both settlements
  - connected recognized road infrastructure
  - several Minecraft days to roughly a week of stable integration rather than temporary disaster/evacuation overlap
- neighboring villages may remain separate indefinitely if they trade/connect but still function as distinct settlements
- a merge does not delete one physical settlement or force a single geometric center
- after merging, the result uses **one Village ID with multiple district/sub-centers**
- former bells/centers may remain recognized as district centers
- existing local storage remains physically distributed; the unified planner may view total resources while logistics still prefer nearby storage and account for transport distance
- housing, population pressure, public works and high-level planning may be evaluated village-wide, while local district demand remains spatially aware
- architectural/building-culture history from both former villages may continue to influence their respective districts rather than being immediately homogenized
- a small declining village may be absorbed by a nearby larger village when sustained daily integration makes independent planning meaningless
- a former parent village and its previously independent Satellite Settlement may later merge again if development physically/socially connects them
- temporary refugee presence, one shared road or occasional trade is not sufficient to force a merge
- the model should preserve the possibility of later re-fission if a very large merged settlement develops weakly connected districts with little shared logistics/social activity

Design constraint: settlement identity follows persistent lived/logistical integration, not just radius overlap.


### Villager breeding overhaul
Replace the purely bed/food-shaped feel with settlement-aware reproduction.

Accepted direction:
- each village maintains a lightweight **Population Pressure / sustainable-population estimate**
- reproduction is evaluated periodically, initially about **once per Minecraft day**, rather than continuously
- reproduction considers:
  - usable housing capacity
  - available/free home space
  - real village food reserves and expected food production
  - average villager Welfare
  - recent fires, raids and other major disasters
  - infrastructure/logistics capacity
  - current population relative to estimated sustainable population
- population capacity is **not equal to raw bed count**
- the effective sustainable population is constrained by the weakest major support factor among housing, food supply and infrastructure/logistics
- adding large numbers of beds alone therefore cannot force unlimited population growth
- initial reproduction eligibility target:
  - village average Welfare around **60+**
  - at least **2 usable spare housing spaces**
  - roughly **3 Minecraft days of food reserve**
  - current population below about **90% of estimated sustainable population**
- meeting these thresholds makes reproduction possible rather than guaranteed; healthier surplus conditions increase the chance/rate
- severe food shortage, overcrowding, poor Welfare or unresolved disaster damage strongly suppresses reproduction
- villages use a **settlement-wide birth cooldown / rate limiter** so population cannot spike through many simultaneous breeding events
- small settlements should normally grow on the order of one child every several Minecraft days under healthy conditions rather than multiplying rapidly
- larger settlements may sustain somewhat more births, but the rate still scales conservatively with real support capacity
- newborn villagers immediately count as real future demand:
  - they consume food
  - require eventual housing
  - contribute to welfare/infrastructure load
  - later create profession/work demand when they mature
- explicit permanent spouse/family simulation is not required
- repeated proximity and shared-home usage may form lightweight household affinity that helps choose home/social behavior, but it does not create genetics or mandatory family trees
- after major population loss, a temporary **Recovery Growth** state may modestly increase reproduction once food, housing and Welfare have actually recovered
- Recovery Growth does not bypass resource requirements and does not activate while the settlement remains unstable
- avoid explicit genetic/eugenic mechanics; this is demographic/resource simulation, not trait breeding

Design constraint: village population should grow only when the settlement can actually support more people, and every new villager should create visible resource and infrastructure demand.

### Forest regeneration
Forests can recover slowly without requiring every sapling to be manually placed.

Accepted direction:
- natural forest recovery is **slow ecological background behavior**, not fast automatic replanting
- mature natural woodland creates a low-strength regeneration field around its edges
- viable nearby ground may occasionally receive a compatible local sapling / young-tree start, allowing ordinary tree growth mechanics to finish the process
- natural regeneration favors the existing local tree family / biome palette rather than introducing unrelated tree types
- an initial mature forest patch should produce only a small number of new starts over several Minecraft days; regeneration must be visibly slower than deliberate Forester replanting
- natural spreading stays local to existing forest edges and does not leap large empty distances
- recently clear-cut natural woodland may slowly refill over long timescales if the land remains viable and unused
- natural regeneration is suppressed on or near:
  - recognized buildings and roads
  - cultivated Village Farms
  - active Quarry / work sites
  - frequently used player-built areas
  - clearly artificial floors, paths and landscaped surfaces
- regeneration does not overwrite placed blocks or force trees into occupied structures
- Foresters are the **active/fast path** for woodland recovery:
  - they use real collected/stored saplings where practical
  - they replant approved Forestry Sites after harvesting
  - they can fill obvious gaps more deliberately than the natural background system
- Foresters prefer maintaining a mixed-age renewable woodland rather than repeatedly harvesting every mature tree at once
- abandoned Forestry Sites may gradually return toward ordinary natural woodland after active management stops
- the system should not create runaway tree spam, exponential spreading or forests invading maintained settlements
- exact natural seeding interval/density is a tuning value; the intended pace is measured in multiple Minecraft days, not minutes

Design constraint: natural forests can heal slowly on their own, while managed forestry recovers much faster without making wood an infinite instantaneous resource.

### Rivers as infrastructure
Settlements treat persistent navigable surface-water corridors as useful geography rather than only as pathfinding obstacles.

Accepted direction:
- the village planner may recognize a **River Corridor** when a connected surface-water route is long/continuous enough to matter for settlement movement or work
- isolated ponds and tiny water patches are not treated as rivers merely because they contain water
- recognized rivers may serve several roles simultaneously:
  - reliable nearby water access
  - fishing-work area
  - natural settlement/district boundary
  - road/bridge crossing constraint
  - transport/logistics corridor
  - suitable location for fishing huts, docks and small river-side work sites
- village planning remains terrain-aware: a river can attract development along its banks while also limiting where roads/buildings can cross
- bridge placement uses the already accepted road/bridge cost comparison rather than placing bridges at every crossing
- frequently used bank access may gain a small path, landing or dock when real traffic justifies it
- villagers do not automatically reroute, dam or massively excavate natural rivers in the initial implementation
- minor safe bank preparation is allowed for paths/docks, but major canal engineering is outside the initial scope

Water and emergency use:
- recognized accessible river water counts as a nearby water source for settlement planning and fire-response logic
- fire responders prefer practical nearby water access and still obey actual travel/container constraints rather than extinguishing remotely

Fishing:
- a suitable river reach may become an approved Fishing Site
- fishing huts and related storage may be built when food/economic demand justifies sustained fishing
- fishing sites follow the same bounded-work-site model as Forestry/Quarry/Farm sites

River logistics:
- water transport becomes available only when two useful endpoints are connected by a **continuous navigable water route**
- endpoints should use recognized docks/landings tied into the local road/storage network
- when a water route is substantially cheaper/safer than overland hauling, the planner may prefer it for bulk logistics
- actual boats / Cargo Rafts use the route physically; items do not teleport between docks
- river logistics may move construction materials, food, trade goods and Outpost supplies
- local road/Porter transport handles the first/last leg between storage/work sites and docks
- route planning must validate practical clearance, water continuity and endpoint access before assigning regular boat traffic
- water transport does not automatically create a new independent settlement; it is another logistics link between existing village districts / Outposts / settlements

Settlement structure:
- rivers may naturally separate districts within one merged village when bridges/docks still maintain strong daily integration
- if a river produces weak connectivity rather than strong shared movement/logistics, settlements on opposite banks may remain distinct
- village expansion should generally preserve recognizable river geography instead of filling the waterway with buildings

Design constraint: rivers should become useful pieces of settlement infrastructure while remaining real terrain that villagers must navigate, cross and physically transport goods through.

### Regional economy integration
Regional trade value, village logistics and autonomous growth share one lightweight supply/demand model rather than maintaining a separate abstract market simulation.

Accepted direction:
- each village tracks a small set of **trade/resource categories** rather than a full per-item commodity exchange
- initial categories may include:
  - Food
  - Wood
  - Stone / Construction
  - Metal
  - Farming
  - Fishing
  - Regional goods
  - Luxury / rare goods
- each category derives a **Scarcity / Surplus state** from real recognized village inventory, reserved materials, active construction/repair demand and expected local consumption
- market state is refreshed infrequently, initially about **once per Minecraft day**, rather than recalculated every tick
- price logic uses the same real resource state already used by village planners and logistics; there is no hidden economic inventory

Initial trade-value bands:
- strong surplus: about **0.80x** base value
- normal supply: **1.00x**
- mild shortage: about **1.15x**
- shortage: about **1.35x**
- severe shortage: about **1.60x**
- strongly non-local / regionally scarce goods may reach roughly **1.80x** where appropriate
- these multipliers are initial tuning values and should remain bounded enough that ordinary trade does not become wildly unstable

Regional value:
- scarcity from inventory/demand and **regional availability** are related but separate inputs
- goods that are naturally difficult to obtain in the surrounding biome/region may receive a regional-value bonus
- examples include desert goods in cold regions, spruce/cold-region materials in deserts, or marine goods in strongly inland settlements
- value should depend primarily on whether the good is locally obtainable, not simply on raw transport distance
- moving goods between genuinely different regions should therefore be more valuable than repeatedly shuttling the same common local item between nearby villages

Real trade feedback:
- when the player sells useful material such as logs, food, stone or metal to a village, the accepted quantity may enter recognized village storage and become usable by the simulation
- imported material can therefore directly unblock construction, repair or food shortages
- as real stock recovers, the shortage premium falls on later market updates
- repeated bulk sale of the same good cannot preserve maximum shortage pricing indefinitely
- when village activity consumes stock again, demand/value may rise naturally

Village selling:
- villages prefer selling **surplus above their operational reserve**
- planners should not voluntarily liquidate critical food, construction or emergency reserves merely because the player requests a trade
- sale availability/pricing may therefore shrink when village stock approaches its target reserve

Trade-price composition:
- final trade pricing may combine:
  - villager/base trade value
  - regional supply/demand modifier
  - regional-availability modifier where applicable
  - existing per-villager Welfare modifier
- these modifiers should remain visible enough that the player can understand why a price changed
- trade UI may expose concise reasons such as **High local demand**, **Stock shortage**, **Regional import**, **Surplus**, or **Welfare +25%**

AI integration:
- the same Scarcity states inform village planning and logistics
- shortages can create gathering, import, public-works or trade needs
- surpluses can make goods available for export
- when two settlements have complementary surplus/shortage states, future Caravan / Cargo Raft logistics may move real goods between them
- imported goods enter real destination storage and exported goods leave real origin storage
- no trade route generates materials from nothing

Design constraint: regional economy should emerge from real village inventory, real consumption and geographic availability, while remaining simple enough to understand and cheap enough to update only periodically.

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

### Atlas / Map Binder

Add a portable atlas item that can store multiple existing filled maps and automatically display the map that matches the player's current location.

Accepted direction:
- the atlas stores multiple normal filled maps rather than replacing vanilla map data
- while held/opened, it automatically selects a stored map whose dimension and covered area contain the player
- moving across map boundaries automatically switches to the appropriate stored map
- Nether / Overworld / End and other dimensions must not accidentally select maps from the wrong dimension
- if multiple stored maps cover the same position, prefer the most detailed usable map; ties can use a stable insertion/order rule
- if no stored map covers the current position, show a clear blank / out-of-coverage state instead of inventing map data
- maps can be added to and removed from the atlas without losing their existing map IDs, exploration data, decorations, or custom names
- the atlas must not automatically generate unexplored maps or reveal terrain the player has not mapped
- normal held-map rendering should be reused where practical so the currently selected page behaves like a vanilla filled map
- the atlas may later support browsing stored pages manually in addition to automatic current-location selection

Design constraint: this is a smart container/viewer for real vanilla maps, not an infinite minimap or automatic world map.


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

Accepted mastery scale:
- enchantment mastery performance uses a 0-100 progression scale
- mastery 0-49: normal growth before specialization
- mastery 50: the enchantment may select its first specialization branch
- mastery 51-99: the selected branch continues to strengthen gradually
- mastery 100: the selected branch reaches its intended completed strength
- performance does not continue scaling past mastery 100
- historical/use tracking may continue past 100 for item-history purposes even though mechanical strength is capped

Examples include Feather Falling becoming safer landing, impact landing, or aerial recovery; Fortune becoming ore-, crop-, or high-variance-focused.
Branches should change play style more than raw DPS/mining output.
- branch effects should, by default, remain self-contained within the original enchantment's own behavior domain
- avoid inventing unrelated subsystems merely to fill branch slots; if only one or two strong branches exist, leave the remaining slot open until a natural option is found

Current accepted branch candidates:
- **Unbreaking**
  - Rested Reserve: leaving the item unused for a while builds a small reserve that negates the next few durability losses
  - Continuous Operation: sustained use of the same item gradually reduces durability consumption; switching away resets the benefit
  - Protective Mode: at low durability, the item trades some performance for sharply reduced further durability loss
- **Infinity**
  - Pure Infinity: normal arrows no longer require even a single seed arrow in inventory
  - Rapid Infinity: sustained normal-arrow fire progressively reduces bow durability consumption
  - Precision Infinity: fully charged deliberate shots greatly reduce or avoid bow durability consumption
- **Thorns**
  - Retaliatory Spikes: specializes in direct reflected damage
  - Entangling Thorns: gives up some reflected damage for slowdown / knockback control
  - Stored Retaliation: incoming hits build retaliation energy that is released through the wearer's next melee attack
- **Looting**
  - Herd Hunter: consecutive kills of the same mob type increase ordinary-drop yield until the streak expires
  - Stripping: emphasizes equipment / carried-item drop chance rather than generic quantity
  - Big-Game Hunter: sacrifices some ordinary-drop improvement to emphasize rare-drop rolls
- **Mending** is an explicit exception to the branch system: it does not choose a mastery branch at 50. Instead, mastery itself unlocks and grows an over-repair durability buffer.
- **Flame**
  - Long Burn: extends the duration of the fire applied by Flame
  - Stacked Ignition: hitting a target that is already burning with Flame adds additional burn duration, with an explicit cap
  - a third Flame branch is intentionally left open for now rather than adding behavior outside Flame's own ignition/burning effect domain
- **Protection**
  - General Defense: improves the consistency of Protection's broad damage reduction without adding a new damage domain
  - First-Hit Defense: after remaining unharmed for a while, the next damaging hit receives stronger Protection mitigation
  - Crisis Defense: Protection becomes more effective as the wearer's health becomes low
- **Fire Protection**
  - Rapid Extinguishing: further shortens burn duration
  - Heat Adaptation: sustained exposure to fire/lava gradually improves Fire Protection's mitigation while exposure continues
  - Lava Adaptation: emphasizes Fire Protection's handling of lava exposure and movement-related penalties while submerged
- **Projectile Protection**
  - Frontal Guard: stronger mitigation against projectiles arriving from the wearer's forward-facing side
  - Sniper Resistance: greater mitigation against projectiles that have traveled a long distance
  - Barrage Resistance: repeated projectile hits within a short window gain progressively stronger mitigation
- **Blast Protection**
  - Blast Anchor: strongly reduces explosion knockback
  - Epicenter Resistance: gains additional mitigation when very close to the explosion center
  - Chain-Blast Resistance: repeated explosions within a short window gain progressively stronger mitigation
- **Feather Falling**
  - Soft Landing: specializes in pure fall-damage safety
  - Impact Landing: converts part of the mitigated fall impact into a local landing shock effect
  - Aerial Recovery: improves horizontal control during falls and immediately after landing
- **Power**
  - Sniping: specializes Power for long-range shots
  - Heavy Draw: emphasizes fully charged shots
  - Quick Shot: reduces the performance penalty of partially charged shots
- **Luck of the Sea**
  - Treasure Hunter: biases Luck of the Sea further toward treasure-category catches
  - Quality Selection: biases applicable caught equipment/books toward better quality rather than only changing catch category
  - Rare Catch: emphasizes rare living / regional / Nether-fishing catches where the fishing table supports them
- **Lure**
  - Fast Bite: further shortens time until a bite
  - Secure Hook: extends the successful-hook reaction window
  - Fishing Rhythm: a successful catch temporarily accelerates the next bite; repeated successful catches can maintain the rhythm
- **Curse of Binding**
  - Bound Legacy: reinforces the curse's stay-with-the-wearer behavior around death/loss without making the item normally removable
  - Familiar Bondage: long continuous wear slightly reduces durability consumption while the curse remains fully active
  - Forced Attachment: strengthens resistance to effects that would forcibly unequip/remove the cursed item; normal inability to remove it remains
- **Curse of Vanishing**
  - Delayed Return: the item still vanishes on death but may return later under the branch's defined delayed-return rules
  - Echo: the item vanishes, but leaves a temporary trace/echo of the lost item at or around the death event
  - Legacy: the item itself is permanently lost, but part of its mastery/history can be inherited by a later same-type replacement
- **Silk Touch**
  - Precision Harvest: expands Silk Touch recovery to a limited allowlist of additional blocks that are safe to obtain; progression-breaking blocks such as spawners remain excluded
  - Batch Harvest: can Silk Touch a small connected group of the same suitable block type, aimed at glass, ice, leaves and building-material relocation rather than vein mining
  - State Preservation: preserves safe/restorable block-state details where practical when harvesting and replacing blocks; unsupported or unsafe state is not serialized blindly
- **Multishot**
  - Converging Volley: narrows the horizontal spread so the three projectiles can be used more effectively against one large or mid-range target
  - Wide Volley: increases spread for area coverage and multiple-target pressure
  - Vertical Volley: changes the three-projectile pattern from horizontal spread to a center/up/down arrangement for vertical terrain, flying targets and narrow spaces
- **Punch**
  - Blowback: specializes in stronger horizontal knockback
  - Launch: trades some horizontal displacement for stronger upward knockback
  - Pinning Shot: greatly reduces ordinary knockback and instead applies a strong short-duration movement slowdown to hold the target near its current position
- **Aqua Affinity**
  - Submerged Mining: further removes underwater mining penalties, especially while not grounded
  - Underwater Construction: improves underwater block-placement / break-workflow handling and reduces disruption while building
  - Current Adaptation: strongly reduces water-current displacement while actively mining or placing blocks, helping the player hold a working position

- **Riptide**
  - Long Range: emphasizes travel distance per activation
  - Steering: emphasizes directional control during Riptide movement
  - Ram: emphasizes collision / contact impact while using Riptide
- **Channeling**
  - Chain Lightning: a successful Channeling strike can propagate a weaker lightning effect to nearby valid targets
  - Rain Channeling: extends part of Channeling's lightning behavior into ordinary rain at reduced strength rather than requiring a full thunderstorm
  - Conductor: improves Channeling interactions with conductive targets such as lightning rods and suitable metal targets
- **Wind Burst**
  - Updraft: emphasizes vertical self-launch height
  - Blast: emphasizes horizontal area knockback around the impact
  - Aerial Control: trades some launch magnitude for better movement control after the burst
- **Frost Walker**
  - Narrow Path: shapes freezing more strongly along the travel direction instead of simply widening the frozen area
  - Lasting Ice: increases how long Frost Walker-created ice remains before reverting
  - Frost: strengthens the slowing effect associated with Frost Walker's freezing behavior on nearby wet targets
- **Sharpness**
  - Duel: repeated attacks against the same target progressively favor sustained single-target pressure
  - Heavy Strike: emphasizes fully charged melee attacks
  - Execute: emphasizes damage against low-health targets
- **Smite**
  - Exorcism: killing an undead target produces a small Smite-themed effect against nearby undead
  - Holy Strike: Smite hits temporarily weaken the offensive pressure of undead targets
  - Gravebreaker: emphasizes damage against armored undead
- **Bane of Arthropods**
  - Binding Venom: emphasizes and extends Bane's slowing effect
  - Swarm Extermination: becomes more effective when fighting groups of arthropods
  - Antivenom: grants limited poison resistance while actively fighting arthropod targets
- **Impaling**
  - Wet Hunt: broadens Impaling's practical target condition toward wet targets
  - Harpoon: gives Impaling hits a pulling component
  - Deep Hunter: improves Impaling performance in deep-water combat
- **Density**
  - Terminal Fall: emphasizes very high-fall smash attacks
  - Low-Altitude Impact: makes smaller and medium-height smash attacks more useful
  - Shock Impact: converts part of Density's smash emphasis into a local impact effect around the strike
- **Breach**
  - Heavy Armor Crusher: becomes more effective against highly armored targets
  - Shield Breaker: emphasizes pressure against shielding / guarding targets
  - Fracture: a Breach hit temporarily leaves the target more vulnerable to armor-bypassing pressure
- **Piercing**
  - Penetration: reduces projectile performance loss as it passes through targets
  - Skewer: emphasizes control / impact on the last target hit in a piercing sequence
  - Line Hunter: improves stability when hitting several targets in a line
- **Sweeping Edge**
  - Wide Arc: increases sweep coverage
  - Focused Sweep: narrows coverage while increasing secondary-target effectiveness
  - Battle Rhythm: successful multi-target sweeps improve the handling of the next sweep attack
- **Fire Aspect**
  - Long Burn: emphasizes longer burn duration
  - Flash Burn: emphasizes a shorter, more intense burn
  - Cauterize: emphasizes pressure against targets that attempt to recover while burning
- **Knockback**
  - Launch: emphasizes vertical displacement
  - Blowback: emphasizes horizontal displacement distance
  - Recoil Step: uses part of the attack reaction as controlled attacker recoil / repositioning
- **Fortune**
  - Ore Specialist: biases Fortune's mastery benefit toward ore-style drops
  - Harvest Specialist: biases Fortune's mastery benefit toward crops / natural harvests
  - High Variance: increases outcome variance, accepting weaker ordinary rolls for a chance at unusually large Fortune results
- **Efficiency**
  - Hard-Material Breaker: gives more of the mastery benefit to difficult / high-hardness blocks
  - Mining Rhythm: sustained mining gradually stabilizes / improves Efficiency performance
  - Generalist Tool: reduces the penalty when the tool is used on somewhat unsuitable block types
- **Quick Charge**
  - First Load: strongly improves the first reload after a pause
  - Reload Rhythm: consecutive reloads become progressively faster while the firing rhythm is maintained
  - Mobile Reload: reduces movement disruption while reloading a crossbow
- **Respiration**
  - Deep Breath: extends total underwater breathing time
  - Quiet Breath: reduces oxygen consumption while stationary or moving slowly underwater
  - Rapid Ventilation: restores air more quickly after returning to breathable conditions
- **Soul Speed**
  - Soul-Sole Conservation: reduces Soul Speed's durability-consumption drawback
  - Lingering Momentum: preserves part of Soul Speed's movement benefit briefly after leaving soul blocks
  - Soul Footing: improves resistance to displacement while moving on soul blocks
- **Swift Sneak**
  - Silent Sneak: further suppresses vibration / sculk-trigger pressure while sneaking
  - Combat Stance: reduces movement loss while using items from a sneaking stance
  - Builder's Sneak: improves controlled edge movement while using sneak for fall prevention during building
- **Depth Strider**
  - Current Rider: improves movement when traveling with water flow
  - Seabed Runner: emphasizes grounded underwater movement and turning
  - Diver: emphasizes vertical underwater movement
- **Loyalty**
  - Fast Return: emphasizes return speed
  - Safe Return: emphasizes obstacle avoidance and loss prevention during return
  - Pursuing Return: improves the returning weapon's ability to catch up when the owner has moved far from the throw point

### Initial mastery-branch tuning defaults

These are the initial balance values for the accepted mastery branches. They are tuning defaults, not compatibility promises.

Common scaling rules:
- unless a branch explicitly says otherwise, the first number is the effect at mastery 50 and the second number is the completed effect at mastery 100
- numeric values interpolate linearly from mastery 50 to 100
- discrete counts / tiers unlock at sensible intermediate thresholds, normally around mastery 50 / 75 / 100
- branch bonuses are applied after the base enchantment's ordinary level behavior unless a branch explicitly modifies that behavior
- damage-reduction branches generally reduce damage remaining after ordinary armor/enchantment mitigation rather than multiplying the original incoming damage
- identical armor branch effects do not add together across multiple pieces; for the same branch, use the strongest mastery value present
- different branches on different armor pieces may coexist unless a specific implementation proves unsafe
- no branch grants full damage immunity, infinite acceleration, progression-block bypass, or free duplication unless explicitly stated
- Mending uses its separately defined over-repair mastery progression and has no normal branch tuning here

#### Unbreaking
- Rested Reserve: while the item is not used, build 1 -> 3 reserve charges; one charge negates one durability-loss event. Recharge interval falls from about 20s -> 10s per charge.
- Continuous Operation: sustained use builds an additional 5% -> 15% durability-loss-negation chance, reaching full branch strength after roughly 10 consecutive qualifying uses; swapping away or leaving the item unused for about 3s resets the streak.
- Protective Mode: activates below 15% -> 25% remaining durability. While active, further durability loss is reduced by about 30% -> 60%, but the item suffers a roughly 10% performance penalty so the mode is protective rather than optimal normal use.

#### Infinity
- Pure Infinity: binary branch; from mastery 50 onward, ordinary Infinity shots no longer require a seed arrow in inventory. No additional numerical scaling is required.
- Rapid Infinity: after roughly 3 consecutive qualifying shots, bow durability-loss chance is reduced by 10% -> 35%; the streak resets after about 4s without firing.
- Precision Infinity: a fully charged shot has a 15% -> 50% chance to avoid the bow's normal durability loss.

#### Thorns
- Retaliatory Spikes: reflected Thorns damage is increased by about 15% -> 40% without increasing the base incoming damage.
- Entangling Thorns: reflected damage is reduced by about 30%, but a successful Thorns retaliation applies roughly 20% -> 40% movement slowdown for 1.0s -> 2.5s and slightly stronger defensive knockback.
- Stored Retaliation: incoming qualifying hits store about 15% -> 35% of their post-mitigation damage as retaliation energy, capped at about 3 -> 8 damage; the next successful melee hit releases the stored amount and clears it.

#### Looting
- Herd Hunter: consecutive kills of the same entity type within 20s build ordinary-drop momentum, reaching roughly +15% -> +30% additional ordinary-drop yield potential at the streak cap; changing target type or letting the timer expire resets it.
- Stripping: applicable equipment / carried-item drop chances are multiplied by about 1.25x -> 1.75x after vanilla Looting handling.
- Big-Game Hunter: rare-drop chances gain roughly +10% -> +30% relative weighting, while the branch reduces Looting's ordinary/common-drop improvement by about 25%.

#### Flame
- Long Burn: Flame-applied burn duration is extended by about 25% -> 75%.
- Stacked Ignition: hitting an already-burning target with another Flame projectile adds about 1.0s -> 2.5s of burn time, with a total extra-duration cap of about 3s -> 8s.
- Third branch: intentionally open.

#### Protection
- General Defense: reduces otherwise-Protectable damage remaining after normal mitigation by an additional 3% -> 8%.
- First-Hit Defense: after about 8s without taking damage, the next qualifying hit receives an additional 10% -> 25% remaining-damage reduction; taking the protected hit restarts the re-arm timer.
- Crisis Defense: below 40% health, the branch ramps up as health falls, reaching about 5% -> 20% additional remaining-damage reduction near 10% health.

#### Fire Protection
- Rapid Extinguishing: remaining burn duration is reduced by an additional 20% -> 50%.
- Heat Adaptation: after about 2s of continuous fire/lava exposure, additional remaining fire/lava damage reduction ramps toward 5% -> 15%, reaching full strength after roughly 6s and resetting after about 3s safe.
- Lava Adaptation: reduces lava movement impairment by about 20% -> 60% while submerged; it does not grant lava immunity.

#### Projectile Protection
- Frontal Guard: projectiles arriving from roughly the forward 120-degree arc receive an additional 8% -> 20% remaining-damage reduction.
- Sniper Resistance: starting around 16 blocks of projectile travel, extra mitigation ramps with distance up to about 10% -> 25% at 48+ blocks.
- Barrage Resistance: repeated projectile hits within 3s add about 3% -> 7% extra remaining-damage reduction per prior hit, capped around 9% -> 21%; the stack resets after roughly 4s without another projectile hit.

#### Blast Protection
- Blast Anchor: explosion knockback remaining after normal Blast Protection is reduced by another 20% -> 55%.
- Epicenter Resistance: explosions within roughly 3 blocks gain an additional 5% -> 20% remaining-damage reduction, fading to zero by about 6 blocks.
- Chain-Blast Resistance: explosions received within 4s of another explosion gain roughly 5% -> 12% extra remaining-damage reduction per prior blast, capped around 15% -> 36% and resetting after about 5s without another blast.

#### Feather Falling
- Soft Landing: remaining fall damage after ordinary Feather Falling is reduced by an additional 10% -> 30%.
- Impact Landing: for falls of roughly 5+ blocks, 10% -> 25% of the fall damage prevented by Feather Falling is converted into a local impact effect, capped around 6 damage with a radius of about 2 -> 4 blocks.
- Aerial Recovery: horizontal air-control authority during falls is improved by about 10% -> 35%; this does not add flight or cancel vertical fall speed.

#### Power
- Sniping: starting around 16 blocks of arrow travel, Power damage gains a distance bonus ramping to about +5% -> +20% at 48+ blocks.
- Heavy Draw: shots released at roughly 95%+ full draw gain about +5% -> +15% damage.
- Quick Shot: reduces the damage penalty from partial draw by about 15% -> 45%, without making tap-fire equal to a full draw.

#### Luck of the Sea
- Treasure Hunter: treasure-category weighting is increased by about 10% -> 35% relative to its post-vanilla value, with other categories renormalized rather than duplicated.
- Quality Selection: applicable equipment / enchanted-book catches gain about a 10% -> 30% chance for one quality-improvement reroll; no infinite reroll loop.
- Rare Catch: dedicated rare-living / regional / Nether-fishing entries gain about +10% -> +40% relative weighting where such entries exist; ordinary tables without a rare category are unchanged.

#### Lure
- Fast Bite: additional wait time is reduced by about 10% -> 30%, subject to a minimum wait floor so bites never become effectively instant.
- Secure Hook: the successful reaction window after a bite is extended by about 20% -> 60%.
- Fishing Rhythm: each successful catch grants a temporary next-bite reduction; branch strength starts around 10% and can build to a capped 20% -> 45% reduction through repeated successful catches. Rhythm expires after roughly 12s without a successful catch.

#### Curse of Binding
- Bound Legacy: on death, a bound item has about a 25% -> 75% chance to remain associated with the wearer and reappear equipped after respawn rather than becoming an ordinary drop; the curse still prevents normal removal.
- Familiar Bondage: after long continuous wear, durability-loss chance is reduced by about 5% -> 15%; full benefit requires roughly 20 -> 10 minutes of uninterrupted wear depending on mastery.
- Forced Attachment: external forced-unequip attempts are resisted about 50% -> 100% of the time. This does not change the ordinary Binding rule that the item cannot simply be removed.

#### Curse of Vanishing
- Delayed Return: the item still disappears on death; it has about a 10% -> 30% chance to return after a delay that falls from roughly 20 -> 5 minutes as mastery rises.
- Echo: a vanished item leaves a non-item trace / echo for roughly 60s -> 300s.
- Legacy: when the item permanently vanishes, about 15% -> 40% of its mastery/history may be inherited by a later same-type replacement through the existing inheritance system.

#### Silk Touch
- Precision Harvest: use three safe allowlist tiers at approximately mastery 50 / 75 / 100. Each tier adds only explicitly reviewed non-progression-breaking blocks; spawners and similar progression-breaking blocks remain excluded.
- Batch Harvest: connected identical suitable blocks can be harvested in batches of about 3 -> 8 blocks. Each harvested block pays normal durability/tool costs and the branch never becomes free vein mining.
- State Preservation: use three reviewed state-preservation tiers at approximately mastery 50 / 75 / 100. Preserve only safe/restorable properties such as orientation or approved waterlogged/state data; never serialize arbitrary block-entity state blindly.

#### Multishot
- Converging Volley: horizontal projectile spread narrows from about 75% -> 40% of vanilla Multishot spread.
- Wide Volley: horizontal projectile spread widens to about 125% -> 180% of vanilla Multishot spread.
- Vertical Volley: binary pattern change at mastery 50 from horizontal to center/up/down; vertical spread then scales from roughly 100% -> 140% of the vanilla Multishot angle.

#### Punch
- Blowback: horizontal knockback is increased by about 15% -> 40%.
- Launch: converts roughly 30% -> 60% of the normal horizontal knockback emphasis into upward launch.
- Pinning Shot: ordinary Punch displacement is heavily reduced and replaced with about 25% -> 45% movement slowdown for roughly 1.0s -> 2.5s.

#### Aqua Affinity
- Submerged Mining: removes about 25% -> 100% of the remaining airborne-underwater mining penalty that Aqua Affinity does not normally solve; mastery 100 may fully remove that specific residual penalty.
- Underwater Construction: after a successful underwater block place/break interaction, water-drag / movement disruption is reduced by about 15% -> 40% for roughly 1.5s, improving repositioning without increasing reach.
- Current Adaptation: while actively mining or placing blocks underwater, water-current displacement is reduced by about 20% -> 60%.

#### Riptide
- Long Range: Riptide travel distance is increased by about 10% -> 25%.
- Steering: directional control during Riptide movement is improved by about 25% -> 75%.
- Ram: valid Riptide collision/contact damage gains roughly +10% -> +30%, capped at about +6 bonus damage from the branch.

#### Channeling
- Chain Lightning: a normal qualifying strike may jump to 1 -> 3 additional valid nearby targets within roughly 4 -> 6 blocks; secondary strikes use about 35% -> 50% of the primary lightning damage/effect and never recursively chain.
- Rain Channeling: during ordinary rain with open sky, Channeling has about a 15% -> 50% chance to produce a reduced strike at roughly 50% primary-lightning damage. Thunderstorms retain normal Channeling behavior.
- Conductor: search radius for intentional conductor interactions grows from roughly 4 -> 8 blocks and increasingly favors a nearby valid lightning rod / approved conductive target over a less suitable strike point.

#### Wind Burst
- Updraft: self-launch vertical impulse is increased by about 10% -> 30%.
- Blast: horizontal burst radius grows by roughly +0.5 -> +2.0 blocks and horizontal impulse by about +10% -> +25%.
- Aerial Control: gives up roughly 10% of raw launch magnitude in exchange for about +25% -> +70% aerial steering authority after the burst.

#### Frost Walker
- Narrow Path: reshape the frozen area so forward reach is about 125% -> 175% of the normal radius while lateral width is reduced to roughly 65% -> 40%; total frozen area should stay in the same broad order rather than becoming a giant rectangle.
- Lasting Ice: Frost Walker-created ice lifetime is extended by about 50% -> 200%.
- Frost: wet valid targets standing on freshly created Frost Walker ice receive about 10% -> 30% movement slowdown for roughly 1.5s -> 3s.

#### Sharpness
- Duel: consecutive hits on the same target within roughly 3s gain about +1% -> +3% damage per stack, capped at 5 stacks.
- Heavy Strike: fully charged melee attacks gain about +5% -> +15% damage.
- Execute: attacks against targets below 25% health gain about +5% -> +20% damage.

#### Smite
- Exorcism: killing an undead target releases about 15% -> 35% of the Smite bonus damage as a nearby-undead-only effect within roughly 2.5 -> 4 blocks; it does not damage non-undead entities.
- Holy Strike: an undead target hit by Smite deals about 5% -> 15% less damage for roughly 2s -> 4s; repeated hits refresh rather than stack the reduction.
- Gravebreaker: against undead targets with substantial armor, the Smite bonus itself is increased by about 10% -> 30%.

#### Bane of Arthropods
- Binding Venom: Bane's existing slowdown duration is extended by about 25% -> 100%.
- Swarm Extermination: each additional nearby arthropod grants about +5% -> +12% Bane bonus damage, capped at 3 nearby arthropods.
- Antivenom: while actively fighting an arthropod (and for a short grace period after a hit), poison damage is reduced by about 15% -> 50%.

#### Impaling
- Wet Hunt: wet non-aquatic targets receive about 50% -> 100% of the normal Impaling bonus; dry non-aquatic targets remain unaffected.
- Harpoon: Impaling hits add a pull impulse of roughly 0.15 -> 0.45 toward the attacker / projectile origin.
- Deep Hunter: while fully submerged and roughly 8+ blocks below the local water surface, Impaling bonus damage increases by about 10% -> 30%.

#### Density
- Terminal Fall: after roughly the first 8 blocks of qualifying fall distance, Density's additional high-fall contribution is increased by about 10% -> 25%.
- Low-Altitude Impact: the early / low-height portion of a qualifying smash gains about 15% -> 50% more Density contribution, making small and medium drops more useful without multiplying extreme falls.
- Shock Impact: about 15% -> 35% of the Density bonus damage is echoed to nearby valid targets within roughly 2 -> 3.5 blocks, capped around 6 branch damage per secondary target.

#### Breach
- Heavy Armor Crusher: against heavily armored targets, Breach removes an additional roughly 5% -> 15% of the armor effectiveness remaining after normal Breach processing.
- Shield Breaker: successful Breach hits that interact with active guarding extend the normal disable/pressure window by roughly 0.5s -> 1.5s where technically supported.
- Fracture: a Breach hit leaves a non-stacking mark for roughly 2s -> 4s that improves subsequent Breach effectiveness against that target by about 5% -> 15%; repeat hits refresh duration.

#### Piercing
- Penetration: preserve roughly 90% -> 100% of projectile momentum / damage quality that would otherwise be lost through valid post-hit continuation; do not add artificial loss when the underlying projectile path has none.
- Skewer: the final target allowed by the projectile's Piercing count receives about +15% -> +40% knockback / control impulse.
- Line Hunter: after each successful pierced target, the projectile gains about +3% -> +8% effectiveness against the next valid target, capped after 3 penetrations; this bonus ends when the projectile stops piercing.

#### Sweeping Edge
- Wide Arc: effective sweep coverage increases by about 10% -> 30%.
- Focused Sweep: sweep coverage is reduced by roughly 25%, while secondary-target sweep damage increases by about 10% -> 30%.
- Battle Rhythm: hitting 2+ valid targets with one sweep improves the next melee attack's recovery / handling by about 5% -> 15% for roughly 2s; it does not stack repeatedly.

#### Fire Aspect
- Long Burn: Fire Aspect burn duration increases by about 25% -> 75%.
- Flash Burn: burn duration is reduced by roughly 40%, but Fire Aspect's burn damage intensity increases by about 20% -> 60%.
- Cauterize: while a target is burning from this Fire Aspect source, healing received is reduced by about 10% -> 30%; the effect ends with the burn.

#### Knockback
- Launch: converts roughly 30% -> 60% of the normal Knockback impulse into vertical displacement.
- Blowback: horizontal Knockback distance increases by about 15% -> 40%.
- Recoil Step: the attacker receives controlled recoil equal to about 10% -> 30% of the target's knockback impulse in the opposite direction.

#### Fortune
- Ore Specialist: when Fortune successfully produces bonus ore drops, there is about a 10% -> 25% chance to add one further bonus item; only approved ore-style Fortune targets qualify.
- Harvest Specialist: same 10% -> 25% extra-bonus chance, but only for approved crop / natural-harvest Fortune targets.
- High Variance: about 10% -> 30% of Fortune's bonus portion becomes volatile; half of volatile outcomes lose that bonus portion and half double it, keeping expected value roughly neutral while increasing variance.

#### Efficiency
- Hard-Material Breaker: qualifying high-hardness blocks receive about +5% -> +15% additional mining speed.
- Mining Rhythm: consecutive qualifying blocks broken within roughly 1.5s build +2% -> +5% speed per stack, capped around +10% -> +25%; the streak resets when the interval is missed.
- Generalist Tool: reduces the mining-speed penalty on somewhat unsuitable block types by about 15% -> 50%, but never grants drops when the tool is invalid for harvesting.

#### Quick Charge
- First Load: after roughly 3s without firing, the next crossbow reload is about 10% -> 30% faster.
- Reload Rhythm: consecutive reloads within roughly 3s gain about 5% -> 10% reload speed per stack, capped around 15% -> 30%; losing the rhythm resets the stack.
- Mobile Reload: reduces movement slowdown while charging/reloading a crossbow by about 15% -> 50%.

#### Respiration
- Deep Breath: effective underwater air-loss rate is reduced by an additional about 10% -> 30%.
- Quiet Breath: while nearly stationary underwater, remaining air-loss rate is reduced by about 25% -> 70%; attacking/mining or moving quickly breaks the quiet condition.
- Rapid Ventilation: air refills about 25% -> 100% faster once the player reaches breathable conditions.

#### Soul Speed
- Soul-Sole Conservation: Soul Speed's durability-consumption drawback is reduced by about 25% -> 75%.
- Lingering Momentum: after leaving soul-speed-valid terrain, retain about 50% -> 75% of the Soul Speed movement bonus for roughly 1.0s -> 3.0s.
- Soul Footing: while on soul-speed-valid terrain, knockback / forced displacement is reduced by about 10% -> 35%.

#### Swift Sneak
- Silent Sneak: suppress about 20% -> 70% of otherwise emitted movement-related vibrations while sneaking; intentionally noisy actions such as block breaking are not hidden for free.
- Combat Stance: while sneaking, item-use movement slowdown is reduced by about 10% -> 35%.
- Builder's Sneak: while crouch edge-protection is actively preventing a fall, controlled edge movement speed is improved by about 10% -> 30% without disabling the edge stop.

#### Depth Strider
- Current Rider: movement with water flow is improved by about 10% -> 30%.
- Seabed Runner: grounded underwater horizontal movement / turning improves by about 10% -> 25%.
- Diver: vertical underwater movement authority improves by about 10% -> 35%.

#### Loyalty
- Fast Return: Loyalty return speed increases by about 15% -> 50%.
- Safe Return: return-path correction / obstacle-avoidance authority improves by about 25% -> 75%, with allowed detour distance growing from roughly 4 -> 12 blocks before giving up on that correction.
- Pursuing Return: when the owner is moving away from the return path, catch-up acceleration improves by about 20% -> 60%, with a final return-speed bonus capped around 10% -> 30% above the branch's ordinary return speed.

### Curse Growth
Curses also accumulate mastery/history and may mutate through long-term use.
The curse remains a meaningful drawback, but veteran cursed gear can develop unusual compensating behavior instead of remaining pure trash.
Examples may include Binding becoming harder to lose on death, or Vanishing evolving into a delayed-return behavior.

### Mutually Exclusive Enchantment Switching
Permit selected normally-exclusive enchantments to coexist on one item while only one is active at a time.

Accepted initial behavior:
- the initial supported pair is Fortune + Silk Touch
- the pair is combined through an anvil with an additional **+5 experience-level cost** on top of the normal anvil cost
- after combination, one enchantment is active and the other remains stored on the same item
- while holding the combined tool, **sneak + right-click in the air** toggles the active enchantment
- no dedicated keybind or Enchanting Table interaction is required for switching
- block-targeted right-click interactions take priority; the toggle should only trigger on an air-use action so normal block interaction is not hijacked
- switching after the initial anvil combination does not consume XP
- toggling should provide short action-bar feedback showing the newly active enchantment
- normal mutually-exclusive behavior remains enforced at effect time; Fortune and Silk Touch are never active simultaneously

Design constraint: pay the progression/combination cost up front, then make ordinary field switching immediate and low-friction.

### Enchantment Mastery Inheritance
Retiring/sacrificing veteran enchanted gear can transfer only part of an enchantment's mastery/history to a replacement.

Accepted direction:
- the primary/left item keeps its own mastery at 100%; using an anvil does not erase the history of the item that remains the base output
- mastery contributed by the secondary/right donor item transfers at **50%**
- for the same enchantment, the output keeps the higher of the primary item's existing mastery and the donor's halved mastery; the two mastery values are not added together
- donor mastery therefore cannot be repeatedly stacked to accelerate an enchantment past normal progression
- branch choice belongs to the surviving primary item and is not overwritten by a donor branch merely because donor mastery transfers
- if the primary item has not chosen a branch yet, donor mastery may move it above the branch threshold, but the player still chooses the branch normally
- historical counters that are purely descriptive may be merged separately later, but they do not increase mechanical mastery

The enchantment itself and the mastery are separate resources: inheritance should preserve attachment without making gear upgrades free.

### Uncapped Anvil Experience Cost
Remove the hard anvil experience ceiling / "Too Expensive!" rejection for normal survival use.
- High-cost operations remain expensive.
- Prior-work and enchantment combination costs may continue to scale.
- If the player actually has the required levels, the operation should be allowed.
- This is required for high-mastery enchantment transfer, switching and late-game item history systems.
- Any separate anti-abuse limits should be explicit configuration, not a hidden vanilla-style hard stop.

Design constraint: anvil changes should remove arbitrary rejection, not make merging/repairing cheap.

### Raised Enchantment Level Caps

Raise the normal maximum levels of enchantments so vanilla caps such as Efficiency V, Sharpness V, Fortune III, and similar limits are no longer the final ceiling.

Accepted direction:
- enchantments whose vanilla maximum level is II or higher can extend up to level 10 by default
- enchantments whose vanilla maximum level is I remain level I by default
- for multi-level enchantments, keep the existing vanilla level-based behavior and simply allow it to continue above the vanilla cap
- do not create bespoke post-cap scaling rules unless an enchantment actually needs one
- only special-case enchantments whose vanilla formula becomes invalid, meaningless, technically capped elsewhere, or excessively disruptive at higher levels
- single-level enchantments can gain additional levels later only as explicit exceptions
- the level-10 cap remains configurable as an implementation safeguard
- obtaining over-cap enchantments does not have to use the ordinary enchanting-table route
- block/item enchantment expansion can reuse the same over-cap system later
- Growing Enchantments / mastery must remain compatible with over-cap levels

Design constraint: default to vanilla formula continuation for existing multi-level enchantments; single-level enchantments stay single-level unless intentionally redesigned.

Current explicit over-cap decisions:
- Soul Speed IV-X: continue the existing vanilla level-scaled behavior; no bespoke post-cap mechanic is added by default
- Swift Sneak IV-X: continue the existing vanilla level-scaled behavior; no bespoke post-cap mechanic is added by default
- Wind Burst IV-X: continue the existing vanilla level-scaled behavior; no bespoke post-cap mechanic is added by default
- if any of these formulas hit a hard technical cap, become meaningless, or create clearly broken behavior at high levels, clamp or special-case only that specific effect rather than redesigning the whole enchantment

### Higher-Level Mending

Mending is an explicit exception to the normal single-level-enchantment rule and may extend above level I.

Accepted direction:
- Mending I keeps vanilla behavior at 2 durability restored per XP
- Mending II restores 3 durability per XP
- Mending III restores 4 durability per XP
- direct single-item repair conversion stops increasing after Mending III; levels IV-X gain multi-item routing behavior instead of continuing raw repair inflation
- Mending IV-IX can distribute repair XP across multiple damaged equipped/held items that also have Mending
- Mending X additionally expands linked-repair targeting to the player's full inventory, allowing damaged inventory items with Mending to participate in XP distribution
- only items that actually have Mending are eligible recipients; high-level Mending does not repair arbitrary non-Mending equipment
- inventory-wide repair is exclusive to Mending X; lower linked-repair levels remain limited to equipped armor, main hand and off hand
- redistributed XP is less efficient at lower Mending levels and becomes progressively more efficient toward Mending X
- a low-level Mending recipient remains less efficient to repair than a high-level Mending recipient, so upgrading Mending across the whole equipment set has value
- distribution should prioritize damaged eligible items rather than wasting repair on full-durability pieces
- linked-repair transfer efficiency is intentionally lossy even at the top end; Mending X caps redistributed repair efficiency at about 80% rather than reaching 100%
- the planned IV-X transfer-efficiency curve is: IV=40%, V=50%, VI=60%, VII=65%, VIII=70%, IX=75%, X=80%
- recipient Mending level also matters: lower-level Mending recipients are repaired less efficiently than higher-level recipients, so a full high-level Mending loadout remains meaningfully better than one Mending X item feeding many low-level pieces
- recipient-side linked-repair efficiency multipliers are: I=50%, II=55%, III=60%, IV=66%, V=72%, VI=78%, VII=84%, VIII=90%, IX=95%, X=100%
- effective linked-repair XP reaching a recipient is: **routed XP × source/router transfer efficiency × recipient efficiency multiplier**
- the recipient then converts the XP that actually reaches it using its own normal Mending repair rate: I=2 durability/XP, II=3 durability/XP, III-X=4 durability/XP
- linked-repair routing is controlled by the highest-level Mending item among currently equipped armor, main hand and off hand; ties prefer the more damaged item
- Mending I-III do not act as multi-item routers and retain ordinary single-item behavior
- a Mending IV-IX router can target equipped armor, main hand and off hand only
- a Mending X router can additionally target damaged Mending items anywhere in the player's inventory
- merely carrying a Mending X item in an ordinary inventory slot does not activate inventory-wide routing; the X item must be part of the active equipped/held router set
- routing prioritizes the most damaged eligible recipient by durability percentage; ties prefer the higher Mending level
- linked repair must preserve ordinary XP gain once all eligible Mending items are fully repaired

Design constraint: higher-level Mending should improve XP use across a maintained equipment set, not become passive repair for every inventory item or create unlimited repair throughput.

Mending mastery-specific effect:
- Mending does not use the normal mastery-50 branch selection
- at mastery 50, Mending unlocks **over-repair**: when the item's normal durability is already full, repair XP may begin filling a temporary additional-durability buffer instead of being wasted on that item
- the additional-durability capacity grows with mastery from about +5% of base maximum durability at mastery 50 to **+20% at mastery 100**
- the buffer is consumed before ordinary durability
- over-repair does not permanently increase the item's true maximum durability; it is a temporary per-item reserve
- the buffer persists with the ItemStack across ordinary inventory movement, equip/unequip and save/reload
- once both normal durability and the allowed over-repair buffer are full, ordinary XP handling resumes normally
- over-repair capacity scales linearly from +5% of base maximum durability at mastery 50 to +20% at mastery 100

### Frost Walker Runtime Toggle

Accepted direction:
- Frost Walker can be explicitly toggled ON/OFF while the enchanted boots are equipped
- the toggle input is **sneak + jump**; no dedicated keybind is added
- the input toggles state rather than only suppressing Frost Walker while the keys are held
- turning it OFF suppresses water-freezing behavior without removing or rewriting the enchantment
- turning it back ON restores the normal level-scaled Frost Walker behavior
- toggling gives clear player feedback, preferably a short action-bar message such as "Frost Walker: ON/OFF"
- toggle state must survive equip/unequip and save/reload
- the toggle state belongs to the enchanted boots/item rather than being a global player setting

Design constraint: higher-level Frost Walker should remain practical to wear in normal travel without forcing the player to freeze every nearby water surface continuously.

### Enchantment-Pool Bookshelves

Add bookshelf variants / bookshelf enchantment behavior that can expand the nearby Enchanting Table's candidate pool beyond ordinary table-available enchantments.

Accepted direction:
- some enchantments that normally never appear from a vanilla Enchanting Table can become eligible when the correct bookshelf condition is present
- this should extend the candidate pool rather than guarantee a specific enchantment
- the Arcane Bookshelf requires a trade-only material rather than being craftable entirely from ordinary gathered resources
- that material is **Arcane Folio / 秘術の書片**
- Arcane Folio is sold by level-4 (Expert) Librarians rather than obtained from normal crafting, mining or loot
- the initial base trade is 24 emeralds for 1 Arcane Folio, with 6 uses before restock
- Arcane Bookshelf crafting consumes 4 Arcane Folios plus 4 amethyst shards around a normal bookshelf
- these values are tuning defaults and can be adjusted after playtesting without changing the progression structure
- the trade-only material is supplied through villager trading, tying access to a functioning village economy
- once an Arcane Bookshelf is available, its special pool can cover otherwise table-excluded enchantments broadly; individual exceptions can still be made for technical/gameplay reasons
- an Arcane Bookshelf also contributes normal bookshelf-equivalent enchanting power; it is not a pool-only utility block
- Arcane Bookshelf count has staged effects rather than being only a binary unlock:
  - 1 Arcane Bookshelf: unlock the base Arcane pool containing Mending I and Frost Walker I-II
  - 3 Arcane Bookshelves: increase Arcane-pool candidate weight to about **1.35x** normal weighting
  - 5 Arcane Bookshelves: unlock the rarer Arcane pool containing Soul Speed I-III, Swift Sneak I-III and Wind Burst I-III; Arcane candidate weight becomes about **1.50x**
  - 10 Arcane Bookshelves: unlock over-cap / high-level Arcane rolls up to the configured level cap where the enchantment supports those levels; this includes Mending II-X, Frost Walker III-X, Soul Speed IV-X, Swift Sneak IV-X and Wind Burst IV-X under the current level-cap rules; Arcane candidate weight becomes about **1.75x**
  - 10 Arcane Bookshelves do not guarantee level X; they only make those levels eligible, with actual rolled level still depending on enchanting power / offer generation
  - 15 Arcane Bookshelves: maximize Arcane-pool weighting at about **2.0x** normal weighting and increase the relative weight of eligible over-cap Arcane levels by about **1.5x**
  - 15 Arcane Bookshelves do not guarantee an Arcane enchantment or level X, and ordinary enchanting-table candidates remain in the pool
  - these multipliers affect weighted selection only; they do not duplicate candidates or bypass compatibility rules
- normal bookshelves remain valid enchanting-power providers; Arcane Bookshelves can replace them physically but are much more expensive
- compatible with raised enchantment level caps and Growing Enchantments
- bookshelf state should be readable from the actual nearby enchanting setup rather than from a global unlock

Design constraint: access to special enchanting should reward maintaining viable villagers instead of simply imprisoning one trader indefinitely.

### Direct Enchanting-Table Reroll

Allow the Enchanting Table to reroll its offered enchantments without forcing the player to enchant disposable gear or books first.

Accepted direction:
- provide an explicit reroll interaction at the Enchanting Table
- rerolling replaces the current offer set
- do not require sacrificing an unrelated item merely to advance the enchantment seed
- rerolling costs player experience
- XP cost is the primary reroll friction; no disposable item enchantment is required
- reroll cost is fixed at 1 experience level per reroll; repeated rerolls do not escalate in price
- bookshelf-based pool expansion must affect rerolled offers normally
- over-cap enchantments, if obtainable through the table later, should participate through the same offer-generation path

Design constraint: remove the junk-enchant workaround while preserving meaningful choice and resource cost.


### Extended Enchanting Targets

Allow selected vanilla items that are normally not enchantable to receive ordinary enchantments.

Accepted initial targets:
- Furnace
- Blast Furnace
- Smoker
- Enchanting Table
- Arrow
- Spectral Arrow
- Tipped Arrow

Accepted direction:
- reuse existing vanilla enchantments rather than requiring a parallel enchantment family
- Crafting Tables are explicitly excluded from extended enchanting
- Efficiency on Furnace / Blast Furnace / Smoker increases processing speed by 10% per level: I=1.1x, V=1.5x, X=2.0x; 2.0x is the final cap
- Efficiency on an Enchanting Table does **not** directly add levels to the resulting enchantments; instead it raises the enchanting table's normal level/power ceiling beyond vanilla level 30
- Enchanting Table Efficiency raises the table ceiling by 10 levels per Efficiency level, capped at enchanting level 100
- progression is: none=30, Efficiency I=40, II=50, III=60, IV=70, V=80, VI=90, VII-X=100
- work-block enchantment effects are defined per supported block type below; enchantments with no defined effect are not eligible for that work block
- enchanted work blocks must retain their full ItemStack enchantment/mastery data while placed and restore it when broken
- arrows retain enchantments on their ItemStack, with the supported projectile-specific behaviors defined in the Arrow Effect Decisions section below
- compatible with raised enchantment level caps and Growing Enchantments



#### Recoverable Embedded Arrows

Accepted direction:
- when Multishot creates multiple projectiles from one ammunition item, only the **primary/original projectile** remains recoverable
- Multishot-created secondary projectiles are never stored for embedded-arrow recovery and never produce recoverable arrow items
- this rule applies equally to enchanted, spectral and tipped arrows and prevents one source arrow from becoming multiple recovered copies
- if Loyalty or another return behavior is involved, only the primary/original projectile may return as an item; secondary Multishot projectiles are disposable projectile instances
- arrows that successfully embed in a living target can be recovered instead of being permanently lost
- recovery preserves the exact arrow ItemStack, including enchantments and other components
- recovery occurs when the target dies; the embedded arrow is dropped with the victim's drops
- only arrows that were normally recoverable are stored for later recovery
- arrows fired in a non-recoverable state, such as Infinity/creative-only pickup cases, must not become duplication sources
- the system applies to normal, spectral and tipped arrows where technically valid

#### Direct Arrow Enchanting at the Enchanting Table

Accepted direction:
- Arrow, Spectral Arrow and Tipped Arrow may be enchanted directly at the Enchanting Table
- one enchanting action enchants **exactly one arrow item**, even when the input stack contains multiple arrows
- if a stacked arrow input is used, one arrow is split out as the enchanted result and the remaining arrows stay unenchanted
- lapis and player-level costs are paid once using the normal enchanting operation
- offer generation uses the same table power, Arcane Bookshelf, raised-level-cap and compatibility rules that apply to other supported enchanting targets
- this one-arrow direct enchanting path is intended to create valuable source/template arrows that can then be batch-copied at the Fletching Table for the full calculated XP cost

#### Enchanted Arrow Copying at the Fletching Table

Accepted direction:
- enchanted-arrow copying is performed at the Fletching Table
- copying requires one enchanted source arrow, compatible ordinary arrows, and player experience
- the source enchanted arrow is retained as the template
- the player may choose a **batch quantity** and copy multiple arrows in one operation
- copying N arrows consumes exactly N compatible ordinary arrows and creates exactly N copied arrows carrying the source arrow's enchantments/components relevant to the enchanted-arrow system
- XP is paid in one combined transaction for the whole batch
- per-copy XP cost is calculated as the sum of **enchantment level × that enchantment's anvil_cost** across all enchantments on the source arrow
- total batch cost is **per-copy XP cost × number of arrows copied**
- there is no extra bulk surcharge or discount; batching is a convenience feature only
- if the player lacks either the required ordinary arrows or the total XP cost, the requested batch cannot be completed
- multiple enchantments add together naturally; higher-level and higher-anvil-cost enchantments therefore cost more to duplicate
- do not maintain a separate hand-authored copy-price table unless a specific enchantment later proves to need an exception
- this copying route is intended to make recovered rare enchanted arrows valuable templates without making large stacks free


#### Infinity Core Behavior

Accepted direction:
- Infinity remains a **single-level enchantment**; its long-term growth comes from mastery branches rather than Infinity II-X
- Infinity is valid on both Bows and Crossbows
- Infinity and Mending are compatible on launchers
- base Infinity applies only to a completely ordinary, non-enchanted Arrow ammunition item
- enchanted arrows, Spectral Arrows, Tipped Arrows, fireworks and other special ammunition are not made free by Infinity
- ammunition is selected first using the launcher priority rules, then Infinity decides whether the selected source item is consumed
- with base Infinity, firing an ordinary arrow still requires at least one ordinary arrow source item to exist in the selected ammunition source; the source item is not consumed
- an ordinary projectile created by Infinity is non-recoverable and cannot become an item through embedded-arrow recovery, pickup, Loyalty-style return or similar recovery paths
- consuming a special / enchanted arrow from an Infinity launcher does **not** make that projectile non-recoverable merely because the launcher has Infinity; if the source ammunition was actually consumed, its ordinary recovery / Loyalty rules remain valid
- Multishot + ordinary Infinity ammunition consumes zero arrows, creates the normal Multishot projectile group, and all Infinity-generated projectile instances are non-recoverable
- Multishot + consumable special/enchanting ammunition consumes exactly one source item; only the primary/original projectile may be recovered or returned
- Infinity does not reduce launcher durability cost by itself; durability savings belong to the Rapid Infinity / Precision Infinity mastery branches
- Pure Infinity mastery removes the requirement to possess a seed ordinary arrow; it generates ordinary non-recoverable ammunition even when no ordinary Arrow ItemStack exists
- Pure Infinity never generates enchanted, spectral, tipped or other special ammunition

Design constraint: Infinity makes ordinary arrows effectively inexhaustible, but it must not erase the resource value of special or enchanted ammunition.

#### Quiver and Dedicated Ammo Slot

Accepted direction:
- add a dedicated **Quiver equipment slot** separate from armor, offhand and the normal inventory
- only Quiver-compatible items may occupy this slot
- a basic Quiver provides an internal ammunition inventory for arrows and other explicitly supported launcher ammunition
- launcher ammunition priority is **selected Quiver ammunition -> offhand ammunition -> ordinary inventory ammunition**
- if the selected Quiver slot is empty or contains ammunition invalid for the current launcher, continue to the offhand and then ordinary inventory rather than failing the shot immediately
- the launcher checks the equipped Quiver before falling back to loose ammunition in the player's ordinary inventory
- the Quiver stores exact ItemStacks, preserving tipped-arrow effects, spectral-arrow identity, enchantments and other relevant components
- enchanted arrows remain discrete ammunition items; the Quiver does not merge different enchanted/component variants merely because their base item id matches
- the currently selected Quiver ammunition type is explicit and persistent rather than being chosen unpredictably on every shot
- ordinary inventory arrows remain usable when no valid Quiver ammunition is selected/available
- the Quiver is a convenience/container system, not an ammunition duplicator and not an automatic crafting system
- Multishot still consumes at most one source ammunition item per shot group under the existing Multishot rules
- Infinity still only makes ordinary arrows free; placing special/enchanting arrows in the Quiver does not make them free
- Infinity is evaluated **after** ammunition selection: if the selected source item is an ordinary arrow, it is not consumed; if the selected source is enchanted/spectral/tipped/special ammunition, one source item is consumed normally
- if the selected Quiver slot contains an ordinary arrow and the launcher has Infinity, the shot does not consume that ordinary arrow
- if the selected Quiver slot contains an enchanted, spectral or tipped arrow, the shot consumes one source item normally unless a separate return/recovery mechanic returns it
- when all eligible Quiver ammunition for the selected type is exhausted, the launcher may fall back to ordinary inventory ammunition according to the normal ammo-priority rules
- Quiver contents and selected-ammo state persist through save/reload

Crafting:
- basic Quiver recipe: **6 Leather + 2 String**, with the center crafting-grid slot empty
- the initial design uses one Quiver tier only; no capacity-upgrade tree is required until playtesting shows a real need
- the Quiver should remain accessible in early survival and should not require a new progression-only material

Initial capacity / UX target:
- one equipped Quiver exposes **9 internal ammo slots** as the initial default
- the in-world Quiver HUD is **display-only** and normally hidden
- while a Bow or Crossbow is equipped/held, only the **currently selected ammunition** is shown persistently, including its icon and remaining count
- the full 9-slot Quiver overlay is not shown during ordinary play
- while holding a Bow or Crossbow, **Ctrl + mouse wheel** cycles through valid non-empty Quiver ammunition slots
- during Ctrl + mouse-wheel cycling, the full 9-slot Quiver overlay appears temporarily so the player can see the available ammunition choices and current selection
- the temporary full overlay fades/hides again shortly after cycling stops, leaving only the selected-ammunition indicator while the launcher remains equipped
- when no Bow or Crossbow is equipped/held, the in-world Quiver HUD is hidden entirely
- cycling skips empty / invalid slots and wraps around at the end
- ordinary mouse-wheel hotbar selection remains unchanged when Ctrl is not held
- switching ammunition through Ctrl + mouse wheel updates the persistent active Quiver slot and refreshes the selected-ammunition indicator
- opening the player inventory while a Quiver is equipped exposes the same 9 Quiver slots directly in the inventory UI
- arrows are inserted/removed from those inventory-visible Quiver slots using ordinary **drag-and-drop / click interactions**
- valid arrow stacks dropped onto a Quiver slot are inserted directly; invalid non-ammunition items are rejected
- one Quiver slot is designated as the active ammo selection at a time
- clicking a Quiver slot in the inventory UI may also set it as the active ammunition slot without requiring a dedicated keybind
- the active slot is visually highlighted both in the inventory UI and in the display-only in-world overlay

Design constraint: the Quiver should make mixed-arrow loadouts practical without making rare or enchanted ammunition free.

#### Unified Bow / Crossbow Enchantment Pool

Accepted direction:
- Bows and Crossbows share the same launcher-enchantment pool rather than keeping separate vanilla-exclusive sets
- the shared initial launcher pool is: **Power, Punch, Flame, Infinity, Quick Charge, Multishot, Piercing**
- Power, Punch and Flame work on either launcher through their ordinary projectile-facing meanings
- Infinity on either launcher applies to ordinary arrows; it does not make fireworks or other special projectile ammunition free
- Quick Charge on a Bow shortens the time needed to reach full draw; on a Crossbow it shortens reload/charge time
- Bow Quick Charge uses diminishing scaling: levels I-V reduce full-draw time by **8% per level**, levels VI-X reduce it by **4% per level**, for about **60% total reduction at Quick Charge X**
- Bow full-draw time is clamped to about **40% of vanilla**; higher effective levels cannot reduce it further
- Bow Quick Charge changes charge time only; it does not directly increase projectile damage
- Power's Quick Shot mastery branch remains distinct: Quick Charge shortens the time required for a full draw, while Quick Shot reduces the damage penalty of releasing before full draw
- Power, Punch, Flame and Infinity use the same projectile-facing meanings on Bow and Crossbow unless a weapon-specific rule explicitly says otherwise
- Multishot on a Bow fires the same three-projectile style used by the shared Multishot system; ammo consumption follows the one-ammo-per-shot-group model unless a later explicit exception is accepted
- Piercing on a Bow allows fired arrows to penetrate valid targets using the same Piercing count rules as Crossbow projectiles
- normal enchantment compatibility/conflict rules remain unless explicitly redesigned later; sharing the eligible launcher pool does not automatically make every launcher enchantment mutually compatible
- raised enchantment-level rules still apply, but any charge-time formula that would reach zero/negative duration must be clamped or given diminishing returns rather than becoming invalid

Design constraint: Bow and Crossbow should differ by their weapon mechanics, not by an arbitrary wall between their enchantment pools.

Launcher compatibility decisions:
- the launcher compatibility set is **Unbreaking, Mending, Power, Punch, Flame, Infinity, Quick Charge, Multishot and Piercing**
- all of these may coexist on the same Bow or Crossbow **except Multishot + Piercing**
- **Infinity and Mending are compatible** on both Bows and Crossbows; the vanilla mutual exclusion between them is removed for these launchers
- Mending continues to use the normal/higher-level Mending repair rules on the launcher
- **Multishot and Piercing remain mutually exclusive on the same launcher item**
- ammunition-side Piercing may still be used with a Multishot launcher because launcher and ammunition are separate enchantment sources
- Power, Punch, Flame and launcher-side Piercing apply to arrow-like ammunition; they are not reinterpreted as arbitrary modifiers for Crossbow-fired fireworks
- Quick Charge and Multishot remain valid weapon-level effects when a Crossbow fires fireworks
- Infinity never makes fireworks free
- Infinity affects ordinary arrows only; enchanted arrows, spectral arrows and tipped arrows remain consumable
- Multishot consumes one ammunition item for one shot group; it creates additional projectile instances rather than additional ammunition items
- when Multishot fires special or enchanted ammunition, only the primary projectile can ever be recovered/returned as an item under the separate recovery rules

Compatibility matrix:

| Launcher enchantment | Unbreaking | Mending | Power | Punch | Flame | Infinity | Quick Charge | Multishot | Piercing |
|---|---|---|---|---|---|---|---|---|---|
| Unbreaking | — | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Mending | Yes | — | Yes | Yes | Yes | **Yes** | Yes | Yes | Yes |
| Power | Yes | Yes | — | Yes | Yes | Yes | Yes | Yes | Yes |
| Punch | Yes | Yes | Yes | — | Yes | Yes | Yes | Yes | Yes |
| Flame | Yes | Yes | Yes | Yes | — | Yes | Yes | Yes | Yes |
| Infinity | Yes | **Yes** | Yes | Yes | Yes | — | Yes | Yes | Yes |
| Quick Charge | Yes | Yes | Yes | Yes | Yes | Yes | — | Yes | Yes |
| Multishot | Yes | Yes | Yes | Yes | Yes | Yes | Yes | — | **No** |
| Piercing | Yes | Yes | Yes | Yes | Yes | Yes | Yes | **No** | — |

Design note:
- this matrix is for enchantments stored on the launcher item itself
- ammunition enchantments are a separate source and follow the Launcher + Arrow Enchantment Stacking rules below


#### Accepted Arrow-Enchantment Candidate Set

The initial set of existing enchantments to support with arrow-specific behavior is:

- Power
- Punch
- Flame
- Piercing
- Sharpness
- Smite
- Bane of Arthropods
- Impaling
- Looting
- Breach
- Wind Burst
- Channeling
- Loyalty

Accepted direction:
- these are the initial supported candidates for normal, spectral and tipped arrows where technically meaningful
- arrow-specific behavior for this initial candidate set is defined in the Arrow Effect Decisions section below
- Density is intentionally excluded from arrow behavior; no fall-distance/downward-velocity damage mechanic is added for arrows
- do not force unrelated enchantments to gain artificial arrow behavior merely for completeness
- bow/crossbow enchantments and arrow enchantments may coexist; stacking rules are decided per effect where necessary


#### Arrow Enchantment Compatibility

Accepted direction:
- all currently supported arrow enchantments may **coexist on the same arrow ItemStack**
- there are no arrow-side mutual-exclusion pairs among the accepted initial arrow-enchantment set
- this includes allowing **Sharpness + Smite + Bane of Arthropods + Impaling** on the same arrow
- target-specific enchantments only contribute when their own normal target condition is satisfied; coexistence does not make every conditional effect apply to every target
- Power, Punch, Flame, Piercing, Sharpness, Smite, Bane of Arthropods, Impaling, Looting, Breach, Wind Burst, Channeling and Loyalty may therefore all be present together on one arrow
- compatibility restrictions on the launcher item remain separate and are not changed by this rule
- launcher + ammunition composition continues to follow the separate stacking rules below

Design constraint: arrow enchantment depth should come from combining effects and ammunition cost rather than from an artificial one-enchantment-per-role restriction.

#### Launcher + Arrow Enchantment Stacking

Accepted direction:
- launcher enchantments and arrow enchantments are evaluated as separate sources
- if two sources produce the **same mechanical effect**, do not add their levels together; use the stronger effective level/effect unless a specific rule below says otherwise
- if two same-named enchantments have intentionally different launcher-side and arrow-side meanings, both effects may apply
- launcher Power and arrow Power may coexist because launcher Power modifies shot damage while arrow Power preserves projectile speed over distance
- launcher Punch and arrow Punch do not stack levels; use the stronger effective Punch
- launcher Flame and arrow Flame do not duplicate ignition; use the stronger/longer effective Flame result
- launcher Piercing and arrow Piercing do not add levels; use the stronger effective Piercing count
- launcher Multishot applies the selected arrow's projectile-side enchantment behavior to every spawned projectile instance, subject to the separate rule that only the primary/original Multishot projectile is recoverable
- launcher Infinity does not make enchanted arrows, spectral arrows, tipped arrows, fireworks or other special ammunition free; ordinary arrows remain the Infinity baseline
- Quick Charge is launcher-side only
- arrow-side Sharpness, Smite, Bane of Arthropods, Impaling, Looting, Breach, Wind Burst, Channeling and Loyalty continue to function when fired from either Bow or Crossbow
- same-item incompatibility rules remain in force on the launcher itself, but launcher + ammunition composition may create combinations that would be impossible on one item alone
- example: a Multishot launcher may fire a Piercing enchanted arrow, producing multiple piercing projectile instances; this is allowed because the ammunition is a separate resource and is consumed/recovered under the arrow rules

Design constraint: avoid double-dipping identical mechanics while preserving useful launcher/ammunition combinations.

#### Loyalty Return Destination

Accepted direction:
- a returning Loyalty arrow preserves its exact ItemStack identity and relevant components
- return destination priority is:
  1. the **original Quiver slot** the arrow was fired from, if that slot still exists and can accept the returning stack
  2. another compatible **empty / mergeable Quiver slot**
  3. the player's ordinary inventory
  4. if no inventory destination can accept it, drop the arrow at the player's feet
- returning to the original Quiver slot must not overwrite a different ammunition stack that has since occupied that slot
- if the original slot now contains a compatible stack, the returning arrow may merge into it when normal stack rules allow
- if the projectile was fired from offhand or ordinary inventory rather than the Quiver, skip the original-Quiver-slot step and use the remaining fallback order
- Loyalty return never duplicates the source ammunition; exactly one recoverable primary projectile may become one returned item
- secondary Multishot projectiles remain non-returnable under the existing rules

Design constraint: Loyalty should restore ammunition to the player's existing ammo-management flow without silently replacing or deleting other ammunition.

#### Piercing + Loyalty Return Timing

Accepted direction:
- when an arrow has both Piercing and Loyalty, Loyalty does **not** begin returning on the first entity hit
- Loyalty does **not** begin returning merely because the arrow has consumed its available Piercing target count
- the arrow continues normal flight and resolves all valid impacts until its projectile flight ends
- **Loyalty return begins only when the arrow's flight has ended**
- flight-end handling may include becoming embedded/stationary in a block or otherwise entering the normal terminal state where the projectile would stop traveling
- once Loyalty return begins, the arrow is removed from any embedded-arrow death-drop path and follows the existing Loyalty return/recovery rules
- Multishot still allows only the primary/original projectile to return as an item; secondary projectile instances remain disposable

Design constraint: Piercing determines what the arrow can do during flight; Loyalty determines what happens after that flight is over.

#### Multi-hit Area / Weather Effect Limits

Accepted direction:
- no additional per-projectile cooldown is added to Wind Burst or Channeling when a Piercing arrow hits multiple targets
- no artificial per-flight trigger cap is added to Wind Burst or Channeling
- each qualifying Piercing hit may trigger the effect independently according to its normal conditions
- existing conditions such as Channeling weather/open-sky requirements still apply normally
- balancing should come from ammunition cost, enchantment acquisition, projectile pathing and the underlying effect strength rather than hidden anti-chain throttles

#### Piercing Multi-hit Effect Resolution

Accepted direction:
- when a Piercing arrow hits multiple valid entities during one flight, **impact-triggered arrow enchantment effects are evaluated independently for every entity hit**
- each pierced target may therefore receive the arrow's applicable Sharpness, Smite, Bane of Arthropods, Impaling, Punch, Flame, Breach, Wind Burst and Channeling behavior as appropriate
- target-conditional effects are checked separately for each target; for example, Smite applies only to undead targets even if the same arrow later pierces a non-undead target
- Breach is evaluated against each pierced target's own armor state
- Punch applies to each directly hit target rather than only the first target
- Wind Burst may trigger its impact-centered radial effect at each valid hit position
- Channeling may trigger at each qualifying hit position when its weather/open-sky conditions are satisfied
- Looting is evaluated independently for any target whose death is actually caused by the arrow
- one target's failed condition does not suppress the effect on later valid targets
- this per-hit resolution does not create additional recoverable arrow items; projectile recovery remains governed by the existing primary-projectile / Infinity / Multishot rules

Design constraint: Piercing should preserve the full identity of an enchanted arrow across its penetration path rather than treating later hits as stripped-down damage-only contacts.

#### Arrow Enchantment Level Scaling

Accepted final tuning for the initial arrow-enchantment set:

| Enchantment | Arrow-side level scaling |
|---|---|
| **Power** | Ordinary air-flight velocity decay is reduced by **8% per level**, capped by the supported X maximum: I=8%, V=40%, X=80%. Gravity and special-medium drag remain. |
| **Sharpness** | Direct impact bonus damage follows the Java-style Sharpness progression: **1.0 + 0.5 × (level - 1)** damage. I=+1.0, V=+3.0, X=+5.5. |
| **Smite** | Against qualifying undead, add **+2.5 damage per level**: I=+2.5, V=+12.5, X=+25.0. |
| **Bane of Arthropods** | Against qualifying arthropods, add **+2.5 damage per level**. Preserve the ordinary Bane slowdown behavior and extend its level-based duration progression through X rather than inventing a second arrow-only formula. |
| **Impaling** | Against targets that qualify under the accepted Impaling target rules, add **+2.5 damage per level**: I=+2.5, V=+12.5, X=+25.0. |
| **Punch** | Preserve the ordinary feel at I-II, then use diminishing post-cap growth. Effective knockback strength is I=1.0, II=2.0, then **+0.5 per level from III onward**: III=2.5, V=3.5, X=6.0. |
| **Flame** | Remains **level I only** under the general single-level rule. It uses ordinary flaming-arrow ignition behavior; there is no Flame II-X arrow progression. |
| **Piercing** | A projectile may pass through **level + 1 valid entities total**: I=2, IV=5, X=11. Every valid hit continues to resolve the arrow's other impact effects independently. |
| **Looting** | Use the ordinary Looting level directly for the kill's loot calculation and extend that normal level-based behavior through X. If another source supplies Looting, use the higher effective level rather than adding levels. |
| **Breach** | Reduce the target's armor effectiveness by **15% per level**, capped at **100%**: I=15%, IV=60%, VI=90%, VII-X=100%. Levels above the cap do not create negative armor effectiveness. |
| **Wind Burst** | Impact burst radius = **2.5 + 0.25 × (level - 1) blocks**: I=2.5, V=3.5, X=4.75. Radial impulse strength is **1.0x at I + 0.10x per level above I**, reaching 1.9x at X. Each Piercing hit may create its own burst. |
| **Channeling** | Remains **level I only** under the general single-level rule. Every qualifying open-sky hit during the accepted weather condition calls the normal full lightning effect; there is no Channeling II-X scaling. |
| **Loyalty** | Extends through X. Return delay after flight end is **max(1, 11 - level) ticks**: I=10 ticks, V=6, X=1. Return travel strength/speed is **1.0x at I + 0.15x per level above I**, reaching 2.35x at X. The returning projectile still uses homing toward its original shooter and the accepted return-destination priority. |

General arrow-scaling rules:
- the configured raised-enchantment cap still controls the highest obtainable level; X is the current default reference
- target-specific damage enchantments may coexist on one arrow, but each contributes only when its own target condition is satisfied
- no same-effect launcher + arrow double-dipping is introduced by these formulas; the existing launcher/ammunition stacking rules still apply
- when a formula has an explicit cap, levels above the point that reaches the cap remain valid enchantment levels but do not push that specific effect beyond the cap
- arrow-side single-level enchantments remain single-level unless separately redesigned later
- these values are the initial balance baseline and may be tuned after playtesting, but their mechanical roles and scaling shape are considered decided

#### Arrow Effect Decisions

Accepted:
- **Power**: reduces the arrow's normal in-flight velocity decay rather than directly adding impact damage. Each Power level reduces ordinary in-flight velocity decay by **8%**, giving 8% at I, 40% at V and **80% at X**. This reduction applies to the normal air-flight velocity-decay component only; gravity remains unchanged and special medium resistance such as water drag is not removed. Power X therefore preserves long-range speed strongly without making arrows perfectly lossless or permanently straight-flying.
- **Sharpness**: adds direct impact damage on hit. Its role is straightforward close-to-any-range damage rather than flight preservation.
- Power and Sharpness may coexist on the same arrow because they improve different parts of the shot.
- **Punch**: applies increased knockback to the directly hit target. Higher levels increase the target's displacement; this is a single-target control effect.
- **Wind Burst**: creates a radial wind-pressure impulse centered on the impact point, affecting nearby entities/items as appropriate. This is an area-control effect rather than a stronger version of Punch.
- when Punch and Wind Burst coexist, the directly hit target receives both the direct Punch knockback and the radial Wind Burst impulse.
- **Flame**: uses vanilla flaming-arrow behavior rather than inventing a separate fire system; it ignites hit targets and interacts with vanilla fire-arrow-responsive blocks/entities normally.
- **Channeling**: during thunderstorms, an impact under open sky calls lightning at the impact position. This may trigger on direct entity hits or on valid block impacts.
- Flame and Channeling may coexist; a qualifying Channeling impact may also apply the normal Flame behavior.
- **Piercing**: lets the arrow pass through multiple valid targets. Higher levels increase the number of targets that may be penetrated.
- **Breach**: reduces or bypasses part of the directly hit target's armor-based damage mitigation. It does not increase penetration count.
- when Piercing and Breach coexist, each target successfully penetrated by the arrow is evaluated with the arrow's Breach effect.
- **Smite**: applies the vanilla Smite target rules and scaling to arrow impact damage against undead targets.
- **Bane of Arthropods**: applies the vanilla arthropod target rules, bonus damage and slowdown behavior on arrow impact.
- **Impaling**: applies the vanilla Impaling target rules and scaling to arrow impact damage against qualifying aquatic/wet targets.
- these three enchantments intentionally reuse vanilla target classification and scaling instead of maintaining separate arrow-specific balance tables.
- **Looting**: applies when the enchanted arrow delivers the kill. If another applicable source already provides Looting, use the higher effective Looting level rather than adding the levels together.
- **Loyalty**: after a valid entity hit or block impact, the arrow returns to its original shooter instead of waiting for manual recovery. Higher Loyalty levels reduce return delay and/or increase return speed.
- Loyalty takes precedence over the embedded-arrow death-drop path: an arrow that begins returning is no longer stored as an embedded recoverable arrow on the target.


#### Work-block enchantment rule

Accepted direction:
- work blocks may receive only enchantments that have a defined, meaningful effect for that specific block type
- enchantments with no active work-block interpretation are excluded from that block's enchanting candidate pool and should not be applied merely for storage
- only enchantments with a natural, understandable interpretation gain work-block behavior
- do not invent arbitrary effects merely so every vanilla enchantment does something on every supported block
- if a new work-block effect is defined later, that enchantment can then be added to the corresponding block's eligible pool
- Furnace / Blast Furnace / Smoker Efficiency scales processing speed up to 2.0x at Efficiency X
- Enchanting Table Efficiency raises the table's enchanting level ceiling from vanilla 30 up to 100


#### Additional work-block enchantment decisions

Accepted:
- **Fortune on Furnace / Blast Furnace / Smoker** applies broadly to smelting outputs rather than being restricted to ores or a hand-authored allowlist
- Fortune may increase the resulting output quantity for any normally smeltable recipe; balancing should come from the Fortune scaling itself rather than excluding food, metals, stone, etc.
- **Fortune on an Enchanting Table** increases how many enchantments a single enchanting operation tends to apply
- Enchanting Table Efficiency and Fortune have separate roles: Efficiency raises enchanting power/level ceiling, while Fortune improves the vanilla-style continuation / multi-enchantment roll
- Fortune does **not** add a simple hard maximum such as +1 enchantment per Fortune level; vanilla enchanting already has no useful fixed enchantment-count cap
- at a high-power setup around internal enchanting level 100, with enough mutually compatible candidates available, **Fortune X should target roughly 8 enchantments on average**
- Fortune modifies the vanilla continuation decay rather than adding a hard enchantment-count cap
- after each successful additional-enchantment roll, the next continuation level uses: **nextLevel = currentLevel × (0.50 + FortuneLevel × 0.035)**
- no Fortune keeps the vanilla-equivalent 50% decay
- Fortune X keeps 85% of the current continuation level after each successful extra roll, producing about 8.3 enchantments on average in an unlimited-compatible-candidate level-100 model
- lower Fortune levels therefore scale smoothly toward that endpoint rather than jumping directly to large multi-enchant rolls
- the formula is the initial accepted tuning rule; real gameplay should still be validated against candidate-pool exhaustion and incompatibility, and only adjusted if the observed average materially misses the intended curve
- normal enchantment compatibility/conflict rules still apply; Fortune does not force mutually exclusive enchantments together
- the table does not fabricate extra enchantments merely to hit the target average when too few valid candidates exist
- Furnace / Blast Furnace / Smoker Fortune grants a **5% chance per Fortune level** to produce one additional copy of the normal recipe output
- Fortune I = 5%, V = 25%, X = 50%
- the bonus applies broadly to normal smelting recipes rather than an allowlist
- one successful Fortune roll adds exactly +1 normal output item; Fortune does not multiply the entire stack

## Accepted transport / alchemy / explosives tweaks

### Potion Mixing
Allow selected brewed potions to be combined into weaker multi-effect mixtures.
- Mixed effects are weaker/shorter than dedicated potions.
- Opposing effects may create special reactions instead of simply stacking.
- Brewing remains useful; mixing is flexibility, not a strict upgrade.
- Keep recipes/data-driven where possible.

### TNT Design
Allow TNT behavior to be customized through material composition or explicit crafting variants.
Possible parameters:
- blast radius
- entity damage
- block destruction
- fuse duration
- wind-pressure output
- shaped/directional bias later

The goal is not merely "bigger TNT", but choosing what kind of explosion is needed.

### Coupled Minecarts
Allow minecarts to be linked into trains using chains or another simple coupling interaction.
- velocity and pulling forces propagate through the consist
- cargo/passenger carts can be mixed
- slopes, braking and high-speed collisions matter
- integrates with uncapped minecart speed
- coupling must remain physically understandable rather than becoming invisible inventory logistics

Design constraint: trains should enable engineering, transport and accidents without turning into a separate rail-management game.


## Accepted world-generation overhaul

### Continental Oceans and Isolated Islands
Add an optional large-scale overworld generation mode inspired by older Minecraft's stronger land/ocean separation.

Target characteristics:
- genuinely vast oceans that take meaningful time to cross
- large continents separated by real ocean basins instead of frequent narrow water gaps
- isolated islands and small island chains far from continental coasts
- occasional remote archipelagos worth discovering
- stronger sense that crossing an ocean is a journey and that distant landmasses are geographically distinct
- preserve modern biomes, caves, structures and vertical terrain where practical rather than recreating an old generator byte-for-byte
- coastline scale should vary: some continents have long continuous coasts, others broken peninsulas and archipelagos
- rare very large islands can function almost like miniature continents
- avoid filling every ocean with constant land fragments; empty sea is an intentional part of the experience

Integration goals:
- boats, maps and long-distance trade become more meaningful; macro geography may imply routes, but no continuous ocean-current physics is required
- regional trade value benefits from real geographic separation
- villages and future caravans/ports can develop differently across continents
- exploration rewards should account for the greater travel commitment
- portal travel becomes strategically important without making surface travel obsolete

Configuration:
- feature toggle
- continent scale
- ocean scale
- island frequency
- archipelago frequency
- minimum separation bias between major landmasses

Compatibility constraint:
This mode should primarily affect newly generated chunks/worlds. Existing worlds must not silently regenerate old terrain, and worldgen changes should remain optional because they can conflict with other terrain-generation mods.


### Continental River Networks

Add an optional macro-scale river-generation layer integrated with the accepted continental world-generation mode.

Accepted direction:
- rivers are generated as **connected drainage networks** rather than as unrelated short water features
- continental terrain first establishes broad elevation/highland structure, then derives drainage basins and downstream flow paths
- the intended topology is **highlands -> streams/tributaries -> main river -> lake/wetland/ocean outlet**
- rivers should normally trend downhill and should not terminate arbitrarily without a plausible sink/outlet
- tributaries may merge into progressively larger downstream rivers
- lakes may participate in the network with inflow and outflow rivers; a smaller number of closed-basin lakes may still exist where terrain justifies them
- river generation should preserve modern biome/terrain variety while making long continuous waterways substantially more common than in vanilla-like fragmented generation

Initial river scale targets:
- **Stream:** roughly 2-4 blocks wide, commonly 1-2 blocks deep
- **Tributary:** roughly 4-8 blocks wide
- **River:** roughly 8-16 blocks wide, commonly navigable by ordinary boats where terrain permits
- **Major River:** roughly 16-32 blocks wide, generally suitable for larger cargo-watercraft logistics where uninterrupted
- river mouths/deltas may widen beyond the normal upstream width
- downstream width/depth should generally increase as tributaries merge rather than every river using one fixed size

Terrain shaping:
- rivers interact with surrounding terrain rather than being painted onto a finished surface
- mountainous terrain favors narrow valleys, gorges, rapids and occasional waterfalls
- plains favor broader channels, floodplains and stronger meandering
- large mature rivers may create wider lowland corridors
- occasional oxbow-like abandoned bends / floodplain water features are acceptable where generation supports them
- river mouths may form deltas or broader estuarine terrain
- not every river is guaranteed end-to-end boat navigation; rapids, waterfalls and terrain breaks are valid geographic obstacles

Navigation / logistics integration:
- river/ocean flow direction is **not simulated as continuous boat physics**
- generated drainage direction may exist as world-generation/planning metadata, but it does not apply current forces, passive drift or per-tick acceleration to boats/entities
- water logistics are route/path based: the system cares whether a continuous navigable water corridor exists, not whether the water physically pushes the craft downstream
- this avoids adding a persistent fluid-current simulation cost to loaded chunks
- long lowland river sections should often provide meaningful continuous boat navigation
- non-navigable interruptions may later support **portage** logistics: unload at an upstream dock, transport goods overland, and resume at a downstream dock
- village River Corridor recognition, docks, fishing sites, bridge planning and Cargo Raft logistics use the generated river network rather than maintaining a separate artificial water graph
- rivers remain physical terrain; logistics still validate actual water continuity and clearance

Settlement / structure integration:
- village/structure placement may modestly favor useful river geography such as banks, confluences, lake shores and river mouths where other placement constraints allow
- this bias should create plausible river settlements without forcing every village onto water
- generated rivers may naturally influence district boundaries, bridge demand, fishing economies, ports and regional trade routes

Generation order target:
1. major continent / ocean placement
2. broad mountain and elevation structure
3. drainage-basin derivation
4. river-network routing
5. lakes / sinks / outlets
6. river valley, floodplain and channel shaping
7. biome/detail integration
8. villages and other structures

Configuration:
- feature toggle
- river density
- major-river frequency
- river width scale
- meander strength
- lake frequency
- waterfall / rapid frequency
- delta frequency

Compatibility constraint:
- this system primarily affects newly generated terrain and must not silently regenerate existing chunks
- it remains optional because macro terrain/river generation can conflict with other world-generation mods

Design constraint: generate rivers as part of continental geography so settlement simulation, roads, bridges, fishing and water logistics all operate on the same coherent terrain.

### Large Boats / Cargo Rafts
Add a larger watercraft tier between vanilla boats and full ship mods.
Planned direction:
- carry multiple players/mobs plus a modest amount of cargo
- visibly slower/heavier than a normal boat when loaded
- compatible with mooring and existing wind-pressure interactions where applicable, but does **not** require simulated river/ocean currents
- usable for long ocean crossings created by continental worldgen
- remain simple enough to steer directly without a separate ship-management UI

### Ocean Drift Debris
Add sparse floating debris and drift cargo to large oceans.
Possible contents:
- logs/planks
- barrels/crates
- rope/chain-like materials
- damaged tools
- shipwreck-adjacent loot
- occasional named or story-like junk

Debris can slowly move with current/wind systems later and should make long crossings less empty without filling every ocean with constant rewards.

Design constraint: both features should make ocean travel more playable without turning AsobibaTweaks into a full naval mod.


## Accepted giant-organism tweaks

### Giant Crops
Allow very rare oversized crop outcomes during ordinary farming.

Planned direction:
- selected crops can rarely mature into visibly oversized variants
- giant crops occupy more space and take longer to finish than normal crops
- harvest yield is meaningfully higher, but not proportional enough to replace ordinary farming
- giant variants should be rare enough to feel like an event rather than an optimization target
- weather, soil quality or special circumstances may influence the chance later, but no progression system is required
- harvesting should feel physical where practical: a giant pumpkin/melon may need multiple breaks or produce several drops

### Giant Mobs
Allow very rare oversized variants of ordinary mobs.

Core behavior:
- size increase affects hitbox, reach/step height where safe, mass, knockback resistance and some movement behavior
- health and damage scale modestly rather than linearly with volume
- drops increase somewhat, but never enough to make forced giant-mob farming the dominant resource strategy
- hostile giants are dangerous encounters, not full boss fights
- passive giants can still participate in Universal Bond where their entity type is otherwise supported
- carrying rules must reject creatures that become too large
- wind-pressure effects treat giant mobs as heavier targets
- some mobs get species-specific giant behavior:
  - giant creeper: larger blast and wind pressure, but not absurd world deletion
  - giant spider: better obstacle traversal / wider web threat later
  - giant skeleton: stronger bow knockback and slower handling
  - giant zombie: high mass and door-breaking pressure
  - giant chicken: ridiculous but mostly harmless
  - giant slime/magma cube should integrate with vanilla size mechanics instead of duplicating them
- bosses and technically fragile entities are excluded by default

Spawn / inheritance policy:
- giantism can occur rarely on natural spawn and, optionally, at birth
- it is not automatically hereditary by default, preventing exponential giant-animal farms
- frequency is configurable globally and per broad mob category

Design constraint: giant organisms should create memorable emergent encounters ("why is that cow enormous?") without becoming a separate RPG rarity/level system.


### Fletching Table Expansion
Give the vanilla Fletching Table a real survival use without turning it into a separate crafting tree.

Planned direction:
- bulk arrow crafting
- lightweight arrows: faster flight, slightly lower damage
- heavy arrows: slower flight, stronger knockback / better momentum
- utility arrow variants can reuse existing tweak systems where sensible, such as torch-placement arrows later
- preserve vanilla arrows and tipped arrows as the baseline
- avoid adding a large family of new materials solely for arrow crafting

Design constraint: this should feel like completing an unfinished vanilla workstation, not introducing a full archery overhaul.


## Accepted riding / creature interaction tweaks

### Expanded Riding
Allow saddles or simple tack to work with a broader set of suitable mobs.
- riding behavior should remain species-specific rather than giving every mob horse controls
- some mounts are slow, awkward, jumpy or difficult to steer
- large/giant variants may support riding where physically sensible
- avoid turning every tameable creature into a strictly better horse

### Mob-on-Mob Riding
Allow selected mobs to mount other suitable mobs in emergent combinations.
- small mobs can ride larger mobs when size/AI rules permit
- some combinations may occur naturally at low probability
- bonded mobs can potentially be commanded into simple riding arrangements later
- preserve readability and avoid recursive absurd stacks by default

Design constraint: these systems should create funny or useful situations without becoming a full mount-breeding framework.

## Accepted Nether fishing expansion

### Nether / Lava Fishing
Allow fishing in lava with a suitably prepared rod or other modest vanilla-adjacent requirement.
- ordinary fishing gear should not trivially work in lava
- loot tables should be distinct from overworld fishing
- include Nether junk, materials and living catches
- fishing remains an activity, not an infinite rare-resource exploit

### Nether Fish
Add a small set of actual lava-dwelling fish or fish-like mobs rather than making lava fishing purely item-table based.
Possible direction:
- 2-4 species with clear silhouettes and simple behaviors
- some swim in open lava lakes, some hug basalt/delta edges, some are rare deep-lava catches
- edible variants should have Nether-appropriate cooking/use quirks
- avoid adding a large aquatic bestiary or separate progression tree

Design constraint: Nether fish should make lava feel inhabited and support fishing, not turn the Nether into a second ocean biome.


### Armor Stand Loadout Swap
Allow the player to swap their currently equipped armor set with an armor stand's equipped set in one interaction.
- preserves item durability, enchantments, trims, names and custom data
- empty slots swap naturally rather than deleting items
- should work as a physical loadout rack without introducing a separate loadout GUI
- optional handling for held items can be considered later, but armor is the initial scope

Design constraint: armor stands should become practical equipment storage while remaining ordinary vanilla entities.


## Accepted small vanilla-adjacent behavior tweaks

### Linked Double Doors
Adjacent matching doors can open/close together from a normal interaction.
- sneak-interact can operate only the targeted half when needed
- preserve redstone behavior predictably
- avoid linking unrelated nearby doors

### Enderman Micro-Building
Endermen can very rarely place carried blocks into tiny intentional-looking arrangements rather than always placing them independently.
- structures remain extremely small, roughly 2-5 blocks
- use only blocks the Enderman actually carried
- no valuable loot or progression reward
- intended to leave strange, harmless traces in the world

### Parrot Perches
Parrots can perch on a wider set of narrow or perch-like vanilla blocks.
Potential examples:
- fences and walls
- chains
- end rods
- armor stands where collision permits
- selected signs / rails / similar narrow surfaces

Perching should primarily be behavioral and visual, not a new progression or pet-stat system.


### Auto-Connected Map Walls
Adjacent maps placed in item frames can recognize neighboring map tiles and present themselves as one continuous map wall.
- preserve ordinary vanilla maps and item frames
- reduce visual seams / orientation mistakes where practical
- make large exploration-map rooms easier to maintain
- no separate map-management GUI required

### Displayed Elytra on Armor Stands
Armor stands can display Elytra in an opened-wing presentation pose.
- visual/display-only behavior
- preserve the actual Elytra item and all of its data
- intended for equipment rooms, trophies and museums
- should coexist naturally with armor-stand loadout swapping


### Mob Gatherings
Very rarely, a small group of same-species mobs can gather in an oddly deliberate arrangement for a short time.
- small circles, loose lines or facing inward are preferred over random clustering
- no loot bonus, quest marker or guaranteed secret
- approaching the group usually breaks the gathering and returns mobs to normal behavior
- passive/neutral mobs are the safest initial scope
- frequency must remain low enough that seeing one feels unusual

Design constraint: the event should create memorable unexplained moments, not become a farmable encounter type.


### Dispenser-Fired Ender Pearls
Allow dispensers to fire Ender Pearls as real teleport projectiles rather than merely ejecting them as items.

Planned direction:
- pearls launched from a dispenser behave like normal thrown Ender Pearls
- ownership should be attributable to the triggering player where that is practical and unambiguous
- when no valid owner exists, configurable neutral behavior should avoid accidental arbitrary-player teleportation
- preserve collision, teleport damage and ordinary pearl travel rules
- support simple redstone-built pearl launchers and transport contraptions without adding a dedicated launcher block
- interaction with temporary pearl return points should remain explicit rather than automatically merging the two systems

Design constraint: this should extend the vanilla dispenser vocabulary, not create a separate teleport-network system.


### High-Speed Minecart Dismount
Allow players to intentionally jump/dismount from a moving minecart while preserving much of the cart's current momentum.
- especially relevant with uncapped minecart speed
- resulting launch can be useful, dangerous, or ridiculous depending on speed and terrain
- preserve fall damage / collision consequences rather than turning it into a safe movement exploit
- should feel like a natural extension of riding physics, not a separate ability

### Rare Armor Stand Pose Drift
Armor stands can very rarely change pose slightly while nobody is directly observing them.
- tiny head/arm/body angle changes only
- no item movement, duplication or equipment changes
- frequency must be extremely low
- should look plausibly like the player may have misremembered the original pose
- optional stronger mode can allow a small set of more noticeable poses, but default behavior should remain subtle

Design constraint: this is an unexplained world oddity, not a horror system. It should create occasional "was it always like that?" moments without constant jump-scare behavior.
