package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.FluidTags;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.entity.ChestBlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.structure.StructureStart;
import net.minecraft.world.level.levelgen.structure.pieces.PiecesContainer;
import net.minecraft.world.level.levelgen.structure.structures.SwampHutPiece;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.phys.Vec3;
import net.neoforged.neoforge.event.level.ChunkEvent;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/**
 * The real carving loop writes loaded LevelChunks inside reserved GameTest structures.
 * Seeded geometry is translated, never resized, into finite, controlled terrain slabs.
 * These prove physical carving/navigation and protection, not natural-world river frequency.
 */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class ContinentalRiverPhysicalGameTests {
    private static final long SEED = 918273645L;
    private ContinentalRiverPhysicalGameTests() {}

    @GameTest(template = "empty80x144x48", batch = "river_physical", skyAccess = true)
    public static void seededCarvingCreatesNavigableSeamsAndARealTerminalLake(GameTestHelper helper) {
        Fixture fixture = new Fixture(helper, 64, 32);
        var model = drainage(fixture.sea);
        var reach = lowlandReach(model);
        List<ContinentalRiverGenerator.DrainageCell> cells = List.of(centerReach(reach, fixture));

        fixture.fillHighTerrain();
        var untouched = fixture.snapshot();
        fixture.carve(cells, false);
        assertPhysicalChannel(fixture, cells, untouched);
        assertNavigableCrossing(fixture, cells);
        var forward = fixture.snapshot();

        // Rebuild identical actual blocks, then visit the same chunks in reverse.
        // Every block (including sediment and both sides of all seams) must agree.
        fixture.fillHighTerrain();
        fixture.carve(cells, true);
        fixture.assertSnapshot(forward, "Reversed chunk order changed physical river blocks");
        assertNavigableCrossing(fixture, cells);

        // A real receiving terminal with an actual incoming seeded reach. The
        // lake crosses x/z chunk seams; incoming higher grades cannot stripe it.
        var sink = receivingSink(model);
        var incoming = incomingReach(model, sink);
        int dx = fixture.x + 32 - sink.x();
        int dz = fixture.z + 16 - sink.z();
        var lake = translate(sink, dx, dz);
        var inflow = translate(incoming, dx, dz);
        List<ContinentalRiverGenerator.DrainageCell> basin = List.of(inflow, lake);
        fixture.fillHighTerrain();
        fixture.carve(basin, true);
        int lakeColumns = 0;
        int sharedFootprint = 0;
        for (int x = fixture.x; x < fixture.x + fixture.width; x++) {
            for (int z = fixture.z; z < fixture.z + fixture.length; z++) {
                if (Math.hypot(x - lake.x(), z - lake.z()) > lake.lakeRadius()) continue;
                lakeColumns++;
                BlockPos surface = new BlockPos(x, lake.sourceY(), z);
                assertSource(helper, surface);
                helper.assertTrue(fixture.level.getBlockState(surface.above()).isAir(),
                        "Incoming reach raised the physical terminal lake plane at " + surface);
                helper.assertTrue(fixture.level.getBlockState(surface.above(2)).isAir(),
                        "Terminal basin retained solid overhead terrain at " + surface);
                var incomingOnly = ContinentalRiverGenerator.sampleAt(x, z, List.of(inflow));
                if (incomingOnly.active() && incomingOnly.surface() > lake.sourceY()) sharedFootprint++;
            }
        }
        helper.assertTrue(lakeColumns >= 100 && sharedFootprint >= 10,
                "Seeded basin fixture must exercise a substantial lake/inflow overlap");
        helper.assertTrue(lake.x() % 16 == 0 && lake.z() % 16 == 0,
                "Receiving basin must straddle four real loaded chunks");
        assertSource(helper, new BlockPos(inflow.downX(), inflow.destinationY(), inflow.downZ()));
        helper.succeed();
    }

    @GameTest(template = "empty32x144x32", batch = "river_physical", skyAccess = true)
    public static void loweredTerrainAndNativeChunkGuardsPreventPhysicalDamage(GameTestHelper helper) {
        Fixture fixture = new Fixture(helper, 16, 16);
        var reach = centerReach(lowlandReach(drainage(fixture.sea)), fixture);
        var cells = List.of(reach);
        LevelChunk chunk = fixture.chunks.getFirst();
        fixture.fillHighTerrain();
        BlockPos active = nearestCenter(fixture, cells, fixture.x + 8);

        // Native structure starts/references and old chunk loads must return
        // before touching either blocks, chest contents, or the chunk dirty flag.
        assertNativeChunkGuards(fixture, active);
        fixture.fillHighTerrain();

        // Reproduce the continental-ocean -> river pipeline on a LevelChunk:
        // WG has already been primed when an earlier pass lowers this column.
        // LevelChunk updates WORLD_SURFACE, but never WORLD_SURFACE_WG.
        Heightmap.primeHeightmaps(chunk, EnumSet.of(Heightmap.Types.WORLD_SURFACE_WG));
        int oldTop = chunk.getHeight(Heightmap.Types.WORLD_SURFACE_WG, active.getX(), active.getZ());
        for (int x = fixture.x; x < fixture.x + 16; x++) {
            int lowTop = switch (Math.floorMod(x - fixture.x, 3)) {
                case 0 -> fixture.sea - 4; // Below the proposed channel and sea.
                case 1 -> reach.sourceY(); // Exactly at its water plane.
                default -> fixture.highTop(x, active.getZ()); // Positive control.
            };
            for (int z = fixture.z; z < fixture.z + 16; z++) {
                if (Math.floorMod(x - fixture.x, 3) == 2) continue;
                for (int y = lowTop + 1; y <= fixture.cap; y++) {
                    chunk.setBlockState(new BlockPos(x, y, z), Blocks.AIR.defaultBlockState(), false);
                }
            }
        }
        helper.assertTrue(oldTop > reach.sourceY(), "Initial high-terrain control was not high");
        var before = fixture.snapshot();
        fixture.carve(cells, false);
        int protectedColumns = 0;
        int carvedColumns = 0;
        for (int x = fixture.x; x < fixture.x + 16; x++) {
            for (int z = fixture.z; z < fixture.z + 16; z++) {
                var sample = ContinentalRiverGenerator.sampleAt(x, z, cells);
                if (!sample.active()) continue;
                if (Math.floorMod(x - fixture.x, 3) == 2) {
                    assertSource(helper, new BlockPos(x, sample.surface(), z));
                    carvedColumns++;
                } else {
                    protectedColumns++;
                    fixture.assertColumn(before, x, z,
                            "River used stale pre-ocean height and raised water over low terrain");
                }
            }
        }
        helper.assertTrue(protectedColumns >= 10 && carvedColumns >= 5,
                "Low-terrain regression needs both active protected and active carved columns");
        helper.succeed();
    }

    private static void assertNativeChunkGuards(Fixture fixture, BlockPos active) {
        var helper = fixture.helper;
        var chunk = fixture.chunks.getFirst();
        BlockPos chestPos = active.above(3);
        chunk.setBlockState(chestPos, Blocks.CHEST.defaultBlockState(), false);
        var chest = (ChestBlockEntity)fixture.level.getBlockEntity(chestPos);
        helper.assertTrue(chest != null, "Fixture chest needs a live block entity");
        chest.setItem(0, new ItemStack(Items.DIAMOND, 7));
        var before = fixture.snapshot();
        var originalStarts = new HashMap<>(chunk.getAllStarts());
        var originalReferences = new HashMap<>(chunk.getAllReferences());
        var structure = fixture.level.registryAccess().registryOrThrow(Registries.STRUCTURE)
                .get(ResourceLocation.withDefaultNamespace("swamp_hut"));
        helper.assertTrue(structure != null, "Vanilla swamp hut structure is required");
        boolean enabled = AsobibaTweaksConfig.CONTINENTAL_WORLDGEN_ENABLED.getAsBoolean();
        try {
            AsobibaTweaksConfig.CONTINENTAL_WORLDGEN_ENABLED.set(true);
            var handler = new ContinentalWorldgenEvents();
            var start = new StructureStart(structure, chunk.getPos(), 0,
                    new PiecesContainer(List.of(new SwampHutPiece(RandomSource.create(SEED),
                            fixture.x + 4, fixture.z + 4))));
            helper.assertTrue(start.isValid(), "Structure-start positive control must be valid");
            chunk.setAllStarts(Map.of(structure, start));
            chunk.setAllReferences(Map.of());
            chunk.setUnsaved(false);
            handler.onChunkLoad(new ChunkEvent.Load(chunk, true));
            assertUnchangedGuard(fixture, before, chestPos, "structure start");

            chunk.setAllStarts(Map.of());
            chunk.addReferenceForStructure(structure, chunk.getPos().toLong());
            chunk.setUnsaved(false);
            handler.onChunkLoad(new ChunkEvent.Load(chunk, true));
            assertUnchangedGuard(fixture, before, chestPos, "structure reference");

            chunk.setAllReferences(Map.of());
            chunk.setUnsaved(false);
            handler.onChunkLoad(new ChunkEvent.Load(chunk, false));
            assertUnchangedGuard(fixture, before, chestPos, "existing chunk");

            // Non-vacuous native entry check: the same unprotected new chunk
            // reaches the end of the enabled handler and is marked unsaved.
            handler.onChunkLoad(new ChunkEvent.Load(chunk, true));
            helper.assertTrue(chunk.isUnsaved(), "Enabled native new-chunk hook never ran");
        } finally {
            AsobibaTweaksConfig.CONTINENTAL_WORLDGEN_ENABLED.set(enabled);
            chunk.setAllStarts(originalStarts);
            chunk.setAllReferences(originalReferences);
            chunk.setUnsaved(true);
        }
    }

    private static void assertUnchangedGuard(Fixture fixture, BlockState[] before,
                                            BlockPos chestPos, String guard) {
        fixture.assertSnapshot(before, "Native " + guard + " guard changed actual terrain");
        var chest = fixture.level.getBlockEntity(chestPos);
        fixture.helper.assertTrue(chest instanceof ChestBlockEntity stored
                        && stored.getItem(0).is(Items.DIAMOND) && stored.getItem(0).getCount() == 7,
                "Native " + guard + " guard destroyed existing chest contents");
        fixture.helper.assertTrue(!fixture.chunks.getFirst().isUnsaved(),
                "Native " + guard + " guard allowed the generation pass to run");
    }

    private static void assertPhysicalChannel(Fixture fixture,
            List<ContinentalRiverGenerator.DrainageCell> cells, BlockState[] before) {
        int wet = 0;
        int deepCenters = 0;
        int untouched = 0;
        for (int x = fixture.x; x < fixture.x + fixture.width; x++) {
            for (int z = fixture.z; z < fixture.z + fixture.length; z++) {
                var sample = ContinentalRiverGenerator.sampleAt(x, z, cells);
                if (!sample.active()) {
                    fixture.assertColumn(before, x, z, "Carving escaped the physical channel footprint");
                    untouched++;
                    continue;
                }
                wet++;
                BlockPos surface = new BlockPos(x, sample.surface(), z);
                assertSource(fixture.helper, surface);
                for (int y = surface.getY() + 1; y <= fixture.highTop(x, z); y++) {
                    fixture.helper.assertTrue(fixture.level.getBlockState(new BlockPos(x, y, z)).isAir(),
                            "Real channel retained obstructing terrain above its water plane");
                }
                int depth = 0;
                while (depth <= 8 && fixture.level.getBlockState(surface.below(depth)).is(Blocks.WATER)) {
                    assertSource(fixture.helper, surface.below(depth));
                    depth++;
                }
                var bed = fixture.level.getBlockState(surface.below(depth));
                fixture.helper.assertTrue(depth >= 1 && depth <= 8
                                && (bed.is(Blocks.SAND) || bed.is(Blocks.GRAVEL) || bed.is(Blocks.CLAY)),
                        "Carved column must have bounded source-water depth and a sediment bed");
                fixture.helper.assertTrue(fixture.level.getBlockState(surface.below(depth + 1)).is(Blocks.STONE),
                        "River carving removed support beneath its sediment bed");
                if (sample.distance() <= 1.0D) {
                    fixture.helper.assertTrue(depth >= 3, "Mature lowland channel lost its real central depth");
                    deepCenters++;
                }
            }
        }
        fixture.helper.assertTrue(wet >= 200 && untouched >= 100 && deepCenters >= 50,
                "Physical channel fixture must include banks, deep centers, and substantial water");
    }

    private static void assertNavigableCrossing(Fixture fixture,
            List<ContinentalRiverGenerator.DrainageCell> cells) {
        BlockPos start = nearestCenter(fixture, cells, fixture.x + 3);
        BlockPos end = nearestCenter(fixture, cells, fixture.x + fixture.width - 4);
        var path = VillageRiverNavigationService.findLoadedPath(fixture.level, start, end);
        fixture.helper.assertTrue(path.size() >= 2 && path.getFirst().equals(start) && path.getLast().equals(end),
                "Production-carved 57-block lowland channel has no real loaded boat route");
        for (int i = 1; i < path.size(); i++) {
            BlockPos from = path.get(i - 1);
            BlockPos to = path.get(i);
            int dx = Integer.signum(to.getX() - from.getX());
            int dz = Integer.signum(to.getZ() - from.getZ());
            fixture.helper.assertTrue(from.getY() == to.getY() && (dx == 0 || dz == 0),
                    "Generated boat route jumped diagonally or changed water elevation");
            for (int step = 0; step <= from.distManhattan(to); step++) {
                BlockPos pos = from.offset(dx * step, 0, dz * step);
                fixture.helper.assertTrue(VillageRiverNavigationService.navigable(fixture.level, pos),
                        "Generated route crossed missing source water or obstructed clearance");
                assertSource(fixture.helper, pos.below());
            }
        }
        int crossedSeams = 0;
        for (int x = fixture.x + 16; x < fixture.x + fixture.width; x += 16) {
            BlockPos right = nearestCenter(fixture, cells, x);
            assertSource(fixture.helper, right);
            assertSource(fixture.helper, right.west());
            fixture.helper.assertTrue(fixture.level.getBlockState(right.above(2)).isAir()
                            && fixture.level.getBlockState(right.west().above(2)).isAir(),
                    "Chunk seam interrupts overhead boat clearance");
            crossedSeams++;
        }
        fixture.helper.assertTrue(crossedSeams == 3, "Route must cross three real chunk seams");
    }

    private static void assertSource(GameTestHelper helper, BlockPos pos) {
        var level = helper.getLevel();
        helper.assertTrue(level.getBlockState(pos).is(Blocks.WATER)
                        && level.getFluidState(pos).is(FluidTags.WATER) && level.getFluidState(pos).isSource(),
                "Expected actual source-water block at " + pos);
    }

    private static ContinentalRiverGenerator.Drainage drainage(int sea) {
        return new ContinentalRiverGenerator.Drainage(SEED, sea,
                new ContinentalRiverGenerator.Settings(224, 1536, 0.12D,
                        1.0D, 0.65D, 0.18D, 0.0D, 1.0D, 0.0D));
    }

    private static ContinentalRiverGenerator.DrainageCell lowlandReach(ContinentalRiverGenerator.Drainage model) {
        for (int gx = -8; gx <= 8; gx++) {
            for (int gz = -8; gz <= 8; gz++) {
                var cell = model.cell(gx, gz);
                int dx = cell.downX() - cell.x();
                int dz = cell.downZ() - cell.z();
                if (cell.hasDownstream() && cell.sourceY() == cell.destinationY()
                        && cell.halfWidth() >= 4.0D && cell.halfWidth() <= 10.0D
                        && dx >= 120 && Math.abs(dz) <= dx * 0.22D) return cell;
            }
        }
        throw new IllegalStateException("Fixed seed has no suitable mature lowland reach");
    }

    private static ContinentalRiverGenerator.DrainageCell receivingSink(ContinentalRiverGenerator.Drainage model) {
        for (int gx = -12; gx <= 12; gx++) {
            for (int gz = -12; gz <= 12; gz++) {
                var cell = model.cell(gx, gz);
                if (!cell.hasDownstream() && cell.sinkLake() && cell.catchment() > 1
                        && cell.lakeRadius() <= 14.0D) return cell;
            }
        }
        throw new IllegalStateException("Fixed seed has no bounded receiving basin");
    }

    private static ContinentalRiverGenerator.DrainageCell incomingReach(
            ContinentalRiverGenerator.Drainage model, ContinentalRiverGenerator.DrainageCell sink) {
        for (int gx = sink.downGX() - 1; gx <= sink.downGX() + 1; gx++) {
            for (int gz = sink.downGZ() - 1; gz <= sink.downGZ() + 1; gz++) {
                var cell = model.cell(gx, gz);
                if (cell.hasDownstream() && cell.downX() == sink.x() && cell.downZ() == sink.z()
                        && cell.sourceY() > sink.sourceY()) return cell;
            }
        }
        throw new IllegalStateException("Receiving basin has no real seeded incoming reach");
    }

    private static ContinentalRiverGenerator.DrainageCell centerReach(
            ContinentalRiverGenerator.DrainageCell cell, Fixture fixture) {
        double vx = cell.downX() - cell.x();
        double vz = cell.downZ() - cell.z();
        double length = Math.hypot(vx, vz);
        int middleX = (int)Math.round((cell.x() + cell.downX()) * 0.5D - vz / length * cell.meanderOffset());
        int middleZ = (int)Math.round((cell.z() + cell.downZ()) * 0.5D + vx / length * cell.meanderOffset());
        return translate(cell, fixture.x + fixture.width / 2 - middleX,
                fixture.z + fixture.length / 2 - middleZ);
    }

    private static ContinentalRiverGenerator.DrainageCell translate(
            ContinentalRiverGenerator.DrainageCell cell, int dx, int dz) {
        return new ContinentalRiverGenerator.DrainageCell(cell.x() + dx, cell.z() + dz,
                cell.sourcePotential(), cell.hasDownstream(), cell.downX() + dx, cell.downZ() + dz,
                cell.downGX(), cell.downGZ(), cell.halfWidth(), cell.meanderOffset(), cell.delta(),
                cell.sinkLake(), cell.lakeRadius(), cell.sourceY(), cell.destinationY(), cell.rapids(), cell.catchment());
    }

    private static BlockPos nearestCenter(Fixture fixture,
            List<ContinentalRiverGenerator.DrainageCell> cells, int x) {
        BlockPos result = null;
        double best = Double.MAX_VALUE;
        for (int z = fixture.z + 2; z < fixture.z + fixture.length - 2; z++) {
            var sample = ContinentalRiverGenerator.sampleAt(x, z, cells);
            if (sample.active() && sample.distance() < best) {
                best = sample.distance();
                result = new BlockPos(x, sample.surface(), z);
            }
        }
        fixture.helper.assertTrue(result != null && best <= 1.0D, "Seeded centerline escaped bounded fixture");
        return result;
    }

    private static final class Fixture {
        final GameTestHelper helper;
        final ServerLevel level;
        final int x, z, width, length, sea, bottom, cap;
        final List<LevelChunk> chunks = new ArrayList<>();

        Fixture(GameTestHelper helper, int width, int length) {
            this.helper = helper;
            this.level = helper.getLevel();
            this.width = width;
            this.length = length;
            this.sea = level.getSeaLevel();
            this.bottom = sea - 10;
            this.cap = sea + 15;
            this.x = Math.floorDiv((int)Math.floor(helper.getBounds().minX) + 16, 16) * 16;
            this.z = Math.floorDiv((int)Math.floor(helper.getBounds().minZ) + 16, 16) * 16;
            helper.assertTrue(helper.getBounds().contains(Vec3.atCenterOf(new BlockPos(x, bottom, z)))
                            && helper.getBounds().contains(Vec3.atCenterOf(new BlockPos(x + width - 1, cap, z + length - 1))),
                    "Every physical fixture block must remain inside its reserved template");
            for (int cx = x; cx < x + width; cx += 16) {
                for (int cz = z; cz < z + length; cz += 16) {
                    var chunk = level.getChunkSource().getChunkNow(Math.floorDiv(cx, 16), Math.floorDiv(cz, 16));
                    helper.assertTrue(chunk != null, "GameTest fixture must already have its chunks loaded");
                    chunks.add(chunk);
                }
            }
        }

        int highTop(int x, int z) {
            return sea + 4 + Math.floorMod((x - this.x) * 3 + (z - this.z) * 5, 9);
        }

        void fillHighTerrain() {
            for (var chunk : chunks) {
                for (int lx = 0; lx < 16; lx++) {
                    for (int lz = 0; lz < 16; lz++) {
                        int x = chunk.getPos().getMinBlockX() + lx;
                        int z = chunk.getPos().getMinBlockZ() + lz;
                        int top = highTop(x, z);
                        for (int y = bottom; y <= cap; y++) {
                            var state = y > top ? Blocks.AIR.defaultBlockState()
                                    : y == top ? Blocks.GRASS_BLOCK.defaultBlockState()
                                    : y >= top - 2 ? Blocks.DIRT.defaultBlockState() : Blocks.STONE.defaultBlockState();
                            chunk.setBlockState(new BlockPos(x, y, z), state, false);
                        }
                    }
                }
                Heightmap.primeHeightmaps(chunk, EnumSet.of(Heightmap.Types.WORLD_SURFACE_WG));
            }
        }

        void carve(List<ContinentalRiverGenerator.DrainageCell> cells, boolean reverse) {
            List<LevelChunk> ordered = new ArrayList<>(chunks);
            if (reverse) Collections.reverse(ordered);
            for (var chunk : ordered) ContinentalRiverGenerator.carveChunk(level, chunk, cells);
        }

        BlockState[] snapshot() {
            BlockState[] states = new BlockState[width * length * (cap - bottom + 1)];
            for (int x = this.x; x < this.x + width; x++) {
                for (int z = this.z; z < this.z + length; z++) {
                    for (int y = bottom; y <= cap; y++) states[index(x, y, z)] = level.getBlockState(new BlockPos(x, y, z));
                }
            }
            return states;
        }

        int index(int x, int y, int z) {
            return ((x - this.x) * length + z - this.z) * (cap - bottom + 1) + y - bottom;
        }

        void assertColumn(BlockState[] expected, int x, int z, String message) {
            for (int y = bottom; y <= cap; y++) {
                BlockPos pos = new BlockPos(x, y, z);
                helper.assertTrue(level.getBlockState(pos).equals(expected[index(x, y, z)]), message + " at " + pos);
            }
        }

        void assertSnapshot(BlockState[] expected, String message) {
            for (int x = this.x; x < this.x + width; x++) {
                for (int z = this.z; z < this.z + length; z++) assertColumn(expected, x, z, message);
            }
        }
    }
}
