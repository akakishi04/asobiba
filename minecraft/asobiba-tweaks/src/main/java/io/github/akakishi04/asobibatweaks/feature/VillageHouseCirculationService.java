package io.github.akakishi04.asobibatweaks.feature;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.BedBlock;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BedPart;
import net.minecraft.world.phys.AABB;

/** Explicit, paid, resumable v1 -> v2 migration. Raw construction cursors never change. */
public final class VillageHouseCirculationService {
    public static final String TEMPLATE = "retrofit_house_circulation_v2";
    static final String CURSOR = "circulation_migration_cursor";
    static final String VERIFIED = "circulation_verified_v2";
    private static final String HOME = "circulation_home";
    private static final String OWNER = "circulation_owner";
    private static final int SLOTS = 8;
    private VillageHouseCirculationService() {}

    public static boolean tryPlan(Villager worker, ServerLevel level, UUID villageId) {
        VillageSavedData data = VillageSavedData.get(level);
        var village = data.village(villageId).orElse(null);
        if (village == null || !"active".equals(village.lifecycle())
                || village.buildingIds().size() > 128 || village.projectIds().size() > 512) return false;
        for (var home : village.buildingIds().stream().sorted(Comparator.comparing(UUID::toString))
                .limit(24).map(data::building).flatMap(java.util.Optional::stream).toList()) {
            if (!home.villageBuilt() || !"residential".equals(home.classification())
                    || !home.villageId().equals(villageId) || floors(home.templateId()) == 0
                    || !home.max().equals(home.min().offset(4, floors(home.templateId()) * 4, 4))
                    || home.min().distManhattan(worker.blockPosition()) > 64
                    || data.activeProjectsForVillage(villageId).stream().anyMatch(p -> p.site().equals(home.min()) || p.parameters().containsValue(home.id().toString()))) continue;
            var owner = village.projectIds().stream().map(data::project).flatMap(java.util.Optional::stream)
                    .filter(p -> "complete".equals(p.phase()) && p.site().equals(home.min())
                            && outputFloors(p) == floors(home.templateId())
                            && (p.templateId().equals(home.templateId())
                                || home.id().toString().equals(p.parameter("expand_building"))
                                || home.id().toString().equals(p.parameter("third_building"))))
                    .filter(p -> !"true".equals(p.parameter(VERIFIED)))
                    .filter(p -> blueprint(data, p, new HashSet<>()) != null).findFirst().orElse(null);
            if (owner == null || !VillageSimulationScheduler.isAreaLoaded(level, home.min(), home.max())) continue;
            var project = data.createProject(villageId, "building", 91, home.min());
            project.setTemplateId(TEMPLATE);
            project.setParameter(HOME, home.id().toString());
            project.setParameter(OWNER, owner.id().toString());
            project.setLeadCarpenterId(worker.getUUID());
            project.setAnchor(home.min());
            project.setPhase("circulation");
            data.touch();
            return true;
        }
        return false;
    }

    static void advance(Villager worker, ServerLevel level, VillageSavedData.ProjectRecord retrofit) {
        VillageSavedData data = VillageSavedData.get(level);
        var home = building(data, retrofit.parameter(HOME));
        var source = project(data, retrofit.parameter(OWNER));
        if (home == null || source == null || !home.villageBuilt()
                || !home.villageId().equals(retrofit.villageId())
                || !home.min().equals(retrofit.site()) || !source.site().equals(home.min())
                || !"complete".equals(source.phase()) || outputFloors(source) != floors(home.templateId())) {
            pause(data, retrofit, "original circulation owner no longer valid");
            return;
        }
        if (!ensure(worker, level, source)) {
            pause(data, retrofit, source.pausedReason());
            return;
        }
        retrofit.setPhase("complete");
        retrofit.setPausedReason("");
        retrofit.clearReservations();
        data.touch();
        VillageSimulationScheduler.enqueueValidation(level, "circulation:" + home.id(),
                () -> VillageBuildingService.revalidateChunk(level, new ChunkPos(home.min())));
    }

