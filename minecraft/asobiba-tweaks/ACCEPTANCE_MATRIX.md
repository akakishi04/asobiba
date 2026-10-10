# AsobibaTweaks acceptance and release verification

Target: Minecraft 1.21.1, NeoForge 21.1.219, Java 21.
Branch: `feat/minecraft-mods-bootstrap`; PR #3.

## Current evidence (2026-10-10 integration checkpoint)

| Evidence | Result and limit |
|---|---|
| Published code | Baseline `6d0426f` contains V91 recipient-warehouse replacement. The larger local integration is uncommitted at this checkpoint; no final published hash/CI result is claimed. |
| Latest completed local GameTestServer | `asobiba-local-gametest-round7.log`: **all 224 required tests passed in 17.99 s; BUILD SUCCESSFUL in 40 s**. This verifies compilation and the required local server suite for that snapshot. |
| Identical-source repeat/full build | `asobiba-final-repeat-build.log`: **224/224 required tests passed in 17.40 s; BUILD SUCCESSFUL in 34 s**. AsobibaTweaks JAR built at `build/libs/asobibatweaks-0.1.0.jar` (1.3 MiB). |
| Resolved earlier failures | Round7 verifies the native Wind-impulse comparison, immediate physical-cover checks independent of delayed sky light, and the live `WORLD_SURFACE` river-height fix. No required test failed in this run. |
| Implementation closure | All bounded accepted integration scopes and their registered regression tests passed round7, including final resource planning and all eleven boundary/history scenarios. Changes after this snapshot require fresh verification. |
| Data Logger | Unchanged and excluded from feature scope. Separate local `data-logger-final-build.log`: BUILD SUCCESSFUL. |
| Final integration gate | Both local builds and identical-source required-suite repeat passed. Dedicated-server smoke and CI for the exact published integration hash remain pending. Local PASS alone does not satisfy publication/conditional merge or human gameplay gates. |

Historical test totals below describe their own snapshots only. Source method/class names are authoritative for newer coverage; no new GT sequence numbers are invented.

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
| G21 | River dock and ChestBoat freight | Real material purchase, no water-source deletion, physically validated water route, real boat inventory conservation, pause/resume after unload and save/reload, passenger takeover, blocked route, full destination and no duplicate carriers | Partial: paid cargo/Porter, reserve/category, recovery/receipt and carrier lifecycle cases passed in round7; actual process/chunk restart, client/multiplayer and long-distance navigation pending. Cargo remains ON by default |
| G22 | Road/bridge terrain safety | No generated road from unloaded/unreachable terrain; cost comparison prefers cheap detours; paid 2–12-column cardinal/45-degree water spans and short founded ravines protect player blocks/source water and provide supported connected decks | Partial: legacy safety plus multi-crossing and `VillageSpanBridgeGameTests` passed round7; real long-running villagers, varied terrain and multiplayer pending. Unsupported angles/long spans/deep or unequal banks remain conservative exclusions |
| G23 | Housing pressure, repair and usable expansion | Real usable housing drives demand; paid second-bed reuse and owner-linked 1→2→3 expansion preserve identity; v2 ordinary homes have three/four supported beds with reachable entry/stairs; bedding/shell repair and migration preserve materials/player edits | Partial: demand, expansion, bedding, access, all eight circulation cases and composite shell repair passed round7. Actual sleeping, autonomous vertical navigation, process restart/crash boundaries and multiplayer remain pending |

## Focused priorities

**P0 before any release**: G02-G05, G07-G10, G12-G13, G16-G17, G20.
These can silently lose or duplicate real items, XP, villagers or world blocks.

**P1**: G01, G06, G11, G14-G15, G18-G19, and balancing with
actual in-game samples.

