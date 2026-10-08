package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.feature.MendingLevelHelper;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.enchantment.EnchantmentHelper;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Vanilla Mending I=2 durability / XP.
 * II=3; III-X=4. IV-X add routing rather than more direct conversion.
 * Preserve the post-vanilla value for unmodified Mending I and no Mending.
 */
@Mixin(EnchantmentHelper.class)
public abstract class MendingXpRateMixin {
    @Inject(method = "modifyDurabilityToRepairFromXp", at = @At("RETURN"), cancellable = true)
    private static void asobibatweaks$higherMendingRepair(
            ServerLevel level, ItemStack stack, int xp,
            CallbackInfoReturnable<Integer> cir) {
        int mending = MendingLevelHelper.level(stack);
        if (mending <= 1 || xp <= 0) return;

        int extraPerXp = MendingLevelHelper.durabilityPerXp(mending) - 2;
        long updated = (long)cir.getReturnValue() + (long)extraPerXp * xp;
        cir.setReturnValue((int)Math.max(0L, Math.min(Integer.MAX_VALUE, updated)));
    }
}
