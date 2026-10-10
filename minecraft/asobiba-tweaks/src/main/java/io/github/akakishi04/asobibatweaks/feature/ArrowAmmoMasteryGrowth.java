package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.tags.EntityTypeTags;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.projectile.AbstractArrow;
import net.minecraft.world.item.ArrowItem;
import net.minecraft.world.item.ItemStack;

/** Use history belongs to the paid physical projectile stack, once per enchantment per flight. */
public final class ArrowAmmoMasteryGrowth {
    private static final String USED = "asobibatweaks_ammo_mastery_used";
    private ArrowAmmoMasteryGrowth() {}

    public static void credit(AbstractArrow arrow, String id) {
        if (!AsobibaTweaksConfig.GROWING_ENCHANTMENTS_ENABLED.getAsBoolean()
                || !AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                || arrow.level().isClientSide() || !(arrow.getOwner() instanceof ServerPlayer)
                || arrow.pickup != AbstractArrow.Pickup.ALLOWED
                || "minecraft:loyalty".equals(id)) return; // Loyalty owns its successful-return credit.
        ItemStack stack = arrow.getPickupItemStackOrigin();
        if (!(stack.getItem() instanceof ArrowItem) || stack.isEmpty()) return;
        var state = arrow.getPersistentData();
        var used = state.getCompound(USED);
        if (used.getBoolean(id)) return;
        for (var holder : EnchantmentMasteryData.enchantments(stack).keySet()) {
            if (!id.equals(EnchantmentMasteryData.id(holder))) continue;
            EnchantmentMasteryData.addMastery(stack, holder, 1);
            used.putBoolean(id, true);
            state.put(USED, used);
            return;
        }
    }

    public static void hit(AbstractArrow arrow, LivingEntity target) {
        credit(arrow, "minecraft:sharpness");
        credit(arrow, "minecraft:punch");
        credit(arrow, "minecraft:piercing");
        if (arrow.isOnFire()) credit(arrow, "minecraft:flame");
        if (target.getArmorValue() > 0) credit(arrow, "minecraft:breach");
        if (target.getType().is(EntityTypeTags.SENSITIVE_TO_SMITE)) credit(arrow, "minecraft:smite");
        if (target.getType().is(EntityTypeTags.SENSITIVE_TO_BANE_OF_ARTHROPODS)) credit(arrow, "minecraft:bane_of_arthropods");
        if (target.getType().is(EntityTypeTags.SENSITIVE_TO_IMPALING)) credit(arrow, "minecraft:impaling");
    }
}
