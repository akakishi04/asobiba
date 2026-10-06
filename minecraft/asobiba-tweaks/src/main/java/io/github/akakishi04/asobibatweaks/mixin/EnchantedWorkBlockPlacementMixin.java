package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.feature.EnchantedWorkBlockSavedData;
import io.github.akakishi04.asobibatweaks.feature.ExtendedEnchantingTargets;
import net.minecraft.core.component.DataComponents;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.item.enchantment.EnchantmentHelper;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(BlockItem.class)
public abstract class EnchantedWorkBlockPlacementMixin {
    @Inject(
            method = "place",
            at = @At(
                    value = "INVOKE",
                    target = "Lnet/minecraft/world/item/ItemStack;consume(ILnet/minecraft/world/entity/LivingEntity;)V"
            )
    )
    private void asobibatweaks$rememberEnchantments(
            BlockPlaceContext context,
            CallbackInfoReturnable<InteractionResult> cir
    ) {
        if (!AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                || !(context.getLevel() instanceof ServerLevel level)) {
            return;
        }

        ItemStack stack = context.getItemInHand();
        if (!ExtendedEnchantingTargets.isExtendedBlockTarget(stack)) {
            return;
        }

        boolean hasEnchantments = !EnchantmentHelper.getEnchantmentsForCrafting(stack).isEmpty();
        boolean hasMasteryData = stack.has(DataComponents.CUSTOM_DATA);
        if (hasEnchantments || hasMasteryData) {
            EnchantedWorkBlockSavedData.get(level).put(context.getClickedPos().asLong(), stack);
        } else {
            EnchantedWorkBlockSavedData.get(level).remove(context.getClickedPos().asLong());
        }
    }
}
