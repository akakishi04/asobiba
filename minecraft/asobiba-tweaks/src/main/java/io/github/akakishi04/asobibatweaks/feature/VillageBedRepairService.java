package io.github.akakishi04.asobibatweaks.feature;

import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.BedBlock;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BedPart;
import net.minecraft.world.phys.AABB;

/** Bounded restoration of a completely missing, originally paid village bed.
 * Adopted homes and ambiguous orphan halves are deliberately excluded.
 * Completed owner-linked expansions and paid second-bed reuse are retained. A recorded paid partial placement resumes without a
 * second debit; this is ordinary SavedData recovery, not crash-atomic storage.
 */
public final class VillageBedRepairService {
    public static final String TEMPLATE = "repair_village_bed_v1";
    private static final String HOME = "bed_repair_home";
    private static final String SOURCE = "bed_repair_source";
    private static final String INDEX = "bed_repair_index";
    private static final String PAID = "bed_repair_paid";
    private static final int CARGO = 8;
    private VillageBedRepairService() {}

    static boolean tryPlan(Villager worker, ServerLevel level, UUID villageId) {
        VillageSavedData data = VillageSavedData.get(level);
        var village = data.village(villageId).orElse(null);
        if (village == null || !"active".equals(village.lifecycle())) return false;
        for (var home : village.buildingIds().stream().sorted(Comparator.comparing(UUID::toString))
                .limit(24).map(data::building).flatMap(java.util.Optional::stream).toList()) {
            if (!home.villageBuilt() || !home.villageId().equals(villageId)
                    || !supported(home.templateId()) || !"residential".equals(home.classification())
                    || home.min().distManhattan(worker.blockPosition()) > 72
                    || !VillageSimulationScheduler.isAreaLoaded(level, home.min(), home.max())
                    || busy(data, home, null)) continue;
            for (var source : authoritativeSources(data, home)) {
                List<VillageSimulationEvents.BuildStep> plan = bedBlueprint(source);
                if (plan.size() > 512) continue;
                for (int i = 0; i < plan.size(); i++) {
                    var step = plan.get(i);
                    if (!bedFoot(step.state()) || !inside(home, step.pos()) || retiredBed(home, step.pos())) continue;
                    BlockPos head = step.pos().relative(step.state().getValue(BedBlock.FACING));
                    if (!inside(home, head) || !VillageSimulationScheduler.tryConsumeBlockProbe(level)) break;
                    if (!level.getBlockState(step.pos()).isAir() || !level.getBlockState(head).isAir()
                            || !safe(level, home, step.pos(), head)) continue;
                    var repair = data.createProject(villageId, "building", 86, step.pos());
                    repair.setTemplateId(TEMPLATE);
                    repair.setLeadCarpenterId(worker.getUUID());
                    repair.setAnchor(home.min());
                    repair.setParameter(HOME, home.id().toString());
                    repair.setParameter(SOURCE, source.id().toString());
                    repair.setParameter(INDEX, Integer.toString(i));
                    repair.setParameter("bed_repair_head", Long.toString(head.asLong()));
                    repair.setPhase("bed_repair");
                    repair.setReservation(VillageStorageService.itemKey(Items.WHITE_BED), 1);
                    data.touch();
                    return true;
                }
            }
        }
        return false;
    }

