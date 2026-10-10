package io.github.akakishi04.asobibatweaks.gametest;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.github.akakishi04.asobibatweaks.feature.EnchantmentMasteryData;
import io.github.akakishi04.asobibatweaks.feature.EnchantmentTweaksEvents;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.item.enchantment.Enchantments;
import net.neoforged.neoforge.common.damagesource.DamageContainer;
import net.neoforged.neoforge.event.entity.living.LivingDamageEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Required integration tests through the real armor-branch event handlers. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class AsobibaArmorBranchTests {
    private static final BlockPos MARK = new BlockPos(1, 1, 1);
    private AsobibaArmorBranchTests() {}

    @GameTest(template = "empty3x3x3", batch = "armor_branches", required = true)
    public static void differentProtectionBranchesCoexistAndRetainFirstHitTiming(GameTestHelper helper) {
        var player = helper.makeMockServerPlayerInLevel();
        player.setItemSlot(EquipmentSlot.HEAD, armor(helper, Items.DIAMOND_HELMET,
                Enchantments.PROTECTION, 100, 0));
        player.setItemSlot(EquipmentSlot.CHEST, armor(helper, Items.DIAMOND_CHESTPLATE,
                Enchantments.PROTECTION, 50, 1));
        var events = new EnchantmentTweaksEvents();
        var first = damage(helper, player);
        events.onLivingDamage(first);
        assertDamage(helper, first, 8.28F, "General Defense and lower-mastery First-Hit Defense must coexist");
        var second = damage(helper, player);
        events.onLivingDamage(second);
        assertDamage(helper, second, 9.2F, "First-Hit cooldown must remain active while General Defense continues");
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "armor_branches", required = true)
    public static void duplicateProtectionUsesStrongestMasteryOnly(GameTestHelper helper) {
        var player = helper.makeMockServerPlayerInLevel();
        player.setItemSlot(EquipmentSlot.FEET, armor(helper, Items.DIAMOND_BOOTS,
                Enchantments.PROTECTION, 50, 0));
        player.setItemSlot(EquipmentSlot.HEAD, armor(helper, Items.DIAMOND_HELMET,
                Enchantments.PROTECTION, 100, 0));
        player.setItemSlot(EquipmentSlot.CHEST, armor(helper, Items.DIAMOND_CHESTPLATE,
                Enchantments.PROTECTION, 75, 0));
        var event = damage(helper, player);
        new EnchantmentTweaksEvents().onLivingDamage(event);
        assertDamage(helper, event, 9.2F, "Identical armor branches must apply only the strongest 8% reduction once");
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "armor_branches", required = true)
    public static void fireExtinguishingCoexistsWithStrongerHeatAdaptation(GameTestHelper helper) {
        var player = helper.makeMockServerPlayerInLevel();
        // Player.setRemainingFireTicks clamps invulnerable creative players to one tick.
        player.getAbilities().invulnerable = false;
        player.setItemSlot(EquipmentSlot.HEAD, armor(helper, Items.DIAMOND_HELMET,
                Enchantments.FIRE_PROTECTION, 50, 0));
        player.setItemSlot(EquipmentSlot.CHEST, armor(helper, Items.DIAMOND_CHESTPLATE,
                Enchantments.FIRE_PROTECTION, 100, 1));
        var events = new EnchantmentTweaksEvents();
        player.setRemainingFireTicks(0);
        events.onFireProtectionTick(new PlayerTickEvent.Post(player));
        player.setRemainingFireTicks(100);
        events.onFireProtectionTick(new PlayerTickEvent.Post(player));
        if (player.getRemainingFireTicks() != 80) {
            helper.fail("Stronger Heat Adaptation must not suppress Rapid Extinguishing on another piece; fire ticks="
                    + player.getRemainingFireTicks(), MARK);
            return;
        }
        events.onFireProtectionTick(new PlayerTickEvent.Post(player));
        if (player.getRemainingFireTicks() != 80) {
            helper.fail("Rapid Extinguishing must not repeatedly shorten the same ignition", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "armor_branches", required = true)
    public static void soulConservationNeverRefundsSwappedOrUnrelatedDamage(GameTestHelper helper) {
        var player = helper.makeMockServerPlayerInLevel();
        // Native item wear skips creative players with infinite materials.
        player.getAbilities().instabuild = false;
        var boots = armor(helper, Items.DIAMOND_BOOTS, Enchantments.SOUL_SPEED, 100, 0);
        player.setItemSlot(EquipmentSlot.FEET, boots);
        var at = helper.absolutePos(MARK);
        helper.getLevel().setBlockAndUpdate(at.below(), net.minecraft.world.level.block.Blocks.SOUL_SAND.defaultBlockState());
        player.setPos(at.getX() + 0.5D, at.getY(), at.getZ() + 0.5D);
        player.setOnGround(true);
        player.setDeltaMovement(0.1D, 0.0D, 0.0D);
        var events = new EnchantmentTweaksEvents();
        events.onSoulSpeedTick(new PlayerTickEvent.Post(player));
        var replacement = boots.copy();
        replacement.setDamageValue(100);
        player.setItemSlot(EquipmentSlot.FEET, replacement);
        events.onSoulSpeedTick(new PlayerTickEvent.Post(player));
        if (replacement.getDamageValue() != 100) {
            helper.fail("Changing boots must not turn previous-item damage into Soul Speed refunds", MARK);
            return;
        }
        // This direct DamageItem invocation represents a different effect, outside Soul Speed's location hook.
        var item = new net.minecraft.world.item.enchantment.EnchantedItemInUse(replacement, EquipmentSlot.FEET, player);
        new net.minecraft.world.item.enchantment.effects.DamageItem(
                net.minecraft.world.item.enchantment.LevelBasedValue.constant(1.0F))
                .apply(helper.getLevel(), 1, item, player, player.position());
        events.onSoulSpeedTick(new PlayerTickEvent.Post(player));
        if (replacement.getDamageValue() != 101) {
            helper.fail("Conservation must not cancel or later refund another effect's item damage; damage="
                    + replacement.getDamageValue(), MARK);
            return;
        }
        helper.succeed();
    }

    private static LivingDamageEvent.Pre damage(GameTestHelper helper, ServerPlayer player) {
        var container = new DamageContainer(helper.getLevel().damageSources().generic(), 20.0F);
        container.setNewDamage(10.0F); // Branches see the remaining post-vanilla damage.
        return new LivingDamageEvent.Pre(player, container);
    }

    private static void assertDamage(GameTestHelper helper, LivingDamageEvent.Pre event,
                                     float expected, String message) {
        if (Math.abs(event.getNewDamage() - expected) > 0.0001F) {
            helper.fail(message + "; got " + event.getNewDamage(), MARK);
        }
    }

    private static ItemStack armor(GameTestHelper helper, Item item,
                                   ResourceKey<Enchantment> key, int mastery, int branch) {
        var enchantment = helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(key);
        var stack = new ItemStack(item);
        stack.enchant(enchantment, 1);
        EnchantmentMasteryData.addMastery(stack, enchantment, mastery);
        for (int i = 0; i <= branch; i++) EnchantmentMasteryData.cycleBranch(stack, enchantment);
        return stack;
    }
}
