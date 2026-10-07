package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaRegistries;
import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
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
    private static final String SETTLE_X = "asobibatweaks_settle_x";
    private static final String SETTLE_Y = "asobibatweaks_settle_y";
    private static final String SETTLE_Z = "asobibatweaks_settle_z";
    private static final String SETTLE_UNTIL = "asobibatweaks_settle_until";

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

        event.getTrades().get(1).add(new BasicItemListing(
                new ItemStack(Items.OAK_LOG, 16), new ItemStack(Items.EMERALD), 16, 2, 0.05F));
        event.getTrades().get(1).add(new BasicItemListing(
                1, new ItemStack(Items.SCAFFOLDING, 8), 12, 1));
        event.getTrades().get(2).add(new BasicItemListing(
                new ItemStack(Items.COBBLESTONE, 24), new ItemStack(Items.EMERALD), 12, 5, 0.05F));
        event.getTrades().get(2).add(new BasicItemListing(
                2, new ItemStack(Items.OAK_DOOR, 4), 12, 5));
        event.getTrades().get(3).add(new BasicItemListing(
                2, new ItemStack(Items.OAK_FENCE, 12), 12, 10));
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
                && "farmer".equals(duty)) {
            VillageSimulationScheduler.enqueueWorker(level, "farmer_export:" + id,
                    () -> runIfActive(villager, level, () -> exportVillagerFood(villager, level)));
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
        int stores = VillageStorageService.containers(villager, level).size();
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

        boolean housingNeed = beds <= population + 1;
        boolean storageNeed = stores < Math.max(2, (population + 3) / 4);
        VillageSavedData.VillageRecord village = data.village(villageId.get()).orElse(null);
        VillageSavedData.WorkSiteRecord fissionOutpost = findFissionOutpost(
                data, village, now, population, skill);
        boolean colony = fissionOutpost != null;
        boolean outpost = !colony
                && AsobibaTweaksConfig.VILLAGE_OUTPOSTS_ENABLED.getAsBoolean()
                && !housingNeed && !storageNeed && population >= 6
                && skill >= 25 && Math.floorMod((int)(now / 24000L) + villager.getId(), 4) == 3;

        if (!housingNeed && !storageNeed && !outpost && !colony) {
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
        BlockPos site;
        if (colony) {
            BlockPos outpostCenter = workSiteCenter(fissionOutpost);
            site = findBuildSiteNear(level, outpostCenter, villager, 8);
        } else {
            site = findBuildSite(villager, level, outpost, false);
        }
        if (site == null) {
            villager.getPersistentData().putLong(NEXT_BUILD, now + 12000L);
            return;
        }

        String templateId;
        if (buildKind == 1) templateId = "storage_5x5";
        else if (colony) templateId = "house_2story_5x5";
        else if (!outpost && skill >= 50 && population >= 8) templateId = "house_2story_5x5";
        else templateId = "house_5x5";

        VillageSavedData.ProjectRecord project = data.createProject(
                villageId.get(), "building", housingNeed ? 80 : storageNeed ? 70 : 40, site);
        project.setTemplateId(templateId);
        project.setVariantSeed(villager.getUUID().getLeastSignificantBits() ^ site.asLong());
        project.setLeadCarpenterId(villager.getUUID());
        project.setAnchor(villager.blockPosition());
        project.setParameter("outpost", Boolean.toString(outpost || colony));
        project.setParameter("colony", Boolean.toString(colony));
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

        List<BuildStep> plan = projectPlan(project);
        int stepIndex = project.workCursor();
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
                && !ensureCargoItem(villager, level, step.cost, 1, CARPENTER_CARGO_SLOTS)) {
            project.setPausedReason("missing " + step.cost.getDescription().getString());
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
        BlockPos from = project.site();
        BlockPos to = project.anchor();
        if (to == null) {
            project.setPhase("cancelled");
            project.setPausedReason("missing route endpoint");
            VillageSavedData.get(level).touch();
            return;
        }

        int dx = to.getX() - from.getX();
        int dz = to.getZ() - from.getZ();
        int steps = Math.max(Math.abs(dx), Math.abs(dz));
        if (steps <= 0) {
            completeRoadProject(level, project);
            return;
        }
        if (steps > 160) {
            project.setPhase("paused");
            project.setPausedReason("route exceeds V5 initial range");
            VillageSavedData.get(level).touch();
            return;
        }

        int cursor = project.workCursor();
        if (cursor > steps) {
            completeRoadProject(level, project);
            return;
        }

        double t = cursor / (double)steps;
        int x = (int)Math.round(from.getX() + dx * t);
        int z = (int)Math.round(from.getZ() + dz * t);
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
        if (villager.distanceToSqr(surface.getCenter()) > 7.0D * 7.0D) {
            project.setPausedReason("worker travelling");
            project.setPhase("roadwork");
            villager.getNavigation().moveTo(surface.getX() + 0.5D, surface.getY() + 1.0D,
                    surface.getZ() + 0.5D, 0.75D);
            VillageSavedData.get(level).touch();
            return;
        }

        BlockState state = level.getBlockState(surface);
        if (level.getFluidState(surface).is(FluidTags.WATER)) {
            Block plank = plankFromName(project.parameter("plank"));
            Item plankItem = plank.asItem();
            if (!ensureCargoItem(villager, level, plankItem, 1, CARPENTER_CARGO_SLOTS)) {
                project.setPausedReason("missing bridge planks");
                project.setPhase("paused");
                VillageSavedData.get(level).touch();
                return;
            }
            if (!VillagerSimData.takeWorkCargo(villager, level.registryAccess(),
                    CARPENTER_CARGO_SLOTS, plankItem, 1)) return;
            level.setBlock(surface, plank.defaultBlockState(), Block.UPDATE_ALL);
            project.setPhase("bridge_deck");
        } else if (state.is(Blocks.GRASS_BLOCK) || state.is(Blocks.DIRT) || state.is(Blocks.COARSE_DIRT)) {
            level.setBlock(surface, Blocks.DIRT_PATH.defaultBlockState(), Block.UPDATE_ALL);
            project.setPhase("roadwork");
        } else if (!state.is(Blocks.DIRT_PATH)) {
            // Preserve player/structure blocks; skip rather than bulldozing.
            project.setPhase("roadwork");
        }

        project.setPausedReason("");
        project.setWorkCursor(cursor + 1);
        VillageSavedData.get(level).touch();

        if (project.workCursor() > steps) completeRoadProject(level, project);
    }

    private static void completeRoadProject(ServerLevel level, VillageSavedData.ProjectRecord project) {
        project.setPhase("complete");
        project.setPausedReason("");
        String rawRoute = project.parameter("route_id");
        if (!rawRoute.isBlank()) {
            try {
                java.util.UUID routeId = java.util.UUID.fromString(rawRoute);
                VillageSavedData.get(level).route(routeId).ifPresent(route -> route.setState("active"));
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
        VillagerSimData.setCarpentrySkill(villager, Math.min(100, skill + 2));

        registerCompletedProject(villager, level, project);

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
            } else {
                sendSettlers(level, villager, project.site().offset(2, 1, 2), 2);
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
        String template = project.templateId();
        if (cursor < 25) return "foundation";
        if ("house_2story_5x5".equals(template)) {
            if (cursor < 75) return "ground_floor";
            if (cursor < 100) return "second_floor";
            if (cursor < 150) return "upper_floor";
            if (cursor < 175) return "roof";
            return "interior";
        }
        if (cursor < 75) return "walls";
        if (cursor < 100) return "roof";
        return "interior";
    }

    private static List<BuildStep> projectPlan(VillageSavedData.ProjectRecord project) {
        if ("storage_5x5".equals(project.templateId())) return storagePlan(project);
        return hutPlan(project);
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

        steps.add(new BuildStep(base.offset(1, 1, 2), Blocks.BARREL.defaultBlockState(), plankItem));
        steps.add(new BuildStep(base.offset(3, 1, 2), Blocks.BARREL.defaultBlockState(), plankItem));
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

        BlockState bedFoot = Blocks.WHITE_BED.defaultBlockState()
                .setValue(BedBlock.PART, BedPart.FOOT)
                .setValue(HorizontalDirectionalBlock.FACING, Direction.SOUTH);
        BlockState bedHead = bedFoot.setValue(BedBlock.PART, BedPart.HEAD);
        steps.add(new BuildStep(base.offset(2, 1, 2), bedFoot, null));
        steps.add(new BuildStep(base.offset(2, 1, 3), bedHead, null));
        if (Boolean.parseBoolean(project.parameter("outpost"))) {
            BlockState secondBedFoot = Blocks.WHITE_BED.defaultBlockState()
                    .setValue(BedBlock.PART, BedPart.FOOT)
                    .setValue(HorizontalDirectionalBlock.FACING, Direction.SOUTH);
            BlockState secondBedHead = secondBedFoot.setValue(BedBlock.PART, BedPart.HEAD);
            steps.add(new BuildStep(base.offset(1, 1, 2), secondBedFoot, null));
            steps.add(new BuildStep(base.offset(1, 1, 3), secondBedHead, null));
            steps.add(new BuildStep(base.offset(3, 1, 2), Blocks.BARREL.defaultBlockState(), plankItem));
            steps.add(new BuildStep(base.offset(3, 1, 3), Blocks.COMPOSTER.defaultBlockState(), plankItem));
            if (Boolean.parseBoolean(project.parameter("colony"))) {
                steps.add(new BuildStep(base.offset(1, 1, 1),
                        AsobibaRegistries.CARPENTER_WORKBENCH.get().defaultBlockState(), plankItem));
            }
        }

        if ("house_2story_5x5".equals(project.templateId())) {
            // Replace the single-story roof layer with a second floor and add an upper shell/roof.
            steps.removeIf(step -> step.pos.getY() == base.getY() + 4);
            for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
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
            steps.add(new BuildStep(base.offset(1, 1, 1), stairState, plankItem));
            steps.add(new BuildStep(base.offset(2, 2, 1), stairState, plankItem));
            steps.add(new BuildStep(base.offset(3, 3, 1), stairState, plankItem));

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

    private static Block stairsForPlank(Block plank) {
        if (plank == Blocks.SPRUCE_PLANKS) return Blocks.SPRUCE_STAIRS;
        if (plank == Blocks.BIRCH_PLANKS) return Blocks.BIRCH_STAIRS;
        if (plank == Blocks.JUNGLE_PLANKS) return Blocks.JUNGLE_STAIRS;
        if (plank == Blocks.ACACIA_PLANKS) return Blocks.ACACIA_STAIRS;
        if (plank == Blocks.DARK_OAK_PLANKS) return Blocks.DARK_OAK_STAIRS;
        if (plank == Blocks.MANGROVE_PLANKS) return Blocks.MANGROVE_STAIRS;
        if (plank == Blocks.CHERRY_PLANKS) return Blocks.CHERRY_STAIRS;
        return Blocks.OAK_STAIRS;
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

        if (village != null && !village.buildingCulture().isEmpty()) {
            int dominant = -1;
            int dominantWeight = 0;
            for (int i = 0; i < names.length; i++) {
                int weight = village.cultureWeight("plank:" + names[i]);
                if (weight > dominantWeight) {
                    dominantWeight = weight;
                    dominant = i;
                }
            }

            if (dominant >= 0) {
                long salt = site.asLong() ^ level.getSeed() ^ (level.getGameTime() / 24000L);
                int roll = Math.floorMod(Long.hashCode(salt), 100);
                if (roll < 75) return blocks[dominant];
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

    private static VillageSavedData.WorkSiteRecord findFissionOutpost(
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
            if (site.createdGameTime() <= 0L || now - site.createdGameTime() < 7L * 24000L) continue;

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

    private static BlockPos findBuildSite(Villager villager, ServerLevel level, boolean outpost, boolean colony) {
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
            if (!VillageSimulationScheduler.isAreaLoaded(level, base.offset(0, -1, 0), base.offset(4, 4, 4))) continue;

            if (isBuildSiteClear(level, base, 4)) return base;
        }
        return null;
    }

    private static void sendSettlers(ServerLevel level, Villager carpenter, BlockPos target, int targetCount) {
        long until = level.getGameTime() + 3L * 24000L;
        List<Villager> candidates = level.getEntitiesOfClass(
                Villager.class,
                carpenter.getBoundingBox().inflate(28.0D),
                v -> v != carpenter && !v.isBaby()
        );
        int sent = 0;
        for (Villager settler : candidates) {
            VillagerProfession profession = settler.getVillagerData().getProfession();
            if (profession != VillagerProfession.NONE && profession != VillagerProfession.NITWIT
                    && profession != VillagerProfession.FARMER) continue;
            var data = settler.getPersistentData();
            data.putInt(SETTLE_X, target.getX());
            data.putInt(SETTLE_Y, target.getY());
            data.putInt(SETTLE_Z, target.getZ());
            data.putLong(SETTLE_UNTIL, until);
            settler.getNavigation().moveTo(target.getX() + 0.5D, target.getY(), target.getZ() + 0.5D, 0.75D);
            if (++sent >= targetCount) break;
        }
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

    private static boolean ensureCargoItem(Villager villager, ServerLevel level, Item item, int count, int capacity) {
        int current = VillagerSimData.workCargoCount(villager, level.registryAccess(), capacity, item);
        if (current >= count) return true;

        int needed = count - current;
        ItemStack probe = new ItemStack(item, needed);
        if (!VillagerSimData.canInsertWorkCargo(villager, level.registryAccess(), probe, capacity)) return false;

        var nearest = VillageStorageService.nearestContainer(villager, level);
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

    private static boolean ensureCargoMatching(Villager villager, ServerLevel level,
                                               java.util.function.Predicate<ItemStack> predicate,
                                               int count, int capacity) {
        int current = VillagerSimData.workCargoCountMatching(
                villager, level.registryAccess(), capacity, predicate);
        if (current >= count) return true;

        var nearest = VillageStorageService.nearestContainer(villager, level);
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
        boolean twoStory = "house_2story_5x5".equals(project.templateId());
        boolean outpost = Boolean.parseBoolean(project.parameter("outpost"));
        boolean colony = Boolean.parseBoolean(project.parameter("colony"));
        int maxY = twoStory ? 8 : 4;

        java.util.UUID ownerVillageId = project.villageId();

        if (colony) {
            String rawOutpost = project.parameter("outpost_id");
            try {
                java.util.UUID outpostId = java.util.UUID.fromString(rawOutpost);
                VillageSavedData.WorkSiteRecord site = data.workSite(outpostId).orElse(null);
                VillageSavedData.VillageRecord parent = data.village(project.villageId()).orElse(null);
                if (site != null && parent != null) {
                    BlockPos daughterCenter = workSiteCenter(site);
                    VillageSavedData.VillageRecord daughter = data.createVillage(daughterCenter, level.getGameTime());
                    daughter.setParentVillageId(parent.id());
                    daughter.setLifecycle("founding");
                    daughter.setNextFissionGameTime(level.getGameTime() + 30L * 24000L);
                    parent.setNextFissionGameTime(level.getGameTime() + 30L * 24000L);

                    parent.buildingCulture().forEach((key, value) ->
                            daughter.recordBuildingCulture(key, Math.max(1, value / 2)));

                    data.transferOutpostSite(outpostId, daughter.id());
                    site.setType("founding_site");
                    site.setState("active");
                    ownerVillageId = daughter.id();
                    project.setParameter("founded_village_id", daughter.id().toString());
                }
            } catch (IllegalArgumentException ignored) {
                // Keep ownership with the parent; founding migration will not start without an ID.
            }
        }

        VillageSavedData.BuildingRecord building = data.createBuilding(
                ownerVillageId, base, base.offset(4, maxY, 4), true);
        building.setTemplateId(project.templateId());
        building.setClassification(storage ? "storage" : "residential");
        building.setValidatedCapacity(storage ? 0 : twoStory ? 4 : outpost ? 2 : 1);
        building.setValidationState("valid");
        building.setLastValidatedGameTime(level.getGameTime());

        String plank = project.parameter("plank");
        if (!plank.isBlank()) {
            java.util.UUID finalOwnerVillageId = ownerVillageId;
            data.village(finalOwnerVillageId).ifPresent(village ->
                    village.recordBuildingCulture("plank:" + plank, 10));
        }
        if (twoStory) {
            java.util.UUID finalOwnerVillageId = ownerVillageId;
            data.village(finalOwnerVillageId).ifPresent(village ->
                    village.recordBuildingCulture("form:multi_story", 8));
        } else {
            java.util.UUID finalOwnerVillageId = ownerVillageId;
            data.village(finalOwnerVillageId).ifPresent(village ->
                    village.recordBuildingCulture("form:one_story", 4));
        }

        if (storage) {
            for (BlockPos storagePos : List.of(base.offset(1, 1, 2), base.offset(3, 1, 2))) {
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
            VillageSavedData.WorkSiteRecord site =
                    data.createWorkSite(project.villageId(), "outpost", base, base.offset(4, maxY, 4));
            site.setCreatedGameTime(level.getGameTime());
            site.setLastUsedGameTime(level.getGameTime());

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
        route.setState("planned");

        VillageSavedData.ProjectRecord road = data.createProject(villageId, "road", 30, from);
        road.setTemplateId("road_path_v1");
        road.setVariantSeed(from.asLong() ^ to.asLong());
        road.setLeadCarpenterId(carpenter.getUUID());
        road.setAnchor(to);
        road.setParameter("route_id", route.id().toString());
        road.setParameter("plank", plankName(chooseBuildingPlanks(level, from, carpenter)));
        road.setPhase("planned");
        road.setWorkCursor(0);
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
        if (!AsobibaTweaksConfig.VILLAGE_PUBLIC_WORKS_ENABLED.getAsBoolean()) return;
        long now = villager.level().getGameTime();
        long last = villager.getPersistentData().getLong("asobibatweaks_last_request");
        if (now - last < 1200L) return;
        villager.getPersistentData().putLong("asobibatweaks_last_request", now);

        var nearest = ((ServerLevel)villager.level()).getNearestPlayer(villager, 20.0D);
        if (nearest instanceof ServerPlayer player) {
            player.sendSystemMessage(net.minecraft.network.chat.Component.literal(
                    "Village carpenter needs " + what + " for current work."
            ).withStyle(ChatFormatting.YELLOW));
        }
    }

    private record BuildStep(BlockPos pos, BlockState state, Item cost) {}

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
