package io.github.akakishi04.asobibatweaks.feature;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.phys.AABB;

/** Temporary supported exterior stairs for the bounded 5x5 vertical templates.
 * Blocks are bought, placed and recovered one physical action at a time. The
 * project retains ownership across ordinary save/reload; player edit events
 * permanently revoke that cell's ownership, even if the replacement looks equal.
 * This is not an atomic transaction across separate world/inventory save files.
 */
public final class VillageConstructionAccessService {
    private static final String HEIGHT = "access_ramp_height";
    private static final String WOOD = "access_ramp_wood";
    private static final String CURSOR = "access_ramp_placed";
    private static final String CLEAN = "access_ramp_clean_cursor";
    private static final String REVOKED = "access_ramp_revoked";
    private static final int CARGO = 8;
    private VillageConstructionAccessService() {}

    /** Invoked only while the original construction target is out of reach. */
    static void approach(Villager worker, ServerLevel level,
                         VillageSavedData.ProjectRecord project, BlockPos target) {
        int height = number(project.parameter(HEIGHT), 0);
        if (height == 0) {
            height = supportedHeight(project);
            if (height == 0 || target.getY() < project.site().getY() + 5) {
                navigate(worker, target); return;
            }
            if (!initialize(level, project, height)) {
                // Preserve the original vanilla navigation option where the
                // existing internal stairs work but exterior land is unsuitable.
                navigate(worker, target);
                pause(level, project, "existing route requested; temporary access site unavailable"); return;
            }
        }
        List<Step> plan = steps(project);
        if (plan.isEmpty()) { pause(level, project, "invalid saved access geometry"); return; }
        int placed = number(project.parameter(CURSOR), 0);
        if (placed < 0 || placed > plan.size()) { pause(level, project, "invalid saved access cursor"); return; }
        if (!validateOwned(level, project, plan, placed)) return;
        if (placed < plan.size()) {
            Step step = plan.get(placed);
            if (!level.getBlockState(step.pos()).isAir() || !level.getFluidState(step.pos()).isEmpty()) {
                pause(level, project, "temporary access target edited; preserved"); return;
            }
            Block timber = VillageBridgeService.plank(project.parameter(WOOD));
            boolean supplied = step.stair()
                    ? VillageCarpenterCraftingService.ensureFixture(worker, level, step.state().getBlock().asItem(), timber, CARGO)
                    : VillageSimulationEvents.ensureCargoItem(worker, level, timber.asItem(), 1, CARGO);
            if (!supplied) { pause(level, project, "temporary access awaits actual stair/plank items"); return; }
            if (worker.distanceToSqr(step.pos().getCenter()) > 49.0D) {
                navigate(worker, previousStanding(project, step.column()));
                pause(level, project, "carrying actual access materials up supported stairs"); return;
            }
            if (!level.getEntitiesOfClass(LivingEntity.class, new AABB(step.pos()), LivingEntity::isAlive).isEmpty()) {
                pause(level, project, "temporary access placement occupied"); return;
            }
            if (!VillagerSimData.takeWorkCargo(worker, level.registryAccess(), CARGO, step.state().getBlock().asItem(), 1)) return;
            if (!level.setBlock(step.pos(), step.state(), Block.UPDATE_ALL)) {
                recover(worker, level, new ItemStack(step.state().getBlock()));
                pause(level, project, "access placement rejected; same item refunded"); return;
            }
            project.setParameter(CURSOR, Integer.toString(placed + 1));
            pause(level, project, "building temporary supported stairs");
            return;
        }
        BlockPos standing = project.site().offset(5, height + 1, 2);
        if (!level.getBlockState(standing).isAir() || !level.getBlockState(standing.above()).isAir()) {
            pause(level, project, "temporary upper work position obstructed"); return;
        }
        navigate(worker, standing);
        pause(level, project, "walking to real upper construction access");
    }

