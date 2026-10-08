package io.github.akakishi04.asobibatweaks.mixin;

import net.minecraft.core.Holder;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.item.enchantment.Enchantments;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * The accepted shared launcher enchantment pool permits Infinity and Mending
 * together. Do not change compatibility for unrelated enchantment pairs.
 *
 * Enchantment.areCompatible has no ItemStack argument, so vanilla enchantment
 * acquisition checks the pair globally; the valid launcher items are still
 * bounded by the normal enchantable/bow and enchantable/crossbow item tags.
 */
@Mixin(Enchantment.class)
public abstract class LauncherEnchantmentCompatibilityMixin {
    @Inject(method = "areCompatible", at = @At("HEAD"), cancellable = true)
    private static void asobibatweaks$allowInfinityMending(
            Holder<Enchantment> first, Holder<Enchantment> second,
            CallbackInfoReturnable<Boolean> cir) {
        if ((first.is(Enchantments.INFINITY) && second.is(Enchantments.MENDING))
                || (first.is(Enchantments.MENDING) && second.is(Enchantments.INFINITY))) {
            cir.setReturnValue(true);
        }
    }
}
