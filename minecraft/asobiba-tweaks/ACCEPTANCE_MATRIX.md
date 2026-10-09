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
| G23 | Housing pressure and safe reuse | Recognized usable homes drive construction; reserve, cooldown, chronic homeless people and food stability change priority; existing village-owned home can gain a real, paid second Bed without modifying player blocks; no bogus extra building capacity | Partial: GT28–GT31 automated; in-place second-floor/roof expansion, sleeping AI and multiplayer still pending |
| G22 | Road/bridge terrain safety | No generated road from unloaded/unreachable terrain; actual cost comparison prefers cheap detours; 2-12-block bridges pay all physical materials, protect player structures, preserve source water and do not strand villagers on unwalkable grades | Partial: GT23-GT27 automated; long-running villagers, extreme terrain and multiplayer still pending |
| G21 | River dock and ChestBoat freight | Real material purchase, no water-source deletion, physically validated water route, real boat inventory conservation, pause/resume after unload and save/reload, passenger takeover, blocked route, full destination and no duplicate carriers | Partial: GT09-GT17 server tests registered; full restart/client/multiplayer and real long-distance Porter navigation pending (cargo ON by default; still experimental) |

## Focused priorities

**P0 before any release**: G02-G05, G07-G10, G12-G13, G16-G17, G20.
These can silently lose or duplicate real items, XP, villagers or world blocks.

**P1**: G01, G06, G11, G14-G15, G18-G19, and balancing with
actual in-game samples.

**Gameplay harness needed**: controlled GameTests and a repeatable long-run
dedicated-server simulation. Thirty-one required NeoForge GameTests passed CI run 37896419540, but the rest of the player,
projectile, village, save/reload and multiplayer scenarios still require
real in-game testing. CI must not be used to label the project feature-complete.

## Downloadable CI deliverables

On successful PR or workflow_dispatch builds, the two jobs attach
binary JARs as 30-day GitHub Actions artifacts:

- `asobiba-tweaks-minecraft-1.21.1`
- `minecraft-data-logger-minecraft-1.21.1`

In GitHub Actions, open the successful run and download the named artifact
from the Artifacts section. Do not install a `-sources.jar`.


## Automated GameTests (required server suite)

The required tests run on a real NeoForge GameTestServer. Existing small-world cases use `asobibatweaks:empty3x3x3`; GT11-GT14 build a real 16x6x9 source-water river fixture with actual Barrel block entities, real ChestBoat entities and durable VillageSavedData:

