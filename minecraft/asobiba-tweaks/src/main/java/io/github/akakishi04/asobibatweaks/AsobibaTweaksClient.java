package io.github.akakishi04.asobibatweaks;

import io.github.akakishi04.asobibatweaks.client.EnchantingScreenEvents;
import io.github.akakishi04.asobibatweaks.client.NetherFishRenderer;
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
        modBus.addListener(this::registerRenderers);
        NeoForge.EVENT_BUS.register(new EnchantingScreenEvents());
    }

    private void registerRenderers(EntityRenderersEvent.RegisterRenderers event) {
        event.registerEntityRenderer(AsobibaRegistries.LAVA_MINNOW.get(), NetherFishRenderer::new);
        event.registerEntityRenderer(AsobibaRegistries.EMBERFIN.get(), NetherFishRenderer::new);
        event.registerEntityRenderer(AsobibaRegistries.BASALT_EEL.get(), NetherFishRenderer::new);
    }
}