    public static boolean ensure(Villager worker, ServerLevel level, VillageSavedData.ProjectRecord source) {
        int floors = outputFloors(source);
        if (floors == 0 || Boolean.parseBoolean(source.parameter("outpost"))
                || Boolean.parseBoolean(source.parameter("colony"))) return true;
        VillageSavedData data = VillageSavedData.get(level);
        if (!VillageSimulationScheduler.isAreaLoaded(level, source.site(), source.site().offset(4, floors * 4, 4)))
            return pause(data, source, "circulation chunks unloaded");
        Map<BlockPos, BlockState> before = blueprint(data, source, new HashSet<>());
        if (before == null) return pause(data, source, "circulation original blueprint ownership invalid");
        Map<BlockPos, BlockState> after = target(before, source.site(), floors);
        List<Operation> operations = operations(before, after);
        int cursor = integer(source.parameter(CURSOR));
        if (cursor < 0 || cursor > operations.size()) return pause(data, source, "invalid circulation cursor");
        if ("true".equals(source.parameter(VERIFIED))) {
            return verify(level, after) && accessible(level, source.site(), floors)
                    || pause(data, source, "verified circulation was player edited");
        }
        // Preflight every owned/target cell before demolition. Only exact original
        // states, exact final states, and already-executed removals are accepted.
        for (var cell : after.entrySet()) {
            BlockState actual = level.getBlockState(cell.getKey());
            BlockState old = before.getOrDefault(cell.getKey(), Blocks.AIR.defaultBlockState());
            if (same(actual, cell.getValue()) || same(actual, old)) continue;
            boolean removed = actual.isAir() && operations.stream()
                    .anyMatch(op -> op.remove() && (op.pos().equals(cell.getKey())
                            || op.bed() && op.pos().relative(op.state().getValue(BedBlock.FACING)).equals(cell.getKey())));
            if (!removed) return pause(data, source, "circulation cell player edited");
        }
        if (cursor == operations.size()) {
            if (!verify(level, after) || !accessible(level, source.site(), floors))
                return pause(data, source, "circulation physical verification incomplete");
            source.setParameter(VERIFIED, "true");
            source.setPausedReason("");
            data.touch();
            return true;
        }
        Operation op = operations.get(cursor);
        if (!op.remove() && !bedComplete(level, op.pos(), op.state())
                && !VillageCarpenterCraftingService.ensureWhiteBed(worker, level,
                        VillageBridgeService.plank(wood(source)), SLOTS))
            return pause(data, source, "stage a real circulation bed before approaching room");
        if (worker.distanceToSqr(op.pos().getCenter()) > 49) {
            worker.getNavigation().moveTo(op.pos().getX() + 0.5, op.pos().getY(), op.pos().getZ() + 0.5, 0.75);
            return pause(data, source, "carpenter approaching circulation work");
        }
        if (op.remove()) {
            BlockPos head = op.bed() ? op.pos().relative(op.state().getValue(BedBlock.FACING)) : op.pos();
            BlockState current = level.getBlockState(op.pos());
            if (op.bed() && same(current, op.state())
                    && same(level.getBlockState(head), op.state().setValue(BedBlock.PART, BedPart.HEAD))) {
                if (current.getValue(BedBlock.OCCUPIED) || level.getBlockState(head).getValue(BedBlock.OCCUPIED))
                    return pause(data, source, "circulation bed occupied");
                AABB area = new AABB(op.pos()).inflate(2);
                Set<UUID> existing = new HashSet<>();
                for (var item : level.getEntitiesOfClass(ItemEntity.class, area)) existing.add(item.getUUID());
                // Vanilla creates the real Bed drop. Pickup only newly produced items.
                if (!level.destroyBlock(head, true, worker)) return pause(data, source, "bed demolition rejected");
                if (same(level.getBlockState(op.pos()), op.state())) level.removeBlock(op.pos(), false);
                for (var item : level.getEntitiesOfClass(ItemEntity.class, area)) {
                    if (existing.contains(item.getUUID()) || !item.getItem().is(Items.WHITE_BED)) continue;
                    ItemStack remaining = VillagerSimData.insertWorkCargo(worker, level.registryAccess(), item.getItem().copy(), SLOTS);
                    if (remaining.isEmpty()) item.discard(); else item.setItem(remaining);
                }
            } else if (!op.bed() && same(current, op.state())) {
                if (!level.destroyBlock(op.pos(), true, worker)) return pause(data, source, "plank demolition rejected");
            } else if (!(same(current, after.getOrDefault(op.pos(), Blocks.AIR.defaultBlockState())) || current.isAir())) {
                return pause(data, source, "owned demolition target changed");
            }
        } else {
            BlockPos head = op.pos().relative(op.state().getValue(BedBlock.FACING));
            BlockState headState = op.state().setValue(BedBlock.PART, BedPart.HEAD);
            boolean complete = same(level.getBlockState(op.pos()), op.state()) && same(level.getBlockState(head), headState);
            if (!complete) {
                if ((!level.getBlockState(op.pos()).isAir() && !same(level.getBlockState(op.pos()), op.state()))
                        || (!level.getBlockState(head).isAir() && !same(level.getBlockState(head), headState)))
                    return pause(data, source, "new circulation bed player occupied");
                // No durable free-placement entitlement: a lost or broken paid
                // half never authorizes minting another bed after save/reload.
                if (!VillagerSimData.takeWorkCargo(worker, level.registryAccess(), SLOTS, Items.WHITE_BED, 1))
                    return pause(data, source, "circulation needs a real bed item");
                level.setBlock(op.pos(), op.state(), Block.UPDATE_CLIENTS);
                level.setBlock(head, headState, Block.UPDATE_CLIENTS);
                level.updateNeighborsAt(op.pos(), Blocks.WHITE_BED);
                level.updateNeighborsAt(head, Blocks.WHITE_BED);
                if (!same(level.getBlockState(op.pos()), op.state()) || !same(level.getBlockState(head), headState))
                    return pause(data, source, "paid circulation bed placement incomplete");
            }
        }
        source.setParameter(CURSOR, Integer.toString(cursor + 1));
        source.setPausedReason("");
        data.touch();
        return false;
    }

