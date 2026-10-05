package io.github.akakishi04.asobibatweaks;

import io.github.akakishi04.asobibatweaks.entity.NetherFishEntity;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.MobCategory;
import net.minecraft.world.food.FoodProperties;
import net.minecraft.world.item.Item;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.neoforge.event.entity.EntityAttributeCreationEvent;
import net.neoforged.neoforge.registries.DeferredHolder;
import net.neoforged.neoforge.registries.DeferredRegister;
import net.neoforged.neoforge.registries.DeferredItem;

public final class AsobibaRegistries {
    public static final DeferredRegister<EntityType<?>> ENTITY_TYPES =
            DeferredRegister.create(BuiltInRegistries.ENTITY_TYPE, AsobibaTweaks.MOD_ID);
    public static final DeferredRegister.Items ITEMS =
            DeferredRegister.createItems(AsobibaTweaks.MOD_ID);

    public static final DeferredHolder<EntityType<?>, EntityType<NetherFishEntity>> LAVA_MINNOW =
            ENTITY_TYPES.register("lava_minnow", () -> EntityType.Builder
                    .of(NetherFishEntity::new, MobCategory.WATER_AMBIENT)
                    .fireImmune()
                    .sized(0.48F, 0.28F)
                    .clientTrackingRange(8)
                    .build("asobibatweaks:lava_minnow"));

    public static final DeferredHolder<EntityType<?>, EntityType<NetherFishEntity>> EMBERFIN =
            ENTITY_TYPES.register("emberfin", () -> EntityType.Builder
                    .of(NetherFishEntity::new, MobCategory.WATER_AMBIENT)
                    .fireImmune()
                    .sized(0.72F, 0.38F)
                    .clientTrackingRange(8)
                    .build("asobibatweaks:emberfin"));

    public static final DeferredHolder<EntityType<?>, EntityType<NetherFishEntity>> BASALT_EEL =
            ENTITY_TYPES.register("basalt_eel", () -> EntityType.Builder
                    .of(NetherFishEntity::new, MobCategory.WATER_AMBIENT)
                    .fireImmune()
                    .sized(0.95F, 0.34F)
                    .clientTrackingRange(8)
                    .build("asobibatweaks:basalt_eel"));

    public static final DeferredItem<Item> LAVA_MINNOW_ITEM = ITEMS.register(
            "lava_minnow",
            () -> new Item(new Item.Properties().food(
                    new FoodProperties.Builder().nutrition(3).saturationModifier(0.25F).build()
            )));
    public static final DeferredItem<Item> EMBERFIN_ITEM = ITEMS.register(
            "emberfin",
            () -> new Item(new Item.Properties().food(
                    new FoodProperties.Builder().nutrition(5).saturationModifier(0.35F).build()
            )));
    public static final DeferredItem<Item> BASALT_EEL_ITEM = ITEMS.register(
            "basalt_eel",
            () -> new Item(new Item.Properties().food(
                    new FoodProperties.Builder().nutrition(6).saturationModifier(0.45F).build()
            )));

    public static void register(IEventBus modBus) {
        ENTITY_TYPES.register(modBus);
        ITEMS.register(modBus);
        modBus.addListener(AsobibaRegistries::registerAttributes);
    }

    private static void registerAttributes(EntityAttributeCreationEvent event) {
        var attributes = NetherFishEntity.createAttributes().build();
        event.put(LAVA_MINNOW.get(), attributes);
        event.put(EMBERFIN.get(), NetherFishEntity.createAttributes().build());
        event.put(BASALT_EEL.get(), NetherFishEntity.createAttributes().build());
    }

    private AsobibaRegistries() {}
}
