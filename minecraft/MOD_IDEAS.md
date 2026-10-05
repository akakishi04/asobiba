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
