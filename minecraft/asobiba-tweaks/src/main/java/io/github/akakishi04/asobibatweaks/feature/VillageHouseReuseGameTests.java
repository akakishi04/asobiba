package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.ChunkPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.Container;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** In-engine checks for V89 housing pressure and genuinely paid reuse. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageHouseReuseGameTests {
    private VillageHouseReuseGameTests() {}

    @GameTest(template = "empty3x3x3", batch = "housing_demand")
    public static void healthyReserveAndRecentHouseSuppressSpam(GameTestHelper helper) {
        VillageHousingPlanner.Demand safe = VillageHousingPlanner.evaluate(
                10, 12, 0, 88, 45, 25_000L, 0L, false, false);
        VillageHousingPlanner.Demand cooldown = VillageHousingPlanner.evaluate(
                10, 11, 0, 88, 45, 25_000L, 30_000L, false, false);
        VillageHousingPlanner.Demand after = VillageHousingPlanner.evaluate(
                10, 11, 0, 88, 45, 30_001L, 30_000L, false, false);
        if (safe.build() || safe.capacity() != 12 || safe.desired() != 12
                || cooldown.build() || cooldown.acute() || !after.build()
                || after.acute()) {
            helper.fail("Healthy spare beds and saved cooldown did not control housing demand",
                    new BlockPos(1, 1, 1));
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "housing_demand")
    public static void acuteShortageBypassesCooldownButDeduplicatesProjects(
            GameTestHelper helper) {
        VillageHousingPlanner.Demand urgent = VillageHousingPlanner.evaluate(
                10, 10, 2, 35, 4, 25_000L, 90_000L, false, false);
        VillageHousingPlanner.Demand alreadyBuilding = VillageHousingPlanner.evaluate(
                10, 10, 2, 35, 4, 25_000L, 90_000L, false, true);
        if (!urgent.build() || !urgent.acute() || urgent.score() < 70
                || alreadyBuilding.build()) {
            helper.fail("Real overcrowding must override normal delay, never duplicate projects",
                    new BlockPos(1, 1, 1));
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "house_reuse")
    public static void carpenterAddsPaidSecondBedWithoutAnotherHouse(GameTestHelper helper) {
        Fixture fixture = prepare(helper);
        fixture.storage().setItem(0, new ItemStack(Items.WHITE_WOOL, 3));
        fixture.storage().setItem(1, new ItemStack(Items.OAK_PLANKS, 6));
        helper.runAtTickTime(4, () -> {
            if (!VillageHouseReuseService.tryPlan(
                    fixture.builder(), fixture.level(), fixture.villageId())) {
                helper.fail("A valid, one-bed village home with real materials must be reused",
                        new BlockPos(6, 2, 4));
                return;
            }
            VillageSavedData.ProjectRecord furnishing = active(fixture);
            if (furnishing == null || !"interior".equals(furnishing.phase())) {
                helper.fail("Housing reuse did not persist a real building project",
                        new BlockPos(6, 2, 4));
                return;
            }
            VillageHouseReuseService.advance(fixture.builder(), fixture.level(), furnishing);
            if (!"complete".equals(furnishing.phase())
                    || !fixture.level().getBlockState(fixture.extraFoot()).is(Blocks.WHITE_BED)
                    || !fixture.level().getBlockState(fixture.extraHead()).is(Blocks.WHITE_BED)
                    || fixture.storage().getItem(0).getCount() != 0
                    || fixture.storage().getItem(1).getCount() != 3
                    || VillagerSimData.hasWorkCargo(
                            fixture.builder(), fixture.level().registryAccess(), 8)
                    || fixture.village().buildingIds().size() != 1
                    || fixture.village().nextHousingExpansionGameTime()
                            <= fixture.level().getGameTime()) {
                helper.fail("Physical second bed must consume 3 wool + 3 planks without duplicating homes",
                        new BlockPos(6, 2, 4));
                return;
            }
            VillageBuildingService.revalidateChunk(fixture.level(),
                    new ChunkPos(fixture.home().min()));
            if (fixture.home().validatedCapacity() != 2
                    || !"valid".equals(fixture.home().validationState())) {
                helper.fail("Original recognized house must regain exactly two real bed spaces",
                        new BlockPos(6, 2, 4));
                return;
            }
            CompoundTag state = fixture.data().save(
                    new CompoundTag(), fixture.level().registryAccess());
            VillageSavedData loaded = VillageSavedData.load(
                    state, fixture.level().registryAccess());
            if (loaded.village(fixture.villageId()).orElseThrow().buildingIds().size() != 1
                    || loaded.project(furnishing.id()).orElseThrow().workCursor() != 1
                    || !"complete".equals(loaded.project(furnishing.id())
                            .orElseThrow().phase())) {
                helper.fail("Village home reuse lost building identity or cursor on NBT roundtrip",
                        new BlockPos(6, 2, 4));
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", batch = "house_reuse")
    public static void playerOccupiedBedSpaceIsNeverOverwrittenOrCharged(
            GameTestHelper helper) {
        Fixture fixture = prepare(helper);
        fixture.storage().setItem(0, new ItemStack(Items.WHITE_BED));
        helper.runAtTickTime(4, () -> {
            if (!VillageHouseReuseService.tryPlan(
                    fixture.builder(), fixture.level(), fixture.villageId())) {
                helper.fail("Cannot verify obstruction without a scheduled furnishing",
                        new BlockPos(6, 2, 4));
                return;
            }
            VillageSavedData.ProjectRecord furnishing = active(fixture);
            fixture.level().setBlock(fixture.extraHead(),
                    Blocks.OBSIDIAN.defaultBlockState(), Block.UPDATE_ALL);
            VillageHouseReuseService.advance(fixture.builder(), fixture.level(), furnishing);
            if (!"cancelled".equals(furnishing.phase())
                    || !fixture.level().getBlockState(fixture.extraHead()).is(Blocks.OBSIDIAN)
                    || fixture.storage().getItem(0).getCount() != 1
                    || VillagerSimData.hasWorkCargo(
                            fixture.builder(), fixture.level().registryAccess(), 8)) {
                helper.fail("A player obstruction must veto reuse without spending or bulldozing",
                        new BlockPos(6, 2, 4));
                return;
            }
            helper.succeed();
        });
    }

    private static Fixture prepare(GameTestHelper helper) {
        ServerLevel level = helper.getLevel();
        BlockPos base = helper.absolutePos(new BlockPos(5, 1, 2));
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village =
                data.createVillage(base, level.getGameTime());
        VillageSavedData.ProjectRecord source = data.createProject(
                village.id(), "building", 75, base);
        source.setTemplateId("house_5x5");
        source.setParameter("plank", "oak");
        source.setParameter("lead_skill", "100");
        source.setParameter("outpost", "false");
        source.setVariantSeed(13L);
        source.setPhase("complete");

        // Reconstruct a genuine original complete shelter with a real bed;
        // this test never fakes physical room or block inventories.
        for (VillageSimulationEvents.BuildStep step :
                VillageSimulationEvents.projectPlan(source)) {
            if (step.cost() == null && !step.state().is(Blocks.WHITE_BED)) continue;
            if (step.state().is(Blocks.WHITE_BED)
                    || step.state().is(Blocks.COBBLESTONE)
                    || step.state().is(BlockTags.PLANKS)) {
                level.setBlock(step.pos(), step.state(), Block.UPDATE_CLIENTS);
            }
        }
        level.updateNeighborsAt(base.offset(2, 1, 2), Blocks.WHITE_BED);
        level.updateNeighborsAt(base.offset(2, 1, 3), Blocks.WHITE_BED);
        VillageSavedData.BuildingRecord building = data.createBuilding(
                village.id(), base, base.offset(4, 4, 4), true);
        building.setClassification("residential");
        building.setTemplateId("house_5x5");
        building.setValidationState("valid");
        building.setValidatedCapacity(1);
        building.setLastValidatedGameTime(level.getGameTime());

        BlockPos supplies = base.offset(3, 1, 1);
        level.setBlock(supplies, Blocks.BARREL.defaultBlockState(), Block.UPDATE_ALL);
        var stored = data.createStorage(village.id(), supplies, "construction");
        stored.setValidationState("valid");
        if (!(level.getBlockEntity(supplies) instanceof Container barrel))
            throw new IllegalStateException("GameTest did not create real materials Barrel");

        Villager builder = EntityType.VILLAGER.create(level);
        if (builder == null) throw new IllegalStateException("Cannot spawn Carpenter");
        builder.setPos(base.getX() + 2.5D, base.getY() + 2.0D, base.getZ() + 0.5D);
        builder.setNoAi(true);
        if (!level.addFreshEntity(builder)) throw new IllegalStateException("Carpenter spawn rejected");
        VillagerSimData.setVillageId(builder, village.id());
        VillagerSimData.setDuty(builder, "carpenter", level.getGameTime());
        VillageStorageService.reconcileVillage(village.id(), level);
        return new Fixture(level, data, village, building, builder, barrel,
                base.offset(1, 1, 2), base.offset(1, 1, 3));
    }

    private static VillageSavedData.ProjectRecord active(Fixture fixture) {
        return fixture.data().activeProjectsForVillage(fixture.villageId())
                .stream().filter(p -> VillageHouseReuseService.TEMPLATE.equals(p.templateId()))
                .findFirst().orElse(null);
    }

    private record Fixture(ServerLevel level, VillageSavedData data,
                           VillageSavedData.VillageRecord village,
                           VillageSavedData.BuildingRecord home,
                           Villager builder, Container storage,
                           BlockPos extraFoot, BlockPos extraHead) {
        UUID villageId() { return village.id(); }
    }
}
