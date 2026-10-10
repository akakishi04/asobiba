# Asobiba Tweaks

A configurable collection of vanilla-adjacent Minecraft experiments for **Minecraft 1.21.1 / NeoForge 21.1.219**.

The guiding rule is simple: features should be independently optional, should reuse vanilla interaction vocabulary where practical, and should create useful or memorable situations without forcing a single progression path.

## Configuration

Open **Mods -> Asobiba Tweaks -> Config**.

Nearly every gameplay family has its own switch. Important defaults:

- **Continental world generation:** OFF by default. It changes only newly generated chunks.
- **Play Time Limit:** OFF by default.
- **Universal Bond boss support:** OFF by default.
- Ordinary gameplay tweaks, oddities, enchantment mastery, Nether fishing, village simulation and transport extensions are ON by default and can be disabled individually.

## Implemented feature families

### Items, enchantments and crafting

- **Growing Items** — damageable items gain use XP, repair chances and individual history.
- **Pickaxe mining-tier mutation** — exceptional pickaxes can rarely improve their effective harvest tier.
- **Growing Enchantments** — enchantments keep independent mastery.
- **Mastery branches** — mature enchantments can select side-grade behavior.
- **Curse growth** — curses remain drawbacks but can gain small compensating behavior.
- **Fortune / Silk Touch switching** — selected mutually exclusive enchantments can coexist with one active mode.
- **Mastery inheritance** — anvil replacement can carry part of enchantment mastery forward.
- **Uncapped anvil cost** — removes the survival `Too Expensive!` rejection while retaining XP cost.
- **Potion mixing** — combine two potions at a cauldron into a weaker mixed potion.
- **Fletching Table expansion** — bulk arrow crafting plus lightweight and heavyweight arrow tuning.
- **Field repair** — inefficient material-based repairs away from an anvil.

### Independent enchantments and quiet oddities

All four enchantments are level I and available through ordinary enchanting-table, enchanted-book trade and random-loot pools. Their behavior can be disabled separately without removing registry entries.

- **Rooted / 根付き** (Hoe): harvesting mature Wheat, Carrots, Potatoes or Beetroot replants the same safe cell using one matching real inventory/offhand planting item. No seed means ordinary harvesting only; it never harvests an area or creates free crops.
- **Ominous / 不吉** (Armor): at most +25% relative chance for already eligible harmless ambience, regardless of armor-piece count. It never creates Bad Omen, hostile spawns or rewards and never strengthens Afterimage.
- **Afterimage / 残像** (Chestplate): a genuine grounded sprint departure leaves a brief translucent decoy. Default lifetime 1.5 seconds / cooldown 15 seconds, with at most three nearby ordinary hostiles already targeting you redirected temporarily. It has no collision, damage, copied inventory, drops or saved phantom targets.
- **Nod / 頷き** (Helmet): face an idle villager and deliberately crouch after standing briefly. They may nod once; children can respond too. No reputation, trade or work benefits.
- **Chicken Conspiracy / 鶏の密談**: three to six nearby idle chickens briefly face the same direction and resume normally when approached. Independent of Mob Gatherings.
- Seven very rare natural events, also possible without Ominous: a distant reply to a nighttime village bell, soft unseen footsteps, a knock by a closed wooden door, smoke from an extinguished campfire, an unusual animal glance, a tiny backward particle breeze, and a quiet unclaimed chord. They never change blocks, spawn an invisible actor or grant loot.

Already-loaded eligibility, priority AI, individual toggles, shared cooldowns and finite query/particle/sound limits are authoritative. See `IMPLEMENTATION_DECISIONS.md` for exact bounds and `ACCEPTANCE_MATRIX.md` for automated versus manual verification.

### Movement and physical interaction

- **Wall Kick**
- **Sliding**
- **Ledge Climb**
- **Weapon throwing**
- **Torch throwing**
- **Carry small mobs**
- **Expanded riding** for more suitable mobs
- **Mob-on-mob riding**
- **Expanded Fishing Rod** pulling dropped items and mobs
- **Extinguish primed creepers** with a water bottle
- **Temporary Ender Pearl return point**
- **Firework propulsion** for selected entities and objects
- **Dispenser-fired Ender Pearls**

