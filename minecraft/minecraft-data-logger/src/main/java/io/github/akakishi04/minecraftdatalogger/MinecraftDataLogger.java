package io.github.akakishi04.minecraftdatalogger;

import io.github.akakishi04.minecraftdatalogger.client.ClientConfigUi;
import io.github.akakishi04.minecraftdatalogger.capture.LoggerEvents;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.fml.ModContainer;
import net.neoforged.fml.common.Mod;
import net.neoforged.fml.config.ModConfig;
import net.neoforged.fml.loading.FMLEnvironment;
import net.neoforged.neoforge.common.NeoForge;

@Mod(MinecraftDataLogger.MOD_ID)
public final class MinecraftDataLogger {
    public static final String MOD_ID = "minecraftdatalogger";

    public MinecraftDataLogger(ModContainer container) {
        container.registerConfig(ModConfig.Type.COMMON, LoggerConfig.SPEC);
        NeoForge.EVENT_BUS.register(new LoggerEvents());

        if (FMLEnvironment.dist == Dist.CLIENT) {
            ClientConfigUi.register(container);
        }
    }
}