    static void advance(Villager worker, ServerLevel level, VillageSavedData.ProjectRecord repair) {
        if ("complete".equals(repair.phase()) || "cancelled".equals(repair.phase())) return;
        VillageSavedData data = VillageSavedData.get(level);
        var home = data.building(id(repair.parameter(HOME))).orElse(null);
        var source = data.project(id(repair.parameter(SOURCE))).orElse(null);
        if (home == null || source == null || !home.villageBuilt() || !supported(home.templateId())
                || !home.villageId().equals(repair.villageId()) || !authoritativeSources(data, home).stream().anyMatch(p -> p.id().equals(source.id()))) {
            stop(data, repair, "original village bed blueprint unavailable", true); return;
        }
        if (!VillageSimulationScheduler.isAreaLoaded(level, home.min(), home.max())
                || busy(data, home, repair.id())) {
            stop(data, repair, "bed repair waits for loaded idle home", false); return;
        }
        List<VillageSimulationEvents.BuildStep> plan = bedBlueprint(source);
        int index;
        try { index = Integer.parseInt(repair.parameter(INDEX)); }
        catch (NumberFormatException e) { index = -1; }
        if (index < 0 || index >= plan.size() || plan.size() > 512
                || !bedFoot(plan.get(index).state()) || !plan.get(index).pos().equals(repair.site()) || retiredBed(home, repair.site())) {
            stop(data, repair, "invalid original bed anchor", true); return;
        }
        BlockPos foot = repair.site();
        BlockState expectedFoot = plan.get(index).state();
        BlockPos head = foot.relative(expectedFoot.getValue(BedBlock.FACING));
        BlockState expectedHead = expectedFoot.setValue(BedBlock.PART, BedPart.HEAD);
        if (!inside(home, foot) || !inside(home, head)) {
            stop(data, repair, "bed anchor outside original home", true); return;
        }
        boolean footMatches = matches(level.getBlockState(foot), expectedFoot);
        boolean headMatches = matches(level.getBlockState(head), expectedHead);
        if (footMatches && headMatches) { finish(data, level, home, repair); return; }
        boolean paid = Boolean.parseBoolean(repair.parameter(PAID));
        String observed = repair.parameter("bed_repair_observed_parts");
        if (paid && (Boolean.parseBoolean(repair.parameter("bed_repair_external_edit"))
                || observed.contains("F") && !footMatches || observed.contains("H") && !headMatches)) {
            stop(data, repair, "paid bed half was externally removed; entitlement revoked", true); return;
        }
        boolean footAir = level.getBlockState(foot).isAir();
        boolean headAir = level.getBlockState(head).isAir();
        if ((!footAir && !(paid && footMatches)) || (!headAir && !(paid && headMatches))) {
            stop(data, repair, "player-edited or unpaid partial bed preserved", true); return;
        }
        if (!safe(level, home, foot, head) || !level.getEntitiesOfClass(LivingEntity.class,
                new AABB(foot).minmax(new AABB(head)), LivingEntity::isAlive).isEmpty()) {
            stop(data, repair, "bed repair space unsafe or occupied", false); return;
        }
        if (!paid && !VillageCarpenterCraftingService.ensureWhiteBed(worker, level,
                VillageBridgeService.plank(wood(source)), CARGO)) {
            stop(data, repair, "stage actual bed at recognized storage", false); return;
        }
        if (worker.distanceToSqr(foot.getCenter()) > 49.0D) {
            worker.getNavigation().moveTo(foot.getX() + 0.5, foot.getY(), foot.getZ() + 0.5, 0.75);
            stop(data, repair, "carrying paid bed to damaged home", false); return;
        }
        if (!paid) {
            if (!VillagerSimData.takeWorkCargo(worker, level.registryAccess(), CARGO, Items.WHITE_BED, 1)) {
                stop(data, repair, "physical bed missing from cargo", false); return;
            }
            repair.setParameter(PAID, "true");
            data.touch();
        }
        if (footAir) level.setBlock(foot, expectedFoot, Block.UPDATE_CLIENTS);
        if (headAir) level.setBlock(head, expectedHead, Block.UPDATE_CLIENTS);
        boolean placedFoot = matches(level.getBlockState(foot), expectedFoot);
        boolean placedHead = matches(level.getBlockState(head), expectedHead);
        repair.setParameter("bed_repair_observed_parts", (placedFoot ? "F" : "") + (placedHead ? "H" : ""));
        data.touch();
        // Never notify an incomplete pair: vanilla may break the survivor and
        // drop a whole Bed, which must not leave a free replacement entitlement.
        if (placedFoot && placedHead) {
            level.updateNeighborsAt(foot, Blocks.WHITE_BED);
            level.updateNeighborsAt(head, Blocks.WHITE_BED);
            if (matches(level.getBlockState(foot), expectedFoot) && matches(level.getBlockState(head), expectedHead))
                finish(data, level, home, repair);
            else stop(data, repair, "paid bed changed during neighbor update; no free replacement", true);
        } else stop(data, repair, "paid bed partial; retry without another debit", false);
    }

