package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaRegistries;
import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.npc.VillagerProfession;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.BaseFireBlock;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.phys.AABB;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;

/**
 * Village-level fire incident detection and resource-aware emergency behavior.
 */
public final class VillageFireEmergencyService {
    private static final int FIRE_THRESHOLD = 4;
    private static final long PERSISTENCE_TICKS = 40L;
    private static final long CLEAR_TICKS = 80L;
    private static final int RESPONDER_LIMIT = 3;
    private static final int RESPONDER_CARGO_SLOTS = 8;

    public VillageFireEmergencyService() {
    }

    @SubscribeEvent
    public void onVillagerTick(EntityTickEvent.Post event) {
        if (!AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                || !AsobibaTweaksConfig.VILLAGE_FIRE_EMERGENCY_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof Villager villager)
                || villager.level().isClientSide()) {
            return;
        }

        ServerLevel level = (ServerLevel)villager.level();
        VillageIdentityBootstrap.ensure(villager, level);
        VillagerSimData.villageId(villager).ifPresent(villageId -> {
            long now = level.getGameTime();
            if (Math.floorMod(now, 40L) != Math.floorMod(villageId.hashCode(), 40)) return;
            VillageSimulationScheduler.enqueueEmergency(
                    level,
                    "fire_village:" + villageId,
                    () -> scanAndRespond(level, villageId)
            );
        });
    }

    private static void scanAndRespond(ServerLevel level, UUID villageId) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null || "abandoned".equals(village.lifecycle()) || "merged".equals(village.lifecycle())) {
            return;
        }

        FireScan scan = scanVillage(level, data, village);
        long now = level.getGameTime();
        String state = village.fireEmergencyState();

        if (scan.fires.size() >= FIRE_THRESHOLD) {
            BlockPos center = average(scan.fires);
            village.setFireCenter(center);
            village.setFireLastSeenGameTime(now);

            if ("none".equals(state)) {
                village.setFireEmergencyState("candidate");
                village.setFireCandidateSinceGameTime(now);
            } else if ("candidate".equals(state)
                    && now - village.fireCandidateSinceGameTime() >= PERSISTENCE_TICKS) {
                village.setFireEmergencyState("active");
            } else if ("suspended".equals(state)) {
                village.setFireEmergencyState("active");
            }
        } else if ("candidate".equals(state)) {
            village.clearFireEmergency();
        }

        state = village.fireEmergencyState();
        if ("active".equals(state)) {
            if (!scan.fires.isEmpty()) {
                village.setFireLastSeenGameTime(now);
                BlockPos center = average(scan.fires);
                village.setFireCenter(center);
                respond(level, data, village, scan.fires, center);
            } else if (!scan.complete) {
                village.setFireEmergencyState("suspended");
                clearEmergencyDuties(level, village);
            } else if (now - village.fireLastSeenGameTime() >= CLEAR_TICKS) {
                finishEmergency(level, data, village);
            }
        } else if ("suspended".equals(state)) {
            if (!scan.fires.isEmpty()) {
                village.setFireEmergencyState("active");
                BlockPos center = average(scan.fires);
                village.setFireCenter(center);
                village.setFireLastSeenGameTime(now);
                respond(level, data, village, scan.fires, center);
            } else if (scan.complete) {
                finishEmergency(level, data, village);
            }
        }

        data.touch();
        VillageSimulationScheduler.enqueuePlanning(
                level,
                "public_works_fire:" + villageId,
                () -> VillagePublicWorksService.refresh(level, villageId)
        );
    }

    private static FireScan scanVillage(
            ServerLevel level,
            VillageSavedData data,
            VillageSavedData.VillageRecord village) {
        List<BlockPos> fires = new ArrayList<>();
        boolean complete = true;
        int scannedBuildings = 0;

        List<VillageSavedData.BuildingRecord> buildings = new ArrayList<>();
        for (UUID buildingId : village.buildingIds()) {
            VillageSavedData.BuildingRecord building = data.building(buildingId).orElse(null);
            if (building != null && !"invalid".equals(building.validationState())) buildings.add(building);
        }
        buildings.sort(Comparator.comparingInt(
                b -> village.center().distManhattan(centerOf(b.min(), b.max()))));

        for (VillageSavedData.BuildingRecord building : buildings) {
            if (scannedBuildings++ >= 4 || fires.size() >= 16) break;
            BlockPos min = building.min().offset(-2, -1, -2);
            BlockPos max = building.max().offset(2, 3, 2);
            if (!VillageSimulationScheduler.isAreaLoaded(level, min, max)) {
                complete = false;
                continue;
            }
            if (!scanBox(level, min, max, fires)) {
                complete = false;
                break;
            }
        }

        if (fires.size() < FIRE_THRESHOLD) {
            BlockPos center = village.center();
            BlockPos min = center.offset(-10, -3, -10);
            BlockPos max = center.offset(10, 4, 10);
            if (VillageSimulationScheduler.isAreaLoaded(level, min, max)) {
                if (!scanBox(level, min, max, fires)) complete = false;
            } else {
                complete = false;
            }
        }

        return new FireScan(List.copyOf(fires), complete);
    }

    private static boolean scanBox(ServerLevel level, BlockPos min, BlockPos max, List<BlockPos> fires) {
        Set<Long> seen = new HashSet<>();
        for (BlockPos existing : fires) seen.add(existing.asLong());

        for (BlockPos pos : BlockPos.betweenClosed(min, max)) {
            if (!VillageSimulationScheduler.tryConsumeEmergencyProbe(level)) return false;
            if (!(level.getBlockState(pos).getBlock() instanceof BaseFireBlock)) continue;
            if (seen.add(pos.asLong())) fires.add(pos.immutable());
            if (fires.size() >= 16) return true;
        }
        return true;
    }

    private static void respond(
            ServerLevel level,
            VillageSavedData data,
            VillageSavedData.VillageRecord village,
            List<BlockPos> fires,
            BlockPos fireCenter) {

        List<Villager> residents = loadedResidents(level, village);
        if (residents.isEmpty()) return;

        for (Villager resident : residents) {
            resident.getPersistentData().putLong(
                    "asobibatweaks_village_distress",
                    level.getGameTime() + 2L * 24_000L
            );
        }

        List<Villager> responderCandidates = residents.stream()
                .filter(v -> !v.isBaby())
                .filter(v -> v.getVillagerData().getProfession() != VillagerProfession.NITWIT)
                .sorted(Comparator
                        .comparingInt(VillageFireEmergencyService::responderPriority)
                        .thenComparing(v -> v.getUUID().toString()))
                .toList();

        Set<UUID> responders = new HashSet<>();
        for (Villager candidate : responderCandidates) {
            if (responders.size() >= RESPONDER_LIMIT) break;
            responders.add(candidate.getUUID());
        }

        BlockPos waterSource = findWaterSource(level, fireCenter, 12);
        for (Villager villager : residents) {
            if (responders.contains(villager.getUUID())) {
                VillagerSimData.setEmergencyDuty(villager, "fire_responder");
                handleResponder(villager, level, fires, waterSource);
            } else {
                VillagerSimData.setEmergencyDuty(villager, "fire_evacuate");
                evacuate(villager, level, fireCenter);
            }
        }
    }

    private static int responderPriority(Villager villager) {
        if (villager.getVillagerData().getProfession() == AsobibaRegistries.CARPENTER.value()) return 0;
        String duty = VillagerSimData.duty(villager);
        if ("porter".equals(duty)) return 1;
        if ("quartermaster".equals(duty)) return 2;
        if (villager.getVillagerData().getProfession() == VillagerProfession.NONE) return 3;
        return 4;
    }

    private static void handleResponder(
            Villager villager,
            ServerLevel level,
            List<BlockPos> fires,
            BlockPos waterSource) {
        if (fires.isEmpty()) return;
        BlockPos fire = fires.stream()
                .min(Comparator.comparingDouble(pos -> villager.distanceToSqr(pos.getCenter())))
                .orElse(fires.getFirst());

        if (!VillagerSimData.fireWaterReady(villager)) {
            if (waterSource != null) {
                if (villager.distanceToSqr(waterSource.getCenter()) > 9.0D) {
                    villager.getNavigation().moveTo(
                            waterSource.getX() + 0.5D,
                            waterSource.getY(),
                            waterSource.getZ() + 0.5D,
                            0.9D
                    );
                    return;
                }
                VillagerSimData.setFireWaterReady(villager, true, false);
                return;
            }

            if (VillagerSimData.workCargoCount(
                    villager, level.registryAccess(), RESPONDER_CARGO_SLOTS, Items.WATER_BUCKET) > 0) {
                VillagerSimData.setFireWaterReady(villager, true, true);
                return;
            }

            var storage = VillageStorageService.nearestContainer(villager, level);
            if (storage.isEmpty()) return;
            BlockPos storagePos = storage.get().record().pos();
            if (villager.distanceToSqr(storagePos.getCenter()) > 9.0D) {
                villager.getNavigation().moveTo(
                        storagePos.getX() + 0.5D,
                        storagePos.getY(),
                        storagePos.getZ() + 0.5D,
                        0.82D
                );
                return;
            }

            List<ItemStack> buckets = VillageStorageService.extract(
                    villager, level, Items.WATER_BUCKET, 1);
            if (buckets.isEmpty()) return;
            ItemStack remainder = VillagerSimData.insertWorkCargo(
                    villager, level.registryAccess(), buckets.getFirst(), RESPONDER_CARGO_SLOTS);
            if (!remainder.isEmpty()) {
                VillageStorageService.insert(villager, level, remainder);
                return;
            }
            VillagerSimData.setFireWaterReady(villager, true, true);
            return;
        }

        if (villager.distanceToSqr(fire.getCenter()) > 16.0D) {
            villager.getNavigation().moveTo(
                    fire.getX() + 0.5D,
                    fire.getY(),
                    fire.getZ() + 0.5D,
                    0.9D
            );
            return;
        }

        if (level.getBlockState(fire).getBlock() instanceof BaseFireBlock) {
            level.setBlock(fire, Blocks.AIR.defaultBlockState(), net.minecraft.world.level.block.Block.UPDATE_ALL);
        }

        if (VillagerSimData.fireWaterFromBucket(villager)) {
            if (VillagerSimData.takeWorkCargo(
                    villager, level.registryAccess(), RESPONDER_CARGO_SLOTS, Items.WATER_BUCKET, 1)) {
                ItemStack remainder = VillagerSimData.insertWorkCargo(
                        villager, level.registryAccess(), new ItemStack(Items.BUCKET), RESPONDER_CARGO_SLOTS);
                if (!remainder.isEmpty()) villager.spawnAtLocation(remainder);
            }
        }
        VillagerSimData.setFireWaterReady(villager, false, false);
    }

    private static void evacuate(Villager villager, ServerLevel level, BlockPos fireCenter) {
        BlockPos shelter = VillageBuildingService.findIndexedShelter(level, villager.blockPosition(), 48);
        double currentDanger = villager.distanceToSqr(fireCenter.getCenter());
        if (shelter != null && shelter.distSqr(fireCenter) >= currentDanger + 64.0D) {
            villager.getNavigation().moveTo(
                    shelter.getX() + 0.5D, shelter.getY(), shelter.getZ() + 0.5D, 0.85D);
            return;
        }

        double dx = villager.getX() - (fireCenter.getX() + 0.5D);
        double dz = villager.getZ() - (fireCenter.getZ() + 0.5D);
        double length = Math.max(0.001D, Math.sqrt(dx * dx + dz * dz));
        int tx = (int)Math.floor(villager.getX() + dx / length * 16.0D);
        int tz = (int)Math.floor(villager.getZ() + dz / length * 16.0D);
        BlockPos column = new BlockPos(tx, level.getMinBuildHeight(), tz);
        if (!VillageSimulationScheduler.isChunkLoaded(level, column)) return;

        int ty = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, tx, tz);
        villager.getNavigation().moveTo(tx + 0.5D, ty, tz + 0.5D, 0.88D);
    }

    private static BlockPos findWaterSource(ServerLevel level, BlockPos center, int radius) {
        for (int ring = 0; ring <= radius; ring += 2) {
            for (int dx = -ring; dx <= ring; dx += 2) {
                BlockPos a = surfaceWater(level, center.getX() + dx, center.getZ() - ring);
                if (a != null) return a;
                BlockPos b = surfaceWater(level, center.getX() + dx, center.getZ() + ring);
                if (b != null) return b;
            }
            for (int dz = -ring + 2; dz <= ring - 2; dz += 2) {
                BlockPos a = surfaceWater(level, center.getX() - ring, center.getZ() + dz);
                if (a != null) return a;
                BlockPos b = surfaceWater(level, center.getX() + ring, center.getZ() + dz);
                if (b != null) return b;
            }
        }
        return null;
    }

    private static BlockPos surfaceWater(ServerLevel level, int x, int z) {
        BlockPos column = new BlockPos(x, level.getMinBuildHeight(), z);
        if (!VillageSimulationScheduler.isChunkLoaded(level, column)) return null;
        if (!VillageSimulationScheduler.tryConsumeEmergencyProbe(level)) return null;

        int y = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z);
        BlockPos surface = new BlockPos(x, y - 1, z);
        return level.getFluidState(surface).is(FluidTags.WATER) ? surface : null;
    }

    private static void finishEmergency(
            ServerLevel level,
            VillageSavedData data,
            VillageSavedData.VillageRecord village) {
        BlockPos center = village.fireCenter();
        clearEmergencyDuties(level, village);
        village.clearFireEmergency();

        if (center != null) {
            ChunkPos chunk = new ChunkPos(center);
            for (int dx = -1; dx <= 1; dx++) {
                for (int dz = -1; dz <= 1; dz++) {
                    ChunkPos affected = new ChunkPos(chunk.x + dx, chunk.z + dz);
                    data.invalidateChunk(affected);
                    VillageSimulationScheduler.enqueueValidation(
                            level,
                            "post_fire_validate:" + affected.toLong(),
                            () -> VillageBuildingService.revalidateChunk(level, affected)
                    );
                }
            }
        }
        data.touch();
    }

    private static void clearEmergencyDuties(ServerLevel level, VillageSavedData.VillageRecord village) {
        for (Villager villager : loadedResidents(level, village)) {
            VillagerSimData.clearEmergencyDuty(villager);
        }
    }

    private static List<Villager> loadedResidents(
            ServerLevel level,
            VillageSavedData.VillageRecord village) {
        return level.getEntitiesOfClass(
                Villager.class,
                new AABB(village.center()).inflate(160.0D, 80.0D, 160.0D),
                villager -> villager.isAlive()
                        && VillagerSimData.villageId(villager).filter(village.id()::equals).isPresent()
        );
    }

    private static BlockPos average(List<BlockPos> positions) {
        long x = 0L;
        long y = 0L;
        long z = 0L;
        for (BlockPos pos : positions) {
            x += pos.getX();
            y += pos.getY();
            z += pos.getZ();
        }
        int count = Math.max(1, positions.size());
        return new BlockPos((int)(x / count), (int)(y / count), (int)(z / count));
    }

    private static BlockPos centerOf(BlockPos min, BlockPos max) {
        return new BlockPos(
                (min.getX() + max.getX()) / 2,
                (min.getY() + max.getY()) / 2,
                (min.getZ() + max.getZ()) / 2
        );
    }

    private record FireScan(List<BlockPos> fires, boolean complete) {
    }
}
