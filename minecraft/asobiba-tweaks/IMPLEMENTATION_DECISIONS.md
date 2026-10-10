# Accepted-feature implementation decisions

This records bounded implementation choices for the accepted `../MOD_IDEAS.md` design. Minecraft Data Logger remains deferred. An implemented feature and a passed server test are not a claim of full real-client, multiplayer, world-restart or modpack acceptance.

## Physical freight

- Recipient warehouse replacement stays in the original receiving village and within 24 Manhattan blocks of both its original dock/warehouse destination and village center. The parcel stores its replacement separately from the shared route endpoint. Only physically accepted matching cargo creates a receipt.
- River hauls preserve their original village identity across worker migration and save/reload. Closed routes cancel unpaid intentions; paid goods return physically. Incoming dock receipts are restored only for the quantity actually returned to the same original dock.
- Unknown chunks remain unknown. Neither an absent carrier entity nor unloaded storage authorizes replacement inventory. Observed terminal boat removal releases dispatch ownership; ordinary vanilla drops remain the only wreck cargo.
- Active project bills and legacy item reservations share one read-only bounded demand snapshot. They reduce exportable surplus and daily scarcity stock, never physical inventory or demographic counts. Unknown/incomplete scans fail closed.

## Buildings and construction

- Missing-bed restoration requires an authoritative completed village-built blueprint, including owner-linked expansion/reuse ancestry. One real finished Bed, or its actual crafting ingredients, pays for one restored two-block Bed. Lost/player-edited paid partials revoke retry entitlement.
- Temporary exterior access is a physically supported plank/stair ramp, not teleportation or an assumption that villagers can climb vanilla Scaffolding. The two-storey aid uses four stair steps with six supporting planks; the three-storey aid uses eight stairs with 28 planks. Only tracked, unchanged, unoccupied aid blocks are recovered.
- Shell repair composes completed original/expansion ancestry and processes larger damage in finite 12-hole projects. Old saved repair indices retain their original interpretation.
- Circulation is validated separately from merely surviving beds/workstations. Ordinary version-2 two-/three-storey homes have three/four supported usable beds, an east entrance, and full two-block stair headroom. The former four/five-bed plans blocked their own entrance or stair clearance. Mixed-purpose Outpost/colony plans are not silently converted.
- Existing construction cursors keep their old blueprint. A separate persistent, physically paid migration salvages the exact original beds, rebuilds only owner-linked geometry, keeps the BuildingRecord identity, and verifies the final route before counting capacity. Player edits stop migration. Completed-home retrofit uses the same process. Shell repairs use a versioned verified final manifest so they cannot close the new doorway or stair openings again.

## Settlement activity and resource work

- The ordinary core is a persisted union of an initial 48-block neighborhood and recognized, connected anchor neighborhoods, capped at 128 horizontal blocks. Growth adds at most eight anchors per refresh; at most 128 anchors survive. The center follows the local anchor concentration gradually. This spatial context never transfers ownership of player buildings.
- Forestry, quarrying and local fishing use immutable planner-designated WorkSite records. Moving a worker cannot move a quarry's original surface or authorize an external tree/vein. Quarry depth is twelve blocks below its designated surface, never below Y=0; exposed fluids suspend work.
- Foresters harvest only bounded simple trunks, preserve standing trees, wait for regrowth and consume a real matching sapling when replanting. Complex/giant trees and protected buildings, roads, farms and newly tracked player-placed resources are skipped. Old untracked isolated player logs cannot be proven natural merely from appearance; conservative surrounding-block heuristics still apply.
- Harvest demand reads actual loaded storage and bounded outstanding construction bills. Unknown inventory fails closed. Deliberately lowering the shared worker-probe configuration below a resource's complete safety preflight requirement pauses that work with a visible reason; normal busy-tick exhaustion retries rather than declaring the site depleted.
- Terminal ephemeral history retains recent results while preserving structural/reuse/expansion blueprints, referenced projects, unknown owners, active reservations and real cargo ownership. Derived reverse-reference indexes prevent global per-village history scans. Oversized legacy record categories fail closed instead of unsafe deletion; they are an explicit conservative maintenance limit.
- Route traffic is a bounded, decaying statistic. Carrier identities and outstanding physical dock receipts are never decayed as if they were traffic counters.

## Contextual building use

- Idle mobs may gather beside simple bench/table combinations or in recognized covered interiors. Normal navigation chooses reachable destinations with bounded preferences for doors, dry bridge decks and cover. Work, combat, rest, cargo duties and occupied targets retain priority.
- Cover is verified from actual nearby sturdy roof blocks, not delayed skylight propagation. Visits do not create furniture entities, seated poses or terrain edits; this remains lightweight contextual behavior.

## Roads and bridges

