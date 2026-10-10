package io.github.akakishi04.asobibatweaks.client;

import com.mojang.blaze3d.vertex.PoseStack;
import io.github.akakishi04.asobibatweaks.AsobibaRegistries;
import io.github.akakishi04.asobibatweaks.entity.NetherFishEntity;
import net.minecraft.client.model.SalmonModel;
import net.minecraft.client.model.geom.ModelLayers;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.client.renderer.entity.MobRenderer;
import net.minecraft.resources.ResourceLocation;

public final class NetherFishRenderer extends MobRenderer<NetherFishEntity, SalmonModel<NetherFishEntity>> {
    private static final ResourceLocation TEXTURE =
            ResourceLocation.fromNamespaceAndPath("minecraft", "textures/entity/fish/salmon.png");

    public NetherFishRenderer(EntityRendererProvider.Context context) {
        super(context, new SalmonModel<>(context.bakeLayer(ModelLayers.SALMON)), 0.22F);
    }

    @Override
    public ResourceLocation getTextureLocation(NetherFishEntity entity) {
        return TEXTURE;
    }

    @Override
    protected void scale(NetherFishEntity entity, PoseStack poseStack, float partialTick) {
        if (entity.getType() == AsobibaRegistries.LAVA_MINNOW.get()) {
            poseStack.scale(0.72F, 0.62F, 0.72F);
        } else if (entity.getType() == AsobibaRegistries.EMBERFIN.get()) {
            poseStack.scale(1.05F, 0.90F, 1.05F);
        } else {
            poseStack.scale(1.45F, 0.72F, 0.82F);
        }
    }
}
