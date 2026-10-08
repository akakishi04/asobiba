package io.github.akakishi04.asobibatweaks.mixin;

import com.llamalad7.mixinextras.injector.ModifyExpressionValue;
import io.github.akakishi04.asobibatweaks.feature.UnbreakingMasteryEvents;
import io.github.akakishi04.asobibatweaks.feature.InfinityMasteryEvents;
import io.github.akakishi04.asobibatweaks.feature.MendingExtendedEvents;
import java.util.function.Consumer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;

/**
 * Compose with vanilla and other durability processing rather than replacing
 * the original EnchantmentHelper call. A broken item cannot be resurrected by
 * a later tick-based durability refund.
 */
@Mixin(ItemStack.class)
public abstract class UnbreakingDurabilityMixin {
    @ModifyExpressionValue(
        method = "hurtAndBreak(ILnet/minecraft/server/level/ServerLevel;Lnet/minecraft/world/entity/LivingEntity;Ljava/util/function/Consumer;)V",
        at = @At(
            value = "INVOKE",
            target = "Lnet/minecraft/world/item/enchantment/EnchantmentHelper;processDurabilityChange(Lnet/minecraft/server/level/ServerLevel;Lnet/minecraft/world/item/ItemStack;I)I"
        )
    )
    private int asobibatweaks$applyMasteryAfterVanilla(
            int postVanilla, int incomingDamage, ServerLevel level,
            LivingEntity wearer, Consumer<Item> onBreak) {
        ItemStack stack = (ItemStack)(Object)this;
        int afterUnbreaking = UnbreakingMasteryEvents.adjustDurability(
                stack, level, wearer, postVanilla);
        int afterInfinity = InfinityMasteryEvents.adjustDurability(stack, level, wearer, afterUnbreaking);
        return MendingExtendedEvents.absorb(stack, afterInfinity);
    }
}
