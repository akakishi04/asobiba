package io.github.akakishi04.asobibatweaks.mixin;

import com.llamalad7.mixinextras.injector.ModifyExpressionValue;
import net.minecraft.core.Holder;
import net.minecraft.core.registries.Registries;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.BowItem;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.item.enchantment.EnchantmentHelper;
import net.minecraft.world.item.enchantment.Enchantments;
import net.minecraft.world.level.Level;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;

/** Bow Quick Charge: scale the actual bow power curve without changing base damage. */
@Mixin(BowItem.class)
public abstract class BowQuickChargeMixin {
    @ModifyExpressionValue(
            method = "releaseUsing",
            at = @At(
                    value = "INVOKE",
                    target = "Lnet/minecraft/world/item/BowItem;getPowerForTime(I)F"
            )
    )
    private float asobibatweaks$quickChargeBowPower(
            float originalPower, ItemStack bow, Level level,
            LivingEntity shooter, int timeLeft) {
        if (!bow.is(Items.BOW) || originalPower >= 1.0F || originalPower <= 0.0F) {
            return originalPower;
        }

        Holder<Enchantment> quickCharge = level.registryAccess()
                .lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.QUICK_CHARGE);
        int enchantLevel = Math.min(10,
                Math.max(0, EnchantmentHelper.getItemEnchantmentLevel(quickCharge, bow)));
        if (enchantLevel == 0) return originalPower;

        // Vanilla bow power: (x*x + 2*x) / 3, x=drawTicks/20.
        // The inverse preserves the draw value after NeoForge's ArrowLoose hook
        // without requiring a local-variable capture from that patched method.
        double normalizedDraw = Math.sqrt(1.0D + 3.0D * originalPower) - 1.0D;
        double remainingFraction = Math.max(0.40D,
                1.0D - 0.08D * Math.min(enchantLevel, 5)
                        - 0.04D * Math.max(0, enchantLevel - 5));
        double accelerated = normalizedDraw / remainingFraction;
        return (float)Math.min(1.0D, (accelerated * accelerated + 2.0D * accelerated) / 3.0D);
    }
}