    /** Return true only when all owned aid blocks have been physically recovered. */
    static boolean cleanup(Villager worker, ServerLevel level, VillageSavedData.ProjectRecord project) {
        if (project.parameter(HEIGHT).isBlank()) return true;
        List<Step> plan = steps(project);
        if (plan.isEmpty()) { pause(level, project, "invalid saved access cleanup geometry"); return false; }
        int placed = number(project.parameter(CURSOR), -1);
        int cursor = number(project.parameter(CLEAN), placed - 1);
        if (placed < 0 || placed > plan.size() || cursor >= placed) {
            pause(level, project, "invalid saved access cleanup cursor"); return false;
        }
        if (cursor < 0) return true;
        Step step = plan.get(cursor);
        if (!VillageSimulationScheduler.isAreaLoaded(level, step.pos().below(), step.pos().above(2))) {
            pause(level, project, "temporary access cleanup chunk unloaded"); return false;
        }
        Set<Integer> revoked = revoked(project);
        BlockState actual = level.getBlockState(step.pos());
        if (actual.isAir()) {
            project.setParameter(CLEAN, Integer.toString(cursor - 1));
            pause(level, project, "missing aid block yields no invented refund"); return false;
        }
        if (revoked.contains(cursor) || !actual.equals(step.state())) {
            pause(level, project, "player-edited temporary aid preserved; clear it before cleanup"); return false;
        }
        if (!level.getBlockState(step.pos().above()).isAir() || foreignAttachment(level, step.pos(), plan)) {
            pause(level, project, "foreign block above temporary support; preserved"); return false;
        }
        if (!level.getEntitiesOfClass(LivingEntity.class,
                new AABB(step.pos()).expandTowards(0, 2, 0), LivingEntity::isAlive).isEmpty()) {
            navigate(worker, previousStanding(project, step.column()));
            pause(level, project, "vacate temporary support before recovering it"); return false;
        }
        if (worker.distanceToSqr(step.pos().getCenter()) > 49.0D) {
            navigate(worker, previousStanding(project, step.column()));
            pause(level, project, "walking down temporary construction access"); return false;
        }
        if (!level.setBlock(step.pos(), Blocks.AIR.defaultBlockState(), Block.UPDATE_ALL)) {
            pause(level, project, "temporary support removal rejected"); return false;
        }
        // No drop plus refund combination: successful removal produces exactly
        // this single original physical item, in cargo or as an actual drop.
        recover(worker, level, new ItemStack(step.state().getBlock()));
        project.setParameter(CLEAN, Integer.toString(cursor - 1));
        pause(level, project, "recovering actual temporary stair materials");
        return false;
    }

    private static boolean foreignAttachment(ServerLevel level, BlockPos pos, List<Step> plan) {
        for (Direction direction : Direction.Plane.HORIZONTAL) {
            BlockPos neighbor = pos.relative(direction);
            if (!VillageSimulationScheduler.isChunkLoaded(level, neighbor)) return true;
            BlockState state = level.getBlockState(neighbor);
            if (state.isAir() || state.isSolidRender(level, neighbor)) continue;
            if (plan.stream().noneMatch(s -> s.pos().equals(neighbor) && s.state().equals(state))) return true;
        }
        return false;
    }

    private static boolean initialize(ServerLevel level, VillageSavedData.ProjectRecord project, int height) {
        String wood = project.parameter("plank");
        if (VillageHouseVerticalExpansionService.TEMPLATE.equals(project.templateId())) wood = project.parameter("expand_plank");
        if (VillageHouseThirdFloorExpansionService.TEMPLATE.equals(project.templateId())) wood = project.parameter("third_plank");
        BlockPos base = project.site();
        BlockPos first = base.offset(5, 0, 3 - height);
        BlockPos last = base.offset(5, height + 2, 2);
        if (!VillageSimulationScheduler.isAreaLoaded(level, first.offset(0, -1, -1), last)) return false;
        for (int column = 0; column <= height; column++) {
            BlockPos ground = base.offset(5, 0, 2 - height + column);
            BlockState surface = level.getBlockState(ground);
            if (!natural(surface) || !level.getBlockState(ground.below()).isFaceSturdy(level, ground.below(), Direction.UP)) return false;
            for (int y = 1; y <= height + 2; y++) {
                if (!VillageSimulationScheduler.tryConsumeWorkerProbe(level)) return false;
                BlockPos pos = ground.above(y);
                if (!level.getBlockState(pos).isAir() || !level.getFluidState(pos).isEmpty()) return false;
            }
        }
        project.setParameter(HEIGHT, Integer.toString(height)); project.setParameter(WOOD, wood);
        project.setParameter(CURSOR, "0"); project.setParameter(CLEAN, ""); project.setParameter(REVOKED, "");
        VillageSavedData.get(level).touch(); return true;
    }

    static List<Step> steps(VillageSavedData.ProjectRecord project) {
        int height = number(project.parameter(HEIGHT), 0);
        if (height != 4 && height != 8) return List.of();
        Block timber = VillageBridgeService.plank(project.parameter(WOOD));
        BlockState stair = VillageSimulationEvents.stairsForPlank(timber).defaultBlockState()
                .setValue(BlockStateProperties.HORIZONTAL_FACING, Direction.SOUTH);
        List<Step> result = new ArrayList<>();
        for (int column = 1; column <= height; column++) {
            BlockPos ground = project.site().offset(5, 0, 2 - height + column);
            for (int y = 1; y < column; y++) result.add(new Step(ground.above(y), timber.defaultBlockState(), column, false));
            result.add(new Step(ground.above(column), stair, column, true));
        }
        return List.copyOf(result);
    }

