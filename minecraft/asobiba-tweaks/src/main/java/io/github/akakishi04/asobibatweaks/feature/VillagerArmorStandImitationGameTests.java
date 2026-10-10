package io.github.akakishi04.asobibatweaks.feature;

import com.mojang.authlib.GameProfile;
import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.netty.channel.embedded.EmbeddedChannel;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.GlobalPos;
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
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.ExperienceOrb;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.ai.behavior.BlockPosTracker;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.entity.ai.memory.MemoryModuleType;
import net.minecraft.world.entity.ai.memory.WalkTarget;
import net.minecraft.world.entity.decoration.ArmorStand;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.monster.Zombie;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.npc.VillagerProfession;
import net.minecraft.world.entity.schedule.Activity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.pathfinder.Node;
import net.minecraft.world.level.pathfinder.Path;
import net.minecraft.world.phys.Vec3;
import net.neoforged.neoforge.event.level.LevelEvent;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Native, unmodified villager brains walk, hold, release and yield. Fixture cleanup also runs on failure. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillagerArmorStandImitationGameTests {
    private VillagerArmorStandImitationGameTests() {}

    @GameTest(template = "empty16x14x16", batch = "villager_armor_stand_imitation", timeoutTicks = 500)
    public static void nativeIdleBrainWalksPosesThenReturnsToItsOwnMovement(GameTestHelper helper) {
        Fixture f = new Fixture(helper);
        f.prepare();
        helper.runAfterDelay(5, () -> {
            testSafetyAndPriorities(helper, f);
            testCleanupOwnership(helper, f);
            f.nativeScene(new BlockPos(4, 2, 8), 50, () -> observeNativeWalk(helper, f));
        });
    }

    private static void observeNativeWalk(GameTestHelper helper, Fixture f) {
        Vec3 origin = f.villager.position();
        var persistent = f.villager.getPersistentData().copy();
        float health = f.villager.getHealth();
        int xp = f.villager.getVillagerXp();
        var inventory = f.villager.getInventory().createTag(f.level.registryAccess());
        helper.assertTrue(!f.villager.isNoAi(), "Imitation must keep the native brain enabled");
        helper.runAfterDelay(30, () -> {
            var snapshot = VillagerArmorStandImitationService.snapshot(f.level);
            helper.assertTrue(snapshot != null && snapshot.posing(),
                    "Native villager navigation has not reached its stand-side pose: " + snapshot
                            + "; " + VillagerArmorStandImitationService.lastStopReason(f.level));
            helper.assertTrue(f.villager.position().distanceToSqr(origin) > 2.0D,
                    "The villager did not physically traverse the route");
            Vec3 posed = f.villager.position();
            helper.runAfterDelay(15, () -> {
                var held = VillagerArmorStandImitationService.snapshot(f.level);
                helper.assertTrue(held != null && held.posing()
                                && f.villager.position().distanceToSqr(posed) < 0.05D
                                && Math.abs(Mth.wrapDegrees(f.villager.getYRot() - f.stand.getYRot())) < 1.0F
                                && Math.abs(Mth.wrapDegrees(f.villager.getYHeadRot() - f.stand.getYRot())) < 1.0F,
                        "Ordinary idle brain ticks stole the held pose or facing");
                helper.assertTrue(f.villager.getBrain().getRunningBehaviors().size() > 0 && !f.villager.isNoAi(),
                        "The hold must coexist with the running vanilla brain");
                int remaining = (int)(held.releaseAt() - f.level.getGameTime());
                helper.runAfterDelay(Math.max(1, remaining - 2), () -> {
                    var finalHold = VillagerArmorStandImitationService.snapshot(f.level);
                    helper.assertTrue(finalHold != null && finalHold.posing(),
                            "A native look-sink timeout truncated the promised pose duration");
                });
                helper.runAfterDelay(remaining + 5, () -> {
                    helper.assertTrue(VillagerArmorStandImitationService.snapshot(f.level) == null,
                            "The brief pose did not release on its deadline");
                    helper.assertTrue(f.villager.isAlive() && f.stand.isAlive() && f.villager.getHealth() == health
                                    && f.villager.getVillagerXp() == xp && f.villager.getPersistentData().equals(persistent)
                                    && f.villager.getInventory().createTag(f.level.registryAccess()).equals(inventory)
                                    && f.level.getEntitiesOfClass(ItemEntity.class, helper.getBounds()).isEmpty()
                                    && f.level.getEntitiesOfClass(ExperienceOrb.class, helper.getBounds()).isEmpty(),
                            "Ambient imitation changed health, inventory, persistent state or generated rewards");
                    BlockPos exit = f.villager.blockPosition().south(3);
                    Vec3 beforeExit = f.villager.position();
                    f.villager.getBrain().setMemory(MemoryModuleType.WALK_TARGET, new WalkTarget(exit, 0.5F, 0));
                    helper.runAfterDelay(12, () -> {
                        helper.assertTrue(f.villager.position().distanceToSqr(beforeExit) > 0.1D,
                                "The native brain could not resume ordinary movement after release");
                        f.nativeScene(new BlockPos(4, 2, 5), 60, () -> helper.runAfterDelay(40, () -> {
                            var diagonal = VillagerArmorStandImitationService.snapshot(f.level);
                            helper.assertTrue(diagonal != null && diagonal.posing(),
                                    "Maximum-length diagonal route failed native arrival tolerance: "
                                            + VillagerArmorStandImitationService.lastStopReason(f.level));
                            Goal newOwner = new Goal() {
                                { setFlags(EnumSet.of(Flag.MOVE)); }
                                @Override public boolean canUse() { return true; }
                            };
                            f.villager.goalSelector.addGoal(0, newOwner);
                            helper.runAfterDelay(5, () -> {
                                helper.assertTrue(VillagerArmorStandImitationService.snapshot(f.level) == null,
                                        "A newly running movement goal must take priority without replacing the path first");
                                nativePriorityInterruption(helper, f, 0);
                            });
                        }));
                    });
                });
            });
        });
    }

    private static void testSafetyAndPriorities(GameTestHelper helper, Fixture f) {
        f.fresh();
        var plan = VillagerArmorStandImitationService.plan(f.level, f.villager, f.stand);
        helper.assertTrue(plan != null && plan.probes() <= VillagerArmorStandImitationService.MAX_BLOCK_PROBES
                        && plan.route().size() <= VillagerArmorStandImitationService.MAX_ROUTE_LENGTH + 1,
                "A safe, short, bounded route beside a real armor stand was not found");
        BlockPos unknown = new BlockPos(29_000_000, 80, 29_000_000);
        var probe = new VillagerArmorStandImitationService.Probe(f.level);
        helper.assertTrue(probe.block(unknown) == null
                        && f.level.getChunkSource().getChunkNow(unknown.getX() >> 4, unknown.getZ() >> 4) == null,
                "A scene terrain probe requested an unloaded chunk");
        for (int i = 0; i < VillagerArmorStandImitationService.MAX_BLOCK_PROBES + 20; i++)
            probe.block(unknown.offset(i, 0, 0));
        helper.assertTrue(probe.count <= VillagerArmorStandImitationService.MAX_BLOCK_PROBES,
                "Terrain checks exceeded the hard budget");
        // Both sides are deliberately made unsafe; no arbitrary substitute position is allowed.
        for (BlockPos pos : List.of(f.stand.blockPosition().east().below(), f.stand.blockPosition().west().below()))
            f.level.setBlock(pos, Blocks.MAGMA_BLOCK.defaultBlockState(), 2);
        helper.assertTrue(VillagerArmorStandImitationService.plan(f.level, f.villager, f.stand) == null,
                "A hazardous armor-stand neighbor was accepted");
        for (BlockPos pos : List.of(f.stand.blockPosition().east().below(), f.stand.blockPosition().west().below()))
            f.level.setBlock(pos, Blocks.STONE.defaultBlockState(), 2);
        var headroom = f.villager.blockPosition().above();
        f.level.setBlock(headroom, Blocks.STONE.defaultBlockState(), 2);
        helper.assertTrue(VillagerArmorStandImitationService.plan(f.level, f.villager, f.stand) == null,
                "An obstructed villager-height corridor was accepted");
        f.level.setBlock(headroom, Blocks.AIR.defaultBlockState(), 2);
        AsobibaTweaksConfig.VILLAGER_ARMOR_STAND_IMITATION_ENABLED.set(false);
        helper.assertTrue(!VillagerArmorStandImitationService.tryStart(f.level, f.player, f.villager, f.stand, 50),
                "Independent toggle did not veto start");
        AsobibaTweaksConfig.VILLAGER_ARMOR_STAND_IMITATION_ENABLED.set(true);
        f.level.setDayTime(6000L);
        helper.assertTrue(!VillagerArmorStandImitationService.idle(f.villager, f.level), "Work hours must win");
        f.level.setDayTime(11000L);
        VillagerSimData.setEmergencyDuty(f.villager, "firefighter");
        helper.assertTrue(!VillagerArmorStandImitationService.idle(f.villager, f.level), "Emergency duty must win");
        VillagerSimData.clearEmergencyDuty(f.villager);
        VillagerSimData.setWorkCargo(f.villager, f.level.registryAccess(), List.of(new ItemStack(Items.OAK_LOG)), 16);
        helper.assertTrue(!VillagerArmorStandImitationService.idle(f.villager, f.level), "Physical work cargo must win");
        VillagerSimData.clearWorkCargo(f.villager);
        f.villager.setTradingPlayer(f.player);
        helper.assertTrue(!VillagerArmorStandImitationService.idle(f.villager, f.level), "Trading must win");
        f.villager.setTradingPlayer(null);
        f.villager.getAttribute(Attributes.SCALE).setBaseValue(2.0D);
        f.villager.refreshDimensions();
        helper.assertTrue(!VillagerArmorStandImitationService.idle(f.villager, f.level),
                "Oversized villagers must not enter a normal-height route proof");
        f.fresh();
    }

    private static void testCleanupOwnership(GameTestHelper helper, Fixture f) {
        f.start(50);
        BlockPos replacementTarget = f.villager.blockPosition().south(3);
        Path replacement = new Path(List.of(new Node(replacementTarget.getX(), replacementTarget.getY(),
                replacementTarget.getZ())), replacementTarget, true);
        WalkTarget walk = new WalkTarget(replacementTarget, 0.75F, 0);
        var look = new BlockPosTracker(replacementTarget);
        f.villager.getNavigation().moveTo(replacement, 0.75D);
        f.villager.getBrain().setMemory(MemoryModuleType.PATH, replacement);
        f.villager.getBrain().setMemory(MemoryModuleType.WALK_TARGET, walk);
        f.villager.getBrain().setMemory(MemoryModuleType.LOOK_TARGET, look);
        VillagerArmorStandImitationService.onEntityTick(f.villager, false);
        helper.assertTrue(VillagerArmorStandImitationService.snapshot(f.level) == null
                        && f.villager.getNavigation().getPath() == replacement
                        && f.villager.getBrain().getMemory(MemoryModuleType.PATH).orElse(null) == replacement
                        && f.villager.getBrain().getMemory(MemoryModuleType.WALK_TARGET).orElse(null) == walk
                        && f.villager.getBrain().getMemory(MemoryModuleType.LOOK_TARGET).orElse(null) == look,
                "Cleanup overwrote a replacement owner's navigation or memory");
        f.fresh(); f.start(50);
        AsobibaTweaksConfig.VILLAGER_ARMOR_STAND_IMITATION_ENABLED.set(false);
        VillagerArmorStandImitationService.tick(f.level);
        assertClean(helper, f, "Config-off");
        AsobibaTweaksConfig.VILLAGER_ARMOR_STAND_IMITATION_ENABLED.set(true);
        f.fresh(); f.start(50);
        new VillagerArmorStandImitationEvents().onUnload(new LevelEvent.Unload(f.level));
        assertClean(helper, f, "World unload");
        f.fresh(); f.start(50);
        f.stand.discard();
        assertClean(helper, f, "Removed armor stand");
        f.fresh(); f.start(50);
        Villager old = f.villager;
        old.discard();
        helper.assertTrue(VillagerArmorStandImitationService.snapshot(f.level) == null
                        && !old.getBrain().hasMemoryValue(MemoryModuleType.WALK_TARGET)
                        && !old.getBrain().hasMemoryValue(MemoryModuleType.PATH)
                        && !old.getBrain().hasMemoryValue(MemoryModuleType.LOOK_TARGET),
                "Unloaded participant retained scene reservations");
        f.fresh(); f.start(50);
        f.level.setBlock(f.villager.blockPosition().below(), Blocks.AIR.defaultBlockState(), 2);
        VillagerArmorStandImitationService.onEntityTick(f.villager, false);
        assertClean(helper, f, "Changed supporting floor");
        f.level.setBlock(f.villager.blockPosition().below(), Blocks.STONE.defaultBlockState(), 2);
    }

    private static void nativePriorityInterruption(GameTestHelper helper, Fixture f, int step) {
        if (step == 6) { helper.succeed(); return; }
        f.level.setDayTime(11000L);
        f.nativeScene(new BlockPos(4, 2, 8), 80, () -> helper.runAfterDelay(20, () -> {
            helper.assertTrue(VillagerArmorStandImitationService.snapshot(f.level) != null,
                    "The scene ended before priority test " + step + ": "
                            + VillagerArmorStandImitationService.lastStopReason(f.level));
            switch (step) {
                case 0 -> VillagerSimData.setEmergencyDuty(f.villager, "firefighter");
                case 1 -> {
                    f.villager.getBrain().setMemory(MemoryModuleType.MEETING_POINT,
                            GlobalPos.of(f.level.dimension(), f.villager.blockPosition().south(3)));
                    f.villager.getBrain().setActiveActivityIfPossible(Activity.MEET);
                }
                case 2 -> f.villager.getBrain().setActiveActivityIfPossible(Activity.REST);
                case 3 -> {
                    f.villager.getBrain().setMemory(MemoryModuleType.JOB_SITE,
                            GlobalPos.of(f.level.dimension(), f.villager.blockPosition().south(3)));
                    f.villager.getBrain().setActiveActivityIfPossible(Activity.WORK);
                }
                case 4 -> f.level.setDayTime(6000L);
                case 5 -> {
                    Zombie danger = helper.spawn(EntityType.ZOMBIE, new BlockPos(11, 2, 8));
                    danger.setNoAi(true);
                    f.entities.add(danger);
                }
                default -> throw new IllegalStateException("Unknown priority case");
            }
            helper.runAfterDelay(2, () -> {
                helper.assertTrue(VillagerArmorStandImitationService.snapshot(f.level) == null,
                        "Native emergency/meeting/rest/work/hostile priority case did not interrupt: " + step);
                nativePriorityInterruption(helper, f, step + 1);
            });
        }));
    }

    private static void assertClean(GameTestHelper helper, Fixture f, String reason) {
        helper.assertTrue(VillagerArmorStandImitationService.snapshot(f.level) == null
                        && !f.villager.getNavigation().isInProgress()
                        && !f.villager.getBrain().hasMemoryValue(MemoryModuleType.WALK_TARGET)
                        && !f.villager.getBrain().hasMemoryValue(MemoryModuleType.PATH)
                        && !f.villager.getBrain().hasMemoryValue(MemoryModuleType.LOOK_TARGET),
                reason + " did not clean the owned transient state");
    }

    private static final class Fixture implements AutoCloseable {
        final GameTestHelper helper;
        final ServerLevel level;
        final List<Entity> entities = new ArrayList<>();
        final boolean oldEnabled = AsobibaTweaksConfig.VILLAGER_ARMOR_STAND_IMITATION_ENABLED.getAsBoolean();
        final double oldChance = AsobibaTweaksConfig.VILLAGER_ARMOR_STAND_IMITATION_CHANCE.getAsDouble();
        final boolean oldSimulation = AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean();
        final long oldDay;
        ServerPlayer player;
        EmbeddedChannel channel;
        Villager villager;
        ArmorStand stand;
        boolean closed;

        Fixture(GameTestHelper helper) {
            this.helper = helper;
            this.level = helper.getLevel();
            this.oldDay = level.getDayTime();
            helper.testInfo.addListener(new GameTestListener() {
                @Override public void testStructureLoaded(GameTestInfo test) {}
                @Override public void testPassed(GameTestInfo test, GameTestRunner runner) { close(); }
                @Override public void testFailed(GameTestInfo test, GameTestRunner runner) { close(); }
                @Override public void testAddedForRerun(GameTestInfo oldTest, GameTestInfo newTest, GameTestRunner runner) { close(); }
            });
        }
        void prepare() {
            VillagerArmorStandImitationService.stop(level);
            for (BlockPos pos : BlockPos.betweenClosed(new BlockPos(0, 1, 0), new BlockPos(15, 1, 15)))
                helper.setBlock(pos, Blocks.STONE);
            level.setDayTime(11000L);
            AsobibaTweaksConfig.VILLAGER_ARMOR_STAND_IMITATION_ENABLED.set(true);
            AsobibaTweaksConfig.VILLAGER_ARMOR_STAND_IMITATION_CHANCE.set(0.0D);
            // The assertion concerns this feature's absence of saved state, not the independently
            // enabled village simulation's intentional census writes to every villager.
            AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.set(false);
            var cookie = CommonListenerCookie.createInitial(new GameProfile(UUID.randomUUID(), "stand-observer"), false);
            player = new ServerPlayer(level.getServer(), level, cookie.gameProfile(), cookie.clientInformation());
            Connection connection = new Connection(PacketFlow.SERVERBOUND);
            channel = new EmbeddedChannel(connection);
            new ServerGamePacketListenerImpl(level.getServer(), connection, player, cookie);
            player.setGameMode(GameType.CREATIVE);
            player.setPos(helper.absoluteVec(new Vec3(14.5D, 2, 2.5D)));
            player.setOnGround(true);
            level.addNewPlayer(player);
        }
        void fresh() { freshAt(new BlockPos(4, 2, 8)); }
        void freshAt(BlockPos position) {
            VillagerArmorStandImitationService.stop(level);
            if (villager != null) villager.discard();
            if (stand != null) stand.discard();
            villager = EntityType.VILLAGER.create(level);
            if (villager == null) throw new IllegalStateException("Could not create native villager");
            villager.setPos(helper.absoluteVec(Vec3.atBottomCenterOf(position)));
            villager.getRandom().setSeed(0L); // Keep unrelated giant-organism spawn RNG deterministic.
            level.addFreshEntity(villager);
            villager.setVillagerData(villager.getVillagerData().setProfession(VillagerProfession.NITWIT));
            villager.refreshBrain(level);
            villager.getBrain().setActiveActivityIfPossible(Activity.IDLE);
            villager.setOnGround(true);
            stand = helper.spawn(EntityType.ARMOR_STAND, new BlockPos(8, 2, 8));
            stand.setYRot(0.0F);
            stand.setOnGround(true);
            entities.add(villager);
            entities.add(stand);
        }
        void nativeScene(BlockPos position, int duration, Runnable afterStart) {
            freshAt(position);
            helper.runAfterDelay(3, () -> {
                helper.assertTrue(villager.onGround() && stand.onGround(),
                        "The native actors must settle through real physics before admission");
                // One fixture setup reset removes any initial random stroll. The scene itself
                // keeps every native behavior and runs real server ticks without further resets.
                villager.getBrain().stopAll(level, villager);
                villager.getBrain().eraseMemory(MemoryModuleType.WALK_TARGET);
                villager.getBrain().eraseMemory(MemoryModuleType.PATH);
                villager.getBrain().eraseMemory(MemoryModuleType.LOOK_TARGET);
                villager.getBrain().eraseMemory(MemoryModuleType.INTERACTION_TARGET);
                villager.getNavigation().stop();
                villager.getMoveControl().setWantedPosition(villager.getX(), villager.getY(), villager.getZ(), 0);
                villager.setDeltaMovement(0, villager.getDeltaMovement().y, 0);
                villager.refreshBrain(level);
                villager.getBrain().setActiveActivityIfPossible(Activity.IDLE);
                Vec3 before = villager.position();
                start(duration);
                helper.assertTrue(villager.position().equals(before), "Scene admission teleported the actor");
                afterStart.run();
            });
        }
        void start(int duration) {
            helper.assertTrue(VillagerArmorStandImitationService.tryStart(level, player, villager, stand, duration),
                    "The eligible native villager fixture could not start imitation: idle="
                            + VillagerArmorStandImitationService.idle(villager, level)
                            + ", plan=" + VillagerArmorStandImitationService.plan(level, villager, stand));
        }
        @Override public void close() {
            if (closed) return;
            closed = true;
            VillagerArmorStandImitationService.stop(level);
            entities.forEach(Entity::discard);
            if (player != null) {
                level.removePlayerImmediately(player, Entity.RemovalReason.DISCARDED);
                player.getTextFilter().leave();
            }
            if (channel != null) channel.finishAndReleaseAll();
            level.setDayTime(oldDay);
            AsobibaTweaksConfig.VILLAGER_ARMOR_STAND_IMITATION_ENABLED.set(oldEnabled);
            AsobibaTweaksConfig.VILLAGER_ARMOR_STAND_IMITATION_CHANCE.set(oldChance);
            AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.set(oldSimulation);
        }
    }
}
