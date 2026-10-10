package io.github.akakishi04.asobibatweaks.gametest;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.github.akakishi04.asobibatweaks.feature.EnchantedArrowCopyService;
import io.github.akakishi04.asobibatweaks.feature.EnchantmentMasteryData;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.enchantment.Enchantments;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/**
 * Server-side purchase tests: unlike quote-only tests these invoke the real
 * Fletching copy transaction with a connected mock ServerPlayer and inspect
 * physical inventory, source stacks and spendable experience afterward.
 *
 * Packet/screen interaction and multiplayer interception remain separate
 * acceptance scenarios; a mock player is not a real remote client.
 */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
@SuppressWarnings("removal")
public final class AsobibaFletchingTransactionTests {
    private static final BlockPos CENTER = new BlockPos(1, 1, 1);

    private AsobibaFletchingTransactionTests() {}

    @GameTest(template = "empty3x3x3", batch = "fletching_transactions")
    public static void paidCopyConservesArrowCountComponentsAndXp(GameTestHelper helper) {
        ServerPlayer player = helper.makeMockServerPlayerInLevel();
        var sharpness = helper.getLevel().registryAccess()
                .lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.SHARPNESS);
        ItemStack template = new ItemStack(Items.ARROW);
        template.enchant(sharpness, 2);
        EnchantmentMasteryData.addMastery(template, sharpness, 50);
        ItemStack material = new ItemStack(Items.ARROW, 7);
        player.giveExperiencePoints(200);

        var quote = EnchantedArrowCopyService.quote(player, template, material);
        long xpBefore = quote.availableXp();
        long cost = quote.total(3);
        if (!quote.valid() || quote.materialCount() != 7 || cost <= 0L || cost > xpBefore) {
            helper.fail("Expected a positive affordable quote for three enchanted arrows", CENTER);
            return;
        }
        if (!EnchantedArrowCopyService.copy(player, template, material, 3)) {
            helper.fail("Valid server copy transaction unexpectedly failed", CENTER);
            return;
        }

        long xpAfter = EnchantedArrowCopyService.quote(player, template, material).availableXp();
        int enchantedOutput = 0;
        int unexpectedArrows = 0;
        for (ItemStack stack : player.getInventory().items) {
            if (!stack.is(Items.ARROW)) continue;
            if (ItemStack.isSameItemSameComponents(stack, template)) {
                enchantedOutput += stack.getCount();
            } else {
                unexpectedArrows += stack.getCount();
            }
        }
        if (material.getCount() != 4 || template.getCount() != 1
                || enchantedOutput != 3 || unexpectedArrows != 0
                || EnchantmentMasteryData.getMastery(template, sharpness) != 50
                || xpBefore - xpAfter != cost) {
            helper.fail("Copy duplicated/lost arrows, item components or experience", CENTER);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "fletching_transactions")
    public static void invalidMaterialsNeverSpendXpOrEmitArrows(GameTestHelper helper) {
        ServerPlayer player = helper.makeMockServerPlayerInLevel();
        var sharpness = helper.getLevel().registryAccess()
                .lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.SHARPNESS);
        ItemStack template = new ItemStack(Items.ARROW);
        template.enchant(sharpness, 1);
        player.giveExperiencePoints(100);
        long before = EnchantedArrowCopyService.quote(player, template,
                new ItemStack(Items.ARROW, 1)).availableXp();

        ItemStack wrongType = new ItemStack(Items.SPECTRAL_ARROW, 5);
        ItemStack alreadyEnchanted = new ItemStack(Items.ARROW, 5);
        alreadyEnchanted.enchant(sharpness, 1);
        if (EnchantedArrowCopyService.quote(player, template, wrongType).valid()
                || EnchantedArrowCopyService.quote(player, template, alreadyEnchanted).valid()
                || EnchantedArrowCopyService.copy(player, template, wrongType, 2)
                || EnchantedArrowCopyService.copy(player, template, alreadyEnchanted, 2)) {
            helper.fail("Invalid arrow materials were accepted", CENTER);
            return;
        }

        long after = EnchantedArrowCopyService.quote(player, template,
                new ItemStack(Items.ARROW, 1)).availableXp();
        if (wrongType.getCount() != 5 || alreadyEnchanted.getCount() != 5
                || !player.getInventory().isEmpty() || before != after) {
            helper.fail("Rejected copy mutated inventory, materials or XP", CENTER);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "fletching_transactions")
    public static void invalidQuantityAndInsufficientXpAreAtomic(GameTestHelper helper) {
        ServerPlayer player = helper.makeMockServerPlayerInLevel();
        var sharpness = helper.getLevel().registryAccess()
                .lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.SHARPNESS);
        ItemStack template = new ItemStack(Items.ARROW);
        template.enchant(sharpness, 2);
        ItemStack material = new ItemStack(Items.ARROW, 3);
        long originalXp = EnchantedArrowCopyService.quote(player, template, material).availableXp();
        long requiredXp = EnchantedArrowCopyService.quote(player, template, material).total(1);
        if (requiredXp <= 0 || originalXp >= requiredXp) {
            helper.fail("Mock player must start without spendable XP", CENTER);
            return;
        }

        if (EnchantedArrowCopyService.copy(player, template, material, 1)
                || EnchantedArrowCopyService.copy(player, template, material, 0)
                || EnchantedArrowCopyService.copy(player, template, material, 4)
                || EnchantedArrowCopyService.copy(player, template, material, 65)) {
            helper.fail("Unfunded or out-of-range purchase was accepted", CENTER);
            return;
        }
        long after = EnchantedArrowCopyService.quote(player, template, material).availableXp();
        if (originalXp != after || material.getCount() != 3
                || template.getCount() != 1 || !player.getInventory().isEmpty()) {
            helper.fail("Invalid purchase consumed or generated game resources", CENTER);
            return;
        }
        helper.succeed();
    }
}
