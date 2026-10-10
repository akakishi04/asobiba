package io.github.akakishi04.asobibatweaks.mixin;

import com.llamalad7.mixinextras.injector.ModifyExpressionValue;
import io.github.akakishi04.asobibatweaks.feature.SweepingMasteryEvents;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.phys.AABB;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.At;

/** Modify only the actual area hitbox passed into the vanilla sweep loop. */
@Mixin(Player.class)
public abstract class PlayerSweepingRangeMixin {
    @Inject(method = "attack", at = @At(value = "INVOKE", target =
            "Lnet/minecraft/world/entity/player/Player;resetAttackStrengthTicker()V", shift = At.Shift.AFTER))
    private void asobibatweaks$recoverAfterRhythmAttack(Entity target, CallbackInfo ci) {
        LivingAttackRecoveryAccessor ticker = (LivingAttackRecoveryAccessor)this;
        ticker.asobibatweaks$setAttackStrengthTicker(ticker.asobibatweaks$getAttackStrengthTicker()
                + SweepingMasteryEvents.consumeRecoveryTicks((Player)(Object)this));
    }

    @ModifyExpressionValue(method = "attack",
            at = @At(value = "INVOKE", target =
                    "Lnet/minecraft/world/item/ItemStack;getSweepHitBox(Lnet/minecraft/world/entity/player/Player;Lnet/minecraft/world/entity/Entity;)Lnet/minecraft/world/phys/AABB;"))
    private AABB asobibatweaks$sweepMasteryRange(AABB original, Entity target) {
        return SweepingMasteryEvents.adjustHitBox(
                (Player)(Object)this, target, original);
    }
}
