package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.animal.Pig;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.schedule.Activity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.SlabBlock;
import net.minecraft.world.level.block.StairBlock;
import net.minecraft.world.level.block.state.properties.Half;
import net.minecraft.world.level.block.state.properties.DoubleBlockHalf;
import net.minecraft.world.level.block.state.properties.SlabType;
import net.minecraft.world.level.pathfinder.Node;
import net.minecraft.world.level.pathfinder.Path;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** In-engine checks for conservative furniture recognition, idle ownership and real movement. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class MobBuildingUseGameTests {
    private MobBuildingUseGameTests() {}

    @GameTest(template = "empty16x6x9", batch = "mob_context_furniture")
    public static void benchRequiresBottomSeatAndRealTabletop(GameTestHelper helper) {
        ServerLevel level = helper.getLevel();
        BlockPos bench = helper.absolutePos(new BlockPos(4, 2, 4));
        BlockPos table = bench.east(2);
        level.setBlock(bench, Blocks.OAK_STAIRS.defaultBlockState(), Block.UPDATE_CLIENTS);
        level.setBlock(table, Blocks.OAK_FENCE.defaultBlockState(), Block.UPDATE_CLIENTS);
        level.setBlock(table.above(), Blocks.OAK_PRESSURE_PLATE.defaultBlockState(), Block.UPDATE_CLIENTS);
        helper.runAtTickTime(4, () -> {
            helper.assertTrue(bench.east().equals(MobBuildingUseService.benchTableStanding(
                    probe(level), bench)), "A bottom stair with a nearby real tabletop was missed");
            level.setBlock(table.above(), Blocks.AIR.defaultBlockState(), Block.UPDATE_CLIENTS);
            helper.assertTrue(MobBuildingUseService.benchTableStanding(probe(level), bench) == null,
                    "An ordinary stair without a table was mistaken for furniture");
            helper.assertTrue(MobBuildingUseService.isBench(Blocks.OAK_SLAB.defaultBlockState()),
                    "Bottom slabs should also be usable bench cues");
            helper.assertTrue(!MobBuildingUseService.isBench(Blocks.OAK_SLAB.defaultBlockState()
                    .setValue(SlabBlock.TYPE, SlabType.TOP))
                    && !MobBuildingUseService.isBench(Blocks.OAK_STAIRS.defaultBlockState()
                    .setValue(StairBlock.HALF, Half.TOP)), "Ceiling slabs/stairs are not benches");
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", batch = "mob_context_occupancy")
    public static void occupiedOrHazardousStandingCellsAreRejected(GameTestHelper helper) {
        flatFloor(helper);
        Pig pig = idlePig(helper, new BlockPos(2, 2, 4));
        BlockPos target = helper.absolutePos(new BlockPos(6, 2, 4));
        helper.runAtTickTime(4, () -> {
            ServerLevel level = helper.getLevel();
            helper.assertTrue(MobBuildingUseService.safeStanding(pig, probe(level), target),
                    "The empty standing cell must start usable");
            var player = helper.makeMockServerPlayerInLevel();
            player.setPos(target.getX() + 0.5D, target.getY(), target.getZ() + 0.5D);
            helper.assertTrue(!MobBuildingUseService.safeStanding(pig, probe(level), target),
                    "Contextual use must not choose a player's occupied cell");
            player.discard();
            level.setBlock(target, Blocks.OBSIDIAN.defaultBlockState(), Block.UPDATE_CLIENTS);
            helper.assertTrue(!MobBuildingUseService.safeStanding(pig, probe(level), target)
                    && level.getBlockState(target).is(Blocks.OBSIDIAN),
                    "Player blocks must remain untouched and unusable");
            level.setBlock(target, Blocks.AIR.defaultBlockState(), Block.UPDATE_CLIENTS);
            level.setBlock(target.below(), Blocks.MAGMA_BLOCK.defaultBlockState(), Block.UPDATE_CLIENTS);
            helper.assertTrue(!MobBuildingUseService.safeStanding(pig, probe(level), target),
                    "Magma is not a gathering floor");
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", batch = "mob_context_interior", skyAccess = true)
    public static void recognizedInteriorNeedsCurrentPhysicalCover(GameTestHelper helper) {
        flatFloor(helper);
        Pig pig = idlePig(helper, new BlockPos(2, 2, 4));
        ServerLevel level = helper.getLevel();
        BlockPos min = helper.absolutePos(new BlockPos(7, 1, 2));
        BlockPos max = min.offset(4, 4, 4);
        VillageSavedData data = VillageSavedData.get(level);
        var village = data.createVillage(min, level.getGameTime());
        var building = data.createBuilding(village.id(), min, max, false);
        building.setValidationState("valid");
        for (BlockPos pos : BlockPos.betweenClosed(min.above(3), max.below()))
            level.setBlock(pos, Blocks.OAK_PLANKS.defaultBlockState(), Block.UPDATE_CLIENTS);
        helper.runAtTickTime(4, () -> {
            List<MobBuildingUseService.Destination> found = new ArrayList<>();
            MobBuildingUseService.addInteriors(pig, probe(level), found, 18);
            helper.assertTrue(!found.isEmpty(), "A valid covered interior should offer standing cells");
            building.setValidationState("invalid");
            found.clear();
            MobBuildingUseService.addInteriors(pig, probe(level), found, 18);
            helper.assertTrue(found.isEmpty(), "An invalid recognized building must not attract idle mobs");
            building.setValidationState("valid");
            for (BlockPos pos : BlockPos.betweenClosed(min.above(3), max.below()))
                level.setBlock(pos, Blocks.AIR.defaultBlockState(), Block.UPDATE_CLIENTS);
            found.clear();
            MobBuildingUseService.addInteriors(pig, probe(level), found, 18);
            helper.assertTrue(found.isEmpty(), "A stale record must not invent a roof after it is removed");
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", batch = "mob_context_idle")
    public static void combatBreedingAndExistingWalkKeepOwnership(GameTestHelper helper) {
        flatFloor(helper);
        Pig pig = idlePig(helper, new BlockPos(2, 2, 4));
        Pig other = idlePig(helper, new BlockPos(12, 2, 4));
        helper.runAtTickTime(4, () -> {
            ServerLevel level = helper.getLevel();
            helper.assertTrue(MobBuildingUseService.isAvailable(pig, level), "Idle pig must be eligible");
            pig.setTarget(other);
            helper.assertTrue(!MobBuildingUseService.isAvailable(pig, level), "Combat must win");
            pig.setTarget(null);
            pig.setInLoveTime(200);
            helper.assertTrue(!MobBuildingUseService.isAvailable(pig, level), "Breeding must win");
            pig.resetLove();
            BlockPos target = helper.absolutePos(new BlockPos(8, 2, 4));
            pig.setOnGround(true);
            helper.assertTrue(pig.getNavigation().moveTo(target.getX() + 0.5D,
                    target.getY(), target.getZ() + 0.5D, 0.6D), "Fixture needs a real existing walk");
            Path existing = pig.getNavigation().getPath();
            helper.assertTrue(!MobBuildingUseService.tryVisit(pig, level, false, false)
                    && pig.getNavigation().getPath() == existing, "Existing navigation must not be replaced");
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", batch = "mob_context_work")
    public static void villageWorkRestEmergencyAndCargoVetoVisits(GameTestHelper helper) {
        Villager villager = helper.spawn(EntityType.VILLAGER, new BlockPos(2, 2, 4));
        villager.setNoAi(true);
        villager.getBrain().setActiveActivityIfPossible(Activity.IDLE);
        ServerLevel level = helper.getLevel();
        helper.assertTrue(!MobBuildingUseService.villagerBusy(villager, level, 11000L),
                "Unassigned idle villager must be free after the work period");
        helper.assertTrue(MobBuildingUseService.villagerBusy(villager, level, 6000L),
                "Work hours must keep their normal owner");
        VillagerSimData.setEmergencyDuty(villager, "firefighter");
        helper.assertTrue(MobBuildingUseService.villagerBusy(villager, level, 11000L),
                "Fire emergency must win over furniture");
        VillagerSimData.clearEmergencyDuty(villager);
        VillagerSimData.setWorkCargo(villager, level.registryAccess(), List.of(new ItemStack(Items.OAK_LOG)), 8);
        helper.assertTrue(MobBuildingUseService.villagerBusy(villager, level, 11000L),
                "A worker carrying real goods must not be distracted");
        VillagerSimData.clearWorkCargo(villager);
        villager.getBrain().setActiveActivityIfPossible(Activity.REST);
        helper.assertTrue(MobBuildingUseService.villagerBusy(villager, level, 11000L),
                "Rest activity must win even before sleeping starts");
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "mob_context_route", skyAccess = true)
    public static void realDoorBridgeAndCoverContributeBoundedPreference(GameTestHelper helper) {
        flatFloor(helper);
        Pig pig = idlePig(helper, new BlockPos(2, 2, 4));
        ServerLevel level = helper.getLevel();
        BlockPos sample = helper.absolutePos(new BlockPos(7, 2, 4));
        Path path = new Path(List.of(new Node(sample.getX(), sample.getY(), sample.getZ())), sample, true);
        helper.runAtTickTime(4, () -> {
            int ordinary = MobBuildingUseService.pathPreference(pig, probe(level), path, true);
            level.setBlock(sample.below(), Blocks.OAK_PLANKS.defaultBlockState(), Block.UPDATE_CLIENTS);
            level.setBlock(sample.below(2), Blocks.WATER.defaultBlockState(), Block.UPDATE_CLIENTS);
            level.setBlock(sample.above(3), Blocks.OAK_PLANKS.defaultBlockState(), Block.UPDATE_CLIENTS);
            int flags = Block.UPDATE_CLIENTS | Block.UPDATE_KNOWN_SHAPE;
            level.setBlock(sample, Blocks.OAK_DOOR.defaultBlockState().setValue(DoorBlock.OPEN, true), flags);
            level.setBlock(sample.above(), Blocks.OAK_DOOR.defaultBlockState()
                    .setValue(DoorBlock.OPEN, true).setValue(DoorBlock.HALF, DoubleBlockHalf.UPPER), flags);
            int preferred = MobBuildingUseService.pathPreference(pig, probe(level), path, true);
            helper.assertTrue(preferred > ordinary && preferred == 15,
                    "Real doors, dry decks and cover need bounded bonuses: ordinary=" + ordinary + ", preferred=" + preferred);
            level.setBlock(sample, Blocks.IRON_DOOR.defaultBlockState(), flags);
            level.setBlock(sample.above(), Blocks.IRON_DOOR.defaultBlockState()
                    .setValue(DoorBlock.HALF, DoubleBlockHalf.UPPER), flags);
            helper.assertTrue(MobBuildingUseService.pathPreference(pig, probe(level), path, true)
                    == Integer.MIN_VALUE, "A closed iron door is not a contextual route");
            helper.assertTrue(MobBuildingUseService.routeBonus(true, true, 40, 40, true) == 15,
                    "Long covered paths must not accumulate unbounded attraction");
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", batch = "mob_context_navigation", timeoutTicks = 120)
    public static void contextualVisitUsesRealNavigationWithoutTeleport(GameTestHelper helper) {
        flatFloor(helper);
        Pig pig = idlePig(helper, new BlockPos(2, 2, 4));
        BlockPos target = helper.absolutePos(new BlockPos(8, 2, 4));
        helper.runAtTickTime(4, () -> {
            pig.setOnGround(true);
            var before = pig.position();
            helper.assertTrue(MobBuildingUseService.navigateBest(pig, helper.getLevel(),
                    List.of(new MobBuildingUseService.Destination(target, 20)), false),
                    "A free reachable contextual destination must start vanilla navigation");
            helper.assertTrue(pig.position().equals(before) && pig.getNavigation().isInProgress(),
                    "Choosing a destination must never teleport the mob");
            helper.succeedWhen(() -> helper.assertTrue(pig.blockPosition().distManhattan(target) <= 1,
                    "The mob has not yet physically walked to its destination"));
        });
    }

    @GameTest(template = "empty16x6x9", batch = "mob_context_unreachable")
    public static void sealedInteriorIsNeverTreatedAsReachable(GameTestHelper helper) {
        flatFloor(helper);
        Pig pig = idlePig(helper, new BlockPos(2, 2, 4));
        BlockPos target = helper.absolutePos(new BlockPos(9, 2, 4));
        ServerLevel level = helper.getLevel();
        for (int x = -1; x <= 1; x++) {
            for (int z = -1; z <= 1; z++) {
                if (x == 0 && z == 0) continue;
                for (int y = 0; y <= 2; y++)
                    level.setBlock(target.offset(x, y, z), Blocks.OBSIDIAN.defaultBlockState(), Block.UPDATE_CLIENTS);
            }
        }
        level.setBlock(target.above(2), Blocks.OBSIDIAN.defaultBlockState(), Block.UPDATE_CLIENTS);
        helper.runAtTickTime(4, () -> {
            pig.setOnGround(true);
            var before = pig.position();
            helper.assertTrue(!MobBuildingUseService.navigateBest(pig, level,
                    List.of(new MobBuildingUseService.Destination(target, 20)), true)
                    && pig.position().equals(before) && !pig.getNavigation().isInProgress(),
                    "A sealed room must not produce a partial-path visit or teleport");
            helper.succeed();
        });
    }

    @GameTest(template = "empty3x3x3", batch = "mob_context_budget")
    public static void blockProbeLimitAndUnloadedChunksFailClosed(GameTestHelper helper) {
        helper.runAtTickTime(4, () -> {
            ServerLevel level = helper.getLevel();
            MobBuildingUseService.Probe probe = new MobBuildingUseService.Probe(level, 2);
            int before = VillageSimulationScheduler.snapshot(level).backgroundProbes();
            BlockPos pos = helper.absolutePos(new BlockPos(1, 1, 1));
            helper.assertTrue(probe.state(pos) != null && probe.state(pos) != null
                    && probe.state(pos.above()) != null && probe.state(pos.below()) == null,
                    "A cached block is free, but unique reads must respect the local bound");
            helper.assertTrue(VillageSimulationScheduler.snapshot(level).backgroundProbes() - before == 2,
                    "Local contextual scans must charge the shared background budget");
            BlockPos unloaded = new BlockPos(29_000_000, 80, 29_000_000);
            helper.assertTrue(!VillageSimulationScheduler.isChunkLoaded(level, unloaded)
                    && probe(level).state(unloaded) == null
                    && !VillageSimulationScheduler.isChunkLoaded(level, unloaded),
                    "Reading a contextual candidate must not load an absent chunk");
            helper.succeed();
        });
    }

    private static MobBuildingUseService.Probe probe(ServerLevel level) {
        return new MobBuildingUseService.Probe(level, MobBuildingUseService.MAX_DESTINATION_PROBES);
    }

    private static Pig idlePig(GameTestHelper helper, BlockPos pos) {
        Pig pig = helper.spawn(EntityType.PIG, pos);
        pig.goalSelector.removeAllGoals(goal -> true);
        pig.setOnGround(true);
        return pig;
    }

    private static void flatFloor(GameTestHelper helper) {
        for (BlockPos pos : BlockPos.betweenClosed(new BlockPos(0, 1, 0), new BlockPos(15, 1, 8)))
            helper.setBlock(pos, Blocks.STONE);
    }
}
