package io.github.akakishi04.asobibatweaks;

import io.github.akakishi04.asobibatweaks.client.EnchantingScreenEvents;
import io.github.akakishi04.asobibatweaks.client.FrostWalkerToggleClientEvents;
import io.github.akakishi04.asobibatweaks.client.FletchingCopyScreen;
import io.github.akakishi04.asobibatweaks.client.NetherFishRenderer;
import io.github.akakishi04.asobibatweaks.client.AfterimageDecoyRenderer;
import io.github.akakishi04.asobibatweaks.client.NodGestureClient;
import io.github.akakishi04.asobibatweaks.client.SnowGolemTiltClient;
import io.github.akakishi04.asobibatweaks.client.CloudLineClient;
import io.github.akakishi04.asobibatweaks.client.DailyPlayTimeClient;
import io.github.akakishi04.asobibatweaks.feature.NodGestureNetworking;
import io.github.akakishi04.asobibatweaks.feature.AfterimageDecoyRegistration;
import io.github.akakishi04.asobibatweaks.client.QuiverClientEvents;
import io.github.akakishi04.asobibatweaks.client.VillageStatusScreen;
import io.github.akakishi04.asobibatweaks.feature.VillageStatusNetworking;
import io.github.akakishi04.asobibatweaks.feature.QuiverNetworking;
import io.github.akakishi04.asobibatweaks.feature.FletchingCopyNetworking;
import io.github.akakishi04.asobibatweaks.feature.QuiverData;
import net.minecraft.client.Minecraft;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.ModContainer;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.client.event.EntityRenderersEvent;
import net.neoforged.neoforge.client.gui.ConfigurationScreen;
import net.neoforged.neoforge.client.gui.IConfigScreenFactory;
import net.neoforged.neoforge.common.NeoForge;

@Mod(value = AsobibaTweaks.MOD_ID, dist = Dist.CLIENT)
public final class AsobibaTweaksClient {
    public AsobibaTweaksClient(IEventBus modBus, ModContainer container) {
        container.registerExtensionPoint(IConfigScreenFactory.class, ConfigurationScreen::new);
        VillageStatusNetworking.installClientHandler(VillageStatusScreen::open);
        NodGestureNetworking.installClientHandler(NodGestureClient::accept);
        FletchingCopyNetworking.installClientHandler(FletchingCopyScreen::open);
        QuiverNetworking.installClientHandler(payload -> {
            if (Minecraft.getInstance().player != null) {
                QuiverData.installSnapshot(Minecraft.getInstance().player, payload.snapshot());
            }
        });
        modBus.addListener(this::registerRenderers);
        NeoForge.EVENT_BUS.register(new EnchantingScreenEvents());
        NeoForge.EVENT_BUS.register(new QuiverClientEvents());
        NeoForge.EVENT_BUS.register(new SnowGolemTiltClient());
        NeoForge.EVENT_BUS.register(new CloudLineClient());
        DailyPlayTimeClient.register();
        NeoForge.EVENT_BUS.register(new FrostWalkerToggleClientEvents());
    }

    private void registerRenderers(EntityRenderersEvent.RegisterRenderers event) {
        event.registerEntityRenderer(AfterimageDecoyRegistration.DECOY.get(), AfterimageDecoyRenderer::new);
        event.registerEntityRenderer(AsobibaRegistries.LAVA_MINNOW.get(), NetherFishRenderer::new);
        event.registerEntityRenderer(AsobibaRegistries.EMBERFIN.get(), NetherFishRenderer::new);
        event.registerEntityRenderer(AsobibaRegistries.BASALT_EEL.get(), NetherFishRenderer::new);
    }
}
