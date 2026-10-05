package io.github.akakishi04.asobibatweaks;

import io.github.akakishi04.asobibatweaks.feature.DailyFavorEvents;
import io.github.akakishi04.asobibatweaks.feature.EnchantmentTweaksEvents;
import io.github.akakishi04.asobibatweaks.feature.GrowingItemsEvents;
import io.github.akakishi04.asobibatweaks.feature.InteractionTweaksEvents;
import io.github.akakishi04.asobibatweaks.feature.MovementTweaksEvents;
import io.github.akakishi04.asobibatweaks.feature.PlayTimeLimitEvents;
import io.github.akakishi04.asobibatweaks.feature.PhysicsTransportEvents;
import io.github.akakishi04.asobibatweaks.feature.TransportTweaksEvents;
import io.github.akakishi04.asobibatweaks.feature.UniversalBondEvents;
import io.github.akakishi04.asobibatweaks.feature.WorldOddityEvents;
import net.neoforged.fml.ModContainer;
import net.neoforged.fml.common.Mod;
import net.neoforged.fml.config.ModConfig;
import net.neoforged.neoforge.common.NeoForge;

@Mod(AsobibaTweaks.MOD_ID)
public final class AsobibaTweaks {
    public static final String MOD_ID = "asobibatweaks";

    public AsobibaTweaks(ModContainer container) {
        container.registerConfig(ModConfig.Type.COMMON, AsobibaTweaksConfig.SPEC);
        NeoForge.EVENT_BUS.register(new GrowingItemsEvents());
        NeoForge.EVENT_BUS.register(new EnchantmentTweaksEvents());
        NeoForge.EVENT_BUS.register(new PlayTimeLimitEvents());
        NeoForge.EVENT_BUS.register(new DailyFavorEvents());
        NeoForge.EVENT_BUS.register(new UniversalBondEvents());
        NeoForge.EVENT_BUS.register(new MovementTweaksEvents());
        NeoForge.EVENT_BUS.register(new InteractionTweaksEvents());
        NeoForge.EVENT_BUS.register(new TransportTweaksEvents());
        NeoForge.EVENT_BUS.register(new PhysicsTransportEvents());
        NeoForge.EVENT_BUS.register(new WorldOddityEvents());
        InteractionTweaksEvents.registerDispenserBehaviors();
    }
}