- Multi-crossing work persists the selected route and bounded survey position, queues one physical crossing at a time, and preserves completed paid crossings.
- Supported initial spans are 2–12 crossing columns. Diagonal spans use 45-degree, overlapping walkable strips, not corner-only touching blocks. Dry ravines require equal-height natural banks and verified foundations no more than eight blocks deep.
- Unsupported angles, larger spans, deep/unnatural foundations or unsafe banks remain explicit conservative exclusions. They never produce an unchecked straight road or free floating bridge.

## Continental rivers

- A deterministic, saturating 32-node upstream catchment estimate drives bounded downstream widths. Shared node elevations and along-channel grades replace independent per-column random water heights.
- Inland terminal basins receiving a stream get a physical sink lake; optional lake frequency controls additional lakes rather than silently deleting required outlets.
- Real loaded-chunk tests exercise source water, bed depth, sediment, navigation, reversed-order seams and receiving lakes. Carving reads the live WORLD_SURFACE heightmap so an earlier ocean/terrain pass cannot leave a stale pre-carving height that raises hanging water.
- Structure protection remains in place, and unusually low existing terrain is not filled with hanging water. These compatibility boundaries can interrupt physical navigation; source-water logistics still validates actual terrain rather than trusting generated topology.

## Mastery behavior

- Performance reaches its designed maximum at mastery 100; continued historical mastery does not increase branch strength.
- Arrow-only effects are restricted to actual arrow ammunition; native tridents use their own owner/return/pickup mechanics.
- Efficiency uses qualifying hardness, a 30-tick five-stack item-local mining rhythm, and partial recovery of the tool's own unsuitable-material speed penalty. It never grants invalid harvest drops.
- Identical equipped armor branches use the strongest mastery, while different branches can coexist. Native Soul Speed wear is intercepted at the actual wear effect; unrelated damage or swapped equipment is never refunded.
- Fortune and Looting modifications operate on native roll/bonus domains, not copies of already-generated rare items or full-table rerolls.
- Fire Aspect and Bane modify their actual registered native effect durations, including native randomized duration. Breach modifies real remaining armor reduction. Punch modifies the native projectile impulse rather than unrelated generic hurt knockback.
- Sweeping Battle Rhythm accelerates one subsequent attack recovery without adding damage. Wind Burst scales the native launch; Aerial Control pays its ten-percent lift reduction and scales actual input rather than generating camera-directed thrust. It uses strongest-only composition with Feather Falling and an owner-only synchronized control window.
- Recoverable paid arrow ammunition records relevant use on its own physical pickup stack, with persistent replay guards and existing Loyalty credit kept separate. Other arrows in a quiver do not inherit the spent arrow's history. Unspecified ammunition-specific variants of launcher/melee specializations remain future domain-specific tuning.

## Verification discipline

The large GameTest templates now encode dimensions using Minecraft's required NBT `TAG_List<TAG_Int>`, with a loader regression test. Terrain-survey tests explicitly allow sky access, so their heightmaps do not see the framework's artificial barrier ceiling. No required assertion or timeout was weakened to address the previous headless startup hang.

The integrated implementation passed all 224 required GameTests twice locally, including a full AsobibaTweaks build on the repeat. The authoritative published verification belongs in `IMPLEMENTATION_STATUS.md` and CI for the exact integration commit; this decisions document is not a claim of completed human gameplay acceptance.

## Independent enchantments and harmless oddities (new pass)

