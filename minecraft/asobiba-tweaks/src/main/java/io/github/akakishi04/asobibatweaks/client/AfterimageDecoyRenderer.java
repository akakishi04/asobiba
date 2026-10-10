package io.github.akakishi04.asobibatweaks.client;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import io.github.akakishi04.asobibatweaks.entity.AfterimageDecoyEntity;
import net.minecraft.client.model.HumanoidModel;
import net.minecraft.client.model.geom.ModelLayers;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.entity.EntityRenderer;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;

/** Fixed translucent silhouette; no player skin request, equipment copy, name or identity. */
public final class AfterimageDecoyRenderer extends EntityRenderer<AfterimageDecoyEntity> {
    private static final ResourceLocation TEXTURE = ResourceLocation.withDefaultNamespace(
            "textures/entity/player/wide/steve.png");
    private final HumanoidModel<AfterimageDecoyEntity> model;

    public AfterimageDecoyRenderer(EntityRendererProvider.Context context) {
        super(context);
        model = new HumanoidModel<>(context.bakeLayer(ModelLayers.PLAYER));
        model.young = false;
        shadowRadius = 0.0F;
    }

    @Override
    public void render(AfterimageDecoyEntity entity, float yaw, float partialTick, PoseStack pose,
                       MultiBufferSource buffers, int light) {
        pose.pushPose();
        pose.mulPose(Axis.YP.rotationDegrees(180.0F - yaw));
        pose.scale(-1.0F, -1.0F, 1.0F);
        pose.translate(0.0F, -1.501F, 0.0F);
        model.setupAnim(entity, 0.0F, 0.0F, 0.0F, 0.0F, 0.0F);
        model.rightArm.xRot = -0.7F;
        model.leftArm.xRot = 0.7F;
        model.rightLeg.xRot = 0.45F;
        model.leftLeg.xRot = -0.45F;
        model.renderToBuffer(pose, buffers.getBuffer(RenderType.entityTranslucent(TEXTURE)),
                light, OverlayTexture.NO_OVERLAY, 0x7097DAFF);
        pose.popPose();
        // No labels, armor, held items or shadow. Vanilla entity tracking handles spawn/removal.
    }

    @Override
    public ResourceLocation getTextureLocation(AfterimageDecoyEntity entity) {
        return TEXTURE;
    }
}