    private static List<Operation> operations(Map<BlockPos, BlockState> before, Map<BlockPos, BlockState> after) {
        List<Operation> result = new ArrayList<>();
        for (var cell : before.entrySet()) {
            BlockState state = cell.getValue();
            if (state.is(Blocks.WHITE_BED)) {
                if (state.getValue(BedBlock.PART) == BedPart.FOOT && !state.equals(after.get(cell.getKey())))
                    result.add(new Operation(cell.getKey(), state, true, true));
            } else if (!state.isAir() && after.get(cell.getKey()).isAir()) {
                result.add(new Operation(cell.getKey(), state, true, false));
            }
        }
        for (var cell : after.entrySet()) if (cell.getValue().is(Blocks.WHITE_BED)
                && cell.getValue().getValue(BedBlock.PART) == BedPart.FOOT
                && !cell.getValue().equals(before.get(cell.getKey())))
            result.add(new Operation(cell.getKey(), cell.getValue(), false, true));
        return result;
    }

    /** Composite exact owner-linked source, including completed expansions. */
    static Map<BlockPos, BlockState> blueprint(VillageSavedData data, VillageSavedData.ProjectRecord source, Set<UUID> seen) {
        if (!seen.add(source.id()) || seen.size() > 4 || !"building".equals(source.type())
                || Boolean.parseBoolean(source.parameter("outpost")) || Boolean.parseBoolean(source.parameter("colony"))) return null;
        Map<BlockPos, BlockState> result = new LinkedHashMap<>();
        if (source.templateId().equals(VillageHouseVerticalExpansionService.TEMPLATE)
                || source.templateId().equals(VillageHouseThirdFloorExpansionService.TEMPLATE)) {
            boolean third = source.templateId().equals(VillageHouseThirdFloorExpansionService.TEMPLATE);
            var parent = project(data, source.parameter(third ? "third_source" : "expand_original"));
            var home = building(data, source.parameter(third ? "third_building" : "expand_building"));
            if (parent == null || home == null || !home.villageBuilt() || !home.min().equals(source.site())
                    || !home.villageId().equals(source.villageId()) || !parent.villageId().equals(source.villageId())
                    || !parent.site().equals(source.site()) || !"complete".equals(parent.phase())) return null;
            Map<BlockPos, BlockState> inherited = blueprint(data, parent, seen);
            if (inherited == null) return null;
            if ("true".equals(parent.parameter(VERIFIED))) inherited = target(inherited, parent.site(), outputFloors(parent));
            result.putAll(inherited);
            if (third) for (var step : VillageHouseThirdFloorExpansionService.steps(source)) {
                if (step.kind() == VillageHouseThirdFloorExpansionService.SALVAGE_BED) {
                    BlockState bed = result.get(step.pos());
                    if (bed == null || !bed.is(Blocks.WHITE_BED) || bed.getValue(BedBlock.PART) != BedPart.FOOT) return null;
                    result.put(step.pos().relative(bed.getValue(BedBlock.FACING)), Blocks.AIR.defaultBlockState());
                    result.put(step.pos(), Blocks.AIR.defaultBlockState());
                } else put(result, step.pos(), step.state());
            } else for (var step : VillageHouseVerticalExpansionService.steps(source)) put(result, step.pos(), step.state());
        } else if (floors(source.templateId()) > 0 || "house_5x5".equals(source.templateId())) {
            for (var step : VillageSimulationEvents.projectPlan(source)) result.put(step.pos(), step.state());
            if ("house_5x5".equals(source.templateId())) {
                var village = data.village(source.villageId()).orElse(null);
                if (village == null || village.projectIds().size() > 512) return null;
                for (UUID id : village.projectIds()) {
                    var reuse = data.project(id).orElse(null);
                    if (reuse == null || !VillageHouseReuseService.TEMPLATE.equals(reuse.templateId())
                            || !"complete".equals(reuse.phase()) || !reuse.site().equals(source.site().offset(1, 1, 2))
                            || !reuse.villageId().equals(source.villageId())
                            || !source.id().toString().equals(reuse.parameter("reuse_original_project"))) continue;
                    var home = building(data, reuse.parameter("reuse_building"));
                    if (home == null || !home.villageBuilt() || !home.min().equals(source.site())
                            || !home.villageId().equals(source.villageId())
                            || !source.parameter("plank").equals(reuse.parameter("reuse_wood"))) return null;
                    put(result, source.site().offset(1, 1, 2), bed(Direction.SOUTH));
                }
            }
        } else return null;
        return result;
    }

