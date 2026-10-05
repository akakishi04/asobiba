package io.github.akakishi04.minecraftdatalogger;

import net.neoforged.api.distmarker.Dist;
import net.neoforged.fml.ModContainer;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.client.gui.ConfigurationScreen;
import net.neoforged.neoforge.client.gui.IConfigScreenFactory;

@Mod(value = MinecraftDataLogger.MOD_ID, dist = Dist.CLIENT)
public final class MinecraftDataLoggerClient {
    public MinecraftDataLoggerClient(ModContainer container) {
        container.registerExtensionPoint(IConfigScreenFactory.class, ConfigurationScreen::new);
    }
}
