package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.client.NodGestureClient;
import net.minecraft.client.model.VillagerModel;
import net.minecraft.client.model.geom.ModelPart;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(VillagerModel.class)
public abstract class VillagerNodModelMixin {
    @Shadow @Final private ModelPart head;

    @Inject(method = "setupAnim", at = @At("TAIL"))
    private void asobibatweaks$nod(Entity entity, float limbSwing, float limbSwingAmount, float ageInTicks,
                                  float netHeadYaw, float headPitch, CallbackInfo ci) {
        head.xRot += NodGestureClient.pitch(entity, ageInTicks);
    }
}
