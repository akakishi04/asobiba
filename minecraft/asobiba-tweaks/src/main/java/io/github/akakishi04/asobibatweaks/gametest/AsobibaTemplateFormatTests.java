package io.github.akakishi04.asobibatweaks.gametest;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import net.minecraft.core.Vec3i;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.resources.ResourceLocation;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Protects test isolation and chunk readiness against malformed NBT size tags. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class AsobibaTemplateFormatTests {
    private AsobibaTemplateFormatTests() {}

    @GameTest(template = "empty3x3x3", batch = "template_format")
    public static void allFixtureDimensionsSurviveMinecraftNbtLoading(GameTestHelper helper) {
        for (int[] size : new int[][] {{3, 3, 3}, {16, 6, 9}, {16, 14, 9}, {16, 14, 16}, {16, 80, 16}, {80, 144, 48}, {32, 144, 32}}) {
            String name = "empty" + size[0] + "x" + size[1] + "x" + size[2];
            var template = helper.getLevel().getStructureManager()
                    .get(ResourceLocation.fromNamespaceAndPath(AsobibaTweaks.MOD_ID, name));
            if (template.isEmpty() || !template.get().getSize().equals(
                    new Vec3i(size[0], size[1], size[2]))) {
                helper.fail("Fixture " + name + " must load its declared dimensions; "
                        + "size must be TAG_List of TAG_Int, not TAG_Int_Array");
                return;
            }
        }
        helper.succeed();
    }
}
