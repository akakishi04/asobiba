package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.client.SnowGolemTiltClient;
import net.minecraft.client.model.SnowGolemModel;
import net.minecraft.client.model.geom.ModelPart;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Vanilla's pumpkin layer already uses this head transform, including its outline path. */
@Mixin(SnowGolemModel.class)
public abstract class SnowGolemTiltModelMixin {
    @Shadow @Final private ModelPart head;

    @Inject(method = "setupAnim", at = @At("TAIL"))
    private void asobibatweaks$headTilt(Entity entity, float limbSwing, float limbSwingAmount, float ageInTicks,
                                      float netHeadYaw, float headPitch, CallbackInfo ci) {
        // Vanilla never resets zRot. Always assign, including zero for the next shared-model entity.
        head.zRot = SnowGolemTiltClient.roll(entity);
    }
}