    static void playerEdited(ServerLevel level, BlockPos pos) {
        var data = VillageSavedData.get(level);
        var chunk = new ChunkPos(pos);
        java.util.Set<UUID> ids = new java.util.HashSet<>();
        for (int x = -1; x <= 1; x++) for (int z = -1; z <= 1; z++)
            ids.addAll(data.recordsForChunk(new ChunkPos(chunk.x + x, chunk.z + z)).projectIds());
        for (UUID id : ids) {
            var p = data.project(id).orElse(null);
            if (p == null || !TEMPLATE.equals(p.templateId()) || "complete".equals(p.phase())
                    || "cancelled".equals(p.phase()) || !Boolean.parseBoolean(p.parameter(PAID))) continue;
            if (pos.equals(p.site()) || Long.toString(pos.asLong()).equals(p.parameter("bed_repair_head"))) {
                p.setParameter("bed_repair_external_edit", "true"); data.touch();
            }
        }
    }

    private static boolean safe(ServerLevel level, VillageSavedData.BuildingRecord home,
                                BlockPos foot, BlockPos head) {
        java.util.Set<Long> reachable = VillageBuildingService.reachableTemplateGround(level, home.min());
        if (reachable.isEmpty()) return false;
        for (BlockPos p : new BlockPos[]{foot, head})
            if (!level.getFluidState(p).isEmpty() || !level.getBlockState(p.above()).isAir()
                    || !level.getBlockState(p.below()).isFaceSturdy(level, p.below(), Direction.UP)
                    || level.canSeeSky(p)) return false;
        int floors = (foot.getY() - home.min().getY() - 1) / 4;
        if (floors > 0 && !VillageBuildingService.connectedUpperStories(level, home.min(), floors)) return false;
        for (BlockPos anchor : new BlockPos[]{foot, head}) for (Direction direction : Direction.Plane.HORIZONTAL) {
            BlockPos standing = anchor.relative(direction);
            if (standing.equals(foot) || standing.equals(head) || !inside(home, standing)) continue;
            if (level.getBlockState(standing).isAir() && level.getBlockState(standing.above()).isAir()
                    && level.getBlockState(standing.below()).isFaceSturdy(level, standing.below(), Direction.UP)
                    && (floors > 0 || reachable.contains(standing.asLong()))) return true;
        }
        return false;
    }

