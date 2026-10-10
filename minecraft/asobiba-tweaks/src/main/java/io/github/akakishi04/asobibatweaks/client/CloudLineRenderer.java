package io.github.akakishi04.asobibatweaks.client;

import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.BufferBuilder;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.MeshData;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.Tesselator;
import com.mojang.blaze3d.vertex.VertexBuffer;
import com.mojang.blaze3d.vertex.VertexFormat;
import io.github.akakishi04.asobibatweaks.feature.CloudLineState;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import net.minecraft.client.CloudStatus;
import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.client.renderer.RenderStateShard;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.ShaderInstance;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;

/** Small cloud-stage mesh, using vanilla weather tint, fog and Fabulous's cloud target. */
final class CloudLineRenderer {
    // A solid cloud-face texel keeps the geometry square while reusing vanilla cloud
    // fog, weather tint, alpha discard and framebuffer behavior without a custom shader.
    private static final RenderType CLOUD_LINE = RenderType.create("asobibatweaks_cloud_line",
            DefaultVertexFormat.POSITION_TEX_COLOR_NORMAL, VertexFormat.Mode.QUADS, 4096, false, false,
            RenderType.CompositeState.builder()
                    .setShaderState(RenderStateShard.RENDERTYPE_CLOUDS_SHADER)
                    .setTextureState(new RenderStateShard.TextureStateShard(ResourceLocation.fromNamespaceAndPath(
                            AsobibaTweaks.MOD_ID, "textures/misc/cloud_line.png"), false, false))
                    .setTransparencyState(RenderStateShard.TRANSLUCENT_TRANSPARENCY)
                    .setDepthTestState(RenderStateShard.LEQUAL_DEPTH_TEST)
                    .setWriteMaskState(RenderStateShard.COLOR_DEPTH_WRITE)
                    .setCullState(RenderStateShard.NO_CULL)
                    .setOutputState(RenderStateShard.CLOUDS_TARGET)
                    .createCompositeState(false));
    private static VertexBuffer buffer;

    private CloudLineRenderer() {}

    static void render(List<CloudLineState.Cloud> clouds, CloudStatus quality, Vec3 tint, float height,
            PoseStack poses, Matrix4f view, Matrix4f projection, double cameraX, double cameraY, double cameraZ) {
        if (clouds.isEmpty()) return;
        List<CloudLineState.Cloud> visible = new ArrayList<>(clouds);
        visible.removeIf(cloud -> cloud.alpha() < 0.1F
                || Math.hypot(cloud.x() - cameraX, cloud.z() - cameraZ) > 384.0D);
        if (visible.isEmpty()) return;
        // One bounded row, at most 5 * 3 visible faces. Sort whole non-overlapping squares.
        visible.sort(Comparator.comparingDouble((CloudLineState.Cloud cloud) ->
                square(cloud.x() - cameraX) + square(cloud.z() - cameraZ)).reversed());
        BufferBuilder vertices = Tesselator.getInstance().begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.POSITION_TEX_COLOR_NORMAL);
        for (var cloud : visible) {
            float x0 = (float) (cloud.x() - cloud.size() / 2.0D - cameraX);
            float x1 = (float) (cloud.x() + cloud.size() / 2.0D - cameraX);
            float z0 = (float) (cloud.z() - cloud.size() / 2.0D - cameraZ);
            float z1 = (float) (cloud.z() + cloud.size() / 2.0D - cameraZ);
            // A shallow layer immediately below normal clouds avoids coplanar flicker.
            float bottom = (float) (height - 4.0D - cameraY);
            float top = bottom + 4.0F;
            if (quality == CloudStatus.FAST) {
                quad(vertices, tint, cloud.alpha(), 1.0F,
                        x0, bottom, z0, x1, bottom, z0, x1, bottom, z1, x0, bottom, z1);
                continue;
            }
            if (bottom >= 0.0F) quad(vertices, tint, cloud.alpha(), 0.7F,
                    x0, bottom, z0, x1, bottom, z0, x1, bottom, z1, x0, bottom, z1);
            if (top <= 0.0F) quad(vertices, tint, cloud.alpha(), 1.0F,
                    x0, top, z0, x1, top, z0, x1, top, z1, x0, top, z1);
            if (x0 >= 0.0F) quad(vertices, tint, cloud.alpha(), 0.9F,
                    x0, bottom, z0, x0, bottom, z1, x0, top, z1, x0, top, z0);
            if (x1 <= 0.0F) quad(vertices, tint, cloud.alpha(), 0.9F,
                    x1, bottom, z0, x1, bottom, z1, x1, top, z1, x1, top, z0);
            if (z0 >= 0.0F) quad(vertices, tint, cloud.alpha(), 0.8F,
                    x0, bottom, z0, x1, bottom, z0, x1, top, z0, x0, top, z0);
            if (z1 <= 0.0F) quad(vertices, tint, cloud.alpha(), 0.8F,
                    x0, bottom, z1, x1, bottom, z1, x1, top, z1, x0, top, z1);
        }
        MeshData mesh = vertices.build();
        if (mesh == null) return;
        if (buffer == null) buffer = new VertexBuffer(VertexBuffer.Usage.DYNAMIC);
        ShaderInstance previousShader = RenderSystem.getShader();
        float[] previousColor = RenderSystem.getShaderColor().clone();
        int previousTexture = RenderSystem.getShaderTexture(0);
        poses.pushPose();
        boolean setup = false;
        try {
            poses.mulPose(view);
            buffer.bind();
            buffer.upload(mesh); // upload closes mesh, including its failure path.
            CLOUD_LINE.setupRenderState();
            setup = true;
            RenderSystem.setShaderColor(1.0F, 1.0F, 1.0F, 1.0F);
            buffer.drawWithShader(poses.last().pose(), projection, RenderSystem.getShader());
        } finally {
            VertexBuffer.unbind();
            if (setup) CLOUD_LINE.clearRenderState();
            RenderSystem.setShaderColor(previousColor[0], previousColor[1], previousColor[2], previousColor[3]);
            RenderSystem.setShader(() -> previousShader);
            RenderSystem.setShaderTexture(0, previousTexture);
            poses.popPose();
        }
    }

    /** No GPU resources survive an idle animation, invalid camera, unload or disconnect. */
    static void release() {
        VertexBuffer old = buffer;
        buffer = null;
        if (old == null) return;
        if (RenderSystem.isOnRenderThread()) old.close();
        else RenderSystem.recordRenderCall(old::close);
    }

    private static double square(double value) {
        return value * value;
    }

    private static void quad(BufferBuilder vertices, Vec3 tint, float alpha, float shade,
            float x0, float y0, float z0, float x1, float y1, float z1,
            float x2, float y2, float z2, float x3, float y3, float z3) {
        float red = (float) tint.x * shade;
        float green = (float) tint.y * shade;
        float blue = (float) tint.z * shade;
        vertices.addVertex(x0, y0, z0).setUv(0.5F, 0.5F).setColor(red, green, blue, alpha).setNormal(0.0F, 1.0F, 0.0F);
        vertices.addVertex(x1, y1, z1).setUv(0.5F, 0.5F).setColor(red, green, blue, alpha).setNormal(0.0F, 1.0F, 0.0F);
        vertices.addVertex(x2, y2, z2).setUv(0.5F, 0.5F).setColor(red, green, blue, alpha).setNormal(0.0F, 1.0F, 0.0F);
        vertices.addVertex(x3, y3, z3).setUv(0.5F, 0.5F).setColor(red, green, blue, alpha).setNormal(0.0F, 1.0F, 0.0F);
    }
}