    private static boolean validateOwned(ServerLevel level, VillageSavedData.ProjectRecord project, List<Step> plan, int placed) {
        Set<Integer> revoked = revoked(project);
        for (int i = 0; i < placed; i++) {
            Step step = plan.get(i);
            if (!VillageSimulationScheduler.isChunkLoaded(level, step.pos())
                    || !VillageSimulationScheduler.tryConsumeWorkerProbe(level)
                    || revoked.contains(i) || !level.getBlockState(step.pos()).equals(step.state())) {
                pause(level, project, "temporary access changed or unloaded; construction paused"); return false;
            }
        }
        for (int i = placed; i < plan.size(); i++) {
            BlockPos pos = plan.get(i).pos();
            if (!VillageSimulationScheduler.isChunkLoaded(level, pos)
                    || !VillageSimulationScheduler.tryConsumeWorkerProbe(level)
                    || !level.getBlockState(pos).isAir() || !level.getFluidState(pos).isEmpty()) {
                pause(level, project, "future temporary access cell edited; preserved"); return false;
            }
        }
        // A saved plan never authorizes changed foundations or blocked headroom.
        for (int column = 0; column <= number(project.parameter(HEIGHT), 0); column++) {
            BlockPos ground = project.site().offset(5, 0, 2 - number(project.parameter(HEIGHT), 0) + column);
            BlockPos standing = ground.above(column + 1);
            if (!VillageSimulationScheduler.isChunkLoaded(level, ground)
                    || !VillageSimulationScheduler.tryConsumeWorkerProbe(level)
                    || !level.getBlockState(ground).isFaceSturdy(level, ground, Direction.UP)
                    || !level.getBlockState(standing).isAir() || !level.getBlockState(standing.above()).isAir()) {
                pause(level, project, "temporary ramp foundation changed"); return false;
            }
        }
        return true;
    }

    /** Called from real block-edit events; neighboring indexed projects suffice
     * because this fixed ramp lies at most 8 blocks from its project site. */
    static void playerEdited(ServerLevel level, BlockPos pos) {
        VillageSavedData data = VillageSavedData.get(level);
        Set<UUID> projects = new HashSet<>(); ChunkPos chunk = new ChunkPos(pos);
        for (int x = -1; x <= 1; x++) for (int z = -1; z <= 1; z++)
            projects.addAll(data.recordsForChunk(new ChunkPos(chunk.x + x, chunk.z + z)).projectIds());
        for (UUID id : projects) {
            var project = data.project(id).orElse(null);
            if (project == null || project.parameter(HEIGHT).isBlank()) continue;
            List<Step> plan = steps(project); int placed = number(project.parameter(CURSOR), 0);
            for (int i = 0; i < Math.min(placed, plan.size()); i++) if (plan.get(i).pos().equals(pos)) {
                Set<Integer> revoked = revoked(project); revoked.add(i);
                project.setParameter(REVOKED, revoked.stream().sorted().map(String::valueOf)
                        .collect(java.util.stream.Collectors.joining(",")));
                data.touch(); break;
            }
        }
    }

    private static Set<Integer> revoked(VillageSavedData.ProjectRecord p) {
        Set<Integer> result = new HashSet<>();
        for (String s : p.parameter(REVOKED).split(",")) { int i = number(s, -1); if (i >= 0 && i < 36) result.add(i); }
        return result;
    }
    private static int supportedHeight(VillageSavedData.ProjectRecord p) {
        return switch (p.templateId()) {
            case "house_2story_5x5" -> 4;
            case "house_3story_5x5" -> 8;
            default -> VillageHouseVerticalExpansionService.TEMPLATE.equals(p.templateId()) ? 4
                    : VillageHouseThirdFloorExpansionService.TEMPLATE.equals(p.templateId()) ? 8 : 0;
        };
    }
    private static boolean natural(BlockState s) {
        return s.is(Blocks.GRASS_BLOCK) || s.is(Blocks.DIRT) || s.is(Blocks.COARSE_DIRT)
                || s.is(Blocks.STONE) || s.is(Blocks.DEEPSLATE);
    }
    private static BlockPos previousStanding(VillageSavedData.ProjectRecord p, int column) {
        int height = number(p.parameter(HEIGHT), 0);
        return p.site().offset(5, Math.max(1, column), 2 - height + Math.max(0, column - 1));
    }
    private static void navigate(Villager v, BlockPos pos) { v.getNavigation().moveTo(pos.getX() + 0.5, pos.getY(), pos.getZ() + 0.5, 0.75); }
    private static void recover(Villager v, ServerLevel level, ItemStack stack) {
        ItemStack remaining = VillagerSimData.insertWorkCargo(v, level.registryAccess(), stack, CARGO);
        if (!remaining.isEmpty()) v.spawnAtLocation(remaining);
    }
    private static int number(String s, int fallback) { try { return Integer.parseInt(s); } catch (NumberFormatException e) { return fallback; } }
    private static void pause(ServerLevel level, VillageSavedData.ProjectRecord p, String reason) {
        p.setPausedReason(reason); VillageSavedData.get(level).touch();
    }
    static record Step(BlockPos pos, BlockState state, int column, boolean stair) {}
}
