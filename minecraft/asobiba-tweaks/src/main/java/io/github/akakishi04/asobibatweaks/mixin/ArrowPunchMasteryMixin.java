package io.github.akakishi04.asobibatweaks.mixin;

import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.llamalad7.mixinextras.injector.wrapoperation.WrapOperation;
import io.github.akakishi04.asobibatweaks.feature.PunchMasteryService;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.projectile.AbstractArrow;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;

@Mixin(AbstractArrow.class)
public abstract class ArrowPunchMasteryMixin {
    @WrapOperation(method = "doKnockback", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/world/entity/LivingEntity;push(DDD)V"))
    private void asobibatweaks$actualPunch(LivingEntity target, double x, double y, double z, Operation<Void> original) {
        Vec3 impulse = PunchMasteryService.impulse((AbstractArrow)(Object)this, target, new Vec3(x, y, z));
        original.call(target, impulse.x, impulse.y, impulse.z);
    }
}
