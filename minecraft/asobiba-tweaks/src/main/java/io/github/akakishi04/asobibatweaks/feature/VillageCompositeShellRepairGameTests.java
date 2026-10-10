package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.Container;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.Blocks;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageCompositeShellRepairGameTests {
    private static final BlockPos MARK = new BlockPos(5, 1, 2);
    private VillageCompositeShellRepairGameTests() {}

    @GameTest(template = "empty16x14x9", batch = "composite_shell_repair", timeoutTicks = 100)
    public static void expandedHomeRepairsOriginalAndUpperShellWithoutClosingStairs(GameTestHelper helper) {
        Fixture f = setup(helper, true);
        BlockPos lower = f.base().offset(0, 1, 1);
        BlockPos upper = f.base().offset(1, 12, 2);
        ((ServerLevel) f.builder().level()).setBlock(lower, Blocks.AIR.defaultBlockState(), 3);
        ((ServerLevel) f.builder().level()).setBlock(upper, Blocks.AIR.defaultBlockState(), 3);
        // The shared background-probe lane may be occupied by another real
        // validation on this tick. Exercise the planner's normal bounded retry,
        // without extending the test timeout or weakening the material checks.
        int[] attempts = {0};
        Runnable[] retry = new Runnable[1];
        retry[0] = () -> {
            var repair = plan(f);
            if (repair == null && ++attempts[0] < 8) {
                helper.runAfterDelay(2, retry[0]);
                return;
            }
            if (repair == null || repair.reservations().getOrDefault("minecraft:oak_planks", 0) != 2
                    || !"3".equals(repair.parameter("repair_blueprint_version"))) {
                helper.fail("Composite plan must contain both original wall and current upper roof: repair=" + (repair == null ? "null" : repair.reservations() + "/" + repair.parameter("repair_blueprint_version")) + ", active=" + f.data().activeProjectsForVillage(f.home().villageId()).stream().map(p -> p.templateId() + ":" + p.phase()).toList(), MARK);
                return;
            }
            var restored = VillageSavedData.load(f.data().save(new CompoundTag(),
                    helper.getLevel().registryAccess()), helper.getLevel().registryAccess())
                    .project(repair.id()).orElseThrow();
            if (!restored.parameter("repair_source_chain").equals(repair.parameter("repair_source_chain"))) {
                helper.fail("Composite source ancestry was not persisted", MARK);
                return;
            }
            VillageBuildingRepairService.advance(f.builder(), helper.getLevel(), repair);
            // Physically carry the second real plank before emulating roof travel.
            ItemStack payment = f.stock().removeItem(0, 1);
            f.stock().setChanged();
            if (!VillagerSimData.insertWorkCargo(f.builder(), helper.getLevel().registryAccess(), payment, 8).isEmpty())
                throw new IllegalStateException("Fixture Carpenter cargo full");
            move(f.builder(), upper);
            VillageBuildingRepairService.advance(f.builder(), helper.getLevel(), repair);
            if (!helper.getLevel().getBlockState(lower).is(Blocks.OAK_PLANKS)
                    || !helper.getLevel().getBlockState(upper).is(Blocks.OAK_PLANKS)
                    || !helper.getLevel().getBlockState(f.base().offset(3, 4, 1)).isAir()
                    || !helper.getLevel().getBlockState(f.base().offset(3, 8, 1)).isAir()
                    || count(f.stock()) != 62 || !"complete".equals(repair.phase())
                    || f.data().village(f.home().villageId()).orElseThrow().buildingIds().size() != 1) {
                helper.fail("Composite repair lost payment, reopened obsolete roofs, or duplicated home identity", MARK);
                return;
            }
            helper.succeed();
        };
        helper.runAtTickTime(4, retry[0]);
    }

    @GameTest(template = "empty16x6x9", batch = "composite_shell_repair", timeoutTicks = 100)
    public static void largeVillageRoofDamageUsesFinitePaidRepairBatches(GameTestHelper helper) {
        Fixture f = setup(helper, false);
        for (int x = 0; x < 4; x++) for (int z = 0; z < 4; z++)
            helper.getLevel().setBlock(f.base().offset(x, 4, z), Blocks.AIR.defaultBlockState(), 3);
        helper.runAtTickTime(14, () -> {
            var first = plan(f);
            if (first == null || first.reservations().getOrDefault("minecraft:oak_planks", 0) != 12) {
                helper.fail("More than twelve genuine holes must create a bounded first batch", MARK);
                return;
            }
            for (int i = 0; i < 12; i++) VillageBuildingRepairService.advance(f.builder(), helper.getLevel(), first);
            if (!"complete".equals(first.phase()) || count(f.stock()) != 52) {
                helper.fail("First repair batch must pay for exactly twelve physical planks", MARK);
                return;
            }
        });
        helper.runAtTickTime(22, () -> {
            var second = plan(f);
            if (second == null || second.reservations().getOrDefault("minecraft:oak_planks", 0) != 4) {
                helper.fail("Remaining roof holes must form a separate four-plank batch", MARK);
                return;
            }
            for (int i = 0; i < 4; i++) VillageBuildingRepairService.advance(f.builder(), helper.getLevel(), second);
            if (!"complete".equals(second.phase()) || count(f.stock()) != 48) {
                helper.fail("Large repair batches duplicated or lost physical material", MARK);
                return;
            }
            for (int x = 0; x < 4; x++) for (int z = 0; z < 4; z++) {
                if (!helper.getLevel().getBlockState(f.base().offset(x, 4, z)).is(Blocks.OAK_PLANKS)) {
                    helper.fail("Large damaged roof remains unfinished", MARK);
                    return;
                }
            }
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", batch = "composite_shell_repair", timeoutTicks = 100)
    public static void foreignExpansionAncestryCannotAuthorizeShellRebuilding(GameTestHelper helper) {
        Fixture f = setup(helper, true);
        var foreign = f.data().createVillage(f.base().offset(40, 0, 0), helper.getLevel().getGameTime());
        var impostor = f.data().createProject(foreign.id(), "building", 70, f.base());
        impostor.setTemplateId("house_2story_5x5");
        impostor.setPhase("complete");
        f.latest().setParameter("third_source", impostor.id().toString());
        helper.getLevel().setBlock(f.base().offset(1, 12, 2), Blocks.AIR.defaultBlockState(), 3);
        helper.runAtTickTime(32, () -> {
            if (plan(f) != null || count(f.stock()) != 64) {
                helper.fail("Foreign completed project must not authorize this building's composite repair", MARK);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", batch = "composite_shell_repair", timeoutTicks = 100)
    public static void legacyRepairIndicesKeepOriginalBlueprintMeaning(GameTestHelper helper) {
        Fixture f = setup(helper, false);
        BlockPos hole = f.base().offset(2, 4, 2);
        helper.getLevel().setBlock(hole, Blocks.AIR.defaultBlockState(), 3);
        List<VillageSimulationEvents.BuildStep> original = VillageSimulationEvents.projectPlan(f.latest());
        int index = -1;
        for (int i = 0; i < original.size(); i++) if (original.get(i).pos().equals(hole)) index = i;
        if (index < 0) throw new IllegalStateException("Legacy fixture roof step missing");
        var repair = f.data().createProject(f.home().villageId(), "building", 85, f.base());
        repair.setTemplateId(VillageBuildingRepairService.TEMPLATE);
        repair.setPhase("repair");
        repair.setParameter("repair_building_id", f.home().id().toString());
        repair.setParameter("repair_source_project", f.latest().id().toString());
        repair.setParameter("repair_blueprint_indices", Integer.toString(index));
        repair.setReservation("minecraft:oak_planks", 1);
        helper.runAtTickTime(42, () -> {
            VillageBuildingRepairService.advance(f.builder(), helper.getLevel(), repair);
            if (!helper.getLevel().getBlockState(hole).is(Blocks.OAK_PLANKS)
                    || count(f.stock()) != 63 || !"complete".equals(repair.phase())) {
                helper.fail("Legacy saved repair index changed meaning during composite upgrade", MARK);
                return;
            }
            helper.succeed();
        });
    }

    private static Fixture setup(GameTestHelper helper, boolean expanded) {
        var level = helper.getLevel();
        BlockPos base = helper.absolutePos(MARK);
        for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++)
            for (int y = 1; y <= (expanded ? 12 : 4); y++)
                level.setBlock(base.offset(x, y, z), Blocks.AIR.defaultBlockState(), 2);
        var data = VillageSavedData.get(level);
        var village = data.createVillage(base, level.getGameTime());
        var source = data.createProject(village.id(), "building", 70, base);
        source.setTemplateId("house_5x5"); source.setPhase("complete");
        source.setParameter("plank", "oak"); source.setParameter("lead_skill", "100"); source.setVariantSeed(25);
        source.setParameter("circulation_version", "2");
        for (var step : VillageSimulationEvents.projectPlan(source)) {
            if (step.cost() != null) level.setBlock(step.pos(), step.state(), 2);
        }
        var home = data.createBuilding(village.id(), base, base.offset(4, expanded ? 12 : 4, 4), true);
        home.setTemplateId(expanded ? "house_3story_5x5" : "house_5x5");
        home.setClassification("residential"); home.setValidationState("invalid");
        if (expanded) {
            var second = data.createProject(village.id(), "building", 70, base);
            second.setTemplateId(VillageHouseVerticalExpansionService.TEMPLATE); second.setPhase("complete");
            second.setParameter("expand_building", home.id().toString());
            second.setParameter("expand_original", source.id().toString()); second.setParameter("expand_plank", "oak");
            second.setParameter("circulation_version", "2");
            for (var step : VillageHouseVerticalExpansionService.steps(second)) {
                if (!step.bed()) level.setBlock(step.pos(), step.state(), 2);
            }
            var third = data.createProject(village.id(), "building", 70, base);
            third.setTemplateId(VillageHouseThirdFloorExpansionService.TEMPLATE); third.setPhase("complete");
            third.setParameter("third_building", home.id().toString());
            third.setParameter("third_source", second.id().toString()); third.setParameter("third_plank", "oak");
            third.setParameter("circulation_version", "2");
            for (var step : VillageHouseThirdFloorExpansionService.steps(third)) {
                if (step.kind() != VillageHouseThirdFloorExpansionService.PLACE_BED)
                    level.setBlock(step.pos(), step.state(), 2);
            }
            source = third;
        }
        BlockPos supply = base.offset(2, 1, 1);
        level.setBlock(supply, Blocks.BARREL.defaultBlockState(), 3);
        var storage = data.createStorage(village.id(), supply, "construction"); storage.setValidationState("valid");
        Container stock = (Container)level.getBlockEntity(supply);
        stock.setItem(0, new ItemStack(Items.OAK_PLANKS, 64));
        Villager builder = EntityType.VILLAGER.create(level);
        if (builder == null) throw new IllegalStateException("Carpenter creation failed");
        move(builder, base.offset(2, 1, 2)); builder.setNoAi(true);
        if (!level.addFreshEntity(builder)) throw new IllegalStateException("Carpenter spawn failed");
        VillagerSimData.setVillageId(builder, village.id());
        VillagerSimData.setDuty(builder, "carpenter", level.getGameTime());
        VillageStorageService.reconcileVillage(village.id(), level);
        return new Fixture(data, home, source, base, builder, stock);
    }

    private static VillageSavedData.ProjectRecord plan(Fixture f) {
        if (!VillageBuildingRepairService.tryPlan(f.builder(), ((ServerLevel) f.builder().level()), f.home().villageId())) return null;
        return f.data().activeProjectsForVillage(f.home().villageId()).stream()
                .filter(p -> VillageBuildingRepairService.TEMPLATE.equals(p.templateId())).findFirst().orElse(null);
    }
    private static void move(Villager builder, BlockPos at) {
        builder.setPos(at.getX() + 0.5D, at.getY() + 0.5D, at.getZ() + 0.5D);
    }
    private static int count(Container stock) {
        int count = 0;
        for (int i = 0; i < stock.getContainerSize(); i++) if (stock.getItem(i).is(Items.OAK_PLANKS)) count += stock.getItem(i).getCount();
        return count;
    }
    private record Fixture(VillageSavedData data, VillageSavedData.BuildingRecord home,
                           VillageSavedData.ProjectRecord latest, BlockPos base, Villager builder, Container stock) {}
}
