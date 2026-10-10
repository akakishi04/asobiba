package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.feature.MasteryFrostIceData;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.FrostedIceBlock;
import net.minecraft.world.level.block.state.BlockState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Delay vanilla melt attempts only for valid, protected mastery ice. */
@Mixin(FrostedIceBlock.class)
public abstract class FrostedIceLifetimeMixin {
    @Inject(method = "tick", at = @At("HEAD"), cancellable = true)
    private void asobibatweaks$preserveTrackedFrost(
            BlockState state, ServerLevel level, BlockPos position,
            RandomSource random, CallbackInfo ci) {
        if (state.is(Blocks.FROSTED_ICE)
                && MasteryFrostIceData.get(level).mustKeep(level, position)) {
            level.scheduleTick(position, Blocks.FROSTED_ICE, 40);
            ci.cancel();
        }
    }
}
