package io.github.akakishi04.asobibatweaks.mixin;

import com.mojang.blaze3d.vertex.PoseStack;
import io.github.akakishi04.asobibatweaks.client.CloudLineClient;
import net.minecraft.client.renderer.LevelRenderer;
import org.joml.Matrix4f;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Draw at vanilla's cloud stage, before Fabulous composites its clouds framebuffer. */
@Mixin(LevelRenderer.class)
public abstract class CloudLineRenderMixin {
    @Inject(method = "renderClouds", at = @At("TAIL"))
    private void asobibatweaks$cloudLine(PoseStack poses, Matrix4f view, Matrix4f projection,
            float partialTick, double cameraX, double cameraY, double cameraZ, CallbackInfo ci) {
        CloudLineClient.render(poses, view, projection, partialTick, cameraX, cameraY, cameraZ);
    }
}
