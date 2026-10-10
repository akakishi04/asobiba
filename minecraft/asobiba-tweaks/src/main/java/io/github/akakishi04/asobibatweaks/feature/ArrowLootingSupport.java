package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.core.Holder;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.projectile.AbstractArrow;
import net.minecraft.world.item.ArrowItem;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.item.enchantment.Enchantments;
import net.minecraft.world.level.storage.loot.LootContext;
import net.minecraft.world.level.storage.loot.parameters.LootContextParams;

/**
 * Opt-in arrow-side Looting for vanilla loot-table evaluation.
 *
 * Both the ENCHANTED_COUNT_INCREASE function and the
 * RANDOM_CHANCE_WITH_ENCHANTED_BONUS predicate query the attacker's held
 * Looting level. This helper raises those results to the greater of the
 * equipped-level and the *physical arrow* level. It does not synthesize
 * extra ItemEntities or reroll loot tables after death.
 */
public final class ArrowLootingSupport {
    private ArrowLootingSupport() {}

    public static int effectiveLevel(
            int vanillaLevel, Holder<Enchantment> enchantment, LootContext context) {
        if (!AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                || enchantment == null || !enchantment.is(Enchantments.LOOTING)
                || context == null || !context.hasParam(LootContextParams.DAMAGE_SOURCE)) {
            return vanillaLevel;
        }

        DamageSource damage = context.getParamOrNull(LootContextParams.DAMAGE_SOURCE);
        if (damage == null || !(damage.getDirectEntity() instanceof AbstractArrow arrow)) {
            return vanillaLevel;
        }

        if (!(arrow.getPickupItemStackOrigin().getItem() instanceof ArrowItem)) return vanillaLevel;

        Entity attacker = context.getParamOrNull(LootContextParams.ATTACKING_ENTITY);
        if (!(attacker instanceof LivingEntity) || arrow.getOwner() != attacker) {
            return vanillaLevel;
        }

        // The original Arrow ItemStack on the projectile retains all custom
        // enchantments, while the Bow/Crossbow's own level is still included
        // in vanillaLevel. Never add the two levels together.
        int arrowLevel = EnchantedArrowImpactEvents.level(
                arrow.getPickupItemStackOrigin(), "minecraft:looting");
        return Math.max(vanillaLevel, arrowLevel);
    }
}