    private static boolean busy(VillageSavedData data, VillageSavedData.BuildingRecord home, UUID self) {
        return data.activeProjectsForVillage(home.villageId()).stream().anyMatch(p -> !p.id().equals(self)
                && "building".equals(p.type()) && (inside(home, p.site())
                || p.anchor() != null && inside(home, p.anchor())));
    }
    /** Follow only completed, owner-linked ancestry, not nominal newer templates. */
    private static List<VillageSavedData.ProjectRecord> authoritativeSources(
            VillageSavedData data, VillageSavedData.BuildingRecord home) {
        var village = data.village(home.villageId()).orElse(null);
        if (village == null) return List.of();
        var roots = village.projectIds().stream().map(data::project).flatMap(java.util.Optional::stream)
                .filter(p -> basicSource(home, p) && (home.templateId().equals(p.templateId())
                    || "house_2story_5x5".equals(home.templateId())
                        && VillageHouseVerticalExpansionService.TEMPLATE.equals(p.templateId())
                        && home.id().toString().equals(p.parameter("expand_building"))
                    || "house_3story_5x5".equals(home.templateId())
                        && VillageHouseThirdFloorExpansionService.TEMPLATE.equals(p.templateId())
                        && home.id().toString().equals(p.parameter("third_building"))))
                .sorted(Comparator.comparing(p -> p.id().toString())).toList();
        if (roots.isEmpty()) return List.of();
        if ("true".equals(roots.getFirst().parameter("circulation_verified_v2")))
            return List.of(roots.getFirst());
        var result = new java.util.ArrayList<VillageSavedData.ProjectRecord>();
        var cursor = roots.getFirst();
        for (int depth = 0; depth < 3; depth++) {
            if (!basicSource(home, cursor)) return List.of();
            result.add(cursor);
            String parent;
            String expected;
            if (VillageHouseThirdFloorExpansionService.TEMPLATE.equals(cursor.templateId())) {
                if (!home.id().toString().equals(cursor.parameter("third_building"))) return List.of();
                parent = cursor.parameter("third_source"); expected = "second";
            } else if (VillageHouseVerticalExpansionService.TEMPLATE.equals(cursor.templateId())) {
                if (!home.id().toString().equals(cursor.parameter("expand_building"))) return List.of();
                parent = cursor.parameter("expand_original"); expected = "first";
            } else break;
            cursor = data.project(id(parent)).orElse(null);
            if (cursor == null || "first".equals(expected) && !"house_5x5".equals(cursor.templateId())
                    || "second".equals(expected) && !"house_2story_5x5".equals(cursor.templateId())
                        && !VillageHouseVerticalExpansionService.TEMPLATE.equals(cursor.templateId())) return List.of();
        }
        java.util.Set<UUID> originalIds = result.stream().map(VillageSavedData.ProjectRecord::id)
                .collect(java.util.stream.Collectors.toSet());
        village.projectIds().stream().map(data::project).flatMap(java.util.Optional::stream)
                .filter(p -> VillageHouseReuseService.TEMPLATE.equals(p.templateId())
                    && "complete".equals(p.phase()) && "building".equals(p.type())
                    && p.villageId().equals(home.villageId())
                    && p.site().equals(home.min().offset(1, 1, 2))
                    && home.id().toString().equals(p.parameter("reuse_building"))
                    && originalIds.contains(id(p.parameter("reuse_original_project"))))
                .sorted(Comparator.comparing(p -> p.id().toString())).limit(1).forEach(result::add);
        return List.copyOf(result);
    }
    private static boolean basicSource(VillageSavedData.BuildingRecord b, VillageSavedData.ProjectRecord p) {
        return "building".equals(p.type()) && "complete".equals(p.phase())
                && b.villageId().equals(p.villageId()) && b.min().equals(p.site());
    }
    private static List<VillageSimulationEvents.BuildStep> bedBlueprint(VillageSavedData.ProjectRecord source) {
        if ("true".equals(source.parameter("circulation_verified_v2"))) {
            boolean third = "house_3story_5x5".equals(source.templateId())
                    || VillageHouseThirdFloorExpansionService.TEMPLATE.equals(source.templateId());
            var beds = new java.util.ArrayList<VillageSimulationEvents.BuildStep>();
            BlockPos base = source.site();
            addExpectedBed(beds, base.offset(1, 1, 3), Direction.EAST);
            if (third) {
                addExpectedBed(beds, base.offset(2, 5, 3), Direction.WEST);
                addExpectedBed(beds, base.offset(1, 9, 2), Direction.NORTH);
                addExpectedBed(beds, base.offset(2, 9, 3), Direction.WEST);
            } else {
                addExpectedBed(beds, base.offset(1, 5, 2), Direction.NORTH);
                addExpectedBed(beds, base.offset(2, 5, 3), Direction.WEST);
            }
            return List.copyOf(beds);
        }
        if (VillageHouseVerticalExpansionService.TEMPLATE.equals(source.templateId()))
            return VillageHouseVerticalExpansionService.steps(source).stream().filter(s -> s.bed())
                    .map(s -> new VillageSimulationEvents.BuildStep(s.pos(), s.state(), Items.WHITE_BED)).toList();
        if (VillageHouseThirdFloorExpansionService.TEMPLATE.equals(source.templateId()))
            return VillageHouseThirdFloorExpansionService.steps(source).stream()
                    .filter(s -> s.kind() == VillageHouseThirdFloorExpansionService.PLACE_BED)
                    .map(s -> new VillageSimulationEvents.BuildStep(s.pos(), s.state(), Items.WHITE_BED)).toList();
        if (VillageHouseReuseService.TEMPLATE.equals(source.templateId()))
            return List.of(new VillageSimulationEvents.BuildStep(source.site(), Blocks.WHITE_BED.defaultBlockState()
                    .setValue(BedBlock.PART, BedPart.FOOT).setValue(BedBlock.FACING, Direction.SOUTH), Items.WHITE_BED));
        return VillageSimulationEvents.projectPlan(source).stream().filter(s -> bedFoot(s.state())).toList();
    }
    private static void addExpectedBed(List<VillageSimulationEvents.BuildStep> result, BlockPos foot, Direction facing) {
        result.add(new VillageSimulationEvents.BuildStep(foot, Blocks.WHITE_BED.defaultBlockState()
                .setValue(BedBlock.PART, BedPart.FOOT).setValue(BedBlock.FACING, facing), Items.WHITE_BED));
    }
    private static boolean retiredBed(VillageSavedData.BuildingRecord home, BlockPos pos) {
        return "house_3story_5x5".equals(home.templateId()) && pos.equals(home.min().offset(2, 5, 1));
    }
    private static String wood(VillageSavedData.ProjectRecord source) {
        if (VillageHouseVerticalExpansionService.TEMPLATE.equals(source.templateId())) return source.parameter("expand_plank");
        if (VillageHouseThirdFloorExpansionService.TEMPLATE.equals(source.templateId())) return source.parameter("third_plank");
        if (VillageHouseReuseService.TEMPLATE.equals(source.templateId())) return source.parameter("reuse_wood");
        return source.parameter("plank");
    }
    private static boolean supported(String template) {
        return List.of("house_5x5", "house_gabled_5x5", "house_2story_5x5", "house_3story_5x5").contains(template);
    }
    private static boolean inside(VillageSavedData.BuildingRecord home, BlockPos p) {
        return p.getX() >= home.min().getX() && p.getX() <= home.max().getX()
                && p.getY() >= home.min().getY() && p.getY() <= home.max().getY()
                && p.getZ() >= home.min().getZ() && p.getZ() <= home.max().getZ();
    }
    private static boolean bedFoot(BlockState s) {
        return s.is(Blocks.WHITE_BED) && s.getValue(BedBlock.PART) == BedPart.FOOT;
    }
    private static boolean matches(BlockState actual, BlockState expected) {
        return actual.is(Blocks.WHITE_BED) && actual.getValue(BedBlock.PART) == expected.getValue(BedBlock.PART)
                && actual.getValue(BedBlock.FACING) == expected.getValue(BedBlock.FACING);
    }
    private static UUID id(String s) {
        try { return UUID.fromString(s); } catch (IllegalArgumentException | NullPointerException e) { return new UUID(0, 0); }
    }
    private static void finish(VillageSavedData data, ServerLevel level,
                               VillageSavedData.BuildingRecord home, VillageSavedData.ProjectRecord repair) {
        repair.clearReservations(); repair.setWorkCursor(1); repair.setPhase("complete"); repair.setPausedReason("");
        data.touch();
        VillageSimulationScheduler.enqueueValidation(level, "bed_repair:" + home.id(),
                () -> VillageBuildingService.revalidateChunk(level, new ChunkPos(home.min())));
    }
    private static void stop(VillageSavedData data, VillageSavedData.ProjectRecord repair, String why, boolean cancel) {
        if (cancel) { repair.clearReservations(); repair.setPhase("cancelled"); }
        repair.setPausedReason(why); data.touch();
    }
}
