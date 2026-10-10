package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.entity.projectile.AbstractArrow;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.EntityJoinLevelEvent;
import net.neoforged.neoforge.event.entity.living.LivingIncomingDamageEvent;

/** The three accepted launcher-side Power mastery specializations. */
public final class PowerMasteryEvents {
    private static final String POWER = "minecraft:power";
    private static final String ORIGIN_X = "asobibatweaks_power_origin_x";
    private static final String ORIGIN_Y = "asobibatweaks_power_origin_y";
    private static final String ORIGIN_Z = "asobibatweaks_power_origin_z";
    private static final String LAUNCH_SPEED = "asobibatweaks_power_launch_speed";

    @SubscribeEvent
    public void onProjectileSpawn(EntityJoinLevelEvent event) {
        if (event.getLevel().isClientSide()
                || !(event.getEntity() instanceof AbstractArrow arrow)) return;

        // Flight origin and initial speed are recorded once, before air drag.
        CompoundTag state = arrow.getPersistentData();
        if (state.contains(ORIGIN_X)) return;
        state.putDouble(ORIGIN_X, arrow.getX());
        state.putDouble(ORIGIN_Y, arrow.getY());
        state.putDouble(ORIGIN_Z, arrow.getZ());
        state.putDouble(LAUNCH_SPEED, arrow.getDeltaMovement().length());
    }

    @SubscribeEvent
    public void onProjectileDamage(LivingIncomingDamageEvent event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getAmount() <= 0.0F
                || !(event.getSource().getDirectEntity() instanceof AbstractArrow arrow)
                || arrow.level().isClientSide()) return;

        ItemStack launcher = event.getSource().getWeaponItem();
        if (launcher == null || launcher.isEmpty()) return;

        Branch power = branch(launcher);
        if (power == null) return;
        double strength = (Math.min(100, power.mastery()) - 50) / 50.0D;
        double bonus = 0.0D;
        CompoundTag flight = arrow.getPersistentData();

        if (power.index() == 0) {
            if (!flight.contains(ORIGIN_X)) return;
            double dx = arrow.getX() - flight.getDouble(ORIGIN_X);
            double dy = arrow.getY() - flight.getDouble(ORIGIN_Y);
            double dz = arrow.getZ() - flight.getDouble(ORIGIN_Z);
            double distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
            if (distance >= 16.0D) {
                double maxBonus = 0.05D + 0.15D * strength;
                bonus = maxBonus * Math.min(1.0D, (distance - 16.0D) / 32.0D);
            }
        } else if (power.index() == 1) {
            // Crossbows fire only after loading, so every legitimate Crossbow
            // arrow shot counts as deliberately fully charged.
            boolean complete = launcher.is(Items.CROSSBOW)
                    || launcher.is(Items.BOW)
                    && flight.getDouble(LAUNCH_SPEED) >= 2.85D;
            if (complete) bonus = 0.05D + 0.10D * strength;
        } else if (power.index() == 2 && launcher.is(Items.BOW)) {
            // A partial draw is still weaker than full draw after this branch.
            double ratio = Math.min(1.0D, Math.max(0.10D,
                    flight.getDouble(LAUNCH_SPEED) / 3.0D));
            if (ratio < 0.95D) {
                double recoveredPenalty = 0.15D + 0.30D * strength;
                bonus = Math.min(2.0D,
                        recoveredPenalty * (1.0D - ratio) / ratio);
            }
        }

        if (bonus > 0.0D) {
            event.setAmount((float)Math.min(Float.MAX_VALUE,
                    (double)event.getAmount() * (1.0D + bonus)));
        }
    }

    private static Branch branch(ItemStack stack) {
        for (var enchanted : EnchantmentMasteryData.enchantments(stack).keySet()) {
            if (!POWER.equals(EnchantmentMasteryData.id(enchanted))) continue;
            int mastery = EnchantmentMasteryData.getMastery(stack, enchanted);
            int choice = EnchantmentMasteryData.getBranch(stack, enchanted);
            return mastery >= 50 && choice >= 0 && choice <= 2
                    ? new Branch(mastery, choice) : null;
        }
        return null;
    }

    private record Branch(int mastery, int index) {}
}
