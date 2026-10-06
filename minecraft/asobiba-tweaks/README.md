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
- **Parrot perches**
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
- Construction consumes real village storage
- Biome/local supplied materials influence architecture
- Low-experience carpenters can make harmless cosmetic substitutions
- Carpenter experience improves work rate
- Housing / storage shortages influence build plans
- **Forester**, **Quarry worker**, **Porter**, **Quartermaster** and farmer logistics
- Shepherds can generate real wool supply for construction
- Villagers use stored wool + planks to make beds during construction
- Roads and simple water-crossing bridges
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
- **Play Time Limit** — warning-only or disconnect mode, disabled by default

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
