package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.projectile.AbstractArrow;
import net.minecraft.world.entity.projectile.ThrownTrident;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.enchantment.EnchantmentHelper;
import net.minecraft.world.phys.Vec3;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;

/** Native trident sidegrades, layered after vanilla's own return acceleration.
 * Never creates an entity/item or changes pickup, owner, collision or return timing.
 */
public final class LoyaltyTridentMasteryEvents {
    private static final String LOYALTY = "minecraft:loyalty";
    private static final String RETURN_USED = "asobibatweaks_trident_loyalty_return_used";

    @SubscribeEvent
    public void onReturningTridentTick(EntityTickEvent.Post event) {
        if (!(event.getEntity() instanceof ThrownTrident trident)
                || !(trident.level() instanceof ServerLevel level)
                || trident.isRemoved() || !trident.isNoPhysics()
                || !(trident.getOwner() instanceof ServerPlayer owner)
                || !owner.isAlive() || owner.isSpectator() || owner.level() != level) return;

        ItemStack stack = trident.getPickupItemStackOrigin();
        int loyalty = Math.clamp(EnchantmentHelper.getTridentReturnToOwnerAcceleration(level, stack, trident), 0, 127);
        if (loyalty <= 0) return;
        // Award once to this physical throw when vanilla begins returning it.
        // The projectile's saved marker prevents save/reload from farming uses.
        if (trident.pickup == AbstractArrow.Pickup.ALLOWED
                && AsobibaTweaksConfig.GROWING_ENCHANTMENTS_ENABLED.getAsBoolean()
                && !trident.getPersistentData().getBoolean(RETURN_USED)) {
            trident.getPersistentData().putBoolean(RETURN_USED, true);
            for (var holder : EnchantmentMasteryData.enchantments(stack).keySet()) {
                if (LOYALTY.equals(EnchantmentMasteryData.id(holder))) {
                    EnchantmentMasteryData.addMastery(stack, holder, 1);
                    break;
                }
            }
        }

        var branch = LauncherReloadMasteryEvents.branch(stack, LOYALTY);
        if (branch == null) return;
        Vec3 offset = owner.getEyePosition().subtract(trident.position());
        if (offset.lengthSqr() < 0.0001D) return;
        Vec3 towardOwner = offset.normalize();
        Vec3 desired = towardOwner;
        if (branch.choice() == 1) {
            desired = LoyaltyArrowEvents.safeReturnDirection(trident, level, towardOwner,
                    4 + (int)Math.round(8.0D * branch.progress()));
        }
        Vec3 corrected = returnMotion(trident.getDeltaMovement(), towardOwner, desired,
                owner.getDeltaMovement(), loyalty, branch.choice(), branch.progress());
        trident.setDeltaMovement(corrected);
        trident.hurtMarked = true;
    }

    /** Vanilla uses v = 0.95*v + direction*(0.05*L), with terminal speed L.
     * Add only the branch's extra acceleration; never multiply all velocity each
     * tick, which would cause exponential acceleration. Keep branch speed bounded.
     */
    static Vec3 returnMotion(Vec3 vanilla, Vec3 towardOwner, Vec3 safeDirection,
                             Vec3 ownerMotion, int loyalty, int branch, double progress) {
        double growth = Math.max(0.0D, Math.min(1.0D, progress));
        double baseSpeed = Math.max(1, loyalty);
        double acceleration = 0.05D * baseSpeed;
        Vec3 corrected = vanilla;
        double speedCap = Math.max(baseSpeed, vanilla.length());
        if (branch == 0) {
            double bonus = 0.15D + 0.35D * growth;
            corrected = vanilla.add(towardOwner.scale(acceleration * bonus));
            speedCap = baseSpeed * (1.0D + bonus);
        } else if (branch == 1) {
            double steering = 1.25D + 0.50D * growth;
            // Replace the vanilla direction contribution and add the accepted
            // stronger steering. This spends no extra speed on obstacle detours.
            corrected = vanilla.subtract(towardOwner.scale(acceleration))
                    .add(safeDirection.scale(acceleration * steering));
            speedCap = vanilla.length();
        } else if (branch == 2 && ownerMotion.dot(towardOwner) > 0.10D) {
            corrected = vanilla.add(towardOwner.scale(acceleration * (0.20D + 0.40D * growth)));
            speedCap = baseSpeed * (1.10D + 0.20D * growth);
        }
        if (corrected.lengthSqr() > speedCap * speedCap && corrected.lengthSqr() > 0.0D)
            corrected = corrected.normalize().scale(speedCap);
        return corrected;
    }
}
