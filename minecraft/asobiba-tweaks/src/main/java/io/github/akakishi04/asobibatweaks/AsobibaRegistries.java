package io.github.akakishi04.asobibatweaks;

import com.google.common.collect.ImmutableSet;
import io.github.akakishi04.asobibatweaks.entity.NetherFishEntity;
import io.github.akakishi04.asobibatweaks.item.AtlasItem;
import io.github.akakishi04.asobibatweaks.item.QuiverItem;
import java.util.Collection;
import net.minecraft.core.Holder;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.MobCategory;
import net.minecraft.world.entity.ai.village.poi.PoiType;
import net.minecraft.world.entity.npc.VillagerProfession;
import net.minecraft.world.food.FoodProperties;
import net.minecraft.world.item.Item;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.SoundType;
import net.minecraft.world.level.block.state.BlockBehaviour;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.material.MapColor;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.neoforge.event.entity.EntityAttributeCreationEvent;
import net.neoforged.neoforge.registries.DeferredBlock;
import net.neoforged.neoforge.registries.DeferredHolder;
import net.neoforged.neoforge.registries.DeferredRegister;
import net.neoforged.neoforge.registries.DeferredItem;

public final class AsobibaRegistries {
    public static final DeferredRegister<EntityType<?>> ENTITY_TYPES =
            DeferredRegister.create(BuiltInRegistries.ENTITY_TYPE, AsobibaTweaks.MOD_ID);
    public static final DeferredRegister.Items ITEMS =
            DeferredRegister.createItems(AsobibaTweaks.MOD_ID);
    public static final DeferredRegister.Blocks BLOCKS =
            DeferredRegister.createBlocks(AsobibaTweaks.MOD_ID);
    public static final DeferredRegister<PoiType> POI_TYPES =
            DeferredRegister.create(BuiltInRegistries.POINT_OF_INTEREST_TYPE, AsobibaTweaks.MOD_ID);
    public static final DeferredRegister<VillagerProfession> PROFESSIONS =
            DeferredRegister.create(BuiltInRegistries.VILLAGER_PROFESSION, AsobibaTweaks.MOD_ID);

    public static final DeferredBlock<Block> ARCANE_BOOKSHELF =
            BLOCKS.registerSimpleBlock("arcane_bookshelf",
                    BlockBehaviour.Properties.of()
                            .mapColor(MapColor.COLOR_PURPLE)
                            .strength(1.5F)
                            .sound(SoundType.WOOD));

    public static final DeferredItem<?> ARCANE_BOOKSHELF_ITEM =
            ITEMS.registerSimpleBlockItem(ARCANE_BOOKSHELF);

    public static final DeferredBlock<Block> CARPENTER_WORKBENCH =
            BLOCKS.registerSimpleBlock("carpenter_workbench",
                    BlockBehaviour.Properties.of()
                            .mapColor(MapColor.WOOD)
                            .strength(2.5F)
                            .sound(SoundType.WOOD));
    public static final DeferredItem<?> CARPENTER_WORKBENCH_ITEM =
            ITEMS.registerSimpleBlockItem(CARPENTER_WORKBENCH);

    public static final Holder<PoiType> CARPENTER_POI = POI_TYPES.register(
            "carpenter",
            () -> new PoiType(ImmutableSet.copyOf(states(CARPENTER_WORKBENCH.get())), 1, 1)
    );

    public static final Holder<VillagerProfession> CARPENTER = PROFESSIONS.register(
            "carpenter",
            () -> createProfession(
                    ResourceLocation.fromNamespaceAndPath(AsobibaTweaks.MOD_ID, "carpenter"),
                    CARPENTER_POI
            )
    );

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

    public static final DeferredItem<AtlasItem> ATLAS = ITEMS.register(
            "atlas",
            () -> new AtlasItem(new Item.Properties().stacksTo(1))
    );

    public static final DeferredItem<QuiverItem> QUIVER = ITEMS.register(
            "quiver",
            () -> new QuiverItem(new Item.Properties().stacksTo(1))
    );

    public static final DeferredItem<Item> ARCANE_FOLIO = ITEMS.register(
            "arcane_folio",
            () -> new Item(new Item.Properties().stacksTo(16))
    );

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
        BLOCKS.register(modBus);
        ITEMS.register(modBus);
        POI_TYPES.register(modBus);
        PROFESSIONS.register(modBus);
        ENTITY_TYPES.register(modBus);
        modBus.addListener(AsobibaRegistries::registerAttributes);
    }

    private static Collection<BlockState> states(Block block) {
        return block.getStateDefinition().getPossibleStates();
    }

    private static VillagerProfession createProfession(ResourceLocation name, Holder<PoiType> poi) {
        ResourceKey<PoiType> poiKey = poi.unwrapKey().orElseThrow();
        return new VillagerProfession(
                name.toString(),
                holder -> holder.is(poiKey),
                holder -> holder.is(poiKey),
                ImmutableSet.of(),
                ImmutableSet.of(),
                SoundEvents.VILLAGER_WORK_MASON
        );
    }

    private static void registerAttributes(EntityAttributeCreationEvent event) {
        event.put(LAVA_MINNOW.get(), NetherFishEntity.createAttributes().build());
        event.put(EMBERFIN.get(), NetherFishEntity.createAttributes().build());
        event.put(BASALT_EEL.get(), NetherFishEntity.createAttributes().build());
    }

    private AsobibaRegistries() {}
}
