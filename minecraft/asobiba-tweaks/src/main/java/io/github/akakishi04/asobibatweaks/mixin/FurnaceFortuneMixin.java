package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.feature.EnchantedWorkBlockSavedData;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.registries.Registries;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.item.enchantment.EnchantmentHelper;
import net.minecraft.world.item.enchantment.Enchantments;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.entity.AbstractFurnaceBlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Add precisely one recipe output with a 5%-per-Fortune-level roll,
 * only after the vanilla furnace actually consumed a recipe ingredient.
 */
@Mixin(AbstractFurnaceBlockEntity.class)
public abstract class FurnaceFortuneMixin {
    @Unique private int asobibatweaks$beforeInputCount;
    @Unique private int asobibatweaks$beforeOutputCount;

    @Inject(method = "serverTick", at = @At("HEAD"))
    private static void asobibatweaks$rememberCookingState(
            Level level, BlockPos position, BlockState state,
            AbstractFurnaceBlockEntity furnace, CallbackInfo ci) {
        FurnaceFortuneMixin self = (FurnaceFortuneMixin)(Object)furnace;
        self.asobibatweaks$beforeInputCount = furnace.getItem(0).getCount();
        self.asobibatweaks$beforeOutputCount = furnace.getItem(2).getCount();
    }

    @Inject(method = "serverTick", at = @At("TAIL"))
    private static void asobibatweaks$bonusSmeltedOutput(
            Level level, BlockPos position, BlockState state,
            AbstractFurnaceBlockEntity furnace, CallbackInfo ci) {
        if (!AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                || !(level instanceof ServerLevel server)) return;
        FurnaceFortuneMixin self = (FurnaceFortuneMixin)(Object)furnace;
        ItemStack output = furnace.getItem(2);
        if (output.isEmpty() || self.asobibatweaks$beforeInputCount <= furnace.getItem(0).getCount()
                || output.getCount() <= self.asobibatweaks$beforeOutputCount
                || output.getCount() >= output.getMaxStackSize()) return;

        ItemStack blockItem = EnchantedWorkBlockSavedData.get(server)
                .peek(position.asLong());
        if (blockItem.isEmpty()) return;
        Holder<Enchantment> fortune = server.registryAccess()
                .lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.FORTUNE);
        int fortuneLevel = Math.max(0, Math.min(10,
                EnchantmentHelper.getItemEnchantmentLevel(fortune, blockItem)));
        if (fortuneLevel > 0
                && server.getRandom().nextDouble() < 0.05D * fortuneLevel) {
            output.grow(1);
            furnace.setChanged();
        }
    }
}
