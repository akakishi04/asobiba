package io.github.akakishi04.asobibatweaks;

import io.github.akakishi04.asobibatweaks.feature.AlchemyExplosivesCraftingEvents;
import io.github.akakishi04.asobibatweaks.feature.ContinentalWorldgenEvents;
import io.github.akakishi04.asobibatweaks.feature.DailyFavorEvents;
import io.github.akakishi04.asobibatweaks.feature.EnchantedWorkBlockEvents;
import io.github.akakishi04.asobibatweaks.feature.EnchantmentTweaksEvents;
import io.github.akakishi04.asobibatweaks.feature.FolkloreAndMoonEvents;
import io.github.akakishi04.asobibatweaks.feature.ForestRegenerationEvents;
import io.github.akakishi04.asobibatweaks.feature.GiantOrganismEvents;
import io.github.akakishi04.asobibatweaks.feature.GrowingItemsEvents;
import io.github.akakishi04.asobibatweaks.feature.InteractionTweaksEvents;
import io.github.akakishi04.asobibatweaks.feature.MobBuildingUseEvents;
import io.github.akakishi04.asobibatweaks.feature.MovementTweaksEvents;
import io.github.akakishi04.asobibatweaks.feature.NetherFishingEvents;
import io.github.akakishi04.asobibatweaks.feature.OceanAndDisplayEvents;
import io.github.akakishi04.asobibatweaks.feature.PlayTimeLimitEvents;
import io.github.akakishi04.asobibatweaks.feature.PhysicsTransportEvents;
import io.github.akakishi04.asobibatweaks.feature.TransportTweaksEvents;
import io.github.akakishi04.asobibatweaks.feature.UniversalBondEvents;
import io.github.akakishi04.asobibatweaks.feature.VillageDirtyEvents;
import io.github.akakishi04.asobibatweaks.feature.VillageEconomyService;
import io.github.akakishi04.asobibatweaks.feature.VillageFireEmergencyService;
import io.github.akakishi04.asobibatweaks.feature.VillageDutyScheduler;
import io.github.akakishi04.asobibatweaks.feature.VillagePopulationMigrationService;
import io.github.akakishi04.asobibatweaks.feature.VillageRiverService;
import io.github.akakishi04.asobibatweaks.feature.VillageSimulationEvents;
import io.github.akakishi04.asobibatweaks.feature.VillageSimulationScheduler;
import io.github.akakishi04.asobibatweaks.feature.VillageStatusEvents;
import io.github.akakishi04.asobibatweaks.feature.VillageStatusNetworking;
import io.github.akakishi04.asobibatweaks.feature.VillagerWelfareService;
import io.github.akakishi04.asobibatweaks.feature.WorldOddityEvents;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.ModContainer;
import net.neoforged.fml.common.Mod;
import net.neoforged.fml.config.ModConfig;
import net.neoforged.neoforge.common.NeoForge;

@Mod(AsobibaTweaks.MOD_ID)
public final class AsobibaTweaks {
    public static final String MOD_ID = "asobibatweaks";

    public AsobibaTweaks(IEventBus modBus, ModContainer container) {
        AsobibaRegistries.register(modBus);
        modBus.addListener(VillageStatusNetworking::registerPayloads);
        container.registerConfig(ModConfig.Type.COMMON, AsobibaTweaksConfig.SPEC);
        NeoForge.EVENT_BUS.register(new GrowingItemsEvents());
        NeoForge.EVENT_BUS.register(new GiantOrganismEvents());
        NeoForge.EVENT_BUS.register(new FolkloreAndMoonEvents());
        NeoForge.EVENT_BUS.register(new EnchantmentTweaksEvents());
        NeoForge.EVENT_BUS.register(new EnchantedWorkBlockEvents());
        NeoForge.EVENT_BUS.register(new PlayTimeLimitEvents());
        NeoForge.EVENT_BUS.register(new DailyFavorEvents());
        NeoForge.EVENT_BUS.register(new ContinentalWorldgenEvents());
        NeoForge.EVENT_BUS.register(new ForestRegenerationEvents());
        NeoForge.EVENT_BUS.register(new AlchemyExplosivesCraftingEvents());
        NeoForge.EVENT_BUS.register(new UniversalBondEvents());
        NeoForge.EVENT_BUS.register(new MovementTweaksEvents());
        NeoForge.EVENT_BUS.register(new InteractionTweaksEvents());
        NeoForge.EVENT_BUS.register(new TransportTweaksEvents());
        NeoForge.EVENT_BUS.register(new PhysicsTransportEvents());
        NeoForge.EVENT_BUS.register(new WorldOddityEvents());
        NeoForge.EVENT_BUS.register(new OceanAndDisplayEvents());
        NeoForge.EVENT_BUS.register(new NetherFishingEvents());
        NeoForge.EVENT_BUS.register(new VillageDutyScheduler());
        NeoForge.EVENT_BUS.register(new VillageFireEmergencyService());
        NeoForge.EVENT_BUS.register(new VillageSimulationEvents());
        NeoForge.EVENT_BUS.register(new VillagePopulationMigrationService());
        NeoForge.EVENT_BUS.register(new VillageRiverService());
        NeoForge.EVENT_BUS.register(new VillageSimulationScheduler());
        NeoForge.EVENT_BUS.register(new VillageDirtyEvents());
        NeoForge.EVENT_BUS.register(new VillageStatusEvents());
        NeoForge.EVENT_BUS.register(new VillageEconomyService());
        NeoForge.EVENT_BUS.register(new VillagerWelfareService());
        NeoForge.EVENT_BUS.register(new MobBuildingUseEvents());
        InteractionTweaksEvents.registerDispenserBehaviors();
    }
}
