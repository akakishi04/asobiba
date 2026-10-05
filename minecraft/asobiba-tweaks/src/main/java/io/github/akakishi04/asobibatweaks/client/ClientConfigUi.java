package io.github.akakishi04.asobibatweaks.client;

import net.neoforged.fml.ModContainer;
import net.neoforged.neoforge.client.gui.ConfigurationScreen;
import net.neoforged.neoforge.client.gui.IConfigScreenFactory;

public final class ClientConfigUi {
    private ClientConfigUi() {
    }

    public static void register(ModContainer container) {
        container.registerExtensionPoint(
                IConfigScreenFactory.class,
                (minecraft, parent) -> new ConfigurationScreen(container, parent)
        );
    }
}
