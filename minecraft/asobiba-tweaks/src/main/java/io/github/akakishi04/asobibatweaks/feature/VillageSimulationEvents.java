package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaRegistries;
import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.Locale;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundSource;
import net.minecraft.tags.BlockTags;
import net.minecraft.tags.FluidTags;
import net.minecraft.tags.ItemTags;
import net.minecraft.world.Container;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.animal.Sheep;
import net.neoforged.neoforge.event.entity.living.BabyEntitySpawnEvent;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.npc.VillagerProfession;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.BedBlock;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BedPart;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.phys.AABB;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.common.BasicItemListing;
import net.neoforged.neoforge.event.entity.player.TradeWithVillagerEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;
import net.neoforged.neoforge.event.village.VillagerTradesEvent;

public final class VillageSimulationEvents {
    private static final int WORKER_CARGO_SLOTS = 8;
    private static final int CARPENTER_CARGO_SLOTS = 8;
    private static final int PORTER_CARGO_SLOTS = 16;

    private static final String BUILD_X = "asobibatweaks_build_x";
    private static final String BUILD_Y = "asobibatweaks_build_y";
    private static final String BUILD_Z = "asobibatweaks_build_z";
    private static final String BUILD_STEP = "asobibatweaks_build_step";
    private static final String BUILD_ACTIVE = "asobibatweaks_build_active";
    private static final String BUILDER_XP = "asobibatweaks_builder_xp";
    private static final String NEXT_BUILD = "asobibatweaks_next_build";
    private static final String DISTRESS = "asobibatweaks_village_distress";
    private static final String RECOVERY_UNTIL = "asobibatweaks_village_recovery_until";
    private static final String BUILD_ANCHOR_X = "asobibatweaks_build_anchor_x";
    private static final String BUILD_ANCHOR_Z = "asobibatweaks_build_anchor_z";
    private static final String BUILD_OUTPOST = "asobibatweaks_build_outpost";
    private static final String BUILD_COLONY = "asobibatweaks_build_colony";
    private static final String BUILD_KIND = "asobibatweaks_build_kind";
    private static final String SHORTAGE_STREAK = "asobibatweaks_shortage_streak";

    @SubscribeEvent
    public void onTrades(VillagerTradesEvent event) {
        if (!AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()) return;

        if (AsobibaTweaksConfig.ENCHANTMENT_POOL_BOOKSHELF_ENABLED.getAsBoolean()
                && event.getType() == VillagerProfession.LIBRARIAN) {
            event.getTrades().get(4).add(new BasicItemListing(
                    24, new ItemStack(AsobibaRegistries.ARCANE_FOLIO.get()), 6, 15));
        }

        if (!AsobibaTweaksConfig.VILLAGE_CARPENTER_ENABLED.getAsBoolean()
                || event.getType() != AsobibaRegistries.CARPENTER.value()) return;

        event.getTrades().get(1).add((trader, random) -> {
            CarpenterTradeWood wood = carpenterTradeWood(trader);
            return new net.minecraft.world.item.trading.MerchantOffer(
                    new net.minecraft.world.item.trading.ItemCost(wood.log(), 16),
                    new ItemStack(Items.EMERALD), 16, 2, 0.05F);
        });
        event.getTrades().get(1).add(new BasicItemListing(
                1, new ItemStack(Items.SCAFFOLDING, 8), 12, 1));
        event.getTrades().get(2).add(new BasicItemListing(
                new ItemStack(Items.COBBLESTONE, 24), new ItemStack(Items.EMERALD), 12, 5, 0.05F));
        event.getTrades().get(2).add((trader, random) -> {
            CarpenterTradeWood wood = carpenterTradeWood(trader);
            return new net.minecraft.world.item.trading.MerchantOffer(
                    new net.minecraft.world.item.trading.ItemCost(Items.EMERALD, 2),
                    new ItemStack(wood.door(), 4), 12, 5, 0.05F);
        });
        event.getTrades().get(3).add((trader, random) -> {
            CarpenterTradeWood wood = carpenterTradeWood(trader);
            return new net.minecraft.world.item.trading.MerchantOffer(
                    new net.minecraft.world.item.trading.ItemCost(Items.EMERALD, 2),
                    new ItemStack(wood.fence(), 12), 12, 10, 0.05F);
        });
        event.getTrades().get(4).add(new BasicItemListing(
                3, new ItemStack(Items.BRICKS, 16), 8, 15));
        event.getTrades().get(5).add(new BasicItemListing(
                5, new ItemStack(Items.LANTERN, 4), 6, 25));
    }

    @SubscribeEvent
    public void onVillagerTick(EntityTickEvent.Post event) {
        if (!AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof Villager villager)
                || villager.level().isClientSide()
                || villager.tickCount % 40 != Math.floorMod(villager.getId(), 40)) {
            return;
        }

        ServerLevel level = (ServerLevel)villager.level();

        // V1 persistence foundation: all loaded villagers, including children, receive the
        // namespaced persistent state and conservative stable Village-ID bootstrap.
        VillageIdentityBootstrap.ensure(villager, level);

        // Periodic reconciliation is limited to already-recognized StorageRecords; it never
        // scans arbitrary containers outside the V3 storage index.
        VillagerSimData.villageId(villager).ifPresent(villageId -> {
            if (villager.tickCount % 200 == Math.floorMod(villager.getId(), 200)) {
                VillageSimulationScheduler.enqueueReconciliation(
                        level,
                        "storage_reconcile:" + villageId,
                        () -> VillageStorageService.reconcileVillage(villageId, level)
                );
            }
        });

        if (VillagerSimData.migrationId(villager).isPresent()) return;
        if (!"none".equals(VillagerSimData.emergencyDuty(villager))) return;

        // Children participate in persistent settlement identity but never execute ordinary Duties.
        if (villager.isBaby()) return;

        String id = villager.getUUID().toString();
        if (VillageOutpostLifecycleService.handleAssignedWorker(villager, level)) {
            return;
        }

        VillageDutyScheduler.ensureFormalDuty(villager, level.getGameTime());
        String duty = VillagerSimData.duty(villager);

        if ("carpenter".equals(duty)
                && AsobibaTweaksConfig.VILLAGE_CARPENTER_ENABLED.getAsBoolean()
                && AsobibaTweaksConfig.VILLAGE_AUTONOMOUS_GROWTH_ENABLED.getAsBoolean()) {
            if (hasActiveCarpenterProject(villager, level) || villager.getPersistentData().getBoolean(BUILD_ACTIVE)) {
                VillageSimulationScheduler.enqueueWorker(level, "carpenter_work:" + id,
                        () -> runIfActive(villager, level, () -> tickCarpenter(villager, level)));
            } else {
                VillageSimulationScheduler.enqueuePlanning(level, "carpenter_plan:" + id,
                        () -> runIfActive(villager, level, () -> tickCarpenter(villager, level)));
            }
        } else if (AsobibaTweaksConfig.VILLAGE_LOGISTICS_ENABLED.getAsBoolean()
                && "quarry".equals(duty)) {
            VillageSimulationScheduler.enqueueWorker(level, "quarry:" + id,
                    () -> runIfActive(villager, level, () -> tickQuarryWorker(villager, level)));
        } else if (AsobibaTweaksConfig.VILLAGE_LOGISTICS_ENABLED.getAsBoolean()
                && "forester".equals(duty)) {
            VillageSimulationScheduler.enqueueWorker(level, "forester:" + id,
                    () -> runIfActive(villager, level, () -> tickForester(villager, level)));
        } else if (AsobibaTweaksConfig.VILLAGE_LOGISTICS_ENABLED.getAsBoolean()
                && "quartermaster".equals(duty)) {
            VillageSimulationScheduler.enqueueReconciliation(level, "quartermaster:" + id,
                    () -> runIfActive(villager, level, () -> tickQuartermaster(villager, level)));
        } else if (AsobibaTweaksConfig.VILLAGE_LOGISTICS_ENABLED.getAsBoolean()
                && "porter".equals(duty)) {
            VillageSimulationScheduler.enqueueWorker(level, "porter:" + id,
                    () -> runIfActive(villager, level, () -> tickPorter(villager, level)));
        } else if (AsobibaTweaksConfig.VILLAGE_LOGISTICS_ENABLED.getAsBoolean()
                && "shepherd".equals(duty)) {
            VillageSimulationScheduler.enqueueWorker(level, "shepherd:" + id,
                    () -> runIfActive(villager, level, () -> tickShepherd(villager, level)));
        } else if (AsobibaTweaksConfig.VILLAGE_LOGISTICS_ENABLED.getAsBoolean()
                && "fisher".equals(duty)) {
            VillageSimulationScheduler.enqueueWorker(level, "fisher:" + id,
                    () -> runIfActive(villager, level, () -> tickFisher(villager, level)));
        } else if (AsobibaTweaksConfig.VILLAGE_LOGISTICS_ENABLED.getAsBoolean()
                && "farmer".equals(duty)) {
            VillageSimulationScheduler.enqueueWorker(level, "farmer:" + id,
                    () -> runIfActive(villager, level, () -> tickFarmer(villager, level)));
        }