**Gameplay harness needed**: controlled GameTests and a repeatable long-run
dedicated-server simulation. The historical 31-test CI run 37896419540 is an
earlier milestone, not the current suite result. Use the current evidence above.
Player input, native projectile firing/pickup, real restart/unload, lived-night
villager behavior, sustained multiplayer and modpack/performance still require
their own scenarios. Neither implementation coverage nor a headless CI pass
alone establishes release readiness.

## Downloadable CI deliverables

On successful PR or workflow_dispatch builds, the two jobs attach
binary JARs as 30-day GitHub Actions artifacts:

- `asobiba-tweaks-minecraft-1.21.1`
- `minecraft-data-logger-minecraft-1.21.1`

In GitHub Actions, open the successful run and download the named artifact
from the Artifacts section. Do not install a `-sources.jar`.


## Automated GameTests (stable legacy references)

The required tests run on a real NeoForge GameTestServer. GT01–GT84 are retained reference labels, not a count of the current suite. Existing small-world cases use `asobibatweaks:empty3x3x3`; GT11–GT14 build a real 16x6x9 source-water river fixture with actual Barrel block entities, real ChestBoat entities and durable VillageSavedData. The later unnumbered class/method coverage is listed after this table:

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
| GT59 | completeThirdFloorMaintainsOriginalIdAndFourRealBeds | Version-2 real connected two-flight stairs, third-floor rooms, existing house identity, bounded revalidation and four actually supported sleeping spaces survive SavedData roundtrip; supersedes the former inaccessible five-bed expectation |
| GT60 | blockProbeExhaustionSchedulesFiniteHousingRetry | A real multistorey home deliberately exhausts the dedicated, finite building-validation probe lane and stays unknown until a later loaded tick, then revalidates its actual bed count without changing its BuildingRecord ID |
| GT61 | expandedUpperRoofUsesOneRealRepairPlankAndRespectsPlayerEdit | A real completed three-storey expansion provides its owner-linked roof blueprint for physical repair; one plank costs one authentic item, player Glass remains untouched and the original BuildingRecord ID is preserved |
| GT62 | nonVanillaLikeBlockEntitiesProtectPlayerLand | A genuine Hopper BlockEntity (not in the old explicit protected-block list) proves loaded machines and modded containers can veto natural saplings without chunk generation or virtual inventory |
| GT63 | closedTradeRoadReturnsPaidParcelToItsRealOrigin | A previously paid 16-item Porter shipment follows a suspended route back to its genuinely owned source Barrel with unchanged total inventory and zero fake trade traffic |
| GT64 | fullReturnWarehouseKeepsPhysicalPaidParcel | A real returned freight parcel stays in persistent Porter cargo while the originating warehouse is full, then inserts exactly once after physical space returns |
| GT65 | destroyedReceivingBarrelNeverStrandsPorterCargo | A loaded, player-destroyed destination Barrel causes actual paid goods to return to their source rather than trapping the worker or fabricating replacement items |
| GT66 | realSpecialistEntryMakesRegisteredStationReachable | A genuine physically completed Armorer workshop with unobstructed public entrance and standing cell retains one physically usable Blast Furnace job site |
| GT67 | blockedSpecialistPassageCannotCountAsWorkingPoi | A player Obsidian block in the real internal access corridor makes a still-present workstation inaccessible; removing obstruction physically restores job-site capacity |
| GT68 | missingSecondStoreyStairCostsOneRealItemAndRestoresRoute | A genuine original two-storey stair hole is restored with the exact oriented StairBlock, one actual stored item debit, conserved house identity and SavedData/cursor replay safety |
| GT69 | playerRotatedStairCannotBeOverwrittenEvenWithMissingNeighbor | A player-rotated neighboring stair vetoes an autonomous repair even when another original tread is missing; no items or player blocks are changed |
| GT70 | threeStoreyRepairCarriesRealStairUpstairsAndRestoresBedAccess | A three-storey home's second stair flight requires real carried worker cargo before walking upstairs; the paid block restores connected stairs and actual upper-bed access |
| GT71 | secondFloorCarpenterPreloadsPhysicalPlankBeforeRoofTravel | An original 1→2-storey Carpenter must withdraw exactly one physical roof plank before starting an unreachable upper-shell trip and consume it only after reaching the real placement site |
| GT72 | thirdFloorWallCargoLoadedBeforeRoofNavigation | An original 2→3-storey Carpenter cannot ping-pong empty-handed to the roof; a single real wooden block remains in durable cargo across travel and is consumed once upon placement |
| GT73 | thirdFloorBedCargoLoadedBeforeUpperBedroomNavigation | A two-half White Bed is physically sourced into Carpenter cargo before upstairs travel and placed using exactly one real existing finished item |
| GT74 | fullOriginUsesPhysicallyRegisteredAlternateWarehouse | Real paid return freight uses another loaded recognized warehouse of the same source village when the original Barrel is full, without incrementing route traffic |
| GT75 | destroyedOriginReturnsPaidCargoToReplacement | Physically paid 16-unit freight can be returned to a real replacement origin Barrel after the original block is destroyed; no free parcel or cross-village receipt |
| GT76 | foreignWarehouseNeverReceivesOriginFreight | A nearby fully loaded but foreign-village Barrel must not receive paid return goods; all 16 real units remain in the Porter's persisted cargo |
| GT77 | carpenterPaysOnePlankBeforeTravelingToDistantRoof | A distant real roof repair preloads exactly one physical plank from recognized ground-level Barrel into persistent Carpenter cargo, then consumes only that item when reaching the actual roof; no duplication or phantom material |
| GT78 | finishedSecondBedIsCarriedBeforeLongHouseWalk | A genuine one-story home physically receives its second Bed from remote registered storage only after the worker first carries its real unstackable item; no warehouse↔home oscillation or repeated payment |
| GT79 | destroyedReceiverReroutesExactNamedCargoAfterReload | Destroyed destination selects a recognized same-village spare without remote insertion; the separate parcel destination and exact named cargo survive entity NBT while the shared route endpoint remains unchanged |
| GT80 | fullReceiverUsesOnlyItsOwnRegisteredSpare | Full receiver routes the physically paid parcel to real recipient-owned spare storage, never a closer foreign warehouse |
| GT81 | foreignOrInvalidReceiverNeverAcceptsHeldFreight | Foreign-village and unvalidated replacement containers remain untouched; a full receiver retains all actual cargo and records no false traffic |
| GT82 | canceledRoadOverridesPersistedRecipientReplacement | Route cancellation supersedes a parcel's persisted replacement receiver and physically returns its exact paid inventory without trade receipts |
| GT83 | partialReceiptReroutesOnlyRemainingPhysicalCargo | A partial four-item receipt followed by a replacement deposits only the remaining twelve real items, with exactly sixteen total traffic and no duplicate replay |
| GT84 | removedReplacementIsRevalidatedBeforeDelivery | A selected spare destroyed before arrival is revalidated and triggers a real return, preserves the replacement player block, and creates no phantom delivery |

