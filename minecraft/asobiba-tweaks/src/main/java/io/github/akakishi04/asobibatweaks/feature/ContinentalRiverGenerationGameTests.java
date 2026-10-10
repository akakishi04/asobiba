package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Seeded production drainage calculations, without changing worldgen config or generating chunks. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class ContinentalRiverGenerationGameTests {
    private static final long SEED = 918273645L;
    private static final int SEA = 63;
    private static final BlockPos MARK = new BlockPos(1, 1, 1);
    private ContinentalRiverGenerationGameTests() {}

    private static ContinentalRiverGenerator.Drainage drainage() {
        // Zero optional lake probability proves required terminal basins still
        // exist. No delta flare isolates the upstream-flow width invariant.
        return new ContinentalRiverGenerator.Drainage(SEED, SEA,
                new ContinentalRiverGenerator.Settings(224, 1536, 0.12D,
                        1.0D, 0.65D, 0.18D, 0.0D, 1.0D, 0.0D));
    }

    @GameTest(template = "empty3x3x3", batch = "forest_safety")
    public static void seededRiverConfluencesAccumulateWithoutNarrowing(GameTestHelper helper) {
        var model = drainage();
        int accumulated = 0;
        for (int x = -8; x <= 8; x++) {
            for (int z = -8; z <= 8; z++) {
                var reach = model.cell(x, z);
                if (reach.catchment() < 1 || reach.catchment() > ContinentalRiverGenerator.MAX_CATCHMENT) {
                    helper.fail("Catchment traversal exceeded its hard saturation bound", MARK);
                    return;
                }
                if (!reach.hasDownstream()) continue;
                var next = model.cell(reach.downGX(), reach.downGZ());
                if (next.catchment() < reach.catchment() || next.halfWidth() < reach.halfWidth()) {
                    helper.fail("Downstream channel forgot an upstream confluence", MARK);
                    return;
                }
                if (reach.catchment() >= 3) accumulated++;
            }
        }
        if (accumulated == 0) {
            helper.fail("Seeded fixture did not exercise accumulated tributaries", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "forest_safety")
    public static void seededRiverGradesShareConfluencesAndNeverClimb(GameTestHelper helper) {
        var model = drainage();
        int reaches = 0;
        int rapids = 0;
        for (int x = -8; x <= 8; x++) {
            for (int z = -8; z <= 8; z++) {
                var reach = model.cell(x, z);
                if (!reach.hasDownstream()) continue;
                reaches++;
                if (reach.rapids()) rapids++;
                var next = model.cell(reach.downGX(), reach.downGZ());
                int last = reach.sourceY();
                for (int step = 0; step <= 64; step++) {
                    int height = ContinentalRiverGenerator.grade(reach, step / 64.0D);
                    if (height > last) {
                        helper.fail("A deterministic river reach flowed uphill", MARK);
                        return;
                    }
                    last = height;
                }
                if (last != next.sourceY() || reach.destinationY() != next.sourceY()) {
                    helper.fail("Adjacent reaches disagree on their shared confluence elevation", MARK);
                    return;
                }
            }
        }
        if (reaches == 0 || rapids == 0) {
            helper.fail("Seed must exercise both ordinary reaches and stepped rapids", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "forest_safety")
    public static void seededTerminalRiversAlwaysReachPhysicalBasinPlan(GameTestHelper helper) {
        var model = drainage();
        int sinks = 0;
        for (int x = -8; x <= 8; x++) {
            for (int z = -8; z <= 8; z++) {
                var cell = model.cell(x, z);
                if (cell.hasDownstream() || cell.catchment() <= 1) continue;
                sinks++;
                var sample = ContinentalRiverGenerator.sampleAt(cell.x(), cell.z(), List.of(cell));
                if (!cell.sinkLake() || cell.lakeRadius() < 6.0D || !sample.active()
                        || !sample.lake() || sample.surface() != cell.sourceY()) {
                    helper.fail("An incoming river ended without a coherent terminal lake plan", MARK);
                    return;
                }
            }
        }
        if (sinks == 0) {
            helper.fail("Seed must exercise receiving terminal drainage cells", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "forest_safety")
    public static void seededRiverChunkSeamsIgnoreGenerationOrder(GameTestHelper helper) {
        var search = drainage();
        int checked = 0;
        for (int x = -4; x <= 4 && checked < 8; x++) {
            for (int z = -4; z <= 4 && checked < 8; z++) {
                var cell = search.cell(x, z);
                if (!cell.hasDownstream()) continue;
                int boundaryX = (int)Math.round(cell.x() / 16.0D) * 16;
                if (Math.abs(boundaryX - cell.x()) > cell.halfWidth()) continue;
                int baseZ = Math.floorDiv(cell.z(), 16) * 16;
                var leftFirst = drainage();
                var left = leftFirst.nearChunk(boundaryX - 16, baseZ);
                var right = leftFirst.nearChunk(boundaryX, baseZ);
                var rightFirst = drainage();
                var reverseRight = rightFirst.nearChunk(boundaryX, baseZ);
                var reverseLeft = rightFirst.nearChunk(boundaryX - 16, baseZ);
                var expected = ContinentalRiverGenerator.sampleAt(boundaryX, cell.z(), left);
                if (!expected.active()) continue;
                if (!expected.equals(ContinentalRiverGenerator.sampleAt(boundaryX, cell.z(), right))
                        || !expected.equals(ContinentalRiverGenerator.sampleAt(boundaryX, cell.z(), reverseRight))
                        || !expected.equals(ContinentalRiverGenerator.sampleAt(boundaryX, cell.z(), reverseLeft))) {
                    helper.fail("Same seeded boundary column changed with chunk generation order", MARK);
                    return;
                }
                checked++;
            }
        }
        if (checked == 0) {
            helper.fail("Chunk seam test must include a genuinely active river column", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "forest_safety")
    public static void riverGradesIgnoreColumnReliefWithoutHangingWater(GameTestHelper helper) {
        var cell = drainage().cell(0, 0);
        int sharedSurface = ContinentalRiverGenerator.grade(cell, 0.5D);
        if (!ContinentalRiverGenerator.canCarve(sharedSurface + 2, sharedSurface, SEA, -64)
                || !ContinentalRiverGenerator.canCarve(sharedSurface + 15, sharedSurface, SEA, -64)
                || ContinentalRiverGenerator.canCarve(sharedSurface, sharedSurface, SEA, -64)
                || ContinentalRiverGenerator.canCarve(sharedSurface - 3, sharedSurface, SEA, -64)) {
            helper.fail("Channel grade must cut varying high terrain but never fill above lower terrain", MARK);
            return;
        }
        helper.succeed();
    }
}
