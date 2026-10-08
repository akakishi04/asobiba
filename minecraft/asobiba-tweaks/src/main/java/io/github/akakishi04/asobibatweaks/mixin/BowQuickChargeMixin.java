package io.github.akakishi04.asobibatweaks.mixin;

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
import org.spongepowered.asm.mixin.injection.ModifyArg;

/**
 * Applies the accepted Bow-side Quick Charge effect at the exact vanilla
 * power calculation point. This does not alter projectile base damage and
 * does not affect Crossbow charging (which has its own native behavior).
 */
@Mixin(BowItem.class)
public abstract class BowQuickChargeMixin {
    @ModifyArg(
            method = "releaseUsing",
            at = @At(
                    value = "INVOKE",
                    target = "Lnet/minecraft/world/item/BowItem;getPowerForTime(I)F"
            ),
            index = 0
    )
    private int asobibatweaks$adjustBowDrawForQuickCharge(
            int vanillaTicks, ItemStack bow, Level level, LivingEntity shooter, int timeLeft) {
        if (!bow.is(Items.BOW) || vanillaTicks <= 0) return vanillaTicks;

        Holder<Enchantment> quickCharge = level.registryAccess()
                .lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.QUICK_CHARGE);
        int enchantLevel = Math.min(10,
                Math.max(0, EnchantmentHelper.getItemEnchantmentLevel(quickCharge, bow)));
        if (enchantLevel == 0) return vanillaTicks;

        // I-V: -8% each; VI-X: -4% each. Level X: 40% of vanilla.
        double remainingFraction = Math.max(
                0.40D,
                1.0D - 0.08D * Math.min(enchantLevel, 5)
                        - 0.04D * Math.max(0, enchantLevel - 5)
        );
        // getPowerForTime reaches a full charge at a virtual 20 ticks.
        // Bound the input to prevent overflow at extreme out-of-band levels.
        return Math.min(20, (int)Math.round(vanillaTicks / remainingFraction));
    }
}