        if (AsobibaTweaksConfig.MOB_USED_BUILDINGS_ENABLED.getAsBoolean()) {
            VillageSimulationScheduler.enqueueValidation(level, "villager_shelter:" + id,
                    () -> runIfActive(villager, level, () -> useBuildingsInRain(villager, level)));
        }
    }

    @SubscribeEvent
    public void onBaby(BabyEntitySpawnEvent event) {
        if (!AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                || !AsobibaTweaksConfig.VILLAGE_BREEDING_ENABLED.getAsBoolean()
                || !(event.getParentA() instanceof Villager parentA)
                || !(event.getParentB() instanceof Villager parentB)
                || !(parentA.level() instanceof ServerLevel level)) {
            return;
        }

        if (!VillagePopulationMigrationService.allowBirth(parentA, parentB, level)) {
            event.setCanceled(true);
        }
    }

    @SubscribeEvent
    public void onRegionalTrade(TradeWithVillagerEvent event) {
        if (!AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                || !(event.getAbstractVillager() instanceof Villager villager)) {
            return;
        }

        VillageIdentityBootstrap.ensure(villager, (ServerLevel)villager.level());
        VillageEconomyService.acceptCompletedTrade(villager, event.getMerchantOffer());
    }

    private static boolean hasActiveCarpenterProject(Villager villager, ServerLevel level) {
        var villageId = VillagerSimData.villageId(villager);
        if (villageId.isEmpty()) return false;
        VillageSavedData data = VillageSavedData.get(level);
        return selectBuildingProject(data, villageId.get()) != null
                || selectRoadProject(data, villageId.get()) != null;
    }

    private static void tickCarpenter(Villager villager, ServerLevel level) {
        long now = level.getGameTime();
        if (VillagerSimData.carpentrySkill(villager) == 0) {
            int legacyXp = Math.max(0, villager.getPersistentData().getInt(BUILDER_XP));
            if (legacyXp > 0) VillagerSimData.setCarpentrySkill(villager, Math.min(100, legacyXp * 10));
        }
        var villageId = VillagerSimData.villageId(villager);
        if (villageId.isEmpty()) return;

        migrateLegacyBuild(villager, level, villageId.get());

        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.ProjectRecord active = selectBuildingProject(data, villageId.get());
        if (active != null) {
            int skill = VillagerSimData.carpentrySkill(villager);
            int actions = skill >= 75 ? 2 : 1;
            for (int i = 0; i < actions && !"complete".equals(active.phase())
                    && !"cancelled".equals(active.phase()); i++) {
                buildOneProjectStep(villager, level, active);
            }
            return;
        }

        VillageSavedData.ProjectRecord road = selectRoadProject(data, villageId.get());
        if (road != null) {
            buildOneRoadProjectStep(villager, level, road);
            return;
        }

        if (now < villager.getPersistentData().getLong(NEXT_BUILD)) return;
        if (!isWorkTime(level)) return;
        if (!areaLoaded(level, villager.blockPosition(), 24, 5, 5)) return;

        AABB villageArea = villager.getBoundingBox().inflate(28.0D);
        int population = level.getEntitiesOfClass(Villager.class, villageArea).size();
        int beds = countBlocks(level, villager.blockPosition(), 24, state -> state.is(BlockTags.BEDS));
        int stores = data.storagesForVillage(villageId.get()).size();
        if (population < 4) {
            villager.getPersistentData().putLong(NEXT_BUILD, now + 12000L);
            return;
        }

        int skill = VillagerSimData.carpentrySkill(villager);
        int activeProjects = data.activeProjectsForVillage(villageId.get()).size();
        int projectCap = population < 12 ? 1 : population < 28 ? 2 : 3;
        if (activeProjects >= projectCap) {
            villager.getPersistentData().putLong(NEXT_BUILD, now + 2400L);
            return;
        }

        VillageHousingPlanner.Demand housingDemand =
                VillageHousingPlanner.assess(level, data, villageId.get(), population, beds);
        boolean housingNeed = housingDemand.build();
        boolean storageNeed = stores < Math.max(2, (population + 3) / 4);

        // Restore a small number of genuine missing shell blocks in existing
        // village-owned buildings before building another detached house.
        if (VillageBuildingRepairService.tryPlan(villager, level, villageId.get())) {
            villager.getPersistentData().putLong(NEXT_BUILD, now + 2400L);
            return;
        }
        if (housingNeed && VillageHouseReuseService.tryPlan(
                villager, level, villageId.get())) {
            villager.getPersistentData().putLong(NEXT_BUILD, now + 2400L);
            return;
        }

        // Reuse a safe, publicly usable player-adopted structure before
        // spending a full new-building budget. Only completed workstation
        // items in real recognized storage can initiate such a project.
        if (VillageWorkstationRetrofitService.tryPlan(villager, level, villageId.get())) {
            villager.getPersistentData().putLong(NEXT_BUILD, now + 2400L);
            return;
        }
        VillageSavedData.VillageRecord village = data.village(villageId.get()).orElse(null);
        VillageSavedData.WorkSiteRecord fissionOutpost = findFissionOutpost(
                level, data, village, now, population, skill);
        boolean colony = fissionOutpost != null;
        String outpostPurpose = colony || village == null ? "" : chooseOutpostPurpose(village);
        boolean outpost = !colony
                && !outpostPurpose.isBlank()
                && AsobibaTweaksConfig.VILLAGE_OUTPOSTS_ENABLED.getAsBoolean()
                && !housingNeed && !storageNeed && population >= 6
                && skill >= 25 && Math.floorMod((int)(now / 24000L) + villager.getId(), 4) == 3;
        boolean craftHallNeed = !housingNeed && !storageNeed
                && !colony && !outpost && skill >= 25
                && VillageCraftHallPlanner.needsHall(
                        villager, level, data, villageId.get());
        String specialist = !housingNeed && !storageNeed
                && !colony && !outpost && !craftHallNeed && skill >= 25
                ? VillageSpecialistWorkshopService.neededTemplate(
                        villager, level, data, villageId.get())
                : "";

        if (!housingNeed && !storageNeed && !outpost && !colony
                && !craftHallNeed && specialist.isBlank()) {
            villager.getPersistentData().putLong(NEXT_BUILD, now + 12000L);
            return;
        }

        if (VillageStorageService.count(villager, level, Items.OAK_PLANKS, Items.SPRUCE_PLANKS,
                Items.BIRCH_PLANKS, Items.ACACIA_PLANKS, Items.JUNGLE_PLANKS, Items.MANGROVE_PLANKS,
                Items.CHERRY_PLANKS, Items.COBBLESTONE) < 28) {
            requestMaterials(villager, "planks/cobblestone");
            villager.getPersistentData().putLong(NEXT_BUILD, now + 2400L);
            return;
        }

        int buildKind = storageNeed && !housingNeed && !colony ? 1 : 0;

        String templateId;
        if (buildKind == 1) templateId = "storage_5x5";
        else if (colony) templateId = "house_2story_5x5";
        else if (outpost) templateId = "house_5x5";
        else if (craftHallNeed) templateId = VillageCraftHallPlanner.TEMPLATE;
        else if (!specialist.isBlank()) templateId = specialist;
        else if (skill >= 75 && population >= 16) templateId = "house_3story_5x5";
        else if (skill >= 50 && population >= 8) templateId = "house_2story_5x5";
        else if (skill >= 25 && population >= 6) templateId = "house_gabled_5x5";
        else templateId = "house_5x5";

        int templateMaxY = templateMaxY(templateId);
        BlockPos site;
        if (colony) {
            BlockPos outpostCenter = workSiteCenter(fissionOutpost);
            site = findBuildSiteNear(level, outpostCenter, villager, templateMaxY);
        } else if (outpost) {
            site = findOutpostBuildSite(villager, level, outpostPurpose);
        } else {
            site = findBuildSite(villager, level, false, false, templateMaxY);
        }
        if (site == null) {
            villager.getPersistentData().putLong(NEXT_BUILD, now + 12000L);
            return;
        }

        VillageSavedData.ProjectRecord project = data.createProject(
                villageId.get(), "building",
                housingNeed ? housingDemand.acute() ? 90 : 75 : storageNeed ? 70
                        : craftHallNeed || !specialist.isBlank() ? 65 : 40, site);
        project.setTemplateId(templateId);
        project.setVariantSeed(villager.getUUID().getLeastSignificantBits() ^ site.asLong());
        project.setLeadCarpenterId(villager.getUUID());
        project.setAnchor(villager.blockPosition());
        project.setParameter("outpost", Boolean.toString(outpost || colony));
        project.setParameter("colony", Boolean.toString(colony));
        if (outpost) project.setParameter("outpost_purpose", outpostPurpose);
        if (colony && fissionOutpost != null) project.setParameter("outpost_id", fissionOutpost.id().toString());
        project.setParameter("lead_skill", Integer.toString(skill));
        project.setParameter("plank", plankName(chooseBuildingPlanks(level, site, villager)));
        project.setPhase("foundation");
        project.setWorkCursor(0);
        project.setPausedReason("");
        initializeProjectReservations(project, projectPlan(project), 0);
        data.touch();

        villager.getNavigation().moveTo(site.getX() + 2.0D, site.getY(), site.getZ() + 2.0D, 0.7D);
    }

    private static VillageSavedData.ProjectRecord selectBuildingProject(VillageSavedData data, java.util.UUID villageId) {
        for (VillageSavedData.ProjectRecord project : data.activeProjectsForVillage(villageId)) {
            if ("building".equals(project.type())) return project;
        }
        return null;
    }

    private static VillageSavedData.ProjectRecord selectRoadProject(VillageSavedData data, java.util.UUID villageId) {
        for (VillageSavedData.ProjectRecord project : data.activeProjectsForVillage(villageId)) {
            if ("road".equals(project.type())) return project;
        }
        return null;
    }

    private static void migrateLegacyBuild(Villager villager, ServerLevel level, java.util.UUID villageId) {
        var legacy = villager.getPersistentData();
        if (!legacy.getBoolean(BUILD_ACTIVE)) return;

        VillageSavedData data = VillageSavedData.get(level);
        if (selectBuildingProject(data, villageId) != null) {
            legacy.putBoolean(BUILD_ACTIVE, false);
            return;
        }

        BlockPos site = new BlockPos(legacy.getInt(BUILD_X), legacy.getInt(BUILD_Y), legacy.getInt(BUILD_Z));
        int kind = legacy.getInt(BUILD_KIND);
        VillageSavedData.ProjectRecord project = data.createProject(villageId, "building", 75, site);
        project.setTemplateId(kind == 1 ? "storage_5x5" : "house_5x5");
        project.setVariantSeed(villager.getUUID().getLeastSignificantBits() ^ site.asLong());
        project.setLeadCarpenterId(villager.getUUID());
        project.setAnchor(new BlockPos(legacy.getInt(BUILD_ANCHOR_X), site.getY(), legacy.getInt(BUILD_ANCHOR_Z)));
        project.setParameter("outpost", Boolean.toString(legacy.getBoolean(BUILD_OUTPOST)));
        project.setParameter("colony", Boolean.toString(legacy.getBoolean(BUILD_COLONY)));
        project.setParameter("lead_skill", Integer.toString(VillagerSimData.carpentrySkill(villager)));
        project.setParameter("plank", plankName(chooseBuildingPlanks(level, site, villager)));
        project.setWorkCursor(Math.max(0, legacy.getInt(BUILD_STEP)));
        project.setPhase(projectPhase(project));
        initializeProjectReservations(project, projectPlan(project), project.workCursor());
        data.touch();

        legacy.putBoolean(BUILD_ACTIVE, false);
        legacy.remove(BUILD_STEP);
        legacy.remove(BUILD_OUTPOST);
        legacy.remove(BUILD_COLONY);
    }

    private static void buildOneProjectStep(Villager villager, ServerLevel level,
                                            VillageSavedData.ProjectRecord project) {
        if (!isWorkTime(level)) return;

        // A retrofit is a single safe, physical placement into a recognized
        // existing building. Never generate a 5x5 shell or register a new
        // BuildingRecord for the already-adopted structure.
        if (VillageWorkstationRetrofitService.TEMPLATE.equals(project.templateId())) {
            VillageWorkstationRetrofitService.advance(
                    villager, level, project, CARPENTER_CARGO_SLOTS);
            return;
        }
        if (VillageRiverDockService.TEMPLATE.equals(project.templateId())) {
            VillageRiverDockService.advance(villager, level, project);
            return;
        }
        if (VillageBuildingRepairService.TEMPLATE.equals(project.templateId())) {
            VillageBuildingRepairService.advance(villager, level, project);
            return;
        }
        if (VillageHouseReuseService.TEMPLATE.equals(project.templateId())) {
            VillageHouseReuseService.advance(villager, level, project);
            return;
        }

        List<BuildStep> plan = projectPlan(project);
        int stepIndex = project.workCursor();
        // Rebuild material reservations once for pre-v74 ongoing projects:
        // the furniture/stair steps now consume actual crafted items
        // (possibly made from real cargo), not one arbitrary plank.
        if (stepIndex < plan.size()
                && (project.reservations().isEmpty()
                || !"real_fixtures_v1".equals(project.parameter("fixture_materials")))) {
            initializeProjectReservations(project, plan, stepIndex);
            project.setParameter("fixture_materials", "real_fixtures_v1");
            VillageSavedData.get(level).touch();
        }
        if (stepIndex >= plan.size()) {
            completeBuildingProject(villager, level, project, plan);
            return;
        }

        BuildStep step = plan.get(stepIndex);
        if (!VillageSimulationScheduler.isChunkLoaded(level, step.pos)) {
            project.setPausedReason("waiting for chunk");
            VillageSavedData.get(level).touch();
            return;
        }

        boolean bedFoot = step.state.getBlock() instanceof BedBlock
                && step.state.hasProperty(BedBlock.PART)
                && step.state.getValue(BedBlock.PART) == BedPart.FOOT;

        if (bedFoot) {
            if (!ensureBedCargo(villager, level)) {
                project.setPausedReason("missing bed materials");
                requestMaterials(villager, "3 wool and 3 planks");
                VillageSavedData.get(level).touch();
                return;
            }
        } else if (step.cost != null
                && !(VillageCarpenterCraftingService.isCraftedFixture(
                        step.cost, plankFromName(project.parameter("plank")))
                    ? VillageCarpenterCraftingService.ensureFixture(
                            villager, level, step.cost,
                            plankFromName(project.parameter("plank")), CARPENTER_CARGO_SLOTS)
                    : ensureCargoItem(villager, level, step.cost,
                            1, CARPENTER_CARGO_SLOTS))) {
            project.setPausedReason("missing materials for " + step.cost.getDescription().getString());
            requestMaterials(villager, step.cost.getDescription().getString().toLowerCase(Locale.ROOT));
            VillageSavedData.get(level).touch();
            return;
        }

        if (villager.distanceToSqr(step.pos.getCenter()) > 7.0D * 7.0D) {
            project.setPausedReason("worker travelling");
            villager.getNavigation().moveTo(step.pos.getX() + 0.5D, step.pos.getY(), step.pos.getZ() + 0.5D, 0.75D);
            VillageSavedData.get(level).touch();
            return;
        }

        BlockState existing = level.getBlockState(step.pos);
        if (!existing.canBeReplaced() && !existing.is(step.state.getBlock())) {
            project.setPausedReason("site changed");
            project.setPhase("paused");
            VillageSavedData.get(level).touch();
            return;
        }

        if (bedFoot) {
            Direction facing = step.state.getValue(HorizontalDirectionalBlock.FACING);
            BlockPos headPos = step.pos.relative(facing);
            if (!VillageSimulationScheduler.isChunkLoaded(level, headPos)) {
                project.setPausedReason("waiting for chunk");
                VillageSavedData.get(level).touch();
                return;
            }
            if (!level.getBlockState(headPos).canBeReplaced()) {
                project.setPausedReason("bed space blocked");
                project.setPhase("paused");
                VillageSavedData.get(level).touch();
                return;
            }
            if (!consumeBedCargo(villager, level)) return;

            BlockState head = step.state.setValue(BedBlock.PART, BedPart.HEAD);
            level.setBlock(step.pos, step.state, Block.UPDATE_CLIENTS);
            level.setBlock(headPos, head, Block.UPDATE_CLIENTS);
            level.updateNeighborsAt(step.pos, step.state.getBlock());
            level.updateNeighborsAt(headPos, head.getBlock());
            project.setWorkCursor(Math.min(plan.size(), stepIndex + 2));
            decrementProjectReservation(project, "tag:minecraft:wool", 3);
            decrementProjectReservation(project, "tag:minecraft:planks", 3);
        } else {
            if (step.cost != null
                    && !VillagerSimData.takeWorkCargo(villager, level.registryAccess(),
                    CARPENTER_CARGO_SLOTS, step.cost, 1)) {
                return;
            }
            level.setBlock(step.pos, step.state, Block.UPDATE_ALL);
            project.setWorkCursor(stepIndex + 1);
            if (step.cost != null) {
                decrementProjectReservation(project, VillageStorageService.itemKey(step.cost), 1);
            }
        }

        project.setPausedReason("");
        project.setPhase(projectPhase(project));
        VillageSavedData.get(level).touch();
    }

    private static void initializeProjectReservations(
            VillageSavedData.ProjectRecord project,
            List<BuildStep> plan,
            int fromIndex) {
        project.clearReservations();
        Map<String, Integer> counts = new HashMap<>();

        for (int i = Math.max(0, fromIndex); i < plan.size(); i++) {
            BuildStep step = plan.get(i);
            boolean bedFoot = step.state.getBlock() instanceof BedBlock
                    && step.state.hasProperty(BedBlock.PART)
                    && step.state.getValue(BedBlock.PART) == BedPart.FOOT;
            if (bedFoot) {
                counts.merge("tag:minecraft:wool", 3, Integer::sum);
                counts.merge("tag:minecraft:planks", 3, Integer::sum);
            } else if (step.cost != null) {
                counts.merge(VillageStorageService.itemKey(step.cost), 1, Integer::sum);
            }
        }

        counts.forEach(project::setReservation);
    }

    private static void decrementProjectReservation(
            VillageSavedData.ProjectRecord project,
            String key,
            int count) {
        int remaining = Math.max(0, project.reservations().getOrDefault(key, 0) - count);
        project.setReservation(key, remaining);
    }

    private static void buildOneRoadProjectStep(Villager villager, ServerLevel level,
                                                VillageSavedData.ProjectRecord project) {
        if (!isWorkTime(level)) return;
        if (VillageBridgeService.TEMPLATE.equals(project.templateId())) {
            VillageBridgeService.advance(villager, level, project);
            return;
        }
        if ("route_planning".equals(project.phase())) {
            // Search requests are short-lived, but the saved project must
            // survive failed/unloaded planning and automatically retry after
            // chunks naturally become loaded.
            try {
                java.util.UUID routeId = java.util.UUID.fromString(
                        project.parameter("route_id"));
                enqueueRoadGeometry(level, routeId, project.id());
            } catch (IllegalArgumentException ignored) {
                project.setPausedReason("invalid route identifier");
                VillageSavedData.get(level).touch();
            }
            return;
        }
        if ("waiting_for_bridge".equals(project.phase())) return;
        BlockPos from = project.site();
        BlockPos to = project.anchor();
        if (to == null) {
            project.setPhase("cancelled");
            project.setPausedReason("missing route endpoint");
            VillageSavedData.get(level).touch();
            return;
        }

        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.RouteRecord route = routeForProject(data, project);

        List<BlockPos> roadNodes = roadPathNodes(route, from, to);
        int centerCount = roadCenterlineCount(roadNodes);
        if (centerCount <= 1) {
            completeRoadProject(level, project);
            return;
        }
        if (centerCount > 640) {
            project.setPhase("paused");
            project.setPausedReason("route exceeds bounded road range");
            data.touch();
            return;
        }

        int targetWidth = roadTargetWidth(project, route);
        int deckUnits = centerCount * targetWidth;
        boolean addBridgeParapet =
                "parapet_v1".equals(project.parameter("bridge_details"));
        int workUnits = deckUnits + (addBridgeParapet ? centerCount * 4 : 0);
        int cursor = project.workCursor();
        if (cursor >= workUnits) {
            completeRoadProject(level, project);
            return;
        }

        // Finish all deck/paving units before the separate support/parapet
        // phases. Legacy road projects without bridge_details keep their
        // old deterministic cursors and completion semantics unchanged.
        if (cursor >= deckUnits) {
            buildOneBridgeParapetStep(villager, level, project, roadNodes,
                    targetWidth, deckUnits, workUnits);
            return;
        }

        int centerCursor = cursor / targetWidth;
        int lane = cursor % targetWidth;
        RoadPoint roadPoint = roadPointAt(roadNodes, centerCursor);
        int x = roadPoint.pos().getX();
        int z = roadPoint.pos().getZ();

        int laneOffset = switch (targetWidth) {
            case 2 -> lane;
            case 3 -> lane - 1;
            default -> 0;
        };
        if (Math.abs(roadPoint.dx()) >= Math.abs(roadPoint.dz())) z += laneOffset;
        else x += laneOffset;

        BlockPos column = new BlockPos(x, level.getMinBuildHeight(), z);
        if (!VillageSimulationScheduler.isChunkLoaded(level, column)) {
            project.setPausedReason("waiting for chunk");
            project.setPhase("paused");
            VillageSavedData.get(level).touch();
            return;
        }
        if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) return;

        int y = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z);
        BlockPos surface = new BlockPos(x, y - 1, z);
        if (centerCursor > 0) {
            RoadPoint previous = roadPointAt(roadNodes, centerCursor - 1);
            BlockPos previousColumn = new BlockPos(
                    previous.pos().getX(), level.getMinBuildHeight(),
                    previous.pos().getZ());
            if (!VillageSimulationScheduler.isChunkLoaded(level, previousColumn)
                    || !VillageSimulationScheduler.tryConsumeBlockProbe(level)) {
                project.setPausedReason("previous road grade unobserved");
                data.touch();
                return;
            }
            int previousY = level.getHeight(
                    Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,
                    previous.pos().getX(), previous.pos().getZ()) - 1;
            if (Math.abs(surface.getY() - previousY) > 1) {
                // An unsupported two-plus-block step is not passable to
                // ordinary villagers. Never fake a road merely by replacing
                // natural cliff or player-built staircase geometry.
                project.setPausedReason("unsafe road grade; reroute or stairs required");
                project.setPhase("paused");
                data.touch();
                return;
            }
        }
        if (villager.distanceToSqr(surface.getCenter()) > 7.0D * 7.0D) {
            project.setPausedReason("worker travelling");
            project.setPhase("roadwork");
            villager.getNavigation().moveTo(surface.getX() + 0.5D, surface.getY() + 1.0D,
                    surface.getZ() + 0.5D, 0.75D);
            VillageSavedData.get(level).touch();
            return;
        }

        BlockState state = level.getBlockState(surface);
        String targetQuality = roadTargetQuality(project, route);

        if (level.getFluidState(surface).is(FluidTags.WATER)) {
            // Never pave directly into river water, which would silently
            // destroy the source and produce an unwalkable, unapproved span.
            // An accepted 2..12 block crossing must first be constructed
            // as a separate raised, physically supported Bridge Project.
            project.setPhase("paused");
            project.setPausedReason("unsupported water crossing; reroute/bridge required");
            data.touch();
            return;
        } else if ("stone".equals(targetQuality)) {
            if (state.is(Blocks.COBBLESTONE) || state.is(Blocks.STONE)
                    || state.is(Blocks.STONE_BRICKS)) {
                project.setPhase("road_paving");
            } else if (state.is(Blocks.DIRT_PATH) || state.is(Blocks.GRAVEL)
                    || state.is(Blocks.GRASS_BLOCK) || state.is(Blocks.DIRT)
                    || state.is(Blocks.COARSE_DIRT) || state.is(BlockTags.PLANKS)) {
                if (!placeRoadMaterial(villager, level, project, surface,
                        Items.COBBLESTONE, Blocks.COBBLESTONE, "missing road stone")) return;
                project.setPhase("road_paving");
            } else {
                project.setPhase("roadwork");
            }
        } else if ("gravel".equals(targetQuality)) {
            if (state.is(Blocks.GRAVEL) || state.is(Blocks.COBBLESTONE)
                    || state.is(Blocks.STONE) || state.is(Blocks.STONE_BRICKS)) {
                project.setPhase("road_gravel");
            } else if (state.is(Blocks.DIRT_PATH) || state.is(Blocks.GRASS_BLOCK)
                    || state.is(Blocks.DIRT) || state.is(Blocks.COARSE_DIRT)) {
                if (!placeRoadMaterial(villager, level, project, surface,
                        Items.GRAVEL, Blocks.GRAVEL, "missing road gravel")) return;
                project.setPhase("road_gravel");
            } else {
                project.setPhase("roadwork");
            }
        } else if (state.is(Blocks.GRASS_BLOCK) || state.is(Blocks.DIRT)
                || state.is(Blocks.COARSE_DIRT)) {
            level.setBlock(surface, Blocks.DIRT_PATH.defaultBlockState(), Block.UPDATE_ALL);
            project.setPhase("roadwork");
        } else {
            // Preserve player/structure blocks and already-higher-quality paving.
            project.setPhase("roadwork");
        }

        project.setPausedReason("");
        project.setWorkCursor(cursor + 1);
        data.touch();

        if (project.workCursor() >= workUnits) completeRoadProject(level, project);
    }

    /**
     * A new-build-only bridge detail pass. Place outboard support shelves
     * and then simple parapet blocks along the actual wet part of a road.
     * It never narrows the usable deck or replaces a player's solid block.
     *
     * Four deterministic work units per centerline point:
     * left support, left parapet, right support, right parapet.
     * Non-water portions are skipped without allocating items.
     */
    private static void buildOneBridgeParapetStep(
            Villager carpenter,
            ServerLevel level,
            VillageSavedData.ProjectRecord project,
            List<BlockPos> nodes,
            int width,
            int deckUnits,
            int workUnits) {
        VillageSavedData data = VillageSavedData.get(level);
        int cursor = project.workCursor();
        int extra = cursor - deckUnits;
        int pointIndex = extra / 4;
        int side = (extra % 4) / 2;
        boolean railing = (extra & 1) != 0;

        RoadPoint point = roadPointAt(nodes, pointIndex);
        int centerX = point.pos().getX();
        int centerZ = point.pos().getZ();
        BlockPos column = new BlockPos(centerX, level.getMinBuildHeight(), centerZ);
        if (!VillageSimulationScheduler.isChunkLoaded(level, column)) {
            project.setPausedReason("bridge center chunk unloaded");
            project.setPhase("paused");
            data.touch();
            return;
        }
        if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) return;

        int surfaceY = level.getHeight(
                Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, centerX, centerZ) - 1;
        BlockPos center = new BlockPos(centerX, surfaceY, centerZ);
        BlockState deck = level.getBlockState(center);
        boolean builtBridge = (deck.is(BlockTags.PLANKS)
                || deck.is(Blocks.COBBLESTONE) || deck.is(Blocks.STONE)
                || deck.is(Blocks.STONE_BRICKS))
                && level.getFluidState(center.below()).is(FluidTags.WATER);

        if (!builtBridge) {
            // Nothing physically in the water at this centerline point:
            // no rail, and no phantom construction resources.
            project.setWorkCursor(cursor + 1);
            project.setPausedReason("");
            data.touch();
            if (project.workCursor() >= workUnits) completeRoadProject(level, project);
            return;
        }

        int leftEdge = width == 3 ? -2 : -1;
        int rightEdge = width == 2 ? 2 : width == 3 ? 2 : 1;
        int offset = side == 0 ? leftEdge : rightEdge;
        int sideX = centerX;
        int sideZ = centerZ;
        if (Math.abs(point.dx()) >= Math.abs(point.dz())) sideZ += offset;
        else sideX += offset;

        BlockPos support = new BlockPos(sideX, surfaceY, sideZ);
        BlockPos placed = railing ? support.above() : support;
        if (!VillageSimulationScheduler.isChunkLoaded(level, placed)) {
            project.setPausedReason("bridge side chunk unloaded");
            project.setPhase("paused");
            data.touch();
            return;
        }

        String quality = roadTargetQuality(project,
                routeForProject(data, project));
        Block block = "stone".equals(quality)
                ? Blocks.COBBLESTONE : plankFromName(project.parameter("plank"));
        Item material = block.asItem();
        BlockState target = level.getBlockState(placed);

        if (railing && !level.getBlockState(support).is(block)) {
            // A different mod/player edited the outboard support. Do not
            // levitate or overwrite their structure with an automatic rail.
            project.setPhase("bridge_parapet");
        } else if (target.is(block)) {
            project.setPhase(railing ? "bridge_parapet" : "bridge_support");
        } else if (!target.canBeReplaced()) {
            // Preserve solid player-built blocks and bridge attachments.
            project.setPhase("bridge_obstructed");
        } else {
            if (carpenter.distanceToSqr(center.getCenter()) > 7.0D * 7.0D) {
                project.setPausedReason("worker travelling to bridge");
                project.setPhase(railing ? "bridge_parapet" : "bridge_support");
                carpenter.getNavigation().moveTo(center.getX() + 0.5D,
                        center.getY() + 1.0D, center.getZ() + 0.5D, 0.75D);
                data.touch();
                return;
            }

            // The item physically travels through standard Carpenter cargo.
            // A support shelf and a parapet block each cost one real item.
            if (!placeRoadMaterial(carpenter, level, project, placed,
                    material, block, "missing bridge parapet materials")) return;
            project.setPhase(railing ? "bridge_parapet" : "bridge_support");
        }

        project.setPausedReason("");
        project.setWorkCursor(cursor + 1);
        data.touch();
        if (project.workCursor() >= workUnits) completeRoadProject(level, project);
    }

    private static List<BlockPos> roadPathNodes(
            VillageSavedData.RouteRecord route, BlockPos from, BlockPos to) {
        if (route != null && route.waypoints().size() >= 2) return route.waypoints();
        return List.of(from, to);
    }

    private static int roadCenterlineCount(List<BlockPos> nodes) {
        if (nodes.size() < 2) return nodes.size();
        int count = 1;
        for (int i = 1; i < nodes.size(); i++) {
            BlockPos a = nodes.get(i - 1);
            BlockPos b = nodes.get(i);
            count += Math.max(Math.abs(b.getX() - a.getX()), Math.abs(b.getZ() - a.getZ()));
        }
        return count;
    }

    private static RoadPoint roadPointAt(List<BlockPos> nodes, int index) {
        BlockPos first = nodes.get(0);
        if (index <= 0 || nodes.size() < 2) {
            BlockPos next = nodes.size() >= 2 ? nodes.get(1) : first;
            return new RoadPoint(first, next.getX() - first.getX(), next.getZ() - first.getZ());
        }

        int remaining = index;
        for (int i = 1; i < nodes.size(); i++) {
            BlockPos a = nodes.get(i - 1);
            BlockPos b = nodes.get(i);
            int dx = b.getX() - a.getX();
            int dz = b.getZ() - a.getZ();
            int length = Math.max(Math.abs(dx), Math.abs(dz));
            if (length <= 0) continue;
            if (remaining <= length) {
                double t = remaining / (double)length;
                BlockPos point = new BlockPos(
                        (int)Math.round(a.getX() + dx * t),
                        0,
                        (int)Math.round(a.getZ() + dz * t));
                return new RoadPoint(point, dx, dz);
            }
            remaining -= length;
        }

        BlockPos last = nodes.get(nodes.size() - 1);
        BlockPos previous = nodes.get(Math.max(0, nodes.size() - 2));
        return new RoadPoint(last, last.getX() - previous.getX(), last.getZ() - previous.getZ());
    }

    private record RoadPoint(BlockPos pos, int dx, int dz) {
    }

    private static VillageSavedData.RouteRecord routeForProject(
            VillageSavedData data, VillageSavedData.ProjectRecord project) {
        String rawRoute = project.parameter("route_id");
        if (rawRoute.isBlank()) return null;
        try {
            return data.route(java.util.UUID.fromString(rawRoute)).orElse(null);
        } catch (IllegalArgumentException ignored) {
            return null;
        }
    }

    private static int roadTargetWidth(
            VillageSavedData.ProjectRecord project, VillageSavedData.RouteRecord route) {
        int fallback = route == null ? 1 : route.width();
        try {
            String raw = project.parameter("road_width");
            return raw.isBlank() ? fallback : Math.max(1, Math.min(3, Integer.parseInt(raw)));
        } catch (NumberFormatException ignored) {
            return fallback;
        }
    }

    private static String roadTargetQuality(
            VillageSavedData.ProjectRecord project, VillageSavedData.RouteRecord route) {
        String raw = project.parameter("road_quality");
        if ("stone".equals(raw) || "gravel".equals(raw) || "dirt".equals(raw)) return raw;
        return route == null ? "dirt" : route.quality();
    }

    private static boolean placeRoadMaterial(
            Villager villager,
            ServerLevel level,
            VillageSavedData.ProjectRecord project,
            BlockPos surface,
            Item item,
            Block block,
            String missingReason) {
        if (!ensureCargoItem(villager, level, item, 1, CARPENTER_CARGO_SLOTS)) {
            project.setPausedReason(missingReason);
            project.setPhase("paused");
            VillageSavedData.get(level).touch();
            return false;
        }
        if (!VillagerSimData.takeWorkCargo(
                villager, level.registryAccess(), CARPENTER_CARGO_SLOTS, item, 1)) {
            return false;
        }
        if (!level.setBlock(surface, block.defaultBlockState(), Block.UPDATE_ALL)) {
            // A canceled placement must not silently destroy a real item.
            ItemStack excess = VillagerSimData.insertWorkCargo(
                    villager, level.registryAccess(), new ItemStack(item),
                    CARPENTER_CARGO_SLOTS);
            if (!excess.isEmpty()) villager.spawnAtLocation(excess);
            project.setPausedReason("road placement rejected; material refunded");
            VillageSavedData.get(level).touch();
            return false;
        }
        return true;
    }

    private static void completeRoadProject(ServerLevel level, VillageSavedData.ProjectRecord project) {
        project.setPhase("complete");
        project.setPausedReason("");
        String rawRoute = project.parameter("route_id");
        if (!rawRoute.isBlank()) {
            try {
                java.util.UUID routeId = java.util.UUID.fromString(rawRoute);
                VillageSavedData.get(level).route(routeId).ifPresent(route -> {
                    route.setQuality(roadTargetQuality(project, route));
                    route.setWidth(roadTargetWidth(project, route));
                    route.setState("active");
                });
            } catch (IllegalArgumentException ignored) {
                // Keep the physical road; only the cached RouteRecord link is malformed.
            }
        }
        VillageSavedData.get(level).touch();
    }

    private static void completeBuildingProject(Villager villager, ServerLevel level,
                                                VillageSavedData.ProjectRecord project,
                                                List<BuildStep> plan) {
        project.setPhase("complete");
        project.setPausedReason("");
        VillageSavedData data = VillageSavedData.get(level);

        int skill = VillagerSimData.carpentrySkill(villager);
        int skillGain = switch (project.templateId()) {
            case "house_gabled_5x5" -> 3;
            case "house_2story_5x5" -> 4;
            case "house_3story_5x5" -> 6;
            default -> 2;
        };
        VillagerSimData.setCarpentrySkill(villager, Math.min(100, skill + skillGain));

        registerCompletedProject(villager, level, project);
        if (project.templateId().startsWith("house_")
                && !Boolean.parseBoolean(project.parameter("outpost"))
                && !Boolean.parseBoolean(project.parameter("colony"))) {
            // Prevent speculative detached construction immediately after a
            // finished real house, except for genuinely acute shortages.
            VillageHousingPlanner.recordFinishedHouse(
                    level, data, project.villageId());
        }

        BlockPos anchor = project.anchor() != null ? project.anchor() : villager.blockPosition();
        if (AsobibaTweaksConfig.VILLAGE_ROADS_ENABLED.getAsBoolean()) {
            BlockPos roadFrom = project.site().offset(2, 0, -1);
            createRoadDemandProject(level, project.villageId(), roadFrom, anchor, villager);
        }

        if (Boolean.parseBoolean(project.parameter("outpost"))
                && AsobibaTweaksConfig.VILLAGE_REFUGEES_ENABLED.getAsBoolean()) {
            boolean colony = Boolean.parseBoolean(project.parameter("colony"));
            if (colony) {
                String rawVillage = project.parameter("founded_village_id");
                try {
                    java.util.UUID daughterId = java.util.UUID.fromString(rawVillage);
                    VillagePopulationMigrationService.startFoundingGroup(level, villager, daughterId, 4);
                } catch (IllegalArgumentException ignored) {
                    // Founding failed to create a durable daughter VillageRecord.
                }
            }
        }

        villager.getPersistentData().putLong(
                NEXT_BUILD,
                level.getGameTime() + (Boolean.parseBoolean(project.parameter("colony")) ? 10L : 5L) * 24000L
        );
        data.touch();
    }

    private static String projectPhase(VillageSavedData.ProjectRecord project) {
        int cursor = project.workCursor();
        if (cursor < 25) return "foundation";

        int total = Math.max(26, projectPlan(project).size());
        double progress = (cursor - 25) / (double)Math.max(1, total - 25);
        String template = project.templateId();
        boolean multiStory = "house_2story_5x5".equals(template)
                || "house_3story_5x5".equals(template);

        if (multiStory) {
            if (progress < 0.28D) return "ground_floor";
            if (progress < 0.55D) return "upper_floor";
            if (progress < 0.78D) return "roof";
            return "interior";
        }
        if ("house_gabled_5x5".equals(template)
                || VillageCraftHallPlanner.TEMPLATE.equals(template)
                || VillageSpecialistWorkshopService.hasGabledRoof(template)) {
            if (progress < 0.58D) return "walls";
            if (progress < 0.88D) return "gabled_roof";
            return "interior";
        }
        if (progress < 0.65D) return "walls";
        if (progress < 0.90D) return "roof";
        return "interior";
    }

    private static int templateMaxY(String templateId) {
        if (VillageSpecialistWorkshopService.hasGabledRoof(templateId)) return 6;
        return switch (templateId) {
            case "house_gabled_5x5", VillageCraftHallPlanner.TEMPLATE -> 6;
            case "house_2story_5x5" -> 8;
            case "house_3story_5x5" -> 12;
            default -> 4;
        };
    }

    static List<BuildStep> projectPlan(VillageSavedData.ProjectRecord project) {
        if ("storage_5x5".equals(project.templateId())) return storagePlan(project);
        if (VillageCraftHallPlanner.TEMPLATE.equals(project.templateId()))
            return craftHallPlan(project);
        if (VillageSpecialistWorkshopService.isSpecialistTemplate(project.templateId()))
            return VillageSpecialistWorkshopService.plan(project, storagePlan(project));
        return hutPlan(project);
    }

    /**
     * A function-first, non-residential workshop. The simple storage shell
     * provides a real floor/walls/entry; its barrel fixtures are replaced by
     * toolsmith and mason workstations with a shared supply barrel.
     * Roof shape and every block/material are deterministic across reloads.
     */
    private static List<BuildStep> craftHallPlan(VillageSavedData.ProjectRecord project) {
        BlockPos base = project.site();
        List<BuildStep> steps = storagePlan(project);
        steps.removeIf(step -> step.state.is(Blocks.BARREL)
                || step.pos.getY() == base.getY() + 4);

        Block plank = plankFromName(project.parameter("plank"));
        BlockState roof = plank.defaultBlockState();
        Item material = plank.asItem();
        for (int z = 0; z < 5; z++) {
            steps.add(new BuildStep(base.offset(0, 4, z), roof, material));
            steps.add(new BuildStep(base.offset(4, 4, z), roof, material));
            steps.add(new BuildStep(base.offset(1, 5, z), roof, material));
            steps.add(new BuildStep(base.offset(3, 5, z), roof, material));
            steps.add(new BuildStep(base.offset(2, 6, z), roof, material));
        }

        steps.add(new BuildStep(base.offset(1, 1, 2),
                Blocks.SMITHING_TABLE.defaultBlockState(), Items.SMITHING_TABLE));
        steps.add(new BuildStep(base.offset(3, 1, 2),
                Blocks.STONECUTTER.defaultBlockState(), Items.STONECUTTER));
        steps.add(new BuildStep(base.offset(2, 1, 3),
                Blocks.BARREL.defaultBlockState(), Items.BARREL));
        return steps;
    }

    private static List<BuildStep> storagePlan(VillageSavedData.ProjectRecord project) {
        BlockPos base = project.site();
        List<BuildStep> steps = new ArrayList<>();
        Block plankBlock = plankFromName(project.parameter("plank"));
        Item plankItem = plankBlock.asItem();
        BlockState plank = plankBlock.defaultBlockState();

        for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
            steps.add(new BuildStep(base.offset(x, 0, z), Blocks.COBBLESTONE.defaultBlockState(), Items.COBBLESTONE));
        }

        for (int y = 1; y <= 3; y++) {
            for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
                boolean edge = x == 0 || x == 4 || z == 0 || z == 4;
                boolean doorway = z == 0 && x == 2 && y <= 2;
                if (edge && !doorway) {
                    steps.add(new BuildStep(base.offset(x, y, z), plank, plankItem));
                }
            }
        }

        for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
            steps.add(new BuildStep(base.offset(x, 4, z), plank, plankItem));
        }

        steps.add(new BuildStep(base.offset(1, 1, 2), Blocks.BARREL.defaultBlockState(), Items.BARREL));
        steps.add(new BuildStep(base.offset(3, 1, 2), Blocks.BARREL.defaultBlockState(), Items.BARREL));
        return steps;
    }

    private static List<BuildStep> hutPlan(VillageSavedData.ProjectRecord project) {
        BlockPos base = project.site();
        List<BuildStep> steps = new ArrayList<>();
        Block plankBlock = plankFromName(project.parameter("plank"));
        Item plankItem = plankBlock.asItem();
        BlockState plank = plankBlock.defaultBlockState();
        BlockState cobble = Blocks.COBBLESTONE.defaultBlockState();

        for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
            steps.add(new BuildStep(base.offset(x, 0, z), cobble, Items.COBBLESTONE));
        }

        for (int y = 1; y <= 3; y++) {
            for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
                boolean edge = x == 0 || x == 4 || z == 0 || z == 4;
                boolean doorway = z == 0 && x == 2 && y <= 2;
                boolean window = y == 2 && ((x == 0 || x == 4) && z == 2);
                if (edge && !doorway && !window) {
                    BlockState state = plank;
                    int leadSkill = parseInt(project.parameter("lead_skill"), 0);
                    int imperfectionChance = leadSkill < 25 ? 20 : leadSkill < 50 ? 12 : leadSkill < 75 ? 5 : 2;
                    if (AsobibaTweaksConfig.VILLAGE_IMPERFECT_CONSTRUCTION_ENABLED.getAsBoolean()
                            && Math.floorMod((int)(project.variantSeed() + x * 31L + y * 17L + z * 13L), 100)
                            < imperfectionChance) {
                        state = cobble;
                    }
                    steps.add(new BuildStep(base.offset(x, y, z), state,
                            state.is(Blocks.COBBLESTONE) ? Items.COBBLESTONE : plankItem));
                }
            }
        }

        for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
            steps.add(new BuildStep(base.offset(x, 4, z), plank, plankItem));
        }

        if ("house_gabled_5x5".equals(project.templateId())) {
            steps.removeIf(step -> step.pos.getY() == base.getY() + 4);
            for (int z = 0; z < 5; z++) {
                steps.add(new BuildStep(base.offset(0, 4, z), plank, plankItem));
                steps.add(new BuildStep(base.offset(4, 4, z), plank, plankItem));
                steps.add(new BuildStep(base.offset(1, 5, z), plank, plankItem));
                steps.add(new BuildStep(base.offset(3, 5, z), plank, plankItem));
                steps.add(new BuildStep(base.offset(2, 6, z), plank, plankItem));
            }
        }

        BlockState bedFoot = Blocks.WHITE_BED.defaultBlockState()
                .setValue(BedBlock.PART, BedPart.FOOT)
                .setValue(HorizontalDirectionalBlock.FACING, Direction.SOUTH);
        BlockState bedHead = bedFoot.setValue(BedBlock.PART, BedPart.HEAD);
        steps.add(new BuildStep(base.offset(2, 1, 2), bedFoot, null));
        steps.add(new BuildStep(base.offset(2, 1, 3), bedHead, null));

        boolean trainedHouse = "house_gabled_5x5".equals(project.templateId())
                || "house_2story_5x5".equals(project.templateId())
                || "house_3story_5x5".equals(project.templateId());
        if (trainedHouse && !Boolean.parseBoolean(project.parameter("outpost"))) {
            BlockState extraGroundFoot = Blocks.WHITE_BED.defaultBlockState()
                    .setValue(BedBlock.PART, BedPart.FOOT)
                    .setValue(HorizontalDirectionalBlock.FACING, Direction.SOUTH);
            BlockState extraGroundHead = extraGroundFoot.setValue(BedBlock.PART, BedPart.HEAD);
            steps.add(new BuildStep(base.offset(1, 1, 2), extraGroundFoot, null));
            steps.add(new BuildStep(base.offset(1, 1, 3), extraGroundHead, null));
        }

        if (Boolean.parseBoolean(project.parameter("outpost"))) {
            BlockState secondBedFoot = Blocks.WHITE_BED.defaultBlockState()
                    .setValue(BedBlock.PART, BedPart.FOOT)
                    .setValue(HorizontalDirectionalBlock.FACING, Direction.SOUTH);
            BlockState secondBedHead = secondBedFoot.setValue(BedBlock.PART, BedPart.HEAD);
            steps.add(new BuildStep(base.offset(1, 1, 2), secondBedFoot, null));
            steps.add(new BuildStep(base.offset(1, 1, 3), secondBedHead, null));
            steps.add(new BuildStep(base.offset(3, 1, 2), Blocks.BARREL.defaultBlockState(), Items.BARREL));
            steps.add(new BuildStep(base.offset(3, 1, 3), Blocks.COMPOSTER.defaultBlockState(), Items.COMPOSTER));
            if (Boolean.parseBoolean(project.parameter("colony"))) {
                steps.add(new BuildStep(base.offset(1, 1, 1),
                        AsobibaRegistries.CARPENTER_WORKBENCH.get().defaultBlockState(),
                        AsobibaRegistries.CARPENTER_WORKBENCH.get().asItem()));
            }
        }

        boolean multiStory = "house_2story_5x5".equals(project.templateId())
                || "house_3story_5x5".equals(project.templateId());
        if (multiStory) {
            // Replace the single-story roof layer with a second floor and add an upper shell/roof.
            steps.removeIf(step -> step.pos.getY() == base.getY() + 4);
            for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
                if (x == 3 && z == 1) continue; // stair opening
                steps.add(new BuildStep(base.offset(x, 4, z), plank, plankItem));
            }
            for (int y = 5; y <= 7; y++) {
                for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
                    boolean edge = x == 0 || x == 4 || z == 0 || z == 4;
                    boolean window = y == 6 && ((x == 0 || x == 4) && z == 2);
                    if (edge && !window) steps.add(new BuildStep(base.offset(x, y, z), plank, plankItem));
                }
            }
            for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
                steps.add(new BuildStep(base.offset(x, 8, z), plank, plankItem));
            }
            // Simple internal stair spine; material cost remains real plank-equivalent.
            Block stair = stairsForPlank(plankBlock);
            BlockState stairState = stair.defaultBlockState();
            steps.add(new BuildStep(base.offset(1, 1, 1), stairState, stair.asItem()));
            steps.add(new BuildStep(base.offset(2, 2, 1), stairState, stair.asItem()));
            steps.add(new BuildStep(base.offset(3, 3, 1), stairState, stair.asItem()));

            BlockState upperBedFoot = Blocks.WHITE_BED.defaultBlockState()
                    .setValue(BedBlock.PART, BedPart.FOOT)
                    .setValue(HorizontalDirectionalBlock.FACING, Direction.SOUTH);
            BlockState upperBedHead = upperBedFoot.setValue(BedBlock.PART, BedPart.HEAD);
            steps.add(new BuildStep(base.offset(2, 5, 2), upperBedFoot, null));
            steps.add(new BuildStep(base.offset(2, 5, 3), upperBedHead, null));

            BlockState extraUpperBedFoot = Blocks.WHITE_BED.defaultBlockState()
                    .setValue(BedBlock.PART, BedPart.FOOT)
                    .setValue(HorizontalDirectionalBlock.FACING, Direction.SOUTH);
            BlockState extraUpperBedHead = extraUpperBedFoot.setValue(BedBlock.PART, BedPart.HEAD);
            steps.add(new BuildStep(base.offset(3, 5, 2), extraUpperBedFoot, null));
            steps.add(new BuildStep(base.offset(3, 5, 3), extraUpperBedHead, null));

            if ("house_3story_5x5".equals(project.templateId())) {
                // Turn the second-story roof into a third-story floor with a stair opening.
                steps.removeIf(step -> step.pos.getY() == base.getY() + 8);
                for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
                    if (x == 3 && z == 1) continue;
                    steps.add(new BuildStep(base.offset(x, 8, z), plank, plankItem));
                }
                for (int y = 9; y <= 11; y++) {
                    for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
                        boolean edge = x == 0 || x == 4 || z == 0 || z == 4;
                        boolean window = y == 10 && ((x == 0 || x == 4) && z == 2);
                        if (edge && !window) {
                            steps.add(new BuildStep(base.offset(x, y, z), plank, plankItem));
                        }
                    }
                }
                for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
                    steps.add(new BuildStep(base.offset(x, 12, z), plank, plankItem));
                }

                steps.add(new BuildStep(base.offset(1, 5, 1), stairState, stair.asItem()));
                steps.add(new BuildStep(base.offset(2, 6, 1), stairState, stair.asItem()));
                steps.add(new BuildStep(base.offset(3, 7, 1), stairState, stair.asItem()));

                BlockState thirdBedFoot = Blocks.WHITE_BED.defaultBlockState()
                        .setValue(BedBlock.PART, BedPart.FOOT)
                        .setValue(HorizontalDirectionalBlock.FACING, Direction.SOUTH);
                BlockState thirdBedHead = thirdBedFoot.setValue(BedBlock.PART, BedPart.HEAD);
                steps.add(new BuildStep(base.offset(2, 9, 2), thirdBedFoot, null));
                steps.add(new BuildStep(base.offset(2, 9, 3), thirdBedHead, null));

                BlockState extraThirdBedFoot = Blocks.WHITE_BED.defaultBlockState()
                        .setValue(BedBlock.PART, BedPart.FOOT)
                        .setValue(HorizontalDirectionalBlock.FACING, Direction.SOUTH);
                BlockState extraThirdBedHead = extraThirdBedFoot.setValue(BedBlock.PART, BedPart.HEAD);
                steps.add(new BuildStep(base.offset(3, 9, 2), extraThirdBedFoot, null));
                steps.add(new BuildStep(base.offset(3, 9, 3), extraThirdBedHead, null));
            }
        }
        return steps;
    }

    private static int parseInt(String value, int fallback) {
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException ignored) {
            return fallback;
        }
    }

    private static String plankName(Block block) {
        if (block == Blocks.SPRUCE_PLANKS) return "spruce";
        if (block == Blocks.BIRCH_PLANKS) return "birch";
        if (block == Blocks.JUNGLE_PLANKS) return "jungle";
        if (block == Blocks.ACACIA_PLANKS) return "acacia";
        if (block == Blocks.DARK_OAK_PLANKS) return "dark_oak";
        if (block == Blocks.MANGROVE_PLANKS) return "mangrove";
        if (block == Blocks.CHERRY_PLANKS) return "cherry";
        return "oak";
    }

    private static Block plankFromName(String name) {
        return switch (name) {
            case "spruce" -> Blocks.SPRUCE_PLANKS;
            case "birch" -> Blocks.BIRCH_PLANKS;
            case "jungle" -> Blocks.JUNGLE_PLANKS;
            case "acacia" -> Blocks.ACACIA_PLANKS;
            case "dark_oak" -> Blocks.DARK_OAK_PLANKS;
            case "mangrove" -> Blocks.MANGROVE_PLANKS;
            case "cherry" -> Blocks.CHERRY_PLANKS;
            default -> Blocks.OAK_PLANKS;
        };
    }

    static Block stairsForPlank(Block plank) {
        if (plank == Blocks.SPRUCE_PLANKS) return Blocks.SPRUCE_STAIRS;
        if (plank == Blocks.BIRCH_PLANKS) return Blocks.BIRCH_STAIRS;
        if (plank == Blocks.JUNGLE_PLANKS) return Blocks.JUNGLE_STAIRS;
        if (plank == Blocks.ACACIA_PLANKS) return Blocks.ACACIA_STAIRS;
        if (plank == Blocks.DARK_OAK_PLANKS) return Blocks.DARK_OAK_STAIRS;
        if (plank == Blocks.MANGROVE_PLANKS) return Blocks.MANGROVE_STAIRS;
        if (plank == Blocks.CHERRY_PLANKS) return Blocks.CHERRY_STAIRS;
        return Blocks.OAK_STAIRS;
    }

    private static CarpenterTradeWood carpenterTradeWood(Entity trader) {
        Block plank = Blocks.OAK_PLANKS;
        if (trader instanceof Villager villager && villager.level() instanceof ServerLevel level) {
            plank = chooseBuildingPlanks(level, villager.blockPosition(), villager);
        }

        if (plank == Blocks.SPRUCE_PLANKS) {
            return new CarpenterTradeWood(Items.SPRUCE_LOG, Items.SPRUCE_DOOR, Items.SPRUCE_FENCE);
        }
        if (plank == Blocks.BIRCH_PLANKS) {
            return new CarpenterTradeWood(Items.BIRCH_LOG, Items.BIRCH_DOOR, Items.BIRCH_FENCE);
        }
        if (plank == Blocks.JUNGLE_PLANKS) {
            return new CarpenterTradeWood(Items.JUNGLE_LOG, Items.JUNGLE_DOOR, Items.JUNGLE_FENCE);
        }
        if (plank == Blocks.ACACIA_PLANKS) {
            return new CarpenterTradeWood(Items.ACACIA_LOG, Items.ACACIA_DOOR, Items.ACACIA_FENCE);
        }
        if (plank == Blocks.DARK_OAK_PLANKS) {
            return new CarpenterTradeWood(Items.DARK_OAK_LOG, Items.DARK_OAK_DOOR, Items.DARK_OAK_FENCE);
        }
        if (plank == Blocks.MANGROVE_PLANKS) {
            return new CarpenterTradeWood(Items.MANGROVE_LOG, Items.MANGROVE_DOOR, Items.MANGROVE_FENCE);
        }
        if (plank == Blocks.CHERRY_PLANKS) {
            return new CarpenterTradeWood(Items.CHERRY_LOG, Items.CHERRY_DOOR, Items.CHERRY_FENCE);
        }
        return new CarpenterTradeWood(Items.OAK_LOG, Items.OAK_DOOR, Items.OAK_FENCE);
    }

    private record CarpenterTradeWood(Item log, Item door, Item fence) {
    }

    private static Block chooseBuildingPlanks(ServerLevel level, BlockPos site, Villager villager) {
        if (!AsobibaTweaksConfig.VILLAGE_BUILDING_CULTURE_ENABLED.getAsBoolean()) {
            return choosePlanks(level, site);
        }

        String[] names = {"oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry"};
        Item[] items = {
                Items.OAK_PLANKS, Items.SPRUCE_PLANKS, Items.BIRCH_PLANKS,
                Items.JUNGLE_PLANKS, Items.ACACIA_PLANKS, Items.DARK_OAK_PLANKS,
                Items.MANGROVE_PLANKS, Items.CHERRY_PLANKS
        };
        Block[] blocks = {
                Blocks.OAK_PLANKS, Blocks.SPRUCE_PLANKS, Blocks.BIRCH_PLANKS,
                Blocks.JUNGLE_PLANKS, Blocks.ACACIA_PLANKS, Blocks.DARK_OAK_PLANKS,
                Blocks.MANGROVE_PLANKS, Blocks.CHERRY_PLANKS
        };

        VillageSavedData.VillageRecord village = VillagerSimData.villageId(villager)
                .flatMap(id -> VillageSavedData.get(level).village(id))
                .orElse(null);

        if (village != null) {
            int districtDominant = -1;
            int districtDominantWeight = 0;
            int districtTotal = village.districtCultureTotal(site, "plank:");
            if (districtTotal > 0) {
                for (int i = 0; i < names.length; i++) {
                    int weight = village.districtCultureWeight(site, "plank:" + names[i]);
                    if (weight > districtDominantWeight) {
                        districtDominantWeight = weight;
                        districtDominant = i;
                    }
                }
            }

            long salt = site.asLong() ^ level.getSeed() ^ (level.getGameTime() / 24000L);
            int roll = Math.floorMod(Long.hashCode(salt), 100);
            if (districtDominant >= 0 && roll < 80) {
                return blocks[districtDominant];
            }

            if (!village.buildingCulture().isEmpty()) {
                int dominant = -1;
                int dominantWeight = 0;
                for (int i = 0; i < names.length; i++) {
                    int weight = village.cultureWeight("plank:" + names[i]);
                    if (weight > dominantWeight) {
                        dominantWeight = weight;
                        dominant = i;
                    }
                }
                if (dominant >= 0 && roll < 75) return blocks[dominant];
            }
        }

        // Non-dominant choices prefer material the village actually has available, but a one-time
        // stock dump does not become culture until completed construction records it below.
        int best = -1;
        int bestCount = 0;
        if (village != null) {
            for (int i = 0; i < items.length; i++) {
                int count = village.ledgerCount(VillageStorageService.itemKey(items[i]));
                if (count > bestCount) {
                    bestCount = count;
                    best = i;
                }
            }
        }
        if (best >= 0 && bestCount >= 16) return blocks[best];

        return choosePlanks(level, site);
    }

    private static Block choosePlanks(ServerLevel level, BlockPos pos) {
        String biome = level.getBiome(pos).unwrapKey().map(k -> k.location().getPath()).orElse("");
        if (biome.contains("taiga") || biome.contains("snow")) return Blocks.SPRUCE_PLANKS;
        if (biome.contains("birch")) return Blocks.BIRCH_PLANKS;
        if (biome.contains("savanna")) return Blocks.ACACIA_PLANKS;
        if (biome.contains("jungle")) return Blocks.JUNGLE_PLANKS;
        if (biome.contains("mangrove")) return Blocks.MANGROVE_PLANKS;
        if (biome.contains("cherry")) return Blocks.CHERRY_PLANKS;
        return Blocks.OAK_PLANKS;
    }

    private static String chooseOutpostPurpose(VillageSavedData.VillageRecord village) {
        int best = 1150;
        String purpose = "";

        int wood = village.marketPermille("wood");
        if (wood > best) {
            best = wood;
            purpose = "forestry";
        }

        int stone = village.marketPermille("stone");
        if (stone > best) {
            best = stone;
            purpose = "quarry";
        }

        int fishing = village.marketPermille("fishing");
        if (fishing > best) {
            best = fishing;
            purpose = "fishing";
        }

        int food = village.marketPermille("food");
        if (food > best) {
            purpose = "farm";
        }

        return purpose;
    }

    private static BlockPos findOutpostBuildSite(Villager villager, ServerLevel level, String purpose) {
        long salt = villager.getUUID().getLeastSignificantBits() ^ level.getGameTime() / 24000L;
        for (int attempt = 0; attempt < 20; attempt++) {
            double angle = ((salt + attempt * 0x9E3779B97F4A7C15L) >>> 11) * 0x1.0p-53 * Math.PI * 2.0D;
            boolean remote = Math.floorMod(Long.hashCode(salt), 4) == 0;
            int radius = remote
                    ? 192 + Math.floorMod(Long.hashCode(salt + attempt * 31L), 129)
                    : 96 + Math.floorMod(Long.hashCode(salt + attempt * 31L), 97);

            int x = (int)Math.floor(villager.getX() + Math.cos(angle) * radius);
            int z = (int)Math.floor(villager.getZ() + Math.sin(angle) * radius);
            BlockPos column = new BlockPos(x, level.getMinBuildHeight(), z);
            if (!VillageSimulationScheduler.isChunkLoaded(level, column)) continue;

            int y = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z);
            BlockPos base = new BlockPos(x - 2, y, z - 2);
            if (!isBuildSiteClear(level, base, 4)) continue;
            if (!outpostSupportsPurpose(level, base.offset(2, 0, 2), purpose, villager)) continue;
            return base;
        }
        return null;
    }

    private static boolean outpostSupportsPurpose(ServerLevel level, BlockPos center,
                                                  String purpose, Villager villager) {
        int useful = 0;
        boolean farmWater = false;
        int samples = 64;

        for (int i = 0; i < samples; i++) {
            if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) return false;

            int dx = villager.getRandom().nextInt(41) - 20;
            int dz = villager.getRandom().nextInt(41) - 20;
            int x = center.getX() + dx;
            int z = center.getZ() + dz;
            BlockPos column = new BlockPos(x, level.getMinBuildHeight(), z);
            if (!VillageSimulationScheduler.isChunkLoaded(level, column)) continue;

            int y = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z);
            BlockPos surface = new BlockPos(x, Math.max(level.getMinBuildHeight(), y - 1), z);
            BlockState state = level.getBlockState(surface);

            switch (purpose) {
                case "forestry" -> {
                    for (int dy = 0; dy <= 6; dy++) {
                        BlockState above = level.getBlockState(surface.above(dy));
                        if (above.is(BlockTags.LOGS) || above.is(BlockTags.LEAVES)) {
                            useful++;
                            break;
                        }
                    }
                }
                case "quarry" -> {
                    if (surface.getY() >= 0
                            && (state.is(Blocks.STONE) || state.is(Blocks.ANDESITE)
                            || state.is(Blocks.DIORITE) || state.is(Blocks.GRANITE))) {
                        useful++;
                    }
                }
                case "fishing" -> {
                    if (level.getFluidState(surface).is(FluidTags.WATER)
                            || level.getFluidState(surface.above()).is(FluidTags.WATER)) {
                        useful++;
                    }
                }
                case "farm" -> {
                    if (state.is(Blocks.GRASS_BLOCK) || state.is(Blocks.DIRT)
                            || state.is(Blocks.COARSE_DIRT) || state.is(Blocks.FARMLAND)) {
                        useful++;
                        if (hasIrrigationWater(level, surface)) farmWater = true;
                    }
                }
                default -> {
                    return false;
                }
            }

            if (useful >= 8 && (!"farm".equals(purpose) || farmWater)) return true;
        }
        return false;
    }

    private static boolean hasIrrigationWater(ServerLevel level, BlockPos soil) {
        int[][] directions = {
                {1, 0}, {-1, 0}, {0, 1}, {0, -1},
                {1, 1}, {1, -1}, {-1, 1}, {-1, -1}
        };
        for (int distance = 1; distance <= 4; distance++) {
            for (int[] direction : directions) {
                BlockPos probe = soil.offset(direction[0] * distance, 0, direction[1] * distance);
                if (level.getFluidState(probe).is(FluidTags.WATER)
                        || level.getFluidState(probe.above()).is(FluidTags.WATER)
                        || level.getFluidState(probe.below()).is(FluidTags.WATER)) {
                    return true;
                }
            }
        }
        return false;
    }

    private static VillageSavedData.WorkSiteRecord findFissionOutpost(
            ServerLevel level,
            VillageSavedData data,
            VillageSavedData.VillageRecord village,
            long now,
            int population,
            int carpenterSkill) {
        if (village == null
                || !AsobibaTweaksConfig.VILLAGE_FISSION_ENABLED.getAsBoolean()
                || population < 12
                || carpenterSkill < 50
                || village.settlementViability() < 60
                || village.sustainablePopulation() < population
                || now < village.nextFissionGameTime()) {
            return null;
        }

        for (VillageSavedData.WorkSiteRecord site : data.workSitesForVillage(village.id())) {
            if (!"outpost".equals(site.type()) || !"active".equals(site.state())) continue;
            if (site.foundingPrepared()) continue;
            if (site.createdGameTime() <= 0L || now - site.createdGameTime() < 7L * 24000L) continue;
            if (site.lastUsedGameTime() <= 0L || now - site.lastUsedGameTime() > 2L * 24000L) continue;
            if (!VillageOutpostLifecycleService.isOperational(level, data, village, site)) continue;

            BlockPos center = workSiteCenter(site);
            if (village.center().distManhattan(center) < 256) continue;

            boolean tooCloseToOtherVillage = data.villagesView().values().stream()
                    .filter(other -> !other.id().equals(village.id()))
                    .filter(other -> !"abandoned".equals(other.lifecycle()))
                    .anyMatch(other -> other.center().distManhattan(center) < 256);
            if (!tooCloseToOtherVillage) return site;
        }
        return null;
    }

    private static BlockPos workSiteCenter(VillageSavedData.WorkSiteRecord site) {
        return new BlockPos(
                (site.min().getX() + site.max().getX()) / 2,
                (site.min().getY() + site.max().getY()) / 2,
                (site.min().getZ() + site.max().getZ()) / 2
        );
    }

    private static BlockPos findBuildSiteNear(ServerLevel level, BlockPos anchor, Villager villager, int maxY) {
        long salt = anchor.asLong() ^ villager.getUUID().getMostSignificantBits() ^ (level.getGameTime() / 24000L);
        for (int attempt = 0; attempt < 16; attempt++) {
            double angle = (attempt / 16.0D) * Math.PI * 2.0D;
            int radius = 8 + Math.floorMod(Long.hashCode(salt + attempt * 17L), 11);
            int x = (int)Math.floor(anchor.getX() + Math.cos(angle) * radius);
            int z = (int)Math.floor(anchor.getZ() + Math.sin(angle) * radius);

            BlockPos column = new BlockPos(x, level.getMinBuildHeight(), z);
            if (!VillageSimulationScheduler.isChunkLoaded(level, column)) continue;

            int y = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z);
            BlockPos base = new BlockPos(x - 2, y, z - 2);
            if (isBuildSiteClear(level, base, maxY)) return base;
        }
        return null;
    }

    private static boolean isBuildSiteClear(ServerLevel level, BlockPos base, int maxY) {
        if (!VillageSimulationScheduler.isAreaLoaded(
                level,
                base.offset(0, -1, 0),
                base.offset(4, maxY, 4))) {
            return false;
        }

        for (int dx = 0; dx < 5; dx++) {
            for (int dz = 0; dz < 5; dz++) {
                if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) return false;

                BlockPos floor = base.offset(dx, -1, dz);
                if (level.getBlockState(floor).isAir() || !level.getFluidState(floor).isEmpty()) {
                    return false;
                }

                for (int dy = 0; dy <= maxY; dy++) {
                    if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) return false;
                    BlockState state = level.getBlockState(base.offset(dx, dy, dz));
                    if (!state.canBeReplaced() && !state.is(BlockTags.REPLACEABLE_BY_TREES)) {
                        return false;
                    }
                }
            }
        }
        return true;
    }

    private static BlockPos findBuildSite(
            Villager villager, ServerLevel level, boolean outpost, boolean colony, int maxY) {
        long salt = villager.getUUID().getLeastSignificantBits() ^ level.getGameTime() / 24000L;
        for (int attempt = 0; attempt < 12; attempt++) {
            double angle = ((salt + attempt * 0x9E3779B97F4A7C15L) >>> 11) * 0x1.0p-53 * Math.PI * 2.0D;
            int radius;
            if (outpost) {
                boolean remote = Math.floorMod(Long.hashCode(salt), 4) == 0;
                radius = remote
                        ? 192 + Math.floorMod(Long.hashCode(salt + attempt * 31L), 129)
                        : 96 + Math.floorMod(Long.hashCode(salt + attempt * 31L), 97);
            } else {
                radius = 10 + Math.floorMod(Long.hashCode(salt + attempt), 9);
            }
            int x = (int)Math.floor(villager.getX() + Math.cos(angle) * radius);
            int z = (int)Math.floor(villager.getZ() + Math.sin(angle) * radius);
            BlockPos columnProbe = new BlockPos(x, level.getMinBuildHeight(), z);
            if (!VillageSimulationScheduler.isChunkLoaded(level, columnProbe)) continue;

            int y = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z);
            BlockPos base = new BlockPos(x - 2, y, z - 2);
            if (!VillageSimulationScheduler.isAreaLoaded(
                    level, base.offset(0, -1, 0), base.offset(4, maxY, 4))) continue;

            if (isBuildSiteClear(level, base, maxY)) return base;
        }
        return null;
    }

    private static void tickQuartermaster(Villager villager, ServerLevel level) {
        if (level.getGameTime() % 240 != Math.floorMod(villager.getId(), 240)) return;
        if (!areaLoaded(level, villager.blockPosition(), 14, 3, 3)) return;
        List<VillageStorageService.LocatedContainer> stores = VillageStorageService.containers(villager, level);
        for (VillageStorageService.LocatedContainer located : stores) {
            Container store = located.container();
            for (int i = 0; i < store.getContainerSize(); i++) {
                ItemStack a = store.getItem(i);
                if (a.isEmpty()) continue;
                for (int j = i + 1; j < store.getContainerSize(); j++) {
                    ItemStack b = store.getItem(j);
                    if (!ItemStack.isSameItemSameComponents(a, b) || b.isEmpty()) continue;
                    int move = Math.min(b.getCount(), a.getMaxStackSize() - a.getCount());
                    if (move <= 0) continue;
                    a.grow(move);
                    b.shrink(move);
                    store.setChanged();
                }
            }
        }

        int food = VillageStorageService.count(villager, level, Items.BREAD, Items.CARROT, Items.POTATO, Items.BEETROOT);
        if (food < 16) {
            requestMaterials(villager, "food reserves");
            int streak = villager.getPersistentData().getInt(SHORTAGE_STREAK) + 1;
            villager.getPersistentData().putInt(SHORTAGE_STREAK, streak);
            if (streak >= 4) {
                villager.getPersistentData().putLong(DISTRESS, level.getGameTime() + 2L * 24000L);
        villager.getPersistentData().putLong(RECOVERY_UNTIL, level.getGameTime() + 4L * 24000L);
            }
        } else {
            villager.getPersistentData().remove(SHORTAGE_STREAK);
        }
    }

    private static void tickQuarryWorker(Villager villager, ServerLevel level) {
        if (!isWorkTime(level) || level.getGameTime() % 200 != Math.floorMod(villager.getId(), 200)) return;
        if (VillagerSimData.hasWorkCargo(villager, level.registryAccess(), WORKER_CARGO_SLOTS)) {
            depositWorkCargo(villager, level, WORKER_CARGO_SLOTS);
            return;
        }

        BlockPos center = villager.blockPosition();
        if (center.getY() < 0 || !areaLoaded(level, center, 11, 5, 5)) return;

        for (int attempt = 0; attempt < 32; attempt++) {
            if (!VillageSimulationScheduler.tryConsumeWorkerProbe(level)) return;
            BlockPos pos = center.offset(
                    villager.getRandom().nextInt(17) - 8,
                    villager.getRandom().nextInt(7) - 3,
                    villager.getRandom().nextInt(17) - 8
            );
            if (pos.getY() < 0) continue;

            BlockState state = level.getBlockState(pos);
            if (!state.is(Blocks.STONE) && !state.is(Blocks.ANDESITE) && !state.is(Blocks.DIORITE) && !state.is(Blocks.GRANITE)) continue;
            if (!hasExposedFace(level, pos) || nearProtectedBuildingBlock(level, pos)) continue;

            ItemStack mined = new ItemStack(Items.COBBLESTONE);
            if (!VillagerSimData.canInsertWorkCargo(villager, level.registryAccess(), mined, WORKER_CARGO_SLOTS)) {
                depositWorkCargo(villager, level, WORKER_CARGO_SLOTS);
                return;
            }
            if (villager.distanceToSqr(pos.getCenter()) > 2.25D) {
                villager.getNavigation().moveTo(pos.getX() + 0.5D, pos.getY(), pos.getZ() + 0.5D, 0.65D);
                return;
            }

            level.setBlock(pos, Blocks.AIR.defaultBlockState(), Block.UPDATE_ALL);
            VillagerSimData.insertWorkCargo(villager, level.registryAccess(), mined, WORKER_CARGO_SLOTS);
            return;
        }
    }

    private static void tickForester(Villager villager, ServerLevel level) {
        if (!isWorkTime(level) || level.getGameTime() % 240 != Math.floorMod(villager.getId(), 240)) return;
        if (VillagerSimData.hasWorkCargo(villager, level.registryAccess(), WORKER_CARGO_SLOTS)) {
            depositWorkCargo(villager, level, WORKER_CARGO_SLOTS);
            return;
        }

        BlockPos center = villager.blockPosition();
        if (!areaLoaded(level, center, 13, 4, 7)) return;

        for (int attempt = 0; attempt < 32; attempt++) {
            if (!VillageSimulationScheduler.tryConsumeWorkerProbe(level)) return;
            BlockPos pos = center.offset(
                    villager.getRandom().nextInt(21) - 10,
                    villager.getRandom().nextInt(8) - 2,
                    villager.getRandom().nextInt(21) - 10
            );
            BlockState state = level.getBlockState(pos);
            if (!state.is(BlockTags.LOGS) || !treeLooksNatural(level, pos)) continue;

            ItemStack log = new ItemStack(state.getBlock().asItem());
            if (log.isEmpty()) continue;
            if (!VillagerSimData.canInsertWorkCargo(villager, level.registryAccess(), log, WORKER_CARGO_SLOTS)) {
                depositWorkCargo(villager, level, WORKER_CARGO_SLOTS);
                return;
            }
            if (villager.distanceToSqr(pos.getCenter()) > 2.25D) {
                villager.getNavigation().moveTo(pos.getX() + 0.5D, pos.getY(), pos.getZ() + 0.5D, 0.7D);
                return;
            }

            level.setBlock(pos, Blocks.AIR.defaultBlockState(), Block.UPDATE_ALL);
            VillagerSimData.insertWorkCargo(villager, level.registryAccess(), log, WORKER_CARGO_SLOTS);

            if (level.getBlockState(pos.below()).is(BlockTags.DIRT)
                    && level.getBlockState(pos).isAir()) {
                Block sapling = saplingFor(state.getBlock());
                if (sapling != null) level.setBlock(pos, sapling.defaultBlockState(), Block.UPDATE_ALL);
            }
            return;
        }
    }

    private static void tickFisher(Villager villager, ServerLevel level) {
        if (!isWorkTime(level) || level.getGameTime() % 360 != Math.floorMod(villager.getId(), 360)) return;

        var siteId = VillagerSimData.outpostSiteId(villager);
        if (siteId.isEmpty()) return;

        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.WorkSiteRecord site = data.workSite(siteId.get()).orElse(null);
        if (site == null || !"outpost".equals(site.type()) || !"active".equals(site.state())
                || !"fishing".equals(site.purpose())) {
            return;
        }

        if (VillagerSimData.hasWorkCargo(villager, level.registryAccess(), WORKER_CARGO_SLOTS)) {
            depositWorkCargo(villager, level, WORKER_CARGO_SLOTS);
            return;
        }

        BlockPos center = workSiteCenter(site);
        BlockPos water = null;
        for (int attempt = 0; attempt < 40 && water == null; attempt++) {
            if (!VillageSimulationScheduler.tryConsumeWorkerProbe(level)) return;

            int x = center.getX() + villager.getRandom().nextInt(25) - 12;
            int z = center.getZ() + villager.getRandom().nextInt(25) - 12;
            BlockPos column = new BlockPos(x, level.getMinBuildHeight(), z);
            if (!VillageSimulationScheduler.isChunkLoaded(level, column)) continue;

            int surfaceY = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z);
            for (int dy = -3; dy <= 1; dy++) {
                BlockPos probe = new BlockPos(
                        x,
                        Math.max(level.getMinBuildHeight(), surfaceY + dy),
                        z
                );
                if (level.getFluidState(probe).is(FluidTags.WATER)) {
                    water = probe;
                    break;
                }
            }
        }
        if (water == null) return;

        if (villager.distanceToSqr(water.getCenter()) > 25.0D) {
            villager.getNavigation().moveTo(
                    water.getX() + 0.5D, water.getY() + 1.0D, water.getZ() + 0.5D, 0.66D);
            return;
        }

        // Common fish only: outpost fishing is a bounded food/logistics source, not a treasure generator.
        if (villager.getRandom().nextInt(3) != 0) return;
        Item catchItem = villager.getRandom().nextInt(5) == 0 ? Items.SALMON : Items.COD;
        ItemStack caught = new ItemStack(catchItem);
        if (!VillagerSimData.canInsertWorkCargo(
                villager, level.registryAccess(), caught, WORKER_CARGO_SLOTS)) {
            depositWorkCargo(villager, level, WORKER_CARGO_SLOTS);
            return;
        }

        VillagerSimData.insertWorkCargo(villager, level.registryAccess(), caught, WORKER_CARGO_SLOTS);
        site.setLastUsedGameTime(level.getGameTime());
        data.touch();
    }

    private static void tickShepherd(Villager villager, ServerLevel level) {
        if (!isWorkTime(level) || level.getGameTime() % 240 != Math.floorMod(villager.getId(), 240)) return;

        List<Sheep> sheep = level.getEntitiesOfClass(
                Sheep.class,
                villager.getBoundingBox().inflate(9.0D),
                s -> s.isAlive() && !s.isBaby() && !s.isSheared()
        );
        if (sheep.isEmpty()) return;

        Sheep target = sheep.getFirst();
        if (villager.distanceToSqr(target) > 6.25D) {
            villager.getNavigation().moveTo(target, 0.68D);
            return;
        }

        target.shear(SoundSource.NEUTRAL);
    }

    private static void tickPorter(Villager villager, ServerLevel level) {
        if (level.getGameTime() % 100 != Math.floorMod(villager.getId(), 100)) return;
        // Physical dock deliveries take precedence over collecting random
        // nearby drops and ordinary fallback cargo deposit.
        if (VillageInterSettlementFreightService.hasActiveTicket(villager)) {
            // Preserve the current real parcel's worker ownership even if a
            // river-dock delivery becomes available during an inter-village haul.
            VillageInterSettlementFreightService.handlePorter(villager, level);
            return;
        }
        if (VillageRiverPorterService.handlePorter(villager, level, null)) return;
        // A paid shipment may need to resume after a saved world or
        // destination-chunk reload before ordinary loose-item collection.
        if (VillageInterSettlementFreightService.handlePorter(villager, level)) return;
        if (!areaLoaded(level, villager.blockPosition(), 14, 3, 3)) return;

        if (VillagerSimData.hasWorkCargo(villager, level.registryAccess(), PORTER_CARGO_SLOTS)) {
            depositWorkCargo(villager, level, PORTER_CARGO_SLOTS);
            return;
        }

        List<ItemEntity> drops = level.getEntitiesOfClass(
                ItemEntity.class,
                villager.getBoundingBox().inflate(7.0D),
                item -> item.isAlive() && !item.getItem().isEmpty()
        );
        if (drops.isEmpty()) return;

        ItemEntity nearest = drops.getFirst();
        if (villager.distanceToSqr(nearest) > 2.25D) {
            villager.getNavigation().moveTo(nearest, 0.7D);
            return;
        }

        ItemStack source = nearest.getItem();
        ItemStack remainder = VillagerSimData.insertWorkCargo(
                villager, level.registryAccess(), source.copy(), PORTER_CARGO_SLOTS);
        int inserted = source.getCount() - remainder.getCount();
        if (inserted <= 0) return;

        source.shrink(inserted);
        if (source.isEmpty()) nearest.discard();
    }

    private static void tickFarmer(Villager villager, ServerLevel level) {
        var siteId = VillagerSimData.outpostSiteId(villager);
        if (siteId.isPresent()) {
            VillageSavedData data = VillageSavedData.get(level);
            VillageSavedData.WorkSiteRecord site = data.workSite(siteId.get()).orElse(null);
            if (site != null && "outpost".equals(site.type()) && "active".equals(site.state())
                    && "farm".equals(site.purpose())) {
                tickFarmOutpost(villager, level, data, site);
                return;
            }
        }
        exportVillagerFood(villager, level);
    }

    private static void tickFarmOutpost(
            Villager villager,
            ServerLevel level,
            VillageSavedData data,
            VillageSavedData.WorkSiteRecord site) {
        if (!isWorkTime(level) || level.getGameTime() % 240 != Math.floorMod(villager.getId(), 240)) return;

        boolean carryingSeed = VillagerSimData.workCargoCount(
                villager, level.registryAccess(), WORKER_CARGO_SLOTS, Items.WHEAT_SEEDS) > 0
                || VillagerSimData.workCargoCount(
                villager, level.registryAccess(), WORKER_CARGO_SLOTS, Items.BEETROOT_SEEDS) > 0;
        if (carryingSeed) {
            plantFarmCropFromCargo(villager, level, data, site);
            return;
        }

        if (VillagerSimData.hasWorkCargo(villager, level.registryAccess(), WORKER_CARGO_SLOTS)) {
            depositWorkCargo(villager, level, WORKER_CARGO_SLOTS);
            return;
        }

        BlockPos center = workSiteCenter(site);
        for (int attempt = 0; attempt < 48; attempt++) {
            if (!VillageSimulationScheduler.tryConsumeWorkerProbe(level)) return;

            int x = site.min().getX() + villager.getRandom().nextInt(
                    Math.max(1, site.max().getX() - site.min().getX() + 1));
            int z = site.min().getZ() + villager.getRandom().nextInt(
                    Math.max(1, site.max().getZ() - site.min().getZ() + 1));
            BlockPos column = new BlockPos(x, level.getMinBuildHeight(), z);
            if (!VillageSimulationScheduler.isChunkLoaded(level, column)) continue;

            int y = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z);
            BlockPos surface = new BlockPos(x, Math.max(level.getMinBuildHeight(), y - 1), z);
            for (int dy = 0; dy <= 2; dy++) {
                BlockPos cropPos = surface.above(dy);
                BlockState cropState = level.getBlockState(cropPos);
                ItemStack harvest = matureFarmHarvest(cropState);
                if (harvest.isEmpty()) continue;

                if (!VillagerSimData.canInsertWorkCargo(
                        villager, level.registryAccess(), harvest, WORKER_CARGO_SLOTS)) {
                    depositWorkCargo(villager, level, WORKER_CARGO_SLOTS);
                    return;
                }
                if (villager.distanceToSqr(cropPos.getCenter()) > 6.25D) {
                    villager.getNavigation().moveTo(
                            cropPos.getX() + 0.5D, cropPos.getY(), cropPos.getZ() + 0.5D, 0.68D);
                    return;
                }

                level.setBlock(cropPos, resetFarmCrop(cropState), Block.UPDATE_ALL);
                VillagerSimData.insertWorkCargo(
                        villager, level.registryAccess(), harvest, WORKER_CARGO_SLOTS);
                site.setLastUsedGameTime(level.getGameTime());
                data.touch();
                return;
            }
        }

        loadLocalFarmSeedCargo(villager, level, data, site);
    }

    private static ItemStack matureFarmHarvest(BlockState state) {
        if (state.is(Blocks.WHEAT)
                && state.getValue(BlockStateProperties.AGE_7) >= BlockStateProperties.MAX_AGE_7) {
            return new ItemStack(Items.WHEAT);
        }
        if (state.is(Blocks.CARROTS)
                && state.getValue(BlockStateProperties.AGE_7) >= BlockStateProperties.MAX_AGE_7) {
            return new ItemStack(Items.CARROT);
        }
        if (state.is(Blocks.POTATOES)
                && state.getValue(BlockStateProperties.AGE_7) >= BlockStateProperties.MAX_AGE_7) {
            return new ItemStack(Items.POTATO);
        }
        if (state.is(Blocks.BEETROOTS)
                && state.getValue(BlockStateProperties.AGE_3) >= BlockStateProperties.MAX_AGE_3) {
            return new ItemStack(Items.BEETROOT);
        }
        return ItemStack.EMPTY;
    }

    private static BlockState resetFarmCrop(BlockState state) {
        if (state.is(Blocks.BEETROOTS)) {
            return state.setValue(BlockStateProperties.AGE_3, 0);
        }
        if (state.is(Blocks.WHEAT) || state.is(Blocks.CARROTS) || state.is(Blocks.POTATOES)) {
            return state.setValue(BlockStateProperties.AGE_7, 0);
        }
        return state;
    }

    private static void plantFarmCropFromCargo(
            Villager villager,
            ServerLevel level,
            VillageSavedData data,
            VillageSavedData.WorkSiteRecord site) {
        BlockPos center = workSiteCenter(site);
        for (int attempt = 0; attempt < 48; attempt++) {
            if (!VillageSimulationScheduler.tryConsumeWorkerProbe(level)) return;

            int x = site.min().getX() + villager.getRandom().nextInt(
                    Math.max(1, site.max().getX() - site.min().getX() + 1));
            int z = site.min().getZ() + villager.getRandom().nextInt(
                    Math.max(1, site.max().getZ() - site.min().getZ() + 1));
            if (Math.abs(x - center.getX()) <= 3 && Math.abs(z - center.getZ()) <= 3) continue;

            BlockPos column = new BlockPos(x, level.getMinBuildHeight(), z);
            if (!VillageSimulationScheduler.isChunkLoaded(level, column)) continue;
            int y = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z);
            BlockPos soil = new BlockPos(x, Math.max(level.getMinBuildHeight(), y - 1), z);
            BlockState soilState = level.getBlockState(soil);
            if (!(soilState.is(Blocks.GRASS_BLOCK) || soilState.is(Blocks.DIRT)
                    || soilState.is(Blocks.COARSE_DIRT) || soilState.is(Blocks.FARMLAND))) {
                continue;
            }
            if (!level.getBlockState(soil.above()).isAir() || !hasIrrigationWater(level, soil)) continue;

            if (villager.distanceToSqr(soil.getCenter()) > 6.25D) {
                villager.getNavigation().moveTo(
                        soil.getX() + 0.5D, soil.getY() + 1.0D, soil.getZ() + 0.5D, 0.68D);
                return;
            }

            BlockState crop;
            if (VillagerSimData.takeWorkCargo(
                    villager, level.registryAccess(), WORKER_CARGO_SLOTS, Items.WHEAT_SEEDS, 1)) {
                crop = Blocks.WHEAT.defaultBlockState();
            } else if (VillagerSimData.takeWorkCargo(
                    villager, level.registryAccess(), WORKER_CARGO_SLOTS, Items.BEETROOT_SEEDS, 1)) {
                crop = Blocks.BEETROOTS.defaultBlockState();
            } else {
                return;
            }

            if (!soilState.is(Blocks.FARMLAND)) {
                level.setBlock(soil, Blocks.FARMLAND.defaultBlockState(), Block.UPDATE_ALL);
            }
            level.setBlock(soil.above(), crop, Block.UPDATE_ALL);
            site.setLastUsedGameTime(level.getGameTime());
            data.touch();
            return;
        }
    }

    private static void loadLocalFarmSeedCargo(
            Villager villager,
            ServerLevel level,
            VillageSavedData data,
            VillageSavedData.WorkSiteRecord site) {
        VillageSavedData.StorageRecord bestRecord = null;
        Container bestContainer = null;
        int bestDistance = Integer.MAX_VALUE;

        for (VillageSavedData.StorageRecord storage : data.storagesForVillage(site.villageId())) {
            BlockPos pos = storage.pos();
            if (pos.getX() < site.min().getX() || pos.getX() > site.max().getX()
                    || pos.getY() < site.min().getY() || pos.getY() > site.max().getY()
                    || pos.getZ() < site.min().getZ() || pos.getZ() > site.max().getZ()) {
                continue;
            }
            if (!VillageSimulationScheduler.isChunkLoaded(level, pos)) continue;
            if (!(level.getBlockEntity(pos) instanceof Container container)) continue;

            boolean hasSeed = false;
            for (int slot = 0; slot < container.getContainerSize(); slot++) {
                ItemStack stack = container.getItem(slot);
                if (stack.is(Items.WHEAT_SEEDS) || stack.is(Items.BEETROOT_SEEDS)) {
                    hasSeed = true;
                    break;
                }
            }
            if (!hasSeed) continue;

            int distance = villager.blockPosition().distManhattan(pos);
            if (distance < bestDistance) {
                bestDistance = distance;
                bestRecord = storage;
                bestContainer = container;
            }
        }

        if (bestRecord == null || bestContainer == null) return;
        BlockPos target = bestRecord.pos();
        if (villager.distanceToSqr(target.getCenter()) > 9.0D) {
            villager.getNavigation().moveTo(
                    target.getX() + 0.5D, target.getY(), target.getZ() + 0.5D, 0.70D);
            return;
        }

        int remaining = 4;
        for (int slot = 0; slot < bestContainer.getContainerSize() && remaining > 0; slot++) {
            ItemStack stack = bestContainer.getItem(slot);
            if (!(stack.is(Items.WHEAT_SEEDS) || stack.is(Items.BEETROOT_SEEDS))) continue;

            int take = Math.min(remaining, stack.getCount());
            ItemStack candidate = stack.copyWithCount(take);
            ItemStack remainder = VillagerSimData.insertWorkCargo(
                    villager, level.registryAccess(), candidate, WORKER_CARGO_SLOTS);
            int inserted = take - remainder.getCount();
            if (inserted <= 0) continue;

            stack.shrink(inserted);
            bestContainer.setChanged();
            remaining -= inserted;
        }
        VillageStorageService.reconcileVillage(site.villageId(), level);
    }

    private static void exportVillagerFood(Villager villager, ServerLevel level) {
        if (level.getGameTime() % 300 != Math.floorMod(villager.getId(), 300)) return;
        if (!areaLoaded(level, villager.blockPosition(), 12, 3, 3)) return;

        if (VillagerSimData.hasWorkCargo(villager, level.registryAccess(), WORKER_CARGO_SLOTS)) {
            depositWorkCargo(villager, level, WORKER_CARGO_SLOTS);
            return;
        }

        for (int i = 0; i < villager.getInventory().getContainerSize(); i++) {
            ItemStack stack = villager.getInventory().getItem(i);
            if (!(stack.is(Items.BREAD) || stack.is(Items.CARROT) || stack.is(Items.POTATO) || stack.is(Items.BEETROOT))
                    || stack.getCount() < 8) continue;

            ItemStack exported = stack.copyWithCount(Math.min(4, stack.getCount() - 4));
            ItemStack remainder = VillagerSimData.insertWorkCargo(
                    villager, level.registryAccess(), exported, WORKER_CARGO_SLOTS);
            int inserted = exported.getCount() - remainder.getCount();
            if (inserted > 0) stack.shrink(inserted);
            return;
        }
    }

    private static void useBuildingsInRain(Villager villager, ServerLevel level) {
        if (!level.isRainingAt(villager.blockPosition()) || villager.getNavigation().isInProgress()) return;

        BlockPos center = villager.blockPosition();
        BlockPos indexed = VillageBuildingService.findIndexedShelter(level, center, 24);
        if (indexed != null) {
            villager.getNavigation().moveTo(
                    indexed.getX() + 0.5D, indexed.getY(), indexed.getZ() + 0.5D, 0.65D);
            return;
        }

        if (!areaLoaded(level, center, 9, 2, 4)) return;
        for (int attempt = 0; attempt < 64; attempt++) {
            if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) return;
            BlockPos pos = center.offset(
                    villager.getRandom().nextInt(17) - 8,
                    villager.getRandom().nextInt(4) - 1,
                    villager.getRandom().nextInt(17) - 8
            );
            if (!level.getBlockState(pos).isAir()) continue;
            if (!level.getBlockState(pos.above(2)).isAir()
                    && level.getBlockState(pos.below()).isFaceSturdy(level, pos.below(), Direction.UP)) {
                villager.getNavigation().moveTo(pos.getX() + 0.5D, pos.getY(), pos.getZ() + 0.5D, 0.65D);
                return;
            }
        }
    }

    private static boolean depositWorkCargo(Villager villager, ServerLevel level, int capacity) {
        if (!VillagerSimData.hasWorkCargo(villager, level.registryAccess(), capacity)) return true;

        var nearest = VillageStorageService.nearestContainer(villager, level);
        if (nearest.isEmpty()) return false;

        BlockPos target = nearest.get().record().pos();
        if (villager.distanceToSqr(target.getCenter()) > 9.0D) {
            villager.getNavigation().moveTo(target.getX() + 0.5D, target.getY(), target.getZ() + 0.5D, 0.72D);
            return false;
        }

        List<ItemStack> cargo = VillagerSimData.workCargo(villager, level.registryAccess(), capacity);
        boolean changed = false;
        for (int slot = 0; slot < cargo.size(); slot++) {
            ItemStack stack = cargo.get(slot);
            if (stack.isEmpty()) continue;
            ItemStack remainder = VillageStorageService.insert(villager, level, stack);
            cargo.set(slot, remainder);
            changed = true;
        }
        if (changed) VillagerSimData.setWorkCargo(villager, level.registryAccess(), cargo, capacity);
        return !VillagerSimData.hasWorkCargo(villager, level.registryAccess(), capacity);
    }

    static boolean ensureCargoItem(Villager villager, ServerLevel level, Item item, int count, int capacity) {
        int current = VillagerSimData.workCargoCount(villager, level.registryAccess(), capacity, item);
        if (current >= count) return true;

        int needed = count - current;
        ItemStack probe = new ItemStack(item, needed);
        if (!VillagerSimData.canInsertWorkCargo(villager, level.registryAccess(), probe, capacity)) return false;

        var nearest = VillageStorageService.nearestContainerWith(villager, level, item);
        if (nearest.isEmpty()) return false;
        BlockPos target = nearest.get().record().pos();
        if (villager.distanceToSqr(target.getCenter()) > 9.0D) {
            villager.getNavigation().moveTo(target.getX() + 0.5D, target.getY(), target.getZ() + 0.5D, 0.72D);
            return false;
        }

        List<ItemStack> extracted = VillageStorageService.extract(villager, level, item, needed);
        if (extracted.isEmpty()) return false;
        for (ItemStack stack : extracted) {
            ItemStack remainder = VillagerSimData.insertWorkCargo(
                    villager, level.registryAccess(), stack, capacity);
            if (!remainder.isEmpty()) {
                VillageStorageService.insert(villager, level, remainder);
                return false;
            }
        }
        return VillagerSimData.workCargoCount(villager, level.registryAccess(), capacity, item) >= count;
    }

    static boolean ensureCargoMatching(Villager villager, ServerLevel level,
                                               java.util.function.Predicate<ItemStack> predicate,
                                               int count, int capacity) {
        int current = VillagerSimData.workCargoCountMatching(
                villager, level.registryAccess(), capacity, predicate);
        if (current >= count) return true;

        var nearest = VillageStorageService.nearestContainerMatching(villager, level, predicate);
        if (nearest.isEmpty()) return false;
        BlockPos target = nearest.get().record().pos();
        if (villager.distanceToSqr(target.getCenter()) > 9.0D) {
            villager.getNavigation().moveTo(target.getX() + 0.5D, target.getY(), target.getZ() + 0.5D, 0.72D);
            return false;
        }

        int needed = count - current;
        List<ItemStack> extracted = VillageStorageService.extractMatching(villager, level, predicate, needed);
        if (extracted.isEmpty()) return false;

        for (ItemStack stack : extracted) {
            if (!VillagerSimData.canInsertWorkCargo(villager, level.registryAccess(), stack, capacity)) {
                VillageStorageService.insert(villager, level, stack);
                return false;
            }
            ItemStack remainder = VillagerSimData.insertWorkCargo(
                    villager, level.registryAccess(), stack, capacity);
            if (!remainder.isEmpty()) {
                VillageStorageService.insert(villager, level, remainder);
                return false;
            }
        }
        return VillagerSimData.workCargoCountMatching(
                villager, level.registryAccess(), capacity, predicate) >= count;
    }

    private static boolean ensureBedCargo(Villager villager, ServerLevel level) {
        return ensureCargoMatching(villager, level, stack -> stack.is(ItemTags.WOOL), 3, CARPENTER_CARGO_SLOTS)
                && ensureCargoMatching(villager, level, stack -> stack.is(ItemTags.PLANKS), 3, CARPENTER_CARGO_SLOTS);
    }

    private static boolean consumeBedCargo(Villager villager, ServerLevel level) {
        return VillagerSimData.takeWorkCargoMatching(
                villager, level.registryAccess(), CARPENTER_CARGO_SLOTS,
                stack -> stack.is(ItemTags.WOOL), 3)
                && VillagerSimData.takeWorkCargoMatching(
                villager, level.registryAccess(), CARPENTER_CARGO_SLOTS,
                stack -> stack.is(ItemTags.PLANKS), 3);
    }

    private static void registerCompletedProject(Villager villager, ServerLevel level,
                                                 VillageSavedData.ProjectRecord project) {
        VillageSavedData data = VillageSavedData.get(level);
        BlockPos base = project.site();
        boolean storage = "storage_5x5".equals(project.templateId());
        boolean craftHall = VillageCraftHallPlanner.TEMPLATE.equals(project.templateId());
        boolean specialist = VillageSpecialistWorkshopService.isSpecialistTemplate(
                project.templateId());
        boolean gabled = "house_gabled_5x5".equals(project.templateId());
        boolean twoStory = "house_2story_5x5".equals(project.templateId());
        boolean threeStory = "house_3story_5x5".equals(project.templateId());
        boolean outpost = Boolean.parseBoolean(project.parameter("outpost"));
        boolean colony = Boolean.parseBoolean(project.parameter("colony"));
        int maxY = templateMaxY(project.templateId());

        java.util.UUID ownerVillageId = project.villageId();

        if (colony) {
            String rawOutpost = project.parameter("outpost_id");
            try {
                java.util.UUID outpostId = java.util.UUID.fromString(rawOutpost);
                VillageSavedData.WorkSiteRecord site = data.workSite(outpostId).orElse(null);
                if (site != null && project.villageId().equals(site.villageId())) {
                    // The second lodging building is still parent-village infrastructure.
                    // Village ID creation waits until housing/storage/food/route validation passes.
                    site.setFoundingPrepared(true);
                    site.setLastUsedGameTime(level.getGameTime());
                }
            } catch (IllegalArgumentException ignored) {
                // Invalid legacy outpost id: keep the completed building under the parent.
            }
        }

        VillageSavedData.BuildingRecord building = data.createBuilding(
                ownerVillageId, base, base.offset(4, maxY, 4), true);
        building.setTemplateId(project.templateId());
        building.setClassification(storage ? "storage"
                : craftHall || specialist ? "workshop" : "residential");
        int specialistCapacity = specialist
                && level.getBlockState(base.offset(2, 1, 2)).is(
                        VillageSpecialistWorkshopService.primaryStation(project.templateId()))
                ? 1 : 0;
        int craftCapacity = craftHall
                ? (level.getBlockState(base.offset(1, 1, 2)).is(Blocks.SMITHING_TABLE) ? 1 : 0)
                        + (level.getBlockState(base.offset(3, 1, 2)).is(Blocks.STONECUTTER) ? 1 : 0)
                : 0;
        building.setValidatedCapacity(storage ? 0
                : specialist ? specialistCapacity
                : craftHall ? craftCapacity
                : threeStory ? 6
                : twoStory ? 4
                : gabled ? 2
                : outpost ? 2 : 1);
        // Do not advertise an apparently complete craft hall as a valid
        // two-job workstation if a placement hook or outside block change
        // removed either of its physical stations.
        building.setValidationState(
                craftHall && craftCapacity < 2 || specialist && specialistCapacity < 1
                        ? "invalid" : "valid");
        building.setLastValidatedGameTime(level.getGameTime());

        String plank = project.parameter("plank");
        if (!plank.isBlank()) {
            java.util.UUID finalOwnerVillageId = ownerVillageId;
            data.village(finalOwnerVillageId).ifPresent(village -> {
                village.recordBuildingCulture("plank:" + plank, 10);
                village.recordDistrictBuildingCulture(base, "plank:" + plank, 10);
            });
        }
        if (threeStory || twoStory) {
            int formWeight = threeStory ? 12 : 8;
            java.util.UUID finalOwnerVillageId = ownerVillageId;
            data.village(finalOwnerVillageId).ifPresent(village -> {
                village.recordBuildingCulture("form:multi_story", formWeight);
                village.recordDistrictBuildingCulture(base, "form:multi_story", formWeight);
            });
        } else if (gabled) {
            java.util.UUID finalOwnerVillageId = ownerVillageId;
            data.village(finalOwnerVillageId).ifPresent(village -> {
                village.recordBuildingCulture("form:gabled", 6);
                village.recordDistrictBuildingCulture(base, "form:gabled", 6);
                village.recordBuildingCulture("form:one_story", 3);
                village.recordDistrictBuildingCulture(base, "form:one_story", 3);
            });
        } else {
            java.util.UUID finalOwnerVillageId = ownerVillageId;
            data.village(finalOwnerVillageId).ifPresent(village -> {
                village.recordBuildingCulture("form:one_story", 4);
                village.recordDistrictBuildingCulture(base, "form:one_story", 4);
            });
        }

        if (storage || craftHall || specialist) {
            List<BlockPos> storagePositions = storage
                    ? List.of(base.offset(1, 1, 2), base.offset(3, 1, 2))
                    : craftHall ? List.of(base.offset(2, 1, 3))
                    : List.of(base.offset(3, 1, 3));
            for (BlockPos storagePos : storagePositions) {
                if (level.getBlockEntity(storagePos) instanceof Container
                        && data.storageAt(ownerVillageId, storagePos).isEmpty()) {
                    VillageSavedData.StorageRecord storageRecord =
                            data.createStorage(ownerVillageId, storagePos, "general");
                    storageRecord.setValidationState("valid");
                    storageRecord.setLastValidatedGameTime(level.getGameTime());
                }
            }
            VillageStorageService.reconcileVillage(ownerVillageId, level);
        }

        if (outpost && !colony) {
            String outpostPurpose = project.parameter("outpost_purpose");
            BlockPos workMin = "farm".equals(outpostPurpose) ? base.offset(-8, -2, -8) : base;
            BlockPos workMax = "farm".equals(outpostPurpose)
                    ? base.offset(12, Math.max(maxY, 4), 12)
                    : base.offset(4, maxY, 4);
            VillageSavedData.WorkSiteRecord site =
                    data.createWorkSite(project.villageId(), "outpost", workMin, workMax);
            site.setPurpose(outpostPurpose);
            site.setCreatedGameTime(level.getGameTime());
            site.setLastUsedGameTime(level.getGameTime());
            site.setLastLifecycleGameTime(level.getGameTime());

            BlockPos localStorage = base.offset(3, 1, 2);
            if (level.getBlockEntity(localStorage) instanceof Container
                    && data.storageAt(project.villageId(), localStorage).isEmpty()) {
                VillageSavedData.StorageRecord storageRecord =
                        data.createStorage(project.villageId(), localStorage, "general");
                storageRecord.setValidationState("valid");
                storageRecord.setLastValidatedGameTime(level.getGameTime());
                VillageStorageService.reconcileVillage(project.villageId(), level);
            }
        }
        data.touch();
    }

    /**
     * Public-works link from an actual completed river dock's LAND access cell
     * toward its parent settlement. Never connect across missing loaded chunks
     * or manufacture a road merely because geography was surveyed.
     */
    static void scheduleDockRoad(ServerLevel level, java.util.UUID villageId,
                                 BlockPos land, BlockPos villageCenter, Villager carpenter) {
        if (!AsobibaTweaksConfig.VILLAGE_ROADS_ENABLED.getAsBoolean()
                || villageCenter == null
                || land.distManhattan(villageCenter) > 96
                || !VillageSimulationScheduler.isAreaLoaded(
                        level,
                        new BlockPos(Math.min(land.getX(), villageCenter.getX()) - 24,
                                level.getMinBuildHeight(),
                                Math.min(land.getZ(), villageCenter.getZ()) - 24),
                        new BlockPos(Math.max(land.getX(), villageCenter.getX()) + 24,
                                level.getMinBuildHeight(),
                                Math.max(land.getZ(), villageCenter.getZ()) + 24))) return;

        createRoadDemandProject(level, villageId, land, villageCenter, carpenter);
    }

    private static void createRoadDemandProject(ServerLevel level, java.util.UUID villageId,
                                                BlockPos from, BlockPos to, Villager carpenter) {
        if (from.distManhattan(to) < 6) return;

        VillageSavedData data = VillageSavedData.get(level);
        for (VillageSavedData.ProjectRecord existing : data.activeProjectsForVillage(villageId)) {
            if (!"road".equals(existing.type())) continue;
            BlockPos end = existing.anchor();
            if (end != null && existing.site().distManhattan(from) < 5 && end.distManhattan(to) < 5) return;
        }

        VillageSavedData.RouteRecord route = data.createRoute(villageId, "road", from, to);
        route.setTrafficScore(1);
        route.setQuality("dirt");
        route.setWidth(from.distManhattan(to) >= 64 ? 2 : 1);
        route.setState("planned");

        VillageSavedData.ProjectRecord road = data.createProject(villageId, "road", 30, from);
        road.setTemplateId("road_path_v2");
        road.setVariantSeed(from.asLong() ^ to.asLong());
        road.setLeadCarpenterId(carpenter.getUUID());
        road.setAnchor(to);
        road.setParameter("route_id", route.id().toString());
        road.setParameter("plank", plankName(chooseBuildingPlanks(level, from, carpenter)));
        road.setParameter("road_quality", route.quality());
        road.setParameter("road_width", Integer.toString(route.width()));
        road.setParameter("bridge_details", "parapet_v1");
        road.setPhase("route_planning");
        road.setPausedReason("planning terrain route");
        road.setWorkCursor(0);
        data.touch();

        java.util.UUID routeId = route.id();
        java.util.UUID projectId = road.id();
        enqueueRoadGeometry(level, routeId, projectId);
    }

    private static void enqueueRoadGeometry(
            ServerLevel level, java.util.UUID routeId, java.util.UUID projectId) {
        VillageSimulationScheduler.enqueueRouteSearch(
                level, "road_geometry:" + routeId,
                () -> refreshRoadGeometry(level, routeId, projectId));
    }

    private static void refreshRoadGeometry(
            ServerLevel level, java.util.UUID routeId, java.util.UUID projectId) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.RouteRecord route = data.route(routeId).orElse(null);
        VillageSavedData.ProjectRecord project = data.project(projectId).orElse(null);
        if (route == null || project == null
                || !"route_planning".equals(project.phase())
                || !route.villageId().equals(project.villageId())) return;
        List<BlockPos> nodes = VillageRoadPlanner.planLoaded(
                level, route.from(), route.to());
        if (nodes.size() < 2) {
            // Keep the durable request pending instead of inventing a
            // straight unverified crossing. The Carpenter enqueues retries
            // on the bounded route-search queue.
            project.setPausedReason("terrain path unavailable; awaiting loaded survey");
            data.touch();
            return;
        }
        // The coarse A* costs water significantly above dry terrain.
        // When a short, truly safe straight crossing saves >=8 route blocks
        // compared to the chosen detour, a proper raised bridge is justified.
        // Otherwise preserve the verified, cheaper land route.
        int fromX = route.from().getX();
        int fromZ = route.from().getZ();
        int toX = route.to().getX();
        int toZ = route.to().getZ();
        int directBlocks = Math.abs(toX - fromX) + Math.abs(toZ - fromZ);
        boolean aligned = (fromX == toX) != (fromZ == toZ);
        VillageBridgeService.Candidate direct = null;
        if (aligned && VillageBridgeService.preferableToDetour(
                directBlocks, roadCenterlineCount(nodes))) {
            List<BlockPos> straight = List.of(route.from(), route.to());
            direct = VillageBridgeService.findLoadedCrossing(
                    level, straight, route.width());
            if (direct != null && !VillageBridgeService.directShortcutSafe(
                    level, route.from(), route.to(), direct)) direct = null;
        }

        List<BlockPos> selected = direct == null
                ? nodes : List.of(route.from(), route.to());
        data.setRouteWaypoints(route.id(), selected);

        boolean queued = direct != null
                ? VillageBridgeService.queueValidatedBridge(
                        level, data, route, project, direct)
                : VillageBridgeService.queueBridge(
                        level, data, route, project, selected);
        if (!queued) {
            project.setPhase("planned");
            project.setPausedReason("");
        }
        data.touch();
    }

    private static int countBlocks(ServerLevel level, BlockPos center, int radius, java.util.function.Predicate<BlockState> predicate) {
        if (!areaLoaded(level, center, radius, 5, 5)) return 0;

        int count = 0;
        for (BlockPos pos : BlockPos.betweenClosed(center.offset(-radius, -5, -radius), center.offset(radius, 5, radius))) {
            if (predicate.test(level.getBlockState(pos)) && ++count >= 64) break;
        }
        return count;
    }

    private static boolean hasExposedFace(ServerLevel level, BlockPos pos) {
        if (!VillageSimulationScheduler.isAreaLoaded(level, pos.offset(-1, -1, -1), pos.offset(1, 1, 1))) return false;
        for (Direction direction : Direction.values()) {
            if (!VillageSimulationScheduler.tryConsumeWorkerProbe(level)) return false;
            if (level.getBlockState(pos.relative(direction)).isAir()) return true;
        }
        return false;
    }

    private static boolean nearProtectedBuildingBlock(ServerLevel level, BlockPos pos) {
        if (!VillageSimulationScheduler.isAreaLoaded(level, pos.offset(-3, -2, -3), pos.offset(3, 3, 3))) return true;
        for (BlockPos p : BlockPos.betweenClosed(pos.offset(-3, -2, -3), pos.offset(3, 3, 3))) {
            if (!VillageSimulationScheduler.tryConsumeWorkerProbe(level)) return true;
            BlockState state = level.getBlockState(p);
            if (state.is(BlockTags.BEDS) || state.is(Blocks.CHEST) || state.is(Blocks.BARREL)
                    || state.is(AsobibaRegistries.CARPENTER_WORKBENCH.get())) return true;
        }
        return false;
    }

    private static boolean treeLooksNatural(ServerLevel level, BlockPos pos) {
        if (!VillageSimulationScheduler.isAreaLoaded(level, pos.offset(-3, 0, -3), pos.offset(3, 5, 3))) return false;
        boolean leaves = false;
        for (BlockPos p : BlockPos.betweenClosed(pos.offset(-3, 0, -3), pos.offset(3, 5, 3))) {
            if (!VillageSimulationScheduler.tryConsumeWorkerProbe(level)) return false;
            if (level.getBlockState(p).is(BlockTags.LEAVES)) {
                leaves = true;
                break;
            }
        }
        return leaves && !nearProtectedBuildingBlock(level, pos);
    }

    private static Block saplingFor(Block log) {
        if (log == Blocks.SPRUCE_LOG) return Blocks.SPRUCE_SAPLING;
        if (log == Blocks.BIRCH_LOG) return Blocks.BIRCH_SAPLING;
        if (log == Blocks.JUNGLE_LOG) return Blocks.JUNGLE_SAPLING;
        if (log == Blocks.ACACIA_LOG) return Blocks.ACACIA_SAPLING;
        if (log == Blocks.DARK_OAK_LOG) return Blocks.DARK_OAK_SAPLING;
        if (log == Blocks.MANGROVE_LOG) return Blocks.MANGROVE_PROPAGULE;
        if (log == Blocks.CHERRY_LOG) return Blocks.CHERRY_SAPLING;
        if (log == Blocks.OAK_LOG) return Blocks.OAK_SAPLING;
        return null;
    }

    private static boolean areaLoaded(ServerLevel level, BlockPos center, int horizontal, int down, int up) {
        return VillageSimulationScheduler.isAreaLoaded(
                level,
                center.offset(-horizontal, -down, -horizontal),
                center.offset(horizontal, up, horizontal)
        );
    }

    private static void runIfActive(Villager villager, ServerLevel level, Runnable work) {
        if (!villager.isAlive() || villager.isRemoved() || villager.level() != level) return;
        work.run();
    }

    private static boolean isWorkTime(ServerLevel level) {
        long t = Math.floorMod(level.getDayTime(), 24000L);
        return t >= 1500L && t <= 10500L && !level.isThundering();
    }

    private static void requestMaterials(Villager villager, String what) {
        if (!AsobibaTweaksConfig.VILLAGE_PUBLIC_WORKS_ENABLED.getAsBoolean()
                || !(villager.level() instanceof ServerLevel level)) {
            return;
        }

        VillagerSimData.villageId(villager).ifPresent(villageId ->
                VillageSimulationScheduler.enqueuePlanning(
                        level,
                        "public_works_immediate:" + villageId,
                        () -> VillagePublicWorksService.refresh(level, villageId)
                )
        );
    }

    static record BuildStep(BlockPos pos, BlockState state, Item cost) {}

    private static final class Vec3Away {
        static void moveAway(Villager villager, BlockPos danger) {
            double dx = villager.getX() - danger.getX();
            double dz = villager.getZ() - danger.getZ();
            double len = Math.max(0.001D, Math.sqrt(dx * dx + dz * dz));
            villager.getNavigation().moveTo(
                    villager.getX() + dx / len * 10.0D,
                    villager.getY(),
                    villager.getZ() + dz / len * 10.0D,
                    1.0D
            );
        }
    }
}