- Rooted, Ominous, Afterimage and Nod are single-level independent datapack enchantments. They share ordinary table/trade/random-loot acquisition (weight 2, level-cost range 20–45, anvil cost 2), retain precise hoe/armor/chestplate/helmet domains, and have no new mastery branches. They do not require the vanilla mastery system or each other. Behavior switches leave registered content loadable.
- Rooted applies to fully mature vanilla Wheat, Carrots, Potatoes and Beetroot harvested by an actual survival player's enchanted mainhand Hoe. A successful ordinary break/drop receipt permits one deferred same-cell replant, with one matching real inventory/offhand seed/item. Canceled harvesting, unsafe/nonempty cells, invalid farmland, immature/unusual crops, missing seeds and creative/fake harvesting do not create a replacement. Ordinary drops are unchanged; placement protection callbacks remain authoritative.
- Ominous biases only separately eligible harmless ambience with capped, nonmultiplicative armor composition. All seven OE events also have a natural unenchanted chance, individual toggles, bounded already-loaded probes and shared player/area/dimension cooldowns. It does not touch Bad Omen, hostility, loot, progress, game speed or Afterimage.
- Chicken Conspiracy is independently enabled and requires at least three safe idle chickens. It uses a short look/meeting cue, yielding immediately on player approach, feeding/breeding, danger or priority AI. It needs no Mob Gatherings feature. Existing gatherings share conservative eligibility and occurrence limits instead of becoming an Ominous reward source.
- Nod requires an independently enchanted Helmet plus a deliberate standing-to-crouching greeting while facing a nearby idle villager, including children. A short server-approved client head animation gives the social cue without changing gossip, trade prices, tasks or inventory. Repeated held crouching does not repeatedly roll. Expiry and missing entities release transient capacity.
- Afterimage requires a real grounded sprint edge followed by measured movement, rather than merely equipping while sprinting, a teleport or standing sprint flag. Defaults are 2-block departure, 30-tick life, 300-tick wearer cooldown, 8-block targeting radius and at most three redirected mobs (hard maximum four). These values are configurable. Only ordinary exact vanilla hostile types already targeting that player and with verified loaded line of sight can receive temporary target leases.
- The Afterimage is a registered nonpersistent, noncolliding, unpickable LivingEntity with a fixed translucent humanoid renderer. It contains no copied player identity, skin, equipment or inventory, gives no loot/XP, deals no damage and does not rewrite durable aggression memories. Unleased incidental acquisition is rejected; expiry, removal, death, logout and dimension change clear only targets still owned by that decoy, then ordinary AI selects normally.
- Real-client animation readability, natural rarity/balance, multiplayer interactions and other mods' protection/AI hooks remain manual acceptance gates in addition to server regression tests. Data Logger remains outside this pass.

### New-pass regression and harness findings

- Caves are recognized from a bounded loaded eight-block overhead sample (at least four natural-stone-type blocks), or the existing below-sea covered condition. This supports high-altitude caves and custom/flat generators whose sea level differs; fresh physical cover takes precedence over asynchronously updated sky-light state.
- A historical composite-shell GameTest retried by inserting the same `Runnable` key while Minecraft `GameTestInfo` was iterating it. The engine removes the current key after invocation, silently deleting that requeued retry. The test now schedules a distinct callback object and deliberately exhausts its first background probe allowance to exercise recovery. Its eight-attempt bound, 100-tick timeout, real-material checks and production repair code are unchanged.

- The full-suite repeat also exposed the same asynchronous skylight assumption in existing second-bed reuse. The known owner-linked 5x5 shell now requires actual solid roof blocks over both proposed bed halves, rather than cached sky brightness. A same-tick roof removal/restoration regression rejects missing cover without billing and accepts immediately restored cover; original real-material assertions remain intact.


## Snow Golem head tilt (2026-10-10)

User-selected quiet cosmetic: occasionally notice a snow golem with its head slightly tilted, then find it normal after looking away and back. The entire model head and vanilla pumpkin/outline layer share the same transform. No sound, jumpscare, reward, entity rotation, AI, hitbox, persistence, packets or gameplay RNG changes.

- Independent COMMON settings: `oddities.snowGolemHeadTilt=true`, `snowGolemHeadTiltChancePerCheck=0.01`, `snowGolemHeadTiltDegrees=6.0` (1–10 degrees). Each client's local configuration and view drive its cosmetic; observers need not see the same moment. Ominous does not affect this feature.
- Nearby loaded Snow Golems only, 2–24 blocks, alive, visible, unhurt, visibly nearly stationary (both interpolated position change and velocity), not burning/in water/riding. Client target state is only an extra veto when available; it cannot prove remote server AI is idle. One observer-local active tilt, at most 32 tracked UUIDs; overcrowded searches stop at 33 and fail closed.
- Sample at most once per 200 observed ticks, after an initial 200-tick warmup, only while outside the current camera frustum. Never start the tilt while continuously looking at the golem. Choose a fixed left/right angle without an animation or twitch.
- A latent tilt may wait up to 600 ticks (30 seconds) to be seen. Once seen, leaving the frustum or losing clear sight cancels it; looking back is neutral. A 1200-tick (60-second) seen lifetime also bounds exceptional continuous observation. Per-golem cooldown is 12000 ticks, observer-wide cooldown 6000 ticks, starting when armed.
- Actual-camera/frame visibility is checked before entity rendering; only the single armed candidate needs a line-of-sight ray. Offscreen objects are processed even when their model is not rendered. Random sampling and expiry advance only in client game ticks.
- Clear pose/observation on world/camera/perspective change, pause/menu, missing camera, disable, stale rendering or lost entity identity; same-world resets preserve cooldowns. State retains no strong level/entity references. Spectator camera use is excluded. Model `zRot` is assigned on every `setupAnim`, including explicit zero, because vanilla does not reset that axis and shares its model across golems.
- Pure state tests cover arming/reveal/look-away, expiry, cooldown, rollback, cache bounds and entity isolation. Client compilation and dedicated-server initialization do not establish rendered visual or multiplayer presentation acceptance; those remain manual checks.
