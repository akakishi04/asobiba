package io.github.akakishi04.asobibatweaks;

import io.github.akakishi04.asobibatweaks.client.ClientConfigUi;
import io.github.akakishi04.asobibatweaks.feature.GrowingItemsEvents;
import io.github.akakishi04.asobibatweaks.feature.PlayTimeLimitEvents;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.fml.ModContainer;
import net.neoforged.fml.common.Mod;
import net.neoforged.fml.config.ModConfig;
import net.neoforged.fml.loading.FMLEnvironment;
import net.neoforged.neoforge.common.NeoForge;

@Mod(AsobibaTweaks.MOD_ID)
public final class AsobibaTweaks {
    public static final String MOD_ID = "asobibatweaks";

    public AsobibaTweaks(ModContainer container) {
        container.registerConfig(ModConfig.Type.COMMON, AsobibaTweaksConfig.SPEC);

        NeoForge.EVENT_BUS.register(new GrowingItemsEvents());
        NeoForge.EVENT_BUS.register(new PlayTimeLimitEvents());

        if (FMLEnvironment.dist == Dist.CLIENT) {
            ClientConfigUi.register(container);
        }
    }
}
