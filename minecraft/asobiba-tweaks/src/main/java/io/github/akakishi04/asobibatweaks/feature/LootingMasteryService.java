package io.github.akakishi04.asobibatweaks.feature;

import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.projectile.AbstractArrow;
import net.minecraft.world.item.ArrowItem;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.storage.loot.LootContext;
import net.minecraft.world.level.storage.loot.parameters.LootContextParams;

/** Adjust genuine Looting rolls, never duplicate an already generated rare item. */
public final class LootingMasteryService {
    private LootingMasteryService() {}

    private static LauncherReloadMasteryEvents.Branch bigGame(LootContext context) {
        if (context == null) return null;
        DamageSource source = context.getParamOrNull(LootContextParams.DAMAGE_SOURCE);
        var attacker = context.getParamOrNull(LootContextParams.ATTACKING_ENTITY);
        if (source == null || !(attacker instanceof LivingEntity living)
                || source.getEntity() != attacker) return null;
        ItemStack weapon = source.getWeaponItem();
        if ((weapon == null || weapon.isEmpty()) && source.getDirectEntity() == attacker)
            weapon = living.getMainHandItem();
        var best = weapon == null ? null : selectedBigGame(weapon);
        if (source.getDirectEntity() instanceof AbstractArrow arrow
                && arrow.getOwner() == attacker
                && arrow.getPickupItemStackOrigin().getItem() instanceof ArrowItem) {
            var ammo = selectedBigGame(arrow.getPickupItemStackOrigin());
            if (ammo != null && (best == null || ammo.mastery() > best.mastery())) best = ammo;
        }
        return best;
    }

    private static LauncherReloadMasteryEvents.Branch selectedBigGame(ItemStack item) {
        var branch = LauncherReloadMasteryEvents.branch(item, "minecraft:looting");
        return branch != null && branch.choice() == 2 ? branch : null;
    }

    public static float rareRoll(float vanillaRoll, LootContext context) {
        var branch = bigGame(context);
        return branch == null ? vanillaRoll : (float)(vanillaRoll / (1.10D + 0.20D * branch.progress()));
    }

    public static int commonBonus(int actualVanillaBonus, LootContext context) {
        if (actualVanillaBonus <= 0 || bigGame(context) == null) return actualVanillaBonus;
        // Remove25% in expectation from the real Looting-added count, including
        // fractional rounding. The recipe/table's ordinary base count is untouched.
        double kept = actualVanillaBonus * 0.75D;
        int whole = (int)Math.floor(kept);
        return whole + (context.getRandom().nextFloat() < kept - whole ? 1 : 0);
    }
}