| ID | Test | Property |
|---|---|---|
| GT01 | arrowEnchantmentEligibility | Normal/Spectral/Tipped eligibility and the 13-effect allowlist |
| GT02 | masteryBranchPersistsOnStack | Exact mastery threshold, branch cycling, ItemStack copy |
| GT03 | workBlockSavedDataRoundTrip | Full enchant/component persistence in encoded SavedData |
| GT04 | frostWalkerToggleIsItemLocal | Stack-local ON/OFF survives ItemStack copy |
| GT05 | furnaceEfficiencyAffectsRealSmelting | Actual furnace recipe completes in less than 125 ticks at Efficiency X |
| GT06 | paidCopyConservesArrowCountComponentsAndXp | Server transaction preserves exact inventory arrows, enchant/mastery components, source count and charged XP |
| GT07 | invalidMaterialsNeverSpendXpOrEmitArrows | Wrong arrow type and already-enchanted source materials reject without mutation |
| GT08 | invalidQuantityAndInsufficientXpAreAtomic | Insufficient XP and out-of-range batch requests never consume or generate resources |
| GT09 | connectedSourceWaterIsNavigable | Three-block loaded source-water corridor produces a direct two-endpoint route |
| GT10 | solidBarrierRequiresRealWaterDetour | Stone barriers cannot be crossed directly; a route is permitted only through actual navigable water even if other test waterways create a legitimate detour |
| GT11 | realChestBoatDeliversAndReturnsWithExactInventory | Real boat spawned for one actual boat item; traverses real water, delivers exactly 16 items to a Barrel and returns with inventory conservation checked during every game tick |
| GT12 | fullBarrelAndPlayerCargoNeverDeleteFreight | Full destination retains freight onboard; unrelated player cargo blocks automated unloading; transfer resumes with exact counts after storage space is freed |
| GT13 | noBoatItemNeverSpawnsBoatOrTransfersCargo | Real items cannot teleport to another dock or synthesize an unpaid boat |
| GT14 | actualBoatAndCarrierSavedDataRoundTrip | Exact boat cargo and unique carrier/route/phase survive NBT encode/decode, without claiming a complete server-process restart |
| GT15 | returnTripCarriesRealReverseFreightAndReceipts | Real reverse cargo transfers from a physical far dock to the home dock without duplication; both persistent dock receipts are updated |
| GT16 | corePorterStagesPhysicalShipment | Real village Porter loads 32 actual blocks into persistent work cargo, then delivers the exact count to the core dock Barrel |
| GT17 | remotePorterCollectsOnlyArrivedFreight | Real Outpost Porter physically collects only the 16 receipted items and delivers to recognized local storage; SavedData roundtrip does not restore spent receipts |
| GT18 | repairsOnlyMissingVillageBlockForOneRealPlank | A village-owned building's exact original missing roof cell is repaired from a real recognized Barrel and the paid project persists |
| GT19 | neverOverwritesPlayerReplacementOrChargesMaterial | A player replacement glass block survives a queued village repair and does not consume the reserved material |
| GT20 | loomConsumesRealPlanksAndString | Physical Loom recipe consumes exactly two planks and two String without minting free items |
| GT21 | lecternCraftsBookshelfWithExactPhysicalInputs | Real Book, Bookshelf and wood Slab intermediates consume actual paper/leather/planks and retain surplus Slabs |
| GT22 | specialistBlueprintsOwnDifferentRoofsAndRealWorkstations | Librarian/Armorer/Fisherman templates expose their real job-site, actual storage Barrel and distinct roof structures |
| GT23 | physicalRaisedBridgeIsBuiltFromPaidStockAndPreservesWater | Real 2-wide bridge spanning six source-water cells is built from exactly paid cobblestone/planks/stairs, including waterlogged piers, raised deck, stairs, rails and SavedData roundtrip |
| GT24 | obstructedBridgeNeverConsumesOrOverwritesPlayerBlock | An existing pier is never billed twice; a newly placed Obsidian block halts bridge progress without inventory loss or bulldozing |
| GT25 | noBridgeForShortWaterOrObstructedBanks | Bridge survey rejects a real player-obstructed shore foundation |
| GT26 | unloadedRoadCorridorNeverBecomesStraightFallback | Absent FULL chunks cannot produce fake straight roads or cause chunk loading during the planner call |
| GT27 | materialDetoursAndProtectedBankCanVetoBridge | A bridge must save substantial detour distance and reject unsafe modified lanes along the shortcut |
| GT28 | healthyReserveAndRecentHouseSuppressSpam | Recognized sleeping-capacity reserve suppresses extra houses, while a saved construction cooldown delays minor shortages |
| GT29 | acuteShortageBypassesCooldownButDeduplicatesProjects | Real acute overcrowding bypasses normal cooldown, but an already active residential construction blocks duplicates |
| GT30 | carpenterAddsPaidSecondBedWithoutAnotherHouse | Existing real village house adds one fully paid, wool-and-plank-crafted White Bed, revalidates two sleeping spaces and survives SavedData roundtrip without duplicate BuildingRecords |
| GT31 | playerOccupiedBedSpaceIsNeverOverwrittenOrCharged | Queued second-bed placement cancels without consuming a physical item or overwriting player Obsidian |
| GT32 | receivingCapacityWinsOverBlockedDockItem | A real ChestBoat transports physically receivable Wheat rather than unavailable Cobblestone, conserves both inventories and records the exact real dock receipt |
| GT33 | lowerDestinationStockTakesFreightPriority | When both goods can be received, a less-stocked destination item wins over earlier source-slot order with unchanged total stock |
| GT34 | realPorterMovesPaidStockBetweenSeparateVillageBarrels | Two separately owned real Barrels exchange 16 actually carried blocks via a persistent Porter ticket without minted inventory or duplicated Village IDs |
| GT35 | fullDestinationRetainsRealPorterParcelUntilSpaceReturns | An obstructed receiving warehouse holds the original parcel in Villager NBT until genuine storage capacity returns |
| GT36 | removedSourceStockCancelsUnpaidTransfer | A pending, unpaid shipment does not fabricate its 16 physical items when source stock disappears |
| GT37 | emptyIdleCarrierReturnsExactlyOnePaidBoatItem | After actually delivering freight, an empty idle ChestBoat returns one genuine reusable boat item to its registered home dock and releases the carrier ID |
| GT38 | idleCarrierWithCargoCannotBeDestroyedForBoatItem | An apparently idle boat with real cargo cannot be converted into a second boat item or lose its freight |
| GT39 | unmodifiedClearingCanRegrowButFarmCannot | A naturally empty dirt clearing is allowed for forest regrowth but physically adjacent farmland is protected |
| GT40 | roadAndStorageNearSaplingAreProtected | Player-built cobble roads and Barrel storage reject natural sapling placement outside any village index |
| GT41 | splitRealStockStillPaysExactParcel | Genuine identical inventory split across multiple stacks contributes exactly 16 paid pieces while retaining 48 local pieces |
| GT42 | sameItemWithDifferentComponentsIsNotSwapped | Custom-named and plain stacks of one vanilla item remain distinguishable during real cross-village pickup/delivery |
| GT43 | stoneSupplyCategoryBlocksRedundantCobbleExport | Real Stone inventory satisfies the same construction category as Cobblestone; redundant import does not start or move any items |
| GT44 | reservedConstructionMaterialRemainsAtHome | A real resource reservation reduces exportable source-category stock and preserves the intended building material |
| GT45 | upperFloorRequiresPhysicalOrientedStairsAndSafeLanding | A real four-tread staircase requires the correct physical orientation, safe landing support and open stairwell; a turned or blocked tread denies upper-floor recognition |
| GT46 | multistoryBlueprintKeepsUpperLandingFreeOfBeds | New 2-/3-storey village house plans allocate physically distinct roof openings, stairs and safely placed beds, with no landing occupied by bedroom furniture |
| GT47 | threeStoryRevalidationFitsDefaultBoundedProbeBudget | 2-story and 3-story built-house semantic scans use 54 and 81 interior cells, not the 325-cell 3-story shell that exceeds the default 256-probe budget |
| GT48 | alreadyPresentFoundationAdvancesWithoutPayingAgain | An exact structural block already present when construction resumes advances the durable cursor and releases only the corresponding bookkeeping reservation without any material debit |
| GT49 | completedTwoHalfBedReconcilesExactlyOneUnpaidCursor | A matching real two-block Bed assembled before its project cursor advanced is acknowledged once, without consuming another three wool and three planks |
| GT50 | brokenBedHalfNeverApprovesFreeCompletedBed | A partially missing or player-obstructed bed head cannot be mistaken for completed usable furniture or allow the work cursor and reservations to advance |
| GT51 | originalPaidHouseSchedulesPersistedSecondFloor | Only a genuine completed village-built one-story home is eligible; its planned in-place expansion retains the original BuildingRecord ID after SavedData roundtrip |
| GT52 | playerUpperShellEditBlocksExpansionWithoutPayment | Existing player-made upper blocks veto construction before any real material is withdrawn |
| GT53 | placedUpperWallReconcilesWithoutSecondItemDebit | Actual Carpenter cargo and Barrel withdraw one plank for a new wall, but repeated cursor reconciliation never spends it twice |
| GT54 | physicallyCompleteSecondStoreyRetainsBuildingIdAndCountsBeds | A complete real stairwell, roof and two upper beds expand original bounds without a duplicate record; 3 real beds remain valid after saved-world roundtrip |
| GT55 | liveExpansionExcludesConflictingHouseRepairs | A live stairwell opening never triggers competing Carpenter shell repair or second-bed furnishings, and a pending repair blocks duplicate expansion; original supplies remain untouched |
| GT56 | skilledOriginalSecondFloorSchedulesPersistentThirdFloor | Master builder selects an actually complete village-owned two-storey house and preserves its original BuildingRecord and project reference on SavedData reload |
| GT57 | playerEditedThirdFloorCannotTriggerDemolition | Player blocks in the upper expansion volume veto all physical demolition and material withdrawal |
| GT58 | secondStoreyBedDemolishesOnceAndDropsRealItem | One obstructing second-storey Bed is physically demolished once by vanilla, producing exactly one real recoverable item even after replay |
| GT59 | completeThirdFloorMaintainsOriginalIdAndFiveRealBeds | Real connected two-flight stairs, third-floor rooms, existing house identity, bounded revalidation and five actually supported sleeping spaces survive SavedData roundtrip |
| GT60 | blockProbeExhaustionSchedulesFiniteHousingRetry | A real multistorey home deliberately exhausts the dedicated, finite building-validation probe lane and stays unknown until a later loaded tick, then revalidates its actual bed count without changing its BuildingRecord ID |

These tests are **not** a full acceptance of G01-G22: real client control, multiplayer, actual process-level server restart, loaded/unloaded chunk recovery, long-lived village construction, projectile firing and inter-mod behavior still require dedicated scenarios.
