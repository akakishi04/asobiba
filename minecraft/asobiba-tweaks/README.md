# Asobiba Tweaks

A collection of small optional gameplay ideas. Every feature is independently configurable from NeoForge's in-game config screen.

## Current features

### Growing Items

Enabled by default.

- Durable items gain growth XP from block breaking and kills.
- Growth data is stored on the individual ItemStack.
- Item tooltip shows growth level and XP.
- Higher levels grant a small durability-repair chance.
- Pickaxes can rarely gain an **effective mining-tier upgrade** when they level.
- Default maximum mining-tier bonus is +2, so an exceptional wooden pickaxe can eventually harvest iron-tier blocks without making every starter tool endgame gear.

### Daily Favor

Enabled by default.

Each Minecraft day deterministically selects one small activity bonus:

- Mining
- Logging
- Farming
- Hunting

Matching actions have a configurable chance to grant a tiny XP reward. The goal is to make the player think "maybe I'll do that today" without forcing a daily quest.

### Universal Bond

Enabled by default.

- Sneak + right-click a Mob with an accepted gift to build Bond.
- Bond reaches 100 -> that Mob becomes bonded to that player.
- Existing animal breeding food works as a gift.
- Hostile/special mobs have simple themed gifts; unknown mobs fall back to emeralds.
- Bonded mobs stop targeting/damaging their owner.
- Owner friendly fire is disabled by default.
- Pathfinding mobs can follow their owner.
- Sneak + empty-hand right-click toggles **Follow / Stay**.
- Ender Dragon and Wither bonding exists behind an experimental config toggle and is OFF by default.

This is a generic base. Mob-specific pet abilities come later rather than hardcoding dozens of custom AI rewrites into the first pass.

### Play Time Limit

Disabled by default.

- Counts active server ticks for each login session.
- Configurable minute limit and warning time.
- Mode: `WARN_ONLY` or `DISCONNECT`.
- Session state is intentionally not persisted yet.

## Configuration UI

Open **Mods -> Asobiba Tweaks -> Config**.

## Direction

The target identity is not "a convenience mod". It is vanilla Minecraft with small systems that generate odd stories: a freakishly capable wooden pickaxe, a pet creeper, or a day where logging happens to be slightly profitable.
