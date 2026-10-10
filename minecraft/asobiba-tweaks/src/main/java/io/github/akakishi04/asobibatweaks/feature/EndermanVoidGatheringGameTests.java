package io.github.akakishi04.asobibatweaks.feature;

import com.mojang.authlib.GameProfile;
import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.netty.channel.embedded.EmbeddedChannel;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.function.Consumer;
import java.util.stream.Collectors;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.Registries;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.gametest.framework.GameTestInfo;
import net.minecraft.gametest.framework.GameTestListener;
import net.minecraft.gametest.framework.GameTestRunner;
import net.minecraft.network.Connection;
import net.minecraft.network.protocol.PacketFlow;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.network.CommonListenerCookie;
import net.minecraft.server.network.ServerGamePacketListenerImpl;
import net.minecraft.util.Mth;
import net.minecraft.world.Difficulty;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.ExperienceOrb;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.monster.EnderMan;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.pathfinder.Path;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/**
 * Native End mobs, goal arbitration, navigation, loaded heightmaps, and real server ticks.
 * Stateful cases run sequentially in one fixture because the production scene/cooldown is per level.
 * The remote End fixture alone loads/tickets chunks; production never does. Its listener restores
 * blocks, actors, settings, tickets and service state on success, failure, and timeout.
 */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class EndermanVoidGatheringGameTests {
    private EndermanVoidGatheringGameTests() {}

    @GameTest(template = "empty16x14x16", batch = "enderman_void_gathering")
    public static void overworldCannotStartAnEndScene(GameTestHelper helper) {
        try (TestPlayer fixture = new TestPlayer(helper.getLevel(),
                helper.absoluteVec(new Vec3(8.5D, 2, 8.5D)))) {
            helper.assertTrue(!helper.getLevel().dimension().equals(Level.END), "Overworld fixture has wrong dimension");
            helper.assertTrue(EndermanVoidGatheringService.plan(helper.getLevel(), fixture.player) == null
                            && !EndermanVoidGatheringService.attempt(fixture.player, 0),
                    "A non-End dimension accepted the End-only oddity");
            helper.assertTrue(EndermanVoidGatheringService.snapshot(helper.getLevel()).members().isEmpty(),
                    "Rejected Overworld attempt retained a group");
        } finally {
            EndermanVoidGatheringService.stop(helper.getLevel());
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x14x16", batch = "enderman_void_gathering", timeoutTicks = 640)
    public static void actualEndWalksRespectSafetyOwnershipAndStaggeredRelease(GameTestHelper helper) {
        ServerLevel end = helper.getLevel().getServer().getLevel(Level.END);
        helper.assertTrue(end != null, "The actual End ServerLevel must exist");
        EndFixture fixture = new EndFixture(helper, end);
        helper.testInfo.addListener(new GameTestListener() {
            @Override public void testStructureLoaded(GameTestInfo test) {}
            @Override public void testPassed(GameTestInfo test, GameTestRunner runner) { fixture.close(); }
            @Override public void testFailed(GameTestInfo test, GameTestRunner runner) { fixture.close(); }
            @Override public void testAddedForRerun(GameTestInfo oldTest, GameTestInfo newTest, GameTestRunner runner) { fixture.close(); }
        });
        try {
            fixture.prepare();
            helper.onEachTick(() -> {
                if (fixture.closed) return;
                if (!fixture.started) {
                    // Full block chunks can precede asynchronous entity-section readiness.
                    // Wait on the actual engine state instead of assuming ten ticks is sufficient.
                    if (!fixture.ready()) return;
                    fixture.started = true;
                    fixture.stage = "loaded-terrain-and-limits";
                    assertLoadedTerrainAndLimits(helper, fixture);
                    fixture.stage = "settings-and-eligibility";
                    assertSettingsAndEligibility(helper, fixture);
                    fixture.stage = "abort-and-navigation-ownership";
                    assertAbortAndNavigationOwnership(helper, fixture);
                    fixture.stage = "actual-native-walking";
                    beginActualWalking(helper, fixture);
                } else if (fixture.observation != null) {
                    fixture.observation.run();
                }
            });
        } catch (RuntimeException | Error failure) {
            fixture.close();
            throw failure;
        }
    }

    private static void assertLoadedTerrainAndLimits(GameTestHelper helper, EndFixture f) {
        f.freshMobs(2);
        var plan = requirePlan(helper, f);
        helper.assertTrue(plan.direction() == Direction.EAST && plan.members().size() == 2,
                "Two real Endermen must obtain an east-facing island-edge plan");
        assertPlanGeometry(helper, f, plan);
        BlockPos unknown = new BlockPos(1_000_000, 81, 1_000_000);
        helper.assertTrue(f.level.getChunkSource().getChunkNow(unknown.getX() >> 4, unknown.getZ() >> 4) == null,
                "Unknown-column fixture was already loaded");
        // Level.getHeight returns min build height for missing chunks: that is not proof of void.
        helper.assertTrue(f.level.getHeight(Heightmap.Types.WORLD_SURFACE, unknown.getX(), unknown.getZ())
                        == f.level.getMinBuildHeight(), "Expected native unknown-column height fallback");
        helper.assertTrue(!EndermanVoidGatheringService.emptyLoadedColumn(f.level, unknown)
                        && f.level.getChunkSource().getChunkNow(unknown.getX() >> 4, unknown.getZ() >> 4) == null,
                "Unloaded terrain was treated as verified void or force-loaded");
        BlockPos actualVoid = new BlockPos(536, 81, 524);
        helper.assertTrue(EndermanVoidGatheringService.emptyLoadedColumn(f.level, actualVoid),
                "Loaded empty End moat column must be distinguishable from unknown terrain");
        BlockPos hiddenGround = actualVoid.atY(20);
        f.set(hiddenGround, Blocks.END_STONE.defaultBlockState());
        helper.assertTrue(!EndermanVoidGatheringService.emptyLoadedColumn(f.level, actualVoid),
                "Deep solid terrain below the edge was mistaken for an empty void column");
        f.set(hiddenGround, Blocks.AIR.defaultBlockState());

        for (BlockState unsafe : List.of(Blocks.AIR.defaultBlockState(), Blocks.MAGMA_BLOCK.defaultBlockState(),
                Blocks.WATER.defaultBlockState())) {
            f.floor(unsafe);
            helper.assertTrue(EndermanVoidGatheringService.plan(f.level, f.player()) == null,
                    "Unsupported, hazardous, or fluid ground produced a walking plan: " + unsafe);
            assertProbeBudget(helper, f);
        }
        f.floor(Blocks.END_STONE.defaultBlockState());
        f.layer(83, Blocks.STONE.defaultBlockState());
        helper.assertTrue(EndermanVoidGatheringService.plan(f.level, f.player()) == null,
                "A two-block-high passage accepted a tall Enderman body");
        assertProbeBudget(helper, f);
        f.layer(83, Blocks.AIR.defaultBlockState());
        requirePlan(helper, f);

        f.freshMobs(EndermanVoidGatheringService.MAX_QUERY_RESULTS + 2);
        helper.assertTrue(EndermanVoidGatheringService.plan(f.level, f.player()) == null,
                "A saturated native entity query must fail closed instead of selecting a hidden subset");
        assertProbeBudget(helper, f);
        f.freshMobs(1);
        helper.assertTrue(EndermanVoidGatheringService.plan(f.level, f.player()) == null,
                "A lone Enderman cannot become a gathering");
    }

    private static void assertSettingsAndEligibility(GameTestHelper helper, EndFixture f) {
        f.freshMobs(2);
        AsobibaTweaksConfig.ENDERMAN_VOID_GATHERING_ENABLED.set(false);
        helper.assertTrue(EndermanVoidGatheringService.plan(f.level, f.player()) == null
                        && !EndermanVoidGatheringService.attempt(f.player(), 0),
                "Independent disabled setting did not veto the event");
        AsobibaTweaksConfig.ENDERMAN_VOID_GATHERING_ENABLED.set(true);
        AsobibaTweaksConfig.ENDERMAN_VOID_GATHERING_CHANCE.set(0.0D);
        helper.assertTrue(!EndermanVoidGatheringService.attempt(f.player(), 0), "Zero chance accepted a zero roll");
        AsobibaTweaksConfig.ENDERMAN_VOID_GATHERING_CHANCE.set(0.05D);
        helper.assertTrue(!EndermanVoidGatheringService.attempt(f.player(), 0.05D)
                        && !EndermanVoidGatheringService.attempt(f.player(), Double.NaN)
                        && !EndermanVoidGatheringService.attempt(f.player(), -0.1D)
                        && !EndermanVoidGatheringService.attempt(f.player(), 1),
                "Chance boundary or invalid rolls bypassed the probability gate");
        ItemStack ominous = new ItemStack(Items.DIAMOND_CHESTPLATE);
        ominous.enchant(f.level.registryAccess().lookupOrThrow(Registries.ENCHANTMENT).getOrThrow(NewEnchantments.OMINOUS), 1);
        f.player().setItemSlot(EquipmentSlot.CHEST, ominous);
        helper.assertTrue(!EndermanVoidGatheringService.attempt(f.player(), 0.06D),
                "Ominous must not boost this independently configured End event");
        f.player().setItemSlot(EquipmentSlot.CHEST, ItemStack.EMPTY);
        helper.assertTrue(EndermanVoidGatheringService.attempt(f.player(), 0.049D),
                "An eligible unenchanted observer must allow the configured natural chance");
        helper.assertTrue(!EndermanVoidGatheringService.attempt(f.player(), 0), "A second scene bypassed level ownership");
        EndermanVoidGatheringService.stop(f.level);
        AsobibaTweaksConfig.ENDERMAN_VOID_GATHERING_CHANCE.set(0.1D);

        record IneligibleCase(String name, Consumer<EnderMan> change) {}
        List<IneligibleCase> ineligible = List.of(
                new IneligibleCase("persistent anger timer", mob -> mob.setRemainingPersistentAngerTime(100)),
                new IneligibleCase("persistent anger target", mob -> mob.setPersistentAngerTarget(f.player().getUUID())),
                new IneligibleCase("stared-at flag", EnderMan::setBeingStaredAt),
                new IneligibleCase("combat target", mob -> mob.setTarget(f.player())),
                new IneligibleCase("carried block", mob -> mob.setCarriedBlock(Blocks.DIRT.defaultBlockState())),
                new IneligibleCase("hurt timer", mob -> mob.hurtTime = 10),
                new IneligibleCase("recent attacker", mob -> mob.setLastHurtByMob(f.player())),
                new IneligibleCase("disabled AI", mob -> mob.setNoAi(true)),
                new IneligibleCase("oversized native body", mob -> {
                    mob.getAttribute(Attributes.SCALE).setBaseValue(1.8D);
                    // LivingEntity normally refreshes scale dimensions at the end of its next tick.
                    mob.refreshDimensions();
                    helper.assertTrue(mob.getBbHeight() > 3, "Oversized fixture must have its actual enlarged collision body");
                }));
        for (IneligibleCase test : ineligible) {
            f.freshMobs(2);
            test.change().accept(f.mobs.getFirst());
            helper.assertTrue(EndermanVoidGatheringService.plan(f.level, f.player()) == null,
                    "Ineligible member was recruited: " + test.name() + "; " + f.diagnostics());
        }
        f.freshMobs(2);
        var busy = f.mobs.getFirst();
        helper.assertTrue(busy.getNavigation().moveTo(529.5D, 81, busy.getZ(), 0.65D),
                "Native pre-existing navigation fixture did not start");
        Path existing = busy.getNavigation().getPath();
        helper.assertTrue(existing != null && EndermanVoidGatheringService.plan(f.level, f.player()) == null
                        && busy.getNavigation().getPath() == existing,
                "Planning stole an existing native navigation path");
        f.freshMobs(2);
        f.player().setPos(532, 81, 524.5D);
        helper.assertTrue(EndermanVoidGatheringService.plan(f.level, f.player()) == null,
                "An observer already beside the actors started the distant scene");
        f.restoreObserver();
    }

    private static void assertAbortAndNavigationOwnership(GameTestHelper helper, EndFixture f) {
        List<Consumer<EnderMan>> interrupts = List.of(
                mob -> mob.setRemainingPersistentAngerTime(100),
                mob -> mob.setPersistentAngerTarget(f.player().getUUID()),
                mob -> mob.setBeingStaredAt(),
                mob -> mob.setTarget(f.player()),
                mob -> mob.setCarriedBlock(Blocks.DIRT.defaultBlockState()),
                mob -> mob.setLastHurtByMob(f.player()));
        for (Consumer<EnderMan> interrupt : interrupts) {
            f.freshMobs(2);
            f.start(helper);
            EnderMan member = f.mobs.getFirst();
            interrupt.accept(member);
            EndermanVoidGatheringService.onEntityTick(member);
            f.assertReleased(helper, "New anger, stare, target, carried block, or retaliation did not release the whole group");
        }

        f.freshMobs(2);
        f.start(helper);
        EnderMan injured = f.mobs.getFirst();
        float health = injured.getHealth();
        helper.assertTrue(injured.hurt(f.level.damageSources().playerAttack(f.player()), 1) && injured.getHealth() < health,
                "Native damage fixture did not actually hurt an Enderman");
        EndermanVoidGatheringService.onEntityTick(injured);
        f.assertReleased(helper, "Real damage failed to abort the gathering immediately");

        f.freshMobs(2);
        f.start(helper);
        EnderMan stared = f.mobs.getFirst();
        f.player().setItemSlot(EquipmentSlot.HEAD, ItemStack.EMPTY);
        face(f.player(), stared);
        helper.assertTrue(!f.player().isCreative() && !f.player().isSpectator()
                        && !f.player().getAbilities().invulnerable && f.level.getDifficulty() != Difficulty.PEACEFUL,
                "Stare test requires a vulnerable survival ServerPlayer and non-Peaceful native targeting");
        Vec3 eyeDirection = stared.getEyePosition().subtract(f.player().getEyePosition()).normalize();
        helper.assertTrue(f.player().getViewVector(1).normalize().dot(eyeDirection) > 0.99999D
                        && f.player().hasLineOfSight(stared),
                "Survival observer fixture must actually look into the Enderman's eyes with unobstructed sight");
        stared.targetSelector.tick();
        helper.assertTrue(stared.hasBeenStaredAt() && stared.getTarget() == null,
                "Vanilla pre-aggro stare goal must be running before it installs an attack target");
        EndermanVoidGatheringService.onEntityTick(stared);
        f.assertReleased(helper, "A real survival stare with getTarget()==null did not immediately release control");
        f.restoreObserver();

        f.freshMobs(2);
        f.start(helper);
        EnderMan changed = f.mobs.getFirst();
        changed.goalSelector.tick();
        Path owned = changed.getNavigation().getPath();
        helper.assertTrue(owned != null && EndermanVoidGatheringService.ownsNavigation(changed),
                "Gathering goal never acquired its native path");
        changed.getNavigation().recomputePath();
        helper.assertTrue(changed.getNavigation().getPath() == owned,
                "Native automatic recomputation replaced the exact validated gathering path");
        Path replacement = changed.getNavigation().createPath(new BlockPos(529, 81, 524), 0);
        helper.assertTrue(replacement != null && changed.getNavigation().moveTo(replacement, 0.8D)
                        && changed.getNavigation().getPath() != owned,
                "Replacement native navigation fixture did not obtain a different path");
        Path installed = changed.getNavigation().getPath();
        EndermanVoidGatheringService.onEntityTick(changed);
        helper.assertTrue(EndermanVoidGatheringService.snapshot(f.level).members().isEmpty()
                        && changed.getNavigation().getPath() == installed,
                "Cancellation stopped or replaced a newer path owned by other AI");
        f.assertNativeGoalsRestored(helper);

        f.freshMobs(2);
        f.start(helper);
        EnderMan priority = f.mobs.getFirst();
        Goal urgent = new Goal() {
            { setFlags(EnumSet.of(Flag.MOVE, Flag.LOOK)); }
            @Override public boolean canUse() { return true; }
        };
        priority.goalSelector.addGoal(1, urgent);
        priority.goalSelector.tick();
        helper.assertTrue(priority.goalSelector.getAvailableGoals().stream()
                        .anyMatch(goal -> goal.getGoal() == urgent && goal.isRunning()),
                "Priority native goal arbitration did not start the urgent goal");
        EndermanVoidGatheringService.onEntityTick(priority);
        helper.assertTrue(EndermanVoidGatheringService.snapshot(f.level).members().isEmpty(),
                "A running higher-priority movement/look goal was suppressed");
        priority.goalSelector.removeGoal(urgent);
        f.assertNativeGoalsRestored(helper);

        f.freshMobs(2);
        f.start(helper);
        f.player().setPos(f.mobs.getFirst().position().add(1, 0, 0));
        EndermanVoidGatheringService.tick(f.level);
        f.assertReleased(helper, "Approaching one member did not release the whole group");
        helper.assertTrue(!EndermanVoidGatheringService.attempt(f.player(), 0), "Abort bypassed the earned level cooldown");
        f.restoreObserver();

        f.freshMobs(2);
        f.start(helper);
        var planned = EndermanVoidGatheringService.snapshot(f.level).members().getFirst();
        f.set(planned.anchor().below(), Blocks.AIR.defaultBlockState());
        EndermanVoidGatheringService.onEntityTick(f.mobs.getFirst());
        f.assertReleased(helper, "A removed support block did not abort before another AI movement tick");
        f.set(planned.anchor().below(), Blocks.END_STONE.defaultBlockState());

        f.freshMobs(2);
        f.start(helper);
        f.mobs.getFirst().discard();
        EndermanVoidGatheringService.tick(f.level);
        f.assertReleased(helper, "A removed participant left an orphaned group");

        f.freshMobs(2);
        f.start(helper);
        AsobibaTweaksConfig.ENDERMAN_VOID_GATHERING_ENABLED.set(false);
        EndermanVoidGatheringService.tick(f.level);
        f.assertReleased(helper, "Disabling the setting retained movement or gaze ownership");
        AsobibaTweaksConfig.ENDERMAN_VOID_GATHERING_ENABLED.set(true);
        f.freshMobs(2);
        f.start(helper);
        EndermanVoidGatheringService.stop(f.level);
        f.assertReleased(helper, "Level unload cleanup retained active goals");
        helper.assertTrue(EndermanVoidGatheringService.snapshot(f.level).cooldownUntil() == 0,
                "Level cleanup retained per-level timing state");
        f.freshMobs(2);
        f.start(helper);
        EndermanVoidGatheringService.reset();
        f.assertReleased(helper, "Server stop cleanup retained active goals");
    }

    private static void beginActualWalking(GameTestHelper helper, EndFixture f) {
        f.freshMobs(4);
        AsobibaTweaksConfig.ENDERMAN_VOID_GATHERING_CHANCE.set(0.0D);
        f.observation = () -> {
            // setOnGround alone is not a settled native body. A first horizontal move with
            // zero vertical velocity can clear that flag; let normal gravity/collision run.
            if (f.mobs.stream().anyMatch(mob -> mob.tickCount < 2 || !mob.onGround()
                    || !mob.getNavigation().isDone() || mob.getDeltaMovement().horizontalDistanceSqr() > 0.0025D)) return;
            f.mobs.forEach(mob -> mob.getRandom().setSeed(0x5EEDL));
            AsobibaTweaksConfig.ENDERMAN_VOID_GATHERING_CHANCE.set(0.1D);
            observeActualWalking(helper, f);
        };
    }

    private static void observeActualWalking(GameTestHelper helper, EndFixture f) {
        var plan = requirePlan(helper, f);
        helper.assertTrue(plan.members().size() == 4, "Safe fixture must prove the four-member upper bound");
        assertPlanGeometry(helper, f, plan);
        Map<UUID, Vec3> starts = f.mobs.stream().collect(Collectors.toMap(Entity::getUUID, Entity::position));
        Map<BlockPos, BlockState> terrain = f.snapshotTerrain();
        Set<UUID> entities = f.entities();
        Set<Long> tickets = new HashSet<>(f.level.getForcedChunks());
        Map<UUID, Float> health = f.mobs.stream().collect(Collectors.toMap(Entity::getUUID, EnderMan::getHealth));
        f.start(helper);
        helper.assertTrue(f.entities().equals(entities) && terrain.equals(f.snapshotTerrain()),
                "Starting a scene spawned entities or wrote world blocks");
        Map<UUID, Vec3> previous = new HashMap<>(starts);
        Map<UUID, Long> releaseTimes = new HashMap<>();
        Set<UUID> alreadyReleased = new HashSet<>();
        long[] firstDwell = { -1 };
        int[] previousCount = { 4 };
        long[] lastReleaseTick = { -1 };
        f.observation = () -> {
            if (f.closed) return;
            var current = EndermanVoidGatheringService.snapshot(f.level);
            long now = f.level.getGameTime();
            Set<UUID> active = current.members().stream().map(EndermanVoidGatheringService.MemberSnapshot::entityId)
                    .collect(Collectors.toSet());
            helper.assertTrue(current.members().size() <= previousCount[0], "Scene recruited replacement actors after it began");
            for (EnderMan mob : f.mobs) {
                helper.assertTrue(mob.isAlive() && !mob.isNoAi() && mob.getHealth() == health.get(mob.getUUID()),
                        "Gathering disabled AI, injured, or removed an original actor");
                if (!alreadyReleased.contains(mob.getUUID())) {
                    Vec3 last = previous.put(mob.getUUID(), mob.position());
                    helper.assertTrue(last.distanceToSqr(mob.position()) < 0.64D,
                            "An active member jumped/teleported instead of taking short native walking steps");
                    helper.assertTrue(Math.abs(mob.getY() - 81) < 0.15D
                                    && f.level.getBlockState(mob.blockPosition().below()).is(Blocks.END_STONE),
                            "An active member left the supported island floor");
                }
                if (!active.contains(mob.getUUID()) && alreadyReleased.add(mob.getUUID())) {
                    helper.assertTrue(releaseTimes.containsKey(mob.getUUID()) && now >= releaseTimes.get(mob.getUUID()),
                            "A member was unexpectedly aborted before its scheduled release; " + f.diagnostics());
                    helper.assertTrue(f.nativeGoals.get(mob.getUUID()).equals(goals(mob)),
                            "Individual release left the temporary goal installed or removed a native goal");
                }
            }
            if (current.dwelling() && firstDwell[0] < 0) {
                firstDwell[0] = now;
                List<Long> times = current.members().stream().map(EndermanVoidGatheringService.MemberSnapshot::releaseAt).sorted().toList();
                helper.assertTrue(current.members().size() == 4 && current.members().stream().allMatch(EndermanVoidGatheringService.MemberSnapshot::arrived),
                        "Dwell began before every actual member reached its anchor");
                helper.assertTrue(times.getFirst() - now >= 120 && times.getFirst() - now <= 200,
                        "Initial quiet dwell must have its finite production duration");
                for (int i = 1; i < times.size(); i++) helper.assertTrue(times.get(i) - times.get(i - 1)
                                == EndermanVoidGatheringService.RELEASE_STAGGER,
                        "Group release schedule must be staggered one actor at a time");
                current.members().forEach(member -> releaseTimes.put(member.entityId(), member.releaseAt()));
                for (EnderMan mob : f.mobs) helper.assertTrue(starts.get(mob.getUUID()).distanceToSqr(mob.position()) > 0.01D,
                        "A member did not actually move through native navigation before arriving");
            }
            if (firstDwell[0] >= 0 && now >= firstDwell[0] + 20 && !active.isEmpty()) {
                for (EnderMan mob : f.mobs) if (active.contains(mob.getUUID())) {
                    helper.assertTrue(Math.abs(Mth.wrapDegrees(mob.getYHeadRot() - Direction.EAST.toYRot())) < 3,
                            "Real Endermen heads did not settle into the same outward direction");
                    helper.assertTrue(Math.abs(mob.getXRot()) < 0.01F, "A dwelling Enderman did not look horizontally outward");
                }
            }
            if (current.members().size() < previousCount[0]) {
                helper.assertTrue(previousCount[0] - current.members().size() == 1,
                        "More than one member was released on the same tick");
                if (lastReleaseTick[0] >= 0) helper.assertTrue(now - lastReleaseTick[0] == EndermanVoidGatheringService.RELEASE_STAGGER,
                        "Observed native releases did not follow the scheduled stagger");
                lastReleaseTick[0] = now;
                previousCount[0] = current.members().size();
            }
            if (active.isEmpty()) {
                helper.assertTrue(firstDwell[0] >= 0 && alreadyReleased.size() == 4,
                        "The real scene did not complete all four natural releases");
                helper.assertTrue(f.entities().equals(entities) && terrain.equals(f.snapshotTerrain())
                                && new HashSet<>(f.level.getForcedChunks()).equals(tickets),
                        "Walking/dwell/release created actors, edited blocks, or altered chunk tickets");
                helper.assertTrue(f.level.getEntitiesOfClass(ItemEntity.class, EndFixture.BOUNDS).isEmpty()
                                && f.level.getEntitiesOfClass(ExperienceOrb.class, EndFixture.BOUNDS).isEmpty(),
                        "The completed gathering created farmable drops or XP");
                helper.assertTrue(!EndermanVoidGatheringService.attempt(f.player(), 0),
                        "Natural completion discarded its long level cooldown");
                f.assertNativeGoalsRestored(helper);
                f.close();
                helper.succeed();
            }
        };
    }

    private static EndermanVoidGatheringService.Plan requirePlan(GameTestHelper helper, EndFixture f) {
        var plan = EndermanVoidGatheringService.plan(f.level, f.player());
        helper.assertTrue(plan != null, "Safe loaded End fixture did not produce a plan; " + f.diagnostics());
        return plan;
    }

    private static void assertPlanGeometry(GameTestHelper helper, EndFixture f, EndermanVoidGatheringService.Plan plan) {
        helper.assertTrue(plan.probes() <= EndermanVoidGatheringService.MAX_BLOCK_PROBES,
                "Planner exceeded its aggregate block/column budget");
        Set<BlockPos> anchors = new HashSet<>();
        for (var member : plan.members()) {
            helper.assertTrue(anchors.add(member.anchor()) && member.anchor().getX() == 534
                            && member.anchor().getY() == 81 && !member.route().isEmpty()
                            && member.route().getLast().equals(member.anchor())
                            && member.origin().distanceToSqr(Vec3.atBottomCenterOf(member.anchor())) <= 64,
                    "Anchors must be distinct, safely inset, and connected by bounded routes");
            for (BlockPos cell : member.route()) {
                for (int x = -1; x <= 1; x++) for (int z = -1; z <= 1; z++)
                    helper.assertTrue(f.level.getBlockState(cell.offset(x, -1, z)).is(Blocks.END_STONE),
                            "Planned route lacks its full solid support margin");
                for (int y = 0; y < 3; y++) helper.assertTrue(f.level.getBlockState(cell.above(y)).isAir(),
                        "Planned route lacks full Enderman body clearance");
            }
        }
        for (BlockPos a : anchors) for (BlockPos b : anchors) if (!a.equals(b))
            helper.assertTrue(a.distSqr(b) >= 4, "Line anchors crowd actors more closely than two blocks");
    }

    private static void assertProbeBudget(GameTestHelper helper, EndFixture f) {
        helper.assertTrue(EndermanVoidGatheringService.snapshot(f.level).probes()
                        <= EndermanVoidGatheringService.MAX_BLOCK_PROBES,
                "A failed plan exceeded its shared geometry budget");
    }

    private static Set<Goal> goals(EnderMan mob) {
        return mob.goalSelector.getAvailableGoals().stream().map(goal -> goal.getGoal()).collect(Collectors.toSet());
    }

    private static void face(ServerPlayer player, Entity target) {
        Vec3 delta = target.getEyePosition().subtract(player.getEyePosition());
        float yaw = (float)(Math.atan2(delta.z, delta.x) * 180 / Math.PI) - 90;
        player.setYRot(yaw);
        // LivingEntity.getViewYRot reads yHeadRot, not the body's yRot.
        player.setYHeadRot(yaw);
        player.setXRot((float)(-Math.atan2(delta.y, delta.horizontalDistance()) * 180 / Math.PI));
    }

    /** Standard ServerPlayer: unlike makeMockServerPlayerInLevel, no creative-mode overrides. */
    private static final class TestPlayer implements AutoCloseable {
        final ServerLevel level;
        final ServerPlayer player;
        final EmbeddedChannel channel;
        boolean closed;

        TestPlayer(ServerLevel level, Vec3 at) {
            this.level = level;
            var cookie = CommonListenerCookie.createInitial(new GameProfile(UUID.randomUUID(), "void-observer"), false);
            player = new ServerPlayer(level.getServer(), level, cookie.gameProfile(), cookie.clientInformation());
            Connection connection = new Connection(PacketFlow.SERVERBOUND);
            channel = new EmbeddedChannel(connection);
            new ServerGamePacketListenerImpl(level.getServer(), connection, player, cookie);
            player.setGameMode(GameType.SURVIVAL);
            player.setPos(at);
            player.setOnGround(true);
            player.setItemSlot(EquipmentSlot.HEAD, new ItemStack(Items.CARVED_PUMPKIN));
            level.addNewPlayer(player);
        }

        @Override public void close() {
            if (closed) return;
            closed = true;
            level.removePlayerImmediately(player, Entity.RemovalReason.DISCARDED);
            player.getTextFilter().leave();
            channel.finishAndReleaseAll();
        }
    }

    private static final class EndFixture implements AutoCloseable {
        static final AABB BOUNDS = new AABB(509, 76, 509, 540, 87, 540);
        final GameTestHelper helper;
        final ServerLevel level;
        final Map<BlockPos, BlockState> original = new LinkedHashMap<>();
        final Set<Long> addedTickets = new HashSet<>();
        final List<EnderMan> mobs = new ArrayList<>();
        final Map<UUID, Set<Goal>> nativeGoals = new HashMap<>();
        final boolean wasEnabled = AsobibaTweaksConfig.ENDERMAN_VOID_GATHERING_ENABLED.getAsBoolean();
        final double oldChance = AsobibaTweaksConfig.ENDERMAN_VOID_GATHERING_CHANCE.getAsDouble();
        TestPlayer observer;
        Runnable observation;
        String stage = "preparation";
        boolean started;
        boolean closed;

        EndFixture(GameTestHelper helper, ServerLevel level) { this.helper = helper; this.level = level; }

        void prepare() {
            EndermanVoidGatheringService.stop(level);
            // This is intentionally fixture-only; no production method is allowed to load chunks.
            for (int x = 31; x <= 34; x++) for (int z = 31; z <= 34; z++) {
                long key = ChunkPos.asLong(x, z);
                if (!level.getForcedChunks().contains(key) && level.setChunkForced(x, z, true)) addedTickets.add(key);
                level.getChunk(x, z);
            }
            for (int x = 510; x <= 539; x++) for (int z = 510; z <= 539; z++) {
                helper.assertTrue(EndermanVoidGatheringService.emptyLoadedColumn(level, new BlockPos(x, 81, z)),
                        "Reserved End moat fixture unexpectedly contains existing terrain");
            }
            floor(Blocks.END_STONE.defaultBlockState());
            observer = new TestPlayer(level, new Vec3(516.5D, 81, 524.5D));
            AsobibaTweaksConfig.ENDERMAN_VOID_GATHERING_ENABLED.set(true);
            // Nothing may auto-start during fixture preparation; explicit attempts set this later.
            AsobibaTweaksConfig.ENDERMAN_VOID_GATHERING_CHANCE.set(0.0D);
        }

        ServerPlayer player() { return observer.player; }

        boolean ready() {
            for (int x = 32; x <= 33; x++) for (int z = 32; z <= 33; z++) {
                if (!level.areEntitiesLoaded(ChunkPos.asLong(x, z))
                        || !level.isPositionEntityTicking(new BlockPos(x * 16 + 8, 81, z * 16 + 8))) return false;
            }
            return level.getEntity(player().getUUID()) == player();
        }

        void restoreObserver() {
            player().setPos(516.5D, 81, 524.5D);
            player().setOnGround(true);
            player().setItemSlot(EquipmentSlot.HEAD, new ItemStack(Items.CARVED_PUMPKIN));
            player().setYRot(180);
            player().setYHeadRot(180);
            player().setXRot(0);
        }

        void set(BlockPos at, BlockState state) {
            original.putIfAbsent(at.immutable(), level.getBlockState(at));
            level.setBlock(at, state, 2);
        }

        void floor(BlockState state) { layer(80, state); }

        void layer(int y, BlockState state) {
            for (int x = 512; x <= 535; x++) for (int z = 512; z <= 535; z++) set(new BlockPos(x, y, z), state);
        }

        void freshMobs(int count) {
            EndermanVoidGatheringService.stop(level);
            mobs.forEach(Entity::discard);
            mobs.clear();
            nativeGoals.clear();
            restoreObserver();
            int[] zs = { 524, 526, 522, 528 };
            for (int i = 0; i < count; i++) {
                EnderMan mob = EntityType.ENDERMAN.create(level);
                if (mob == null) throw new IllegalStateException("Cannot create native Enderman fixture");
                mob.setPos(533.5D, 81, zs[i % zs.length] + 0.5D);
                mob.setOnGround(true);
                mob.setPersistenceRequired();
                // Pin independent random spawn modifications as well as first idle arbitration.
                mob.getRandom().setSeed(0x5EEDL);
                if (!level.addFreshEntity(mob)) throw new IllegalStateException("Cannot add native Enderman fixture");
                // Keep the first arbitration genuinely idle: this native RNG seed's first
                // nextInt(60) is 38, so vanilla RandomStroll does not start just before priority 6.
                // Subsequent real server ticks use normal unmodified AI and RNG progression.
                mob.getRandom().setSeed(0x5EEDL);
                mobs.add(mob);
                nativeGoals.put(mob.getUUID(), goals(mob));
                helper.assertTrue(level.getEntity(mob.getUUID()) == mob
                                && level.getEntitiesOfClass(EnderMan.class, mob.getBoundingBox()).contains(mob),
                        "Fixture Enderman must be visible through native UUID and spatial lookups before planning");
            }
        }

        void start(GameTestHelper helper) {
            helper.assertTrue(EndermanVoidGatheringService.attempt(player(), 0),
                    "Eligible actual End group failed to start; probes=" + EndermanVoidGatheringService.snapshot(level).probes());
            // Start the actual production goal through native arbitration, without moving actors.
            mobs.forEach(mob -> mob.goalSelector.tick());
            helper.assertTrue(mobs.stream().allMatch(EndermanVoidGatheringService::ownsNavigation),
                    "Native goal arbitration did not give each member its validated route");
        }

        void assertReleased(GameTestHelper helper, String message) {
            helper.assertTrue(EndermanVoidGatheringService.snapshot(level).members().isEmpty(), message);
            helper.assertTrue(mobs.stream().allMatch(mob -> mob.getNavigation().isDone()
                            && mob.getNavigation().getTargetPos() == null
                            && !EndermanVoidGatheringService.ownsNavigation(mob)),
                    "Released group retained a path, stale target, or automatic recomputation ownership");
            mobs.forEach(mob -> mob.getNavigation().recomputePath());
            helper.assertTrue(mobs.stream().allMatch(mob -> mob.getNavigation().isDone()),
                    "Native recomputation resurrected a stale gathering path after release");
            assertNativeGoalsRestored(helper);
        }

        void assertNativeGoalsRestored(GameTestHelper helper) {
            for (EnderMan mob : mobs) helper.assertTrue(nativeGoals.get(mob.getUUID()).equals(goals(mob)),
                    "Cleanup retained a temporary goal or removed an original native goal");
        }

        String diagnostics() {
            var sampled = AmbientOddityService.nearby(level, Entity.class, player().getBoundingBox().inflate(32, 8, 32));
            return "stage=" + stage + ", probes=" + EndermanVoidGatheringService.snapshot(level).probes()
                    + ", enabled=" + AsobibaTweaksConfig.ENDERMAN_VOID_GATHERING_ENABLED.getAsBoolean()
                    + ", safePlayer=" + AmbientOddityService.safePlayer(player()) + ", player=" + player().position()
                    + ", playerHurt=" + player().hurtTime + ", playerLastAttacker=" + player().getLastHurtByMob()
                    + ", sampled=" + sampled.size() + ", actors=" + sampled.stream().map(entity -> {
                        if (!(entity instanceof EnderMan mob)) return entity.getType().toShortString();
                        return "enderman:" + mob.getUUID() + " alive=" + mob.isAlive() + " onGround=" + mob.onGround()
                                + " noAi=" + mob.isNoAi() + " pos=" + mob.position() + " velocity=" + mob.getDeltaMovement()
                                + " size=" + mob.getBbWidth() + "x" + mob.getBbHeight() + " hurt=" + mob.hurtTime
                                + " target=" + mob.getTarget() + " anger=" + mob.getRemainingPersistentAngerTime()
                                + " angerTarget=" + mob.getPersistentAngerTarget() + " stare=" + mob.hasBeenStaredAt()
                                + " creepy=" + mob.isCreepy() + " carried=" + mob.getCarriedBlock()
                                + " path=" + mob.getNavigation().isInProgress()
                                + " goals=" + mob.goalSelector.getAvailableGoals().stream().filter(goal -> goal.isRunning())
                                        .map(goal -> goal.getGoal().getClass().getSimpleName()).toList()
                                + " targetGoals=" + mob.targetSelector.getAvailableGoals().stream().filter(goal -> goal.isRunning())
                                        .map(goal -> goal.getGoal().getClass().getSimpleName()).toList();
                    }).toList();
        }

        Set<UUID> entities() {
            return level.getEntities((Entity)null, BOUNDS).stream().map(Entity::getUUID).collect(Collectors.toSet());
        }

        Map<BlockPos, BlockState> snapshotTerrain() {
            Map<BlockPos, BlockState> result = new HashMap<>();
            for (int x = 510; x <= 539; x++) for (int z = 510; z <= 539; z++) for (int y = 79; y <= 85; y++) {
                BlockPos at = new BlockPos(x, y, z);
                result.put(at, level.getBlockState(at));
            }
            return result;
        }

        @Override public void close() {
            if (closed) return;
            closed = true;
            EndermanVoidGatheringService.stop(level);
            mobs.forEach(Entity::discard);
            if (observer != null) observer.close();
            original.forEach((pos, state) -> level.setBlock(pos, state, 2));
            for (long key : addedTickets) level.setChunkForced(ChunkPos.getX(key), ChunkPos.getZ(key), false);
            AsobibaTweaksConfig.ENDERMAN_VOID_GATHERING_ENABLED.set(wasEnabled);
            AsobibaTweaksConfig.ENDERMAN_VOID_GATHERING_CHANCE.set(oldChance);
        }
    }
}