    /** Shared final manifest for repair consumers; never reinterpret raw plan indices. */
    static Map<BlockPos, BlockState> verifiedTarget(VillageSavedData.ProjectRecord source,
            Map<BlockPos, BlockState> before) {
        return "true".equals(source.parameter(VERIFIED)) && outputFloors(source) > 0
                ? target(before, source.site(), outputFloors(source)) : before;
    }

    private static Map<BlockPos, BlockState> target(Map<BlockPos, BlockState> before, BlockPos base, int floors) {
        Map<BlockPos, BlockState> result = new LinkedHashMap<>(before);
        result.replaceAll((pos, state) -> state.is(Blocks.WHITE_BED) ? Blocks.AIR.defaultBlockState() : state);
        put(result, base.offset(1, 1, 3), bed(Direction.EAST));
        for (int floor = 1; floor < floors; floor++) {
            int y = floor * 4 + 1;
            if (floor == floors - 1) put(result, base.offset(1, y, 2), bed(Direction.NORTH));
            put(result, base.offset(2, y, 3), bed(Direction.WEST));
            result.put(base.offset(2, y - 1, 1), Blocks.AIR.defaultBlockState());
            result.put(base.offset(2, y, 2), Blocks.AIR.defaultBlockState());
            result.put(base.offset(2, y + 1, 2), Blocks.AIR.defaultBlockState());
        }
        result.put(base.offset(4, 1, 1), Blocks.AIR.defaultBlockState());
        result.put(base.offset(4, 2, 1), Blocks.AIR.defaultBlockState());
        return result;
    }
    private static void put(Map<BlockPos, BlockState> map, BlockPos pos, BlockState state) {
        map.put(pos, state);
        if (state.is(Blocks.WHITE_BED) && state.getValue(BedBlock.PART) == BedPart.FOOT)
            map.put(pos.relative(state.getValue(BedBlock.FACING)), state.setValue(BedBlock.PART, BedPart.HEAD));
    }
    private static BlockState bed(Direction facing) { return Blocks.WHITE_BED.defaultBlockState().setValue(BedBlock.FACING, facing).setValue(BedBlock.PART, BedPart.FOOT); }
    private static boolean same(BlockState actual, BlockState expected) {
        return expected != null && (actual.equals(expected) || actual.is(Blocks.WHITE_BED) && expected.is(Blocks.WHITE_BED)
                && actual.setValue(BedBlock.OCCUPIED, false).equals(expected.setValue(BedBlock.OCCUPIED, false)));
    }
    private static boolean verify(ServerLevel level, Map<BlockPos, BlockState> desired) {
        for (var entry : desired.entrySet()) if (!same(level.getBlockState(entry.getKey()), entry.getValue())) return false;
        return true;
    }
    private static boolean bedComplete(ServerLevel level, BlockPos pos, BlockState foot) {
        return same(level.getBlockState(pos), foot) && same(level.getBlockState(pos.relative(foot.getValue(BedBlock.FACING))),
                foot.setValue(BedBlock.PART, BedPart.HEAD));
    }
    private static boolean accessible(ServerLevel level, BlockPos base, int floors) {
        if (!VillageBuildingService.connectedUpperStories(level, base, floors - 1)
                || !VillageBuildingService.reachableTemplateGround(level, base).contains(base.offset(1, 1, 2).asLong())) return false;
        for (int floor = 1; floor < floors; floor++) {
            BlockPos standing = base.offset(2, floor * 4 + 1, 2);
            if (!level.getBlockState(standing).isAir() || !level.getBlockState(standing.above()).isAir()
                    || !level.getBlockState(standing.below()).isFaceSturdy(level, standing.below(), Direction.UP)) return false;
        }
        return true;
    }
    private static int outputFloors(VillageSavedData.ProjectRecord source) {
        if (VillageHouseVerticalExpansionService.TEMPLATE.equals(source.templateId())) return 2;
        if (VillageHouseThirdFloorExpansionService.TEMPLATE.equals(source.templateId())) return 3;
        return floors(source.templateId());
    }
    private static int floors(String template) { return "house_2story_5x5".equals(template) ? 2 : "house_3story_5x5".equals(template) ? 3 : 0; }
    private static String wood(VillageSavedData.ProjectRecord p) {
        return p.templateId().equals(VillageHouseVerticalExpansionService.TEMPLATE) ? p.parameter("expand_plank")
                : p.templateId().equals(VillageHouseThirdFloorExpansionService.TEMPLATE) ? p.parameter("third_plank") : p.parameter("plank");
    }
    private static int integer(String value) { try { return value.isBlank() ? 0 : Integer.parseInt(value); } catch (NumberFormatException e) { return -1; } }
    private static VillageSavedData.ProjectRecord project(VillageSavedData data, String id) { try { return data.project(UUID.fromString(id)).orElse(null); } catch (IllegalArgumentException e) { return null; } }
    private static VillageSavedData.BuildingRecord building(VillageSavedData data, String id) { try { return data.building(UUID.fromString(id)).orElse(null); } catch (IllegalArgumentException e) { return null; } }
    private static boolean pause(VillageSavedData data, VillageSavedData.ProjectRecord p, String why) { p.setPausedReason(why); data.touch(); return false; }
    private record Operation(BlockPos pos, BlockState state, boolean remove, boolean bed) {}
}