### Minecarts, explosions and wind pressure

- **Uncapped minecart rail speed**
- **Speed-scaled minecart collision damage**
- **Minecart momentum dismount**
- **Chain-coupled minecart trains**
- **Blast / slipstream wind pressure**
- **Wind Pressure Resistance** armor enchantment
- **TNT design** — tune power, fuse, block damage, fire and wind output; designs persist with the world

### Mobs and odd world behavior

- **Universal Bond** — generic bonding, owner safety and Follow / Stay behavior for mobs
- **Giant mobs** with real scale/hitbox changes, restrained stat scaling and species-specific behavior
- **Giant crops**
- **Rare mob gatherings**
- **Enderman micro-building**
- **Cloud line** — rare, differently sized square clouds drift in a neat row and gradually disperse. This is an independently configurable local sky cosmetic.
- **Villager armor-stand imitation** — a passing idle villager briefly lines up beside a nearby armor stand, faces the same way, then returns to ordinary activity. Work and danger take priority.
- **Endermen gazing into the void** — in the End, a rare small group walks short, verified solid routes to spaced positions inside an island rim, looks outward, and returns to ordinary behavior one by one. Combat and anger take priority; no teleporting, spawning or rewards.
- **Parrot perches**
- **Snow Golem head tilt** — very rarely, a calm nearby golem is already holding its head/pumpkin slightly askew when you look; looking away and back restores its normal pose. Client-only cosmetic, independently configurable.
- **Rare armor-stand pose drift**
- **Armor Stand loadout swap**
- **Opened Elytra display on Armor Stands**
- **Linked double doors**

### World folklore

- Seed-specific hidden folklore rules
- True, false and incomplete rumors
- Persistent local place memory and ritual history
- Tiny player-created ritual responses
- **Moon Toss / Lunar Offering** with delayed, seed-influenced returns

These systems intentionally avoid exposing the exact hidden rule as a checklist.

### Ocean and world generation

- Optional **continental ocean worldgen** with large separated landmasses
- Configurable continent scale, separation, island frequency and archipelago frequency
- **Large cargo rafts** based on upgraded chest boats
- **Ocean drift debris**
- **Auto-connected map walls**
- Slow **forest-edge regeneration**

The continental generator is deliberately **OFF by default** because enabling it changes newly generated Overworld chunks.

### Nether fishing

- Heat-treat a fishing rod with magma cream
- Fish directly in lava
- Distinct Nether fishing loot
- Three lava-dwelling creatures:
  - Lava Minnow
  - Emberfin
  - Basalt Eel
- Natural Nether-fish spawning can be disabled separately from lava fishing
- Each fish has a small food quirk

### Village simulation

The village family is resource-backed rather than free structure spawning.

