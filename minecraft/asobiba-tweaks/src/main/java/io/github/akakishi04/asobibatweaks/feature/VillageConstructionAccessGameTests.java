package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
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
public final class VillageConstructionAccessGameTests {
    private static final BlockPos MARK = new BlockPos(10, 4, 5);
    private VillageConstructionAccessGameTests() {}

    @GameTest(template = "empty16x14x9", batch = "temporary_access_paid", timeoutTicks = 80)
    public static void supportedAccessPaysAndRecoversExactActualMaterials(GameTestHelper h) {
        Fixture f = setup(h);
        h.runAtTickTime(4, () -> {
            build(f);
            var plan = VillageConstructionAccessService.steps(f.project());
            if (plan.size() != 10 || !"10".equals(f.project().parameter("access_ramp_placed"))
                    || count(f.stock(), Items.OAK_PLANKS) != 0 || count(f.stock(), Items.OAK_STAIRS) != 0
                    || plan.stream().anyMatch(s -> !f.level().getBlockState(s.pos()).equals(s.state()))) {
                h.fail("Four supported temporary stairs must cost six planks and four real stairs", MARK); return;
            }
            var decoded = VillageSavedData.load(f.data().save(new CompoundTag(), f.level().registryAccess()), f.level().registryAccess());
            if (!"10".equals(decoded.project(f.project().id()).orElseThrow().parameter("access_ramp_placed"))) {
                h.fail("Temporary paid ownership cursor did not persist", MARK); return;
            }
            boolean done = false;
            for (int i = 0; i < 12; i++) done = VillageConstructionAccessService.cleanup(f.worker(), f.level(), f.project());
            if (!done || plan.stream().anyMatch(s -> !f.level().getBlockState(s.pos()).isAir())
                    || cargo(f, Items.OAK_PLANKS) != 6 || cargo(f, Items.OAK_STAIRS) != 4) {
                h.fail("Cleanup must recover each physically removed item once", MARK); return;
            }
            VillageConstructionAccessService.cleanup(f.worker(), f.level(), f.project());
            if (cargo(f, Items.OAK_PLANKS) != 6 || cargo(f, Items.OAK_STAIRS) != 4) {
                h.fail("Repeated cleanup duplicated recovered materials", MARK); return;
            }
            h.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", batch = "temporary_access_player", timeoutTicks = 80)
    public static void playerSameStateReplacementRevokesTemporaryOwnership(GameTestHelper h) {
        Fixture f = setup(h);
        h.runAtTickTime(4, () -> {
            build(f);
            var plan = VillageConstructionAccessService.steps(f.project());
            if (plan.size() != 10) { h.fail("No temporary stair plan", MARK); return; }
            var last = plan.getLast();
            // A player's break/re-place can look identical. The event alone
            // revokes ownership; state equality is insufficient for recovery.
            VillageConstructionAccessService.playerEdited(f.level(), last.pos());
            f.level().setBlock(last.pos(), last.state(), 3);
            boolean done = VillageConstructionAccessService.cleanup(f.worker(), f.level(), f.project());
            if (done || !f.level().getBlockState(last.pos()).equals(last.state())
                    || cargo(f, Items.OAK_PLANKS) != 0 || cargo(f, Items.OAK_STAIRS) != 0) {
                h.fail("Player-owned replacement must never be removed/refunded by cleanup", MARK); return;
            }
            h.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", batch = "temporary_access_occupied", timeoutTicks = 80)
    public static void occupiedTemporaryStepIsNotRemovedUnderWorker(GameTestHelper h) {
        Fixture f = setup(h);
        h.runAtTickTime(4, () -> {
            build(f);
            var plan = VillageConstructionAccessService.steps(f.project());
            if (plan.size() != 10) { h.fail("No temporary stair plan", MARK); return; }
            var last = plan.getLast();
            f.worker().setPos(last.pos().getX() + 0.5, last.pos().getY() + 1, last.pos().getZ() + 0.5);
            VillageConstructionAccessService.cleanup(f.worker(), f.level(), f.project());
            if (!f.level().getBlockState(last.pos()).equals(last.state())
                    || cargo(f, Items.OAK_PLANKS) != 0 || cargo(f, Items.OAK_STAIRS) != 0) {
                h.fail("Cleanup must wait for real worker movement off a supported step", MARK); return;
            }
            h.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", batch = "temporary_access_blocked", timeoutTicks = 80)
    public static void blockedAccessFootprintNeverConsumesOrOverwrites(GameTestHelper h) {
        Fixture f = setup(h);
        BlockPos occupied = f.project().site().offset(5, 1, 0);
        f.level().setBlock(occupied, Blocks.GLASS.defaultBlockState(), 3);
        h.runAtTickTime(4, () -> {
            VillageConstructionAccessService.approach(f.worker(), f.level(), f.project(), f.target());
            if (!f.project().parameter("access_ramp_height").isBlank()
                    || count(f.stock(), Items.OAK_PLANKS) != 6 || count(f.stock(), Items.OAK_STAIRS) != 4
                    || !f.level().getBlockState(occupied).is(Blocks.GLASS)) {
                h.fail("A blocked player footprint must preserve blocks and all stock", MARK); return;
            }
            h.succeed();
        });
    }

    private static void build(Fixture f) {
        for (int i = 0; i < 11; i++) VillageConstructionAccessService.approach(f.worker(), f.level(), f.project(), f.target());
    }
    private static Fixture setup(GameTestHelper h) {
        ServerLevel level = h.getLevel(); BlockPos base = h.absolutePos(new BlockPos(5, 1, 3));
        for (int z = -2; z <= 2; z++) {
            level.setBlock(base.offset(5, -1, z), Blocks.STONE.defaultBlockState(), 3);
            level.setBlock(base.offset(5, 0, z), Blocks.DIRT.defaultBlockState(), 3);
        }
        VillageSavedData data = VillageSavedData.get(level); var village = data.createVillage(base, level.getGameTime());
        var project = data.createProject(village.id(), "building", 70, base);
        project.setTemplateId("house_2story_5x5"); project.setParameter("plank", "oak"); project.setPhase("upper_shell");
        BlockPos supply = base.offset(2, 1, -1); level.setBlock(supply, Blocks.BARREL.defaultBlockState(), 3);
        var storage = data.createStorage(village.id(), supply, "construction"); storage.setValidationState("valid");
        Container stock = (Container)level.getBlockEntity(supply);
        stock.setItem(0, new ItemStack(Items.OAK_PLANKS, 6)); stock.setItem(1, new ItemStack(Items.OAK_STAIRS, 4));
        Villager worker = EntityType.VILLAGER.create(level);
        if (worker == null) throw new IllegalStateException("Cannot create Carpenter");
        worker.setPos(base.getX() + 4.5, base.getY() + 1, base.getZ() + 0.5); worker.setNoAi(true); level.addFreshEntity(worker);
        VillagerSimData.setVillageId(worker, village.id()); VillagerSimData.setDuty(worker, "carpenter", level.getGameTime());
        project.setLeadCarpenterId(worker.getUUID()); VillageStorageService.reconcileVillage(village.id(), level);
        return new Fixture(level, data, project, worker, stock, base.offset(0, 8, 4));
    }
    private static int count(Container c, net.minecraft.world.item.Item item) {
        int n = 0; for (int i = 0; i < c.getContainerSize(); i++) if (c.getItem(i).is(item)) n += c.getItem(i).getCount(); return n;
    }
    private static int cargo(Fixture f, net.minecraft.world.item.Item item) {
        return VillagerSimData.workCargoCount(f.worker(), f.level().registryAccess(), 8, item);
    }
    private record Fixture(ServerLevel level, VillageSavedData data, VillageSavedData.ProjectRecord project,
                           Villager worker, Container stock, BlockPos target) {}
}