## New integration coverage by source class

“Passed in round7” means those scenarios ran in the completed 224-test snapshot, in which all required tests passed. It does not verify later edits to those classes or production code. Class names intentionally replace invented GT numbers.

| Source class / methods | Property established or targeted | Evidence |
|---|---|---|
| `AsobibaTemplateFormatTests.allFixtureDimensionsSurviveMinecraftNbtLoading` | Real Minecraft structure loading accepts fixture dimensions as the required NBT list type | Passed in round7 |
| `VillageBedRepairGameTests` | One physical Bed per restored pair; original/expanded/reuse provenance; blocked entry/player edits; real partial-payment persistence and revocation; no stock/orphan-half free placement | Passed in round7; no crash-atomicity claim |
| `VillageCompositeShellRepairGameTests` | Owner-linked lower/upper shell composition; finite batches for larger damage; foreign ancestry veto; immutable legacy repair-index meaning | Passed in round7, including circulation-aware schema/manifest integration; identical-source repeat also passed |
| `VillageGroundAccessGameTests` | Entrance-reachable sheltered interactions, dangerous/unsupported-floor veto, east entry and full stair headroom governing real capacity | Passed in round7; full NPC navigation not established |
| `VillageCirculationVersionGameTests` | Native v2 three/four-bed geometry plus absent-version legacy plan/cursor NBT preservation | Passed in round7 |
| `VillageConstructionAccessGameTests` | Actual ramp material payment/recovery, occupied-support retention, same-state player-edit ownership revocation and blocked-footprint veto | Passed in round7; controlled actions do not prove autonomous construction travel |
| `VillageHouseCirculationGameTests` | Legacy bed salvage, unrelated drop preservation, player-edit veto, cursor replay, same-ID retrofit, v2 no-op verification, adopted exclusion and lost-paid-bed replay safety | All eight cases passed in round7 |
| `VillageHouseCirculationGameTests.legacyShellRepairKeepsVerifiedDoorwayAndHeadroomOpen` | Repair the real damaged shell without rebuilding intentional v2 circulation openings | Passed in round7 |
| `VillageBridgeGameTests.twoPaidCrossingsResumeSavedRouteWithoutDuplicateBills`, `unsafeSecondCrossingKeepsPaidFirstAndSurveyPending`, `legacyCompletedSlotResumesOnceAndChangedRoutePauses`, `missingChunkContinuationNeverInventsSurveyedRoad` | Saved multi-crossing continuation, no duplicate payment, unsafe/unknown terrain pause and preservation of completed crossings | Passed in round7 |
| `VillageSpanBridgeGameTests` | Paid 45-degree connected water geometry in both directions; short dry-ravine physical foundations; foundation-change pause and player-bank veto | Passed in round7 |
| `VillageRiverFreightSafetyGameTests` | Real warehouse/category demand, exact-item reservations, late pickup rechecks, unknown/absent stores and exact named paid cargo | Passed in round7; unknown-store fixtures are not actual chunk reloads |
| `VillageRiverHaulRecoveryGameTests` | Closed-route physical return, only actual restored receipts, original ownership through NBT/migration and unpaid-ticket cancellation | Passed in round7 |
| `VillageRiverCarrierLifecycleGameTests` | Actual destroyed boat produces only vanilla paid drops; no free replacement carrier; unloaded-removal reason retains route ownership | Passed in round7; simulated removal reason is not a complete chunk lifecycle |
| `VillageProjectReservationGameTests` | Actual/paused item/tag project bills affect price and V90/V91 export/pickup while preserving physical stock, paid cargo and demographics; unknown/oversized demand fails closed | Passed in round7 |
| `EfficiencyMasteryGameTests` | Hardness-qualified scaling, real per-tool mining rhythm/expiry and partial unsuitable-speed recovery without invalid harvest permission | Passed in round7 |
| `FeatherFallingMasteryGameTests` | Strongest copy per branch, mastery cap, post-vanilla fall mitigation, actual prevented-impact domain and real input acceleration without gravity changes | Passed in round7 |
| `AsobibaArmorBranchTests` | Distinct equipped branches coexist; duplicate branches apply once at strongest mastery; one-time extinguishing; no refund for swapped/unrelated boot damage | Passed in round7 |
| `EnchantmentLootMasteryGameTests` | Native common/rare roll modifications; Fortune variance applies to actual bonus, preserves crop baseline and excludes ineligible raw blocks | Passed in round7 |
| `FrostWalkerExtensionGameTests` | Directional ice preserves waterlogged/player/flowing water, schedules normal melting and never loads remote terrain | Passed in round7 |
| `EnchantedArrowDomainGameTests` | Arrow-only damage/flight/return effects cannot claim native tridents, including stale arrow return markers | Passed in round7 |
| `EnchantedArrowFlameGameTests` | Actual Flame-ammo projectile lights a vanilla campfire; extinguished state remains extinguished through entity NBT/rejoin | Passed in round7 |
| `LoyaltyTridentMasteryGameTests` | Bounded distinct native return motion, owner/pickup/paid-item retention and one growth credit through NBT | Passed in round7; handler/motion tests do not prove naturally thrown full flight/pickup |
| `ArrowAmmoMasteryGameTests` | Relevant history belongs to the paid recoverable ammo stack, survives native save/pickup and does not replay or ignore target/config gates | Passed in round7 |
| `CombatRecoveryMasteryGameTests` | Whole-event Unbreaking reserve; actual attack recovery; genuine two-target sweep; native Wind launch and real strongest-only aerial input | All five cases passed in round7, including native launch comparison with independent wind-pressure contribution |
| `NativeEffectMasteryGameTests` | Native Fire Aspect/Bane durations, actual Breach armor reduction, nonduplicating Binding reclaim and native Punch impulse/source handling | All six cases passed in round7 |
| `ContinentalRiverGenerationGameTests` | Five seeded production-model checks: nonshrinking accumulated width, downhill shared grades, receiving sink lakes, order-independent seam samples and no hanging-water carve permission | Passed in round7; these tests do not place a generated river into real chunks |
| `VillageResourceSiteGameTests` | Fixed Forestry/Quarry/Fishing assignment/bounds, physical demand/saplings, quarry depth/fluids/player protection, persistence, missing/unknown sites and exhausted/undersized budgets | All twelve cases passed in round7; identical-source repeat/full build also passed |
| `VillageActivityBoundaryGameTests` / `VillageHistoryMaintenanceGameTests` | Connected bounded growth and invalid-anchor retirement; active clocks/NBT; safe indexed ephemeral compaction, retained physical/referenced ownership, terminal reservation release and traffic decay without consuming receipts | All five boundary and six history cases passed in round7 |
| `MobBuildingUseGameTests` | Actual furniture/cover/occupancy, essential AI ownership, reachable navigation, path preferences and hard probe/loaded-world bounds | All nine cases passed in round7, including physical cover immediately after roof edits |
| `ContinentalRiverPhysicalGameTests.seededCarvingCreatesNavigableSeamsAndARealTerminalLake` | Production carving into actual chunks; physical seam/order continuity, navigable water and receiving lake | Passed in round7; not a general new-world visual/modpack acceptance |
| `ContinentalRiverPhysicalGameTests.loweredTerrainAndNativeChunkGuardsPreventPhysicalDamage` | Actual lowered terrain plus native existing-chunk/structure/reference guards | Passed in round7 after production switched from stale `WORLD_SURFACE_WG` to live `WORLD_SURFACE` |

## Explicit limits and remaining gameplay evidence

- **G01–G23 remain scenario gates.** Passing a narrower automated transaction/model test does not make the full corresponding gameplay scenario PASS.
- **Persistence:** entity/SavedData NBT roundtrips and cursor-replay checks do not prove actual process restart, interrupted disk writes, real chunk unload/reload or crash-atomic two-half Bed transactions.
- **Physical AI:** scripted movement/placement and bounded geometry checks do not prove that villagers complete long routes, build upper floors autonomously or sleep successfully across live nights.
- **Client/multiplayer:** UI gestures, native projectile launch/collision/pickup, Wind/Feather input synchronization and simultaneous player edits need real-client/multiplayer verification.
- **World generation:** model determinism is narrower than physical channel continuity, shore appearance and useful boat navigation. Structure/reference guards and exceptional low terrain intentionally remain possible interruptions.
- **Compatibility/performance:** sustained multiplayer, actual modpack POIs/loot/terrain hooks and long-lived history budgets need their own measured runs.
- **Intentional scope:** all 41 selectable enchantment families have code; Mending is branchless and Flame's third slot is deliberately open. Additional ammo-domain specializations, pack animals, portage and unrestricted bridge geometry are not missing initial-release implementations.
