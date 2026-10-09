# AsobibaTweaks accepted-feature completion roadmap

This tracks **code implementation**, not a demand to finish all gameplay polishing before more code is written. The authoritative accepted details remain in `../MOD_IDEAS.md`. Historical version notes are in `IMPLEMENTATION_STATUS.md`, and explicit gameplay gates are in `ACCEPTANCE_MATRIX.md`.

## Current completed foundations

- Persistent village identities, records, indexed buildings and storages, bounded scheduler, actual worker cargo, welfare, migration and Outpost life cycle
- Incremental housing/storage/craft-hall construction, real material workstations and renovation of public adopted buildings
- River corridor recognition, two bounded physically built docks, verified water routing, paid ChestBoat entity freight, real return shipments and physically carried first/last-mile Porter work (V85)
- A NeoForge GameTestServer suite; user reports real-client problems when found

## Remaining implementation passes (ordered)

| Pass | Area | Remaining acceptance work |
|---|---|---|
| V86 | Building reuse and repair | **Initial V86 implemented**: real-paid, persistent missing village-owned shell restoration, no player-block overwrite, GT18/19. Still pending: full house reuse, beds, upper floors and larger repair plans |
| V87 | Workstation and building families | **Initial V87 implemented**: eleven unique career halls with real physical stations, three roof families and exact ingredient recipes. Still pending: detailed building variants, POI reachability, modded workstation support and long playtesting |
| V88 | Bridges and roads | **V88 initial implemented:** persisted phased 2-12-wide crossing span, outboard waterlogged piers, stair-bank approaches, real wood/mixed/stone material bills, explicit safe detour comparison, no unverified road fallback, 5 additional real GameTests. Remaining: multi-crossing routes, diagonals, ravines and long NPC pathing |
| V89 | Demand-aware settlement planning | **Initial V89 implemented and 31/31 GameTests PASS:** actual recognized-home/welfare/chronic-homeless pressure, active-project/food safeguards, persistent three-day cooldown, physically paid second-bed reuse without duplicate buildings (GT28–GT31). Still pending: navigable in-place upper-floor expansion, new capacity validation and long-lived sleeping AI |
| V90 | More general physical freight | **Initial V90 dock-level prioritization implemented (GT32–GT33 added):** select physically receivable cargo before a blocked shipment, then prefer the less-stocked destination item; retain existing full-dock hold behavior. **Empty idle boat reclamation with real items added (GT37–GT38 staged):** an unoccupied, cargo-free boat at its registered home dock becomes one real reusable boat item after one Minecraft day. Still pending: warehouse-wide demand, additional site categories, mixed loads, pack animals, destroyed-carrier salvage and full finite route work |
| V91 | Inter-settlement economy | **Initial bounded V91 Porter exchange implemented (GT34–GT36 added):** physically move paid stacks between independently registered village Barrels across an accepted loaded road plan, persist worker transfer tickets and respect real shortage/stock thresholds. Remaining: wider regional goods, price integration, longer roads/river-caravan variants, night/obstacle recovery and multiplayer simulation |
| V92 | Remaining enchantment behavior | Audit every accepted vanilla enchantment mastery family and projectile integration against the design and implement genuinely missing runtime effects (without inventing slots intentionally left open) |
| V93 | Ecology and world generation | **Initial guarded forest regrowth added (GT39–GT40 staged):** slow natural regrowth declines to invade nearby player-farmed soil, roads, containers or constructed surfaces, even outside indexed villages. Still pending: regional sites, river visual and shore tuning, modded-block compatibility and long worldgen testing |
| V94 | Feature integration and release hardening | Durable world process restart, chunk unload/restore, multiplayer, client UI, real-client long-duration performance and all G01-G21 scenario regressions |

A pass number denotes a direction of work, not an assertion that every listed behavior fits into one commit. Do not close a pass before its implementation and important conservation properties are exercised.

## Working policy

1. **Implement accepted missing functions first**, then use bounded automated checks to prevent build/save corruption. Do not stop feature implementation solely because human playtest polish is still pending.
2. Continue to run Java 21 / Minecraft 1.21.1 / NeoForge 21.1.219 compilation and the required GameTestServer/dedicated-server CI checks on each implementation batch.
3. Keep the river cargo option default ON per user choice. Do not force-load chunks, mint replacement items or silently destroy existing player blocks or real cargo.
4. Treat issues reported during real client play as a high-priority correction queue.
5. **Minecraft Data Logger remains explicitly deferred**; do not count its planned features against the AsobibaTweaks completion target.
