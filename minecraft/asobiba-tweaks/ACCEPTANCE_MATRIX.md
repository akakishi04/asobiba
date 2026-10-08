# AsobibaTweaks acceptance and release verification

Target: Minecraft 1.21.1, NeoForge 21.1.219, Java 21.
Branch: `feat/minecraft-mods-bootstrap`; PR #3.

**Definitions**

- **CI PASS**: both Gradle builds complete, a headless NeoForge
  dedicated server reaches "Done (", and all *registered, required* NeoForge
  GameTests pass on a real GameTestServer. This does not prove every
  untested feature or long-lived world remains consistent.
- **Gameplay PASS**: a real client/host executes the exact item,
  persistence, resource, and world-safety scenarios below.
- **Release-ready**: all P0 conservation and persistence gates pass, the
  performance budget passes for a sustained multiplayer simulation,
  and the server/client build is tested against the documented modpack.

## Essential scenarios

| ID | Scenario | Acceptance criteria | Status |
|---|---|---|---|
| G01 | Normal Arrow + Infinity Bow | Seed Arrow retained; nonrecoverable projectile | Needs gameplay test |
| G02 | Enchanted Arrow + Infinity | One enchanted Arrow consumed; recoverable exact components | Needs gameplay test |
| G03 | Quiver + selected slot | Only selected compatible ammo used; HUD reflects server-authoritative count | Needs gameplay test |
| G04 | Crossbow charged + logout/reload | Exactly one ammo charge, no duplicates on launch after reload | Needs gameplay test |
| G05 | Multishot + Piercing + Loyalty | Secondary projectiles never returned; primary returns only at flight end; armor stands/nonliving targets consume real Piercing capacity | Needs gameplay test |
| G06 | Arrow killed mob with Looting | Enchanted ammo modifies normal and rare loot rolls without inventing drops | Needs gameplay test |
| G07 | Enchant Arrow at table and anvil | Exactly 13 allowed effects; coexisting enchantments; one-arrow output for both normal and forced-stacked inputs; identical XP/lapis charge; remainder unenchanted | Needs gameplay test |
| G08 | Fletching Table copying | Screen +/-/Max picker and server XP preview; table distance and hands revalidated; template survives, N materials and N×anvil-weighted XP removed, N output; full-inventory overflow safe | Needs gameplay test |
| G09 | Vanilla/raised Mending mixed equipment | Conservation of orb XP and durability; IV–IX equipped-only; X inventory | Needs gameplay test |
| G10 | Mending over-repair | 5%–20% persistent buffer before normal durability, no item resurrection | Needs gameplay test |
| G11 | Frost Walker toggle, Lasting Ice | Item-local ON/OFF across save/reload; only generated ice protected | Needs gameplay test |
| G12 | Curse of Binding bound legacy | One original stack escrows and re-equips on respawn; keepInventory unchanged | Needs gameplay test |
| G13 | Curse of Vanishing delayed/echo/legacy | Delayed return once, nonitem trace, one-time matching mastery inheritance | Needs gameplay test |
| G14 | Furnace/Blast Furnace/Smoker Fortune | After each real cook, one bonus normal recipe result with 5% per level, capacity respected | Needs gameplay test |
| G15 | Enchanting Table Fortune | Weighted compatible pool, continuation decay 0.50+0.035×level, no forced extras | Needs gameplay test |
| G16 | Multi-story village project interrupted | Pause while chunks unload; resume after load and builder change, no free blocks | Needs gameplay test |
| G17 | Village storage/porter/carpenter cargo | Inventory conservation with unloading and saved ledger consistency | Needs gameplay test |
| G18 | Refugee/outpost/merger lifecycle | Stable Village IDs, correct destination caps, return and abandonment hysteresis | Needs gameplay test |
| G19 | Continental worldgen and rivers | Determinism for seed, visually sane lakes/rivers/deltas, no accidental chunk loads | Needs gameplay test |
| G20 | Multiplayer + world save/reload | No per-tick unbounded work, duplication, dropped inventories, corrupted SaveData | Needs gameplay test |

## Focused priorities

**P0 before any release**: G02-G05, G07-G10, G12-G13, G16-G17, G20.
These can silently lose or duplicate real items, XP, villagers or world blocks.

**P1**: G01, G06, G11, G14-G15, G18-G19, and balancing with
actual in-game samples.

**Gameplay harness needed**: controlled GameTests and a repeatable long-run
dedicated-server simulation. There are currently no dedicated Minecraft
GameTest/automated gameplay tests in this repository, so the CI gate must
not be used to label this project feature-complete.

## Downloadable CI deliverables

On successful PR or workflow_dispatch builds, the two jobs attach
binary JARs as 30-day GitHub Actions artifacts:

- `asobiba-tweaks-minecraft-1.21.1`
- `minecraft-data-logger-minecraft-1.21.1`

In GitHub Actions, open the successful run and download the named artifact
from the Artifacts section. Do not install a `-sources.jar`.


## Automated GameTests (first tranche)

The required tests registered in `AsobibaGameplayTests` execute on a real NeoForge GameTestServer, using the `asobibatweaks:empty3x3x3` structure:

| ID | Test | Property |
|---|---|---|
| GT01 | arrowEnchantmentEligibility | Normal/Spectral/Tipped eligibility and the 13-effect allowlist |
| GT02 | masteryBranchPersistsOnStack | Exact mastery threshold, branch cycling, ItemStack copy |
| GT03 | workBlockSavedDataRoundTrip | Full enchant/component persistence in encoded SavedData |
| GT04 | frostWalkerToggleIsItemLocal | Stack-local ON/OFF survives ItemStack copy |
| GT05 | furnaceEfficiencyAffectsRealSmelting | Actual furnace recipe completes in less than 125 ticks at Efficiency X |

These are **not** substitutes for the remaining G01-G20 full player/projectile/village/save-reload scenarios. All of those remain pending until implemented as equally meaningful GameTests.