- **Carpenter profession** and Carpenter Workbench
- Carpenter builds structures progressively
- Functional `craft_hall_5x5` workshop for local Toolsmith/Mason job-site shortages, with a smithing table, stonecutter and shared barrel; finished fixtures or their actual recipe ingredients are consumed
- Construction consumes real village storage
- Biome/local supplied materials influence architecture
- Low-experience carpenters can make harmless cosmetic substitutions
- Carpenter experience improves work rate
- Housing / storage shortages influence build plans
- **Forester**, **Quarry worker**, **Porter**, **Quartermaster** and farmer logistics
- Incremental, paid roof/wall/foundation repair for village-owned houses, warehouses and workshops; no overwriting player-edited blocks
- Housing pressure considers recognized homes, chronic missing home memories, welfare, food supply, active projects and a persistent three-day cooldown; original one-bed huts can be furnished with a second *real* White Bed before building new detached houses
- Profession-driven village work halls for 11 additional vanilla careers, with gabled, stone-roof and ventilated building variants plus real workstations/Barrels
- Shepherds can generate real wool supply for construction
- Villagers use stored wool + planks to make beds during construction
- Roads are selected by loaded-terrain cost instead of unverified straight fallbacks; qualifying 2-12-block crossings gain staged real raised bridges with waterlogged outboard piers, walkable shore stairs and railings (wood/mixed/stone), without filling the central boat channel
- Physical river landings built by Carpenters after a navigable-river survey: three plank deck sections and a recognized storage Barrel, with actual material withdrawals and no water block replacement
- Dock-to-dock route discovery along verified already-loaded source water, without teleporting cargo
- Porter first/last-mile deliveries connect recognized core and Outpost warehouses to the physically built dock Barrels; a persisted route receipt tracks each delivered item until a real Porter picks it up, and return boats may carry actual reverse freight
- Experimental autonomous real ChestBoat cargo trips between finished dock Barrels, **ON by default** via `village.experimentalRiverCargo = true`. A real Oak Chest Boat item must be present in the source dock's recognized storage; no synthetic boat or hidden cargo inventory is created. On existing installations, a previously generated `config/asobibatweaks-common.toml` can still explicitly contain `false`; change that entry to `true` to enable it there.
- Satellite outposts and physical settler movement
- Fire emergencies and reconstruction pressure
- Refugee / migration behavior after severe failure
- Settlement-aware breeding pressure
- Regional trade value
- Actual public-works requests derived from missing resources
- Passive mobs and villagers can make lightweight use of shelters and campfire spaces

Village subsystems have individual config switches in addition to a master village-simulation switch.

### Session / daily-life features

- **Daily Favor** — a small deterministic activity bonus for the current Minecraft day
- **Daily Play Time Limit** — saved per-world/per-player daily time budget, real-calendar played-day count and remaining-time HUD; disconnects at the cap and rejects same-date re-entry. Opt-in per world.

## World safety

AsobibaTweaks is designed so disabling an optional gameplay system does not make the world unloadable.

Features that add persistent registered content, such as Nether fish or the Carpenter Workbench, remain registered even when their behavior is disabled. Configuration disables the gameplay behavior rather than deleting registry entries.

## Development status

The accepted implementation backlog in `../MOD_IDEAS.md` now has an MVP implementation in code.

CI performs:

1. Java / NeoForge build for AsobibaTweaks.
2. A dedicated-server smoke start, which exercises registries, mixins and datapack loading.
3. A build of the separate Minecraft data-logger mod.

Actual gameplay balance, visuals and long-running world simulation still require in-game playtesting.


## Daily play timer settings

At world creation, open **More → Game Rules** and find the daily play timer settings under **Player**. Japanese labels are provided. New and existing worlds default to disabled; selecting the timer is explicit.

- `asobibaDailyPlayTimeEnabled`: enable the daily limit (default `false`).
- `asobibaDailyPlayTimeLimitMinutes`: daily allowance, 1–1440 minutes (default `120`).
- `asobibaDailyPlayTimeResetUtcOffsetMinutes`: real-calendar midnight's fixed UTC offset, −840 to +840 minutes (default `540`, Japan/UTC+9). This is a fixed offset, not an automatic daylight-saving timezone.

Existing worlds and dedicated servers use the same world-saved rules. An operator can run `/gamerule asobibaDailyPlayTimeEnabled true`, `/gamerule asobibaDailyPlayTimeLimitMinutes 120`, and `/gamerule asobibaDailyPlayTimeResetUtcOffsetMinutes 540`.

The HUD shows the number of different real-calendar dates actually played and today's remaining time. Rejoining on the same date does not add a day; skipped dates do not count; sleeping in Minecraft does not advance this counter. Offline time and a genuinely paused integrated server are excluded. Disabling the timer pauses accounting while retaining previous records; re-enabling resumes the saved budget. The limit exits the world/server, not Minecraft or the operating system.

Legacy global `playTimeLimit.*` session settings are retained only for configuration compatibility and no longer enforce limits. They do not silently enable the new world rule. Old versions stored no daily history, so historical played dates cannot be backfilled: counting starts with actual play while the new timer is enabled. World administrators can change rules/files and system clocks; this is a playtime aid, not tamper-resistant parental-control software.
