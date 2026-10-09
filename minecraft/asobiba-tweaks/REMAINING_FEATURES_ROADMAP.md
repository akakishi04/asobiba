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
| V86 | Building reuse and repair | Recognized damaged-house repair from real stored blocks; reuse priority over new houses; avoid replacing player-owned blocks; persist step cursor |
| V87 | Workstation and building families | Profession-specific validated buildings for Librarian, Armorer, Fisherman and other outstanding trades; no inaccessible stations or imaginary fixture recipes |
| V88 | Bridges and roads | Real pier/foundation variants for 2-12-block crossings, bridge-versus-detour decisions, safe slope/stair paths, recovery from partly built crossings |
| V89 | Demand-aware settlement planning | Housing pressure beyond raw nearby bed count, recent overcrowding and welfare inputs, existing-building vertical expansion and deliberate growth cooldown |
| V90 | More general physical freight | Extend real Porter/pack-animal/boat first- and last-mile handling to more resource sites, mixed loads, storage-demand priorities, boat loss/salvage recovery and finite route work |
| V91 | Inter-settlement economy | Recognized inter-village routes, demand/surplus matching and transferred actual ItemStacks, without hidden money/resources |
| V92 | Remaining enchantment behavior | Audit every accepted vanilla enchantment mastery family and projectile integration against the design and implement genuinely missing runtime effects (without inventing slots intentionally left open) |
| V93 | Ecology and world generation | Review river-network continental generation, shoreline use, slow forest recovery, regional sites and cross-mod guardrails for unimplemented specifics |
| V94 | Feature integration and release hardening | Durable world process restart, chunk unload/restore, multiplayer, client UI, real-client long-duration performance and all G01-G21 scenario regressions |

A pass number denotes a direction of work, not an assertion that every listed behavior fits into one commit. Do not close a pass before its implementation and important conservation properties are exercised.

## Working policy

1. **Implement accepted missing functions first**, then use bounded automated checks to prevent build/save corruption. Do not stop feature implementation solely because human playtest polish is still pending.
2. Continue to run Java 21 / Minecraft 1.21.1 / NeoForge 21.1.219 compilation and the required GameTestServer/dedicated-server CI checks on each implementation batch.
3. Keep the river cargo option default ON per user choice. Do not force-load chunks, mint replacement items or silently destroy existing player blocks or real cargo.
4. Treat issues reported during real client play as a high-priority correction queue.
5. **Minecraft Data Logger remains explicitly deferred**; do not count its planned features against the AsobibaTweaks completion target.
