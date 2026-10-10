package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageActivityBoundaryGameTests {
    private VillageActivityBoundaryGameTests() {}

    @GameTest(template = "empty16x6x9", batch = "activity_boundary")
    public static void growsOneConnectedHopAsymmetricallyAndStopsAtCap(GameTestHelper helper) {
        var data = new VillageSavedData();
        var village = data.createVillage(new BlockPos(0, -40, 0), 0L);
        helper.assertTrue(VillageActivityBoundary.contains(village, new BlockPos(48, -80, 0))
                && !VillageActivityBoundary.contains(village, new BlockPos(49, -40, 0)), "Initial horizontal radius must be 48");
        List<BlockPos> chain = List.of(new BlockPos(44, -40, 0), new BlockPos(60, -40, 0),
                new BlockPos(76, -40, 0), new BlockPos(92, -40, 0), new BlockPos(108, -40, 0),
                new BlockPos(124, -40, 0), new BlockPos(140, -40, 0), new BlockPos(156, -40, 0));
        VillageActivityBoundary.grow(village, chain);
        helper.assertTrue(!VillageActivityBoundary.contains(village, new BlockPos(76, -40, 0)),
                "A whole chain was absorbed during one refresh");
        helper.assertTrue(!VillageActivityBoundary.contains(village, new BlockPos(-60, -40, 0)),
                "East growth expanded the unrelated west side");
        for (int i = 0; i < 12; i++) VillageActivityBoundary.grow(village, chain);
        helper.assertTrue(VillageActivityBoundary.contains(village, new BlockPos(124, -40, 0)), "Connected growth failed");
        helper.assertTrue(!VillageActivityBoundary.contains(village, village.center().offset(129, 0, 0)),
                "Core escaped its effective-center cap");
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "activity_boundary")
    public static void isolatedKnownBuildingDoesNotGrowOrClaimOtherProperty(GameTestHelper helper) {
        var data = new VillageSavedData();
        BlockPos origin = helper.absolutePos(new BlockPos(3, 2, 3));
        var village = data.createVillage(origin, 0L);
        var remote = data.createBuilding(village.id(), origin.offset(100, 0, 0), origin.offset(104, 4, 4), true);
        remote.setClassification("residential"); remote.setValidationState("valid"); remote.setValidatedCapacity(2);
        for (int dx : new int[]{8, 10, 12}) {
            var storage = data.createStorage(village.id(), origin.offset(dx, 0, 0), "general");
            storage.setValidationState("valid");
        }
        for (int i = 0; i < 8; i++) VillageActivityBoundary.refresh(helper.getLevel(), data, village);
        helper.assertTrue(village.center().getX() > origin.getX(), "Center did not follow recognized local anchors");
        helper.assertTrue(!VillageActivityBoundary.contains(village, remote.min()), "Isolated distant building became core");
        helper.assertTrue(village.buildingIds().size() == 1 && village.storageIds().size() == 3,
                "Boundary refresh adopted unregistered player/world property");
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "activity_boundary")
    public static void boundedEnvelopeAndActiveClockSurviveReload(GameTestHelper helper) {
        var data = new VillageSavedData();
        var village = data.createVillage(new BlockPos(0, -50, 0), 0L);
        var anchors = new ArrayList<BlockPos>();
        for (int x = 0; x < 300; x++) anchors.add(new BlockPos(x % 100, -50, x / 100));
        village.replaceActivityAnchors(anchors);
        village.observeActive(100L); village.observeActive(140L);
        long active = village.activeObservedTicks();
        var loaded = VillageSavedData.load(data.save(new CompoundTag(), helper.getLevel().registryAccess()),
                helper.getLevel().registryAccess());
        var restored = loaded.village(village.id()).orElseThrow();
        restored.observeActive(10_000_000L);
        helper.assertTrue(restored.activityAnchors().size() <= VillageActivityBoundary.MAX_ANCHORS,
                "Saved anchor history exceeded fixed limit");
        helper.assertTrue(restored.activityOrigin().equals(village.activityOrigin())
                && restored.activeObservedTicks() == active + 1L, "Offline elapsed time aged the village");
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "activity_boundary")
    public static void footprintChecksNonConvexInteriorAndNegativeAltitude(GameTestHelper helper) {
        var village = new VillageSavedData().createVillage(new BlockPos(0, -50, 0), 0L);
        village.replaceActivityAnchors(List.of(new BlockPos(70, -50, -20), new BlockPos(70, -50, 20)));
        BlockPos min = new BlockPos(64, -50, -14), max = new BlockPos(64, -40, 14);
        helper.assertTrue(VillageActivityBoundary.contains(village, min) && VillageActivityBoundary.contains(village, max),
                "Test corners should each fit an anchor neighborhood");
        helper.assertTrue(!VillageActivityBoundary.containsFootprint(village, min, max),
                "Corner-only check admitted a footprint crossing a gap");
        helper.assertTrue(VillageActivityBoundary.containsFootprint(village,
                new BlockPos(-2, -60, -2), new BlockPos(2, -40, 2)), "Negative terrain altitude was mistaken for outside core");
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "activity_boundary")
    public static void provenInvalidAnchorsRetireButUnloadedRecordsAreNotRemoved(GameTestHelper helper) {
        var data = new VillageSavedData();
        BlockPos origin = helper.absolutePos(new BlockPos(3, 2, 3));
        var village = data.createVillage(origin, 0L);
        var broken = data.createStorage(village.id(), origin.offset(44, 0, 0), "general");
        broken.setValidationState("invalid");
        village.replaceActivityAnchors(List.of(broken.pos(), origin.offset(100, 0, 0)));
        VillageActivityBoundary.refresh(helper.getLevel(), data, village);
        helper.assertTrue(!village.activityAnchors().contains(broken.pos().asLong())
                && !village.activityAnchors().contains(origin.offset(100, 0, 0).asLong()),
                "Proven-invalid anchor or disconnected cached island survived refresh");
        helper.assertTrue(data.storage(broken.id()).isPresent(), "Boundary maintenance deleted a physical asset record");
        helper.succeed();
    }

}
