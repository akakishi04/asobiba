package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.github.akakishi04.asobibatweaks.entity.AfterimageDecoyEntity;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.MobCategory;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.neoforge.event.entity.EntityAttributeCreationEvent;
import net.neoforged.neoforge.registries.DeferredHolder;
import net.neoforged.neoforge.registries.DeferredRegister;

/** Registry content stays registered when its independently optional behavior is disabled. */
public final class AfterimageDecoyRegistration {
    private static final DeferredRegister<EntityType<?>> TYPES =
            DeferredRegister.create(BuiltInRegistries.ENTITY_TYPE, AsobibaTweaks.MOD_ID);
    public static final DeferredHolder<EntityType<?>, EntityType<AfterimageDecoyEntity>> DECOY =
            TYPES.register("afterimage_decoy", () -> EntityType.Builder
                    .of(AfterimageDecoyEntity::new, MobCategory.MISC)
                    .sized(0.6F, 1.8F).fireImmune().noSave().noSummon()
                    .clientTrackingRange(8).updateInterval(20)
                    .build(AsobibaTweaks.MOD_ID + ":afterimage_decoy"));

    private AfterimageDecoyRegistration() {}

    public static void register(IEventBus modBus) {
        TYPES.register(modBus);
        modBus.addListener(AfterimageDecoyRegistration::attributes);
    }

    private static void attributes(EntityAttributeCreationEvent event) {
        event.put(DECOY.get(), AfterimageDecoyEntity.createAttributes().build());
    }
}
