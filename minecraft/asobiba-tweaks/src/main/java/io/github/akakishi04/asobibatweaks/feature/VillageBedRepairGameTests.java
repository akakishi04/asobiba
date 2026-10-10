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
import net.minecraft.world.level.block.BedBlock;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.properties.BedPart;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageBedRepairGameTests {
    private VillageBedRepairGameTests() {}

    @GameTest(template = "empty16x6x9", batch = "bed_repair_paid", timeoutTicks = 80)
    public static void restoresOriginalBedForOneActualItemAndKeepsBuilding(GameTestHelper h) {
        Fixture f = prepare(h);
        h.runAtTickTime(4, () -> {
            var p = plan(h, f); if (p == null) return;
            int before = f.data().village(f.home().villageId()).orElseThrow().buildingIds().size();
            VillageBedRepairService.advance(f.worker(), f.level(), p);
            if (!f.level().getBlockState(f.foot()).is(Blocks.WHITE_BED)
                    || !f.level().getBlockState(f.foot().south()).is(Blocks.WHITE_BED)
                    || bedStock(f.stock()) != 1 || !"complete".equals(p.phase())
                    || !p.reservations().isEmpty() || before != f.data().village(f.home().villageId())
                            .orElseThrow().buildingIds().size()) {
                h.fail("Missing original bed must consume one real Bed and retain its building", new BlockPos(7, 2, 4)); return;
            }
            VillageBedRepairService.advance(f.worker(), f.level(), p);
            var saved = VillageSavedData.load(f.data().save(new CompoundTag(), f.level().registryAccess()), f.level().registryAccess());
            if (bedStock(f.stock()) != 1 || !"complete".equals(saved.project(p.id()).orElseThrow().phase())
                    || saved.building(f.home().id()).isEmpty()) {
                h.fail("Finished bed repair was paid twice or lost its identity across NBT", new BlockPos(7, 2, 4)); return;
            }
            h.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", batch = "bed_repair_player", timeoutTicks = 80)
    public static void playerReplacementCancelsWithoutSpendingBed(GameTestHelper h) {
        Fixture f = prepare(h);
        h.runAtTickTime(4, () -> {
            var p = plan(h, f); if (p == null) return;
            f.level().setBlock(f.foot().south(), Blocks.GLASS.defaultBlockState(), 3);
            VillageBedRepairService.advance(f.worker(), f.level(), p);
            if (!f.level().getBlockState(f.foot().south()).is(Blocks.GLASS)
                    || !f.level().getBlockState(f.foot()).isAir() || bedStock(f.stock()) != 2
                    || !"cancelled".equals(p.phase())) {
                h.fail("New player edit must survive without a repair charge", new BlockPos(7, 2, 4)); return;
            }
            h.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", batch = "bed_repair_partial", timeoutTicks = 80)
    public static void savedPaidHalfResumesWithoutSecondInventoryDebit(GameTestHelper h) {
        Fixture f = prepare(h);
        h.runAtTickTime(4, () -> {
            var p = plan(h, f); if (p == null) return;
            // Emulate the real interruption boundary: one physical Bed already
            // removed, paid state persisted, first exact half physically present.
            f.stock().removeItem(0, 1);
            p.setParameter("bed_repair_paid", "true");
            p.setParameter("bed_repair_observed_parts", "F");
            f.level().setBlock(f.foot(), Blocks.WHITE_BED.defaultBlockState()
                    .setValue(BedBlock.PART, BedPart.FOOT)
                    .setValue(BedBlock.FACING, net.minecraft.core.Direction.SOUTH), 2);
            var decoded = VillageSavedData.load(f.data().save(new CompoundTag(), f.level().registryAccess()), f.level().registryAccess());
            var restored = decoded.project(p.id()).orElseThrow();
            if (!Boolean.parseBoolean(restored.parameter("bed_repair_paid"))) {
                h.fail("Paid partial-bed marker did not persist", new BlockPos(7, 2, 4)); return;
            }
            // Restore durable fields on the live record as a replacement worker
            // would see them. No inventory or world block is synthesized here.
            p.setParameter("bed_repair_paid", restored.parameter("bed_repair_paid"));
            VillageBedRepairService.advance(f.worker(), f.level(), p);
            if (!"complete".equals(p.phase()) || bedStock(f.stock()) != 1
                    || !f.level().getBlockState(f.foot().south()).is(Blocks.WHITE_BED)) {
                h.fail("Saved paid partial repair consumed another Bed or failed to finish", new BlockPos(7, 2, 4)); return;
            }
            h.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", batch = "bed_repair_supply", timeoutTicks = 80)
    public static void absentPhysicalBedPausesWithoutFreeBedding(GameTestHelper h) {
        Fixture f = prepare(h); f.stock().clearContent();
        h.runAtTickTime(4, () -> {
            var p = plan(h, f); if (p == null) return;
            VillageBedRepairService.advance(f.worker(), f.level(), p);
            if (!f.level().getBlockState(f.foot()).isAir() || !f.level().getBlockState(f.foot().south()).isAir()
                    || "complete".equals(p.phase()) || Boolean.parseBoolean(p.parameter("bed_repair_paid"))) {
                h.fail("Empty storage must never create a Bed or paid marker", new BlockPos(7, 2, 4)); return;
            }
            h.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", batch = "bed_repair_orphan", timeoutTicks = 80)
    public static void unknownOrphanHalfNeverAuthorizesFreeReplacement(GameTestHelper h) {
        Fixture f = prepare(h);
        h.runAtTickTime(4, () -> {
            f.level().setBlock(f.foot(), Blocks.WHITE_BED.defaultBlockState()
                    .setValue(BedBlock.PART, BedPart.FOOT)
                    .setValue(BedBlock.FACING, net.minecraft.core.Direction.SOUTH), 2);
            if (VillageBedRepairService.tryPlan(f.worker(), f.level(), f.home().villageId())
                    || bedStock(f.stock()) != 2
                    || !f.level().getBlockState(f.foot().south()).isAir()) {
                h.fail("An unknown orphan half cannot prove original bed payment", new BlockPos(7, 2, 4)); return;
            }
            h.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", batch = "bed_repair_blocked", timeoutTicks = 80)
    public static void blockedEntranceNeverPlansReplacementCapacity(GameTestHelper h) {
        Fixture f = prepare(h);
        h.runAtTickTime(4, () -> {
            f.level().setBlock(f.home().min().offset(2, 1, 0), Blocks.GLASS.defaultBlockState(), 3);
            if (VillageBedRepairService.tryPlan(f.worker(), f.level(), f.home().villageId())
                    || bedStock(f.stock()) != 2) {
                h.fail("An inaccessible home cannot authorize replacement bedding", new BlockPos(7, 2, 4)); return;
            }
            h.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", batch = "bed_repair_second", timeoutTicks = 80)
    public static void expandedSecondFloorRepairsOnlyItsPaidBedBlueprint(GameTestHelper h) {
        expanded(h, false);
    }

    @GameTest(template = "empty16x14x9", batch = "bed_repair_third", timeoutTicks = 80)
    public static void expandedThirdFloorRepairsPaidBedWithoutRevivingSalvagedBed(GameTestHelper h) {
        expanded(h, true);
    }

    private static void expanded(GameTestHelper h, boolean third) {
        Fixture f = prepare(h); BlockPos base = f.home().min();
        var original = f.data().village(f.home().villageId()).orElseThrow().projectIds().stream()
                .map(f.data()::project).flatMap(java.util.Optional::stream).findFirst().orElseThrow();
        placeBed(f.level(), f.foot(), Blocks.WHITE_BED.defaultBlockState()
                .setValue(BedBlock.PART, BedPart.FOOT).setValue(BedBlock.FACING, net.minecraft.core.Direction.SOUTH));
        var second = f.data().createProject(f.home().villageId(), "building", 80, base);
        second.setTemplateId(VillageHouseVerticalExpansionService.TEMPLATE);
        second.setParameter("circulation_version", "2");
        second.setParameter("expand_building", f.home().id().toString());
        second.setParameter("expand_original", original.id().toString()); second.setParameter("expand_plank", "oak");
        for (var step : VillageHouseVerticalExpansionService.steps(second)) {
            if (step.bed()) placeBed(f.level(), step.pos(), step.state());
            else f.level().setBlock(step.pos(), step.state(), 2);
        }
        second.setPhase("complete"); f.data().upgradeVillageHouseSecondFloor(f.home().id());
        installV2Interior(f, false);
        second.setParameter("circulation_verified_v2", "true");
        if (third) {
            var top = f.data().createProject(f.home().villageId(), "building", 80, base);
            top.setTemplateId(VillageHouseThirdFloorExpansionService.TEMPLATE);
            top.setParameter("circulation_version", "2");
            top.setParameter("third_source_circulation", "2");
            top.setParameter("third_building", f.home().id().toString());
            top.setParameter("third_source", second.id().toString()); top.setParameter("third_plank", "oak");
            for (var step : VillageHouseThirdFloorExpansionService.steps(top)) {
                if (step.kind() == VillageHouseThirdFloorExpansionService.SALVAGE_BED) {
                    var old = f.level().getBlockState(step.pos());
                    f.level().setBlock(step.pos().relative(old.getValue(BedBlock.FACING)), Blocks.AIR.defaultBlockState(), 2);
                    f.level().setBlock(step.pos(), Blocks.AIR.defaultBlockState(), 2);
                } else if (step.kind() == VillageHouseThirdFloorExpansionService.PLACE_BED)
                    placeBed(f.level(), step.pos(), step.state());
                else f.level().setBlock(step.pos(), step.state(), 2);
            }
            top.setPhase("complete"); f.data().upgradeVillageHouseThirdFloor(f.home().id());
            installV2Interior(f, true);
            top.setParameter("circulation_verified_v2", "true");
        }
        BlockPos missing = base.offset(1, third ? 9 : 5, 2);
        f.level().setBlock(missing, Blocks.AIR.defaultBlockState(), 2);
        f.level().setBlock(missing.north(), Blocks.AIR.defaultBlockState(), 2);
        h.runAtTickTime(4, () -> {
            var repair = plan(h, f); if (repair == null) return;
            if (!repair.site().equals(missing)) {
                h.fail("Expansion repair selected a nominal or retired unpaid bed anchor", new BlockPos(6, 6, 4)); return;
            }
            VillageBedRepairService.advance(f.worker(), f.level(), repair);
            if (!"complete".equals(repair.phase())) {
                f.worker().setPos(base.getX() + 3.5, missing.getY(), base.getZ() + 3.5);
                VillageBedRepairService.advance(f.worker(), f.level(), repair);
            }
            if (!"complete".equals(repair.phase()) || bedStock(f.stock()) != 1
                    || !f.level().getBlockState(missing).is(Blocks.WHITE_BED)
                    || third && f.level().getBlockState(base.offset(2, 5, 1)).is(Blocks.WHITE_BED)) {
                h.fail("Expanded bed repair failed exact real payment or restored salvaged bed", new BlockPos(6, 6, 4)); return;
            }
            h.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", batch = "bed_repair_reuse", timeoutTicks = 80)
    public static void completedPaidReuseAuthorizesMissingSecondBedRepair(GameTestHelper h) {
        Fixture f = prepare(h);
        var original = f.data().village(f.home().villageId()).orElseThrow().projectIds().stream()
                .map(f.data()::project).flatMap(java.util.Optional::stream).findFirst().orElseThrow();
        placeBed(f.level(), f.foot(), Blocks.WHITE_BED.defaultBlockState()
                .setValue(BedBlock.PART, BedPart.FOOT).setValue(BedBlock.FACING, net.minecraft.core.Direction.SOUTH));
        BlockPos secondFoot = f.home().min().offset(1, 1, 2);
        var reuse = f.data().createProject(f.home().villageId(), "building", 80, secondFoot);
        reuse.setTemplateId(VillageHouseReuseService.TEMPLATE); reuse.setPhase("complete");
        reuse.setParameter("reuse_building", f.home().id().toString());
        reuse.setParameter("reuse_original_project", original.id().toString()); reuse.setParameter("reuse_wood", "oak");
        h.runAtTickTime(4, () -> {
            var p = plan(h, f); if (p == null) return;
            VillageBedRepairService.advance(f.worker(), f.level(), p);
            if (!p.site().equals(secondFoot) || !"complete".equals(p.phase())
                    || bedStock(f.stock()) != 1 || !f.level().getBlockState(secondFoot).is(Blocks.WHITE_BED)) {
                h.fail("Completed owner-linked second-bed reuse lost exact bedding restoration", new BlockPos(6, 2, 4)); return;
            }
            h.succeed();
        });
    }

    private static void installV2Interior(Fixture f, boolean third) {
        BlockPos base = f.home().min();
        for (BlockPos pos : BlockPos.betweenClosed(base, base.offset(4, third ? 12 : 8, 4)))
            if (f.level().getBlockState(pos).is(Blocks.WHITE_BED)) f.level().setBlock(pos, Blocks.AIR.defaultBlockState(), 2);
        for (BlockPos pos : new BlockPos[]{base.offset(4, 1, 1), base.offset(4, 2, 1), base.offset(2, 4, 1)})
            f.level().setBlock(pos, Blocks.AIR.defaultBlockState(), 2);
        if (third) f.level().setBlock(base.offset(2, 8, 1), Blocks.AIR.defaultBlockState(), 2);
        var foot = Blocks.WHITE_BED.defaultBlockState().setValue(BedBlock.PART, BedPart.FOOT);
        placeBed(f.level(), base.offset(1, 1, 3), foot.setValue(BedBlock.FACING, net.minecraft.core.Direction.EAST));
        placeBed(f.level(), base.offset(2, 5, 3), foot.setValue(BedBlock.FACING, net.minecraft.core.Direction.WEST));
        if (third) {
            placeBed(f.level(), base.offset(1, 9, 2), foot.setValue(BedBlock.FACING, net.minecraft.core.Direction.NORTH));
            placeBed(f.level(), base.offset(2, 9, 3), foot.setValue(BedBlock.FACING, net.minecraft.core.Direction.WEST));
        } else placeBed(f.level(), base.offset(1, 5, 2), foot.setValue(BedBlock.FACING, net.minecraft.core.Direction.NORTH));
    }

    private static void placeBed(ServerLevel level, BlockPos foot, net.minecraft.world.level.block.state.BlockState state) {
        level.setBlock(foot, state, 2);
        level.setBlock(foot.relative(state.getValue(BedBlock.FACING)), state.setValue(BedBlock.PART, BedPart.HEAD), 2);
    }

    @GameTest(template = "empty16x6x9", batch = "bed_repair_revoked", timeoutTicks = 80)
    public static void brokenPaidHalfCannotProduceAnotherFreeBed(GameTestHelper h) {
        Fixture f = prepare(h);
        h.runAtTickTime(4, () -> {
            var p = plan(h, f); if (p == null) return;
            f.stock().removeItem(0, 1);
            p.setParameter("bed_repair_paid", "true");
            p.setParameter("bed_repair_observed_parts", "F");
            f.level().setBlock(f.foot(), Blocks.WHITE_BED.defaultBlockState()
                    .setValue(BedBlock.PART, BedPart.FOOT)
                    .setValue(BedBlock.FACING, net.minecraft.core.Direction.SOUTH), 2);
            VillageBedRepairService.playerEdited(f.level(), f.foot());
            f.level().destroyBlock(f.foot(), true);
            VillageBedRepairService.advance(f.worker(), f.level(), p);
            if (!"cancelled".equals(p.phase()) || !f.level().getBlockState(f.foot()).isAir()
                    || !f.level().getBlockState(f.foot().south()).isAir() || bedStock(f.stock()) != 1) {
                h.fail("Breaking a paid half must revoke its free replacement entitlement", new BlockPos(7, 2, 4)); return;
            }
            h.succeed();
        });
    }

    private static VillageSavedData.ProjectRecord plan(GameTestHelper h, Fixture f) {
        if (!VillageBedRepairService.tryPlan(f.worker(), f.level(), f.home().villageId())) {
            h.fail("Supported original missing bed did not create repair", new BlockPos(7, 2, 4)); return null;
        }
        return f.data().activeProjectsForVillage(f.home().villageId()).stream()
                .filter(p -> VillageBedRepairService.TEMPLATE.equals(p.templateId())).findFirst().orElseThrow();
    }
    private static Fixture prepare(GameTestHelper h) {
        ServerLevel level = h.getLevel(); BlockPos base = h.absolutePos(new BlockPos(5, 1, 2));
        VillageSavedData data = VillageSavedData.get(level);
        var village = data.createVillage(base, level.getGameTime());
        var source = data.createProject(village.id(), "building", 70, base);
        source.setTemplateId("house_5x5"); source.setVariantSeed(25);
        source.setParameter("plank", "oak"); source.setParameter("lead_skill", "100"); source.setPhase("complete");
        for (var step : VillageSimulationEvents.projectPlan(source))
            if (!step.state().is(Blocks.WHITE_BED)) level.setBlock(step.pos(), step.state(), 3);
        var home = data.createBuilding(village.id(), base, base.offset(4, 4, 4), true);
        home.setTemplateId("house_5x5"); home.setClassification("residential"); home.setValidationState("invalid");
        BlockPos supply = base.offset(-2, 1, 1);
        level.setBlock(supply, Blocks.BARREL.defaultBlockState(), 3);
        var storage = data.createStorage(village.id(), supply, "construction"); storage.setValidationState("valid");
        Container barrel = (Container)level.getBlockEntity(supply); barrel.setItem(0, new ItemStack(Items.WHITE_BED)); barrel.setItem(1, new ItemStack(Items.WHITE_BED));
        Villager worker = EntityType.VILLAGER.create(level);
        if (worker == null) throw new IllegalStateException("Cannot create Carpenter");
        // Material staging has a real three-block interaction radius. Start
        // beside the real Barrel, on real footing, rather than freezing this
        // fixture four blocks away and expecting navigation to teleport it.
        level.setBlock(base.offset(-1, 0, 1), Blocks.COBBLESTONE.defaultBlockState(), 3);
        worker.setPos(base.getX() - 0.5, base.getY() + 1, base.getZ() + 1.5); worker.setNoAi(true); level.addFreshEntity(worker);
        VillagerSimData.setVillageId(worker, village.id()); VillagerSimData.setDuty(worker, "carpenter", level.getGameTime());
        VillageStorageService.reconcileVillage(village.id(), level);
        return new Fixture(level, data, home, worker, barrel, base.offset(2, 1, 2));
    }
    private static int bedStock(Container stock) {
        int count = 0;
        for (int i = 0; i < stock.getContainerSize(); i++) if (stock.getItem(i).is(Items.WHITE_BED)) count += stock.getItem(i).getCount();
        return count;
    }
    private record Fixture(ServerLevel level, VillageSavedData data, VillageSavedData.BuildingRecord home,
                           Villager worker, Container stock, BlockPos foot) {}
}
