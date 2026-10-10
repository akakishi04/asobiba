package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.level.block.BedBlock;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.properties.BedPart;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageCirculationVersionGameTests {
    private VillageCirculationVersionGameTests() {}

    @GameTest(template="empty16x14x9", batch="circulation_v2_two", timeoutTicks=80)
    public static void v2TwoStoreyHasThreeSupportedBedsAndTrueStairClearance(GameTestHelper h) { verify(h, false); }

    @GameTest(template="empty16x14x9", batch="circulation_v2_three", timeoutTicks=80)
    public static void v2ThreeStoreyHasFourSupportedBedsAndTrueStairClearance(GameTestHelper h) { verify(h, true); }

    private static void verify(GameTestHelper h, boolean third) {
        var level = h.getLevel(); var data = VillageSavedData.get(level);
        BlockPos base = h.absolutePos(new BlockPos(4,1,2));
        var village = data.createVillage(base, level.getGameTime());
        var project = data.createProject(village.id(), "building", 70, base);
        project.setTemplateId(third ? "house_3story_5x5" : "house_2story_5x5");
        project.setParameter("plank", "oak"); project.setParameter("lead_skill", "100");
        project.setParameter("circulation_version", "2");
        var plan = VillageSimulationEvents.projectPlan(project);
        for (var step : plan) level.setBlock(step.pos(), step.state(), 2);
        h.runAtTickTime(4, () -> {
            int beds=0;
            for (var step : plan) if (step.state().is(Blocks.WHITE_BED) && step.state().getValue(BedBlock.PART)==BedPart.FOOT) {
                beds++;
                BlockPos head = step.pos().relative(step.state().getValue(BedBlock.FACING));
                if (!level.getBlockState(step.pos().below()).isFaceSturdy(level, step.pos().below(), Direction.UP)
                        || !level.getBlockState(head.below()).isFaceSturdy(level, head.below(), Direction.UP)
                        || !level.getBlockState(head).is(Blocks.WHITE_BED)) {
                    h.fail("Every v2 Bed half must have real physical floor support", new BlockPos(6,6,4)); return;
                }
            }
            var ground = VillageBuildingService.reachableTemplateGround(level, base);
            if (beds != (third ? 4 : 3) || !ground.contains(base.offset(1,1,2).asLong())
                    || !ground.contains(base.offset(2,1,2).asLong())
                    || !VillageBuildingService.connectedUpperStories(level, base, third ? 2 : 1)) {
                h.fail("v2 capacity requires real ground circulation and full stair headroom", new BlockPos(6,6,4)); return;
            }
            h.succeed();
        });
    }

    @GameTest(template="empty16x14x9", batch="circulation_legacy_cursor", timeoutTicks=80)
    public static void absentVersionPreservesLegacyBlueprintAndSavedCursor(GameTestHelper h) {
        var level=h.getLevel(); var data=VillageSavedData.get(level);
        BlockPos base=h.absolutePos(new BlockPos(4,1,2));
        var village=data.createVillage(base,level.getGameTime());
        var source=data.createProject(village.id(),"building",70,base);
        source.setTemplateId("house_2story_5x5"); source.setParameter("plank","oak");
        source.setWorkCursor(37); source.setPhase("walls");
        var legacy=VillageSimulationEvents.projectPlan(source);
        var loaded=VillageSavedData.load(data.save(new CompoundTag(),level.registryAccess()),level.registryAccess());
        var restored=loaded.project(source.id()).orElseThrow();
        if (!restored.parameter("circulation_version").isBlank() || restored.workCursor()!=37
                || !legacy.equals(VillageSimulationEvents.projectPlan(restored))
                || legacy.stream().noneMatch(s -> s.pos().equals(base.offset(2,4,1)) && s.state().is(Blocks.OAK_PLANKS))
                || legacy.stream().noneMatch(s -> s.pos().equals(base.offset(2,5,1)) && s.state().is(Blocks.WHITE_BED))) {
            h.fail("Old saved project indices and old geometry must remain unchanged until explicit retrofit", new BlockPos(6,6,4)); return;
        }
        h.succeed();
    }
}
