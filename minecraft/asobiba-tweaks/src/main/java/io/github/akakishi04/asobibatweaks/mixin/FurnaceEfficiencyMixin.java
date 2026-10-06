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
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(AbstractFurnaceBlockEntity.class)
public abstract class FurnaceEfficiencyMixin {
    @Shadow int cookingProgress;
    @Shadow int cookingTotalTime;

    @Unique private int asobibatweaks$progressBeforeTick;
    @Unique private double asobibatweaks$extraProgress;

    @Inject(method = "serverTick", at = @At("HEAD"))
    private static void asobibatweaks$captureProgress(
            Level level,
            BlockPos pos,
            BlockState state,
            AbstractFurnaceBlockEntity furnace,
            CallbackInfo ci
    ) {
        FurnaceEfficiencyMixin self = (FurnaceEfficiencyMixin)(Object)furnace;
        self.asobibatweaks$progressBeforeTick = self.cookingProgress;
    }

    @Inject(method = "serverTick", at = @At("TAIL"))
    private static void asobibatweaks$applyEfficiency(
            Level level,
            BlockPos pos,
            BlockState state,
            AbstractFurnaceBlockEntity furnace,
            CallbackInfo ci
    ) {
        if (!AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                || !(level instanceof ServerLevel serverLevel)) {
            return;
        }

        FurnaceEfficiencyMixin self = (FurnaceEfficiencyMixin)(Object)furnace;

        // Only accelerate a tick in which vanilla actually advanced an active recipe.
        if (self.cookingProgress <= self.asobibatweaks$progressBeforeTick
                || self.cookingTotalTime <= 0) {
            return;
        }

        ItemStack placedStack = EnchantedWorkBlockSavedData.get(serverLevel).peek(pos.asLong());
        if (placedStack.isEmpty()) {
            return;
        }

        Holder<Enchantment> efficiency = serverLevel.registryAccess()
                .lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.EFFICIENCY);
        int levelValue = Math.min(10,
                EnchantmentHelper.getItemEnchantmentLevel(efficiency, placedStack));
        if (levelValue <= 0) {
            return;
        }

        // +10% processing speed per level: I=1.1x ... X=2.0x.
        self.asobibatweaks$extraProgress += levelValue * 0.1D;
        int wholeExtra = (int)self.asobibatweaks$extraProgress;
        if (wholeExtra <= 0) {
            return;
        }

        self.asobibatweaks$extraProgress -= wholeExtra;
        self.cookingProgress = Math.min(
                self.cookingTotalTime - 1,
                self.cookingProgress + wholeExtra
        );
    }
}
