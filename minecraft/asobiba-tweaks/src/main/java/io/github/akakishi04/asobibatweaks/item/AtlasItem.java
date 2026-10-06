package io.github.akakishi04.asobibatweaks.item;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import net.minecraft.ChatFormatting;
import net.minecraft.core.component.DataComponents;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResultHolder;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.MapItem;
import net.minecraft.world.item.TooltipFlag;
import net.minecraft.world.item.component.ItemContainerContents;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.saveddata.maps.MapId;
import net.minecraft.world.level.saveddata.maps.MapItemSavedData;

public final class AtlasItem extends Item {
    public static final int MAX_MAPS = 128;

    public AtlasItem(Properties properties) {
        super(properties.stacksTo(1));
    }

    @Override
    public InteractionResultHolder<ItemStack> use(Level level, Player player, InteractionHand hand) {
        ItemStack atlas = player.getItemInHand(hand);
        if (!AsobibaTweaksConfig.ATLAS_ENABLED.getAsBoolean()) {
            return InteractionResultHolder.pass(atlas);
        }

        InteractionHand otherHand = hand == InteractionHand.MAIN_HAND ? InteractionHand.OFF_HAND : InteractionHand.MAIN_HAND;
        ItemStack other = player.getItemInHand(otherHand);

        if (!level.isClientSide() && other.is(Items.FILLED_MAP) && other.has(DataComponents.MAP_ID)) {
            ItemStack page = other.copyWithCount(1);
            AddResult result = addMap(atlas, page);
            if (result == AddResult.ADDED) {
                if (!player.getAbilities().instabuild) {
                    other.shrink(1);
                }
                updateActiveMap(atlas, player);
                player.displayClientMessage(
                        Component.translatable("message.asobibatweaks.atlas.added", mapCount(atlas), MAX_MAPS)
                                .withStyle(ChatFormatting.AQUA),
                        true
                );
            } else if (result == AddResult.DUPLICATE) {
                player.displayClientMessage(
                        Component.translatable("message.asobibatweaks.atlas.duplicate")
                                .withStyle(ChatFormatting.YELLOW),
                        true
                );
            } else {
                player.displayClientMessage(
                        Component.translatable("message.asobibatweaks.atlas.full", MAX_MAPS)
                                .withStyle(ChatFormatting.RED),
                        true
                );
            }
            return InteractionResultHolder.sidedSuccess(atlas, false);
        }

        if (!level.isClientSide() && player.isShiftKeyDown() && other.isEmpty()) {
            ItemStack removed = removeActiveOrLast(atlas);
            if (!removed.isEmpty()) {
                if (!player.getInventory().add(removed)) {
                    player.drop(removed, false);
                }
                updateActiveMap(atlas, player);
                player.displayClientMessage(
                        Component.translatable("message.asobibatweaks.atlas.removed", mapCount(atlas))
                                .withStyle(ChatFormatting.GRAY),
                        true
                );
                return InteractionResultHolder.sidedSuccess(atlas, false);
            }

            player.displayClientMessage(
                    Component.translatable("message.asobibatweaks.atlas.empty")
                            .withStyle(ChatFormatting.GRAY),
                    true
            );
            return InteractionResultHolder.sidedSuccess(atlas, false);
        }

        return InteractionResultHolder.pass(atlas);
    }

    @Override
    public void inventoryTick(ItemStack stack, Level level, Entity entity, int slotId, boolean selected) {
        super.inventoryTick(stack, level, entity, slotId, selected);

        if (level.isClientSide() || !(entity instanceof ServerPlayer player)) {
            return;
        }

        if (!AsobibaTweaksConfig.ATLAS_ENABLED.getAsBoolean()) {
            stack.remove(DataComponents.MAP_ID);
            return;
        }

        boolean held = player.getMainHandItem() == stack || player.getOffhandItem() == stack;
        if (!held) {
            return;
        }

        updateActiveMap(stack, player);

        MapId active = stack.get(DataComponents.MAP_ID);
        if (active != null) {
            ItemStack vanillaMapProxy = new ItemStack(Items.FILLED_MAP);
            vanillaMapProxy.set(DataComponents.MAP_ID, active);
            Items.FILLED_MAP.inventoryTick(vanillaMapProxy, level, entity, slotId, true);
        }
    }

    @Override
    public void appendHoverText(ItemStack stack, TooltipContext context, List<Component> tooltip, TooltipFlag flag) {
        super.appendHoverText(stack, context, tooltip, flag);

        int count = mapCount(stack);
        tooltip.add(Component.translatable("tooltip.asobibatweaks.atlas.maps", count, MAX_MAPS)
                .withStyle(ChatFormatting.GRAY));

        MapId active = stack.get(DataComponents.MAP_ID);
        if (active != null) {
            tooltip.add(Component.translatable("tooltip.asobibatweaks.atlas.active", active.id())
                    .withStyle(ChatFormatting.DARK_AQUA));
        } else if (count > 0) {
            tooltip.add(Component.translatable("tooltip.asobibatweaks.atlas.out_of_coverage")
                    .withStyle(ChatFormatting.DARK_GRAY));
        }

        tooltip.add(Component.translatable("tooltip.asobibatweaks.atlas.insert")
                .withStyle(ChatFormatting.DARK_GRAY));
        tooltip.add(Component.translatable("tooltip.asobibatweaks.atlas.remove")
                .withStyle(ChatFormatting.DARK_GRAY));
    }

    public static boolean hasActiveMap(ItemStack atlas) {
        return atlas.has(DataComponents.MAP_ID);
    }

    public static int mapCount(ItemStack atlas) {
        return getMaps(atlas).size();
    }

    public static void updateActiveMap(ItemStack atlas, Player player) {
        MapId selected = selectMap(atlas, player.level(), player.getX(), player.getZ());
        MapId previous = atlas.get(DataComponents.MAP_ID);

        if (!Objects.equals(previous, selected)) {
            if (selected == null) {
                atlas.remove(DataComponents.MAP_ID);
            } else {
                atlas.set(DataComponents.MAP_ID, selected);
            }
        }
    }

    private static MapId selectMap(ItemStack atlas, Level level, double x, double z) {
        MapId best = null;
        int bestScale = Integer.MAX_VALUE;

        for (ItemStack map : getMaps(atlas)) {
            MapId id = map.get(DataComponents.MAP_ID);
            if (id == null) {
                continue;
            }

            MapItemSavedData data = MapItem.getSavedData(id, level);
            if (data == null || !data.dimension.equals(level.dimension())) {
                continue;
            }

            int blocksPerPixel = 1 << data.scale;
            double halfSize = 64.0D * blocksPerPixel;
            boolean inside = x >= data.centerX - halfSize
                    && x < data.centerX + halfSize
                    && z >= data.centerZ - halfSize
                    && z < data.centerZ + halfSize;

            if (inside && data.scale < bestScale) {
                best = id;
                bestScale = data.scale;
            }
        }

        return best;
    }

    private static AddResult addMap(ItemStack atlas, ItemStack map) {
        List<ItemStack> maps = getMaps(atlas);
        if (maps.size() >= MAX_MAPS) {
            return AddResult.FULL;
        }

        MapId incoming = map.get(DataComponents.MAP_ID);
        if (incoming == null) {
            return AddResult.DUPLICATE;
        }

        for (ItemStack existing : maps) {
            if (incoming.equals(existing.get(DataComponents.MAP_ID))) {
                return AddResult.DUPLICATE;
            }
        }

        maps.add(map.copyWithCount(1));
        saveMaps(atlas, maps);
        return AddResult.ADDED;
    }

    private static ItemStack removeActiveOrLast(ItemStack atlas) {
        List<ItemStack> maps = getMaps(atlas);
        if (maps.isEmpty()) {
            return ItemStack.EMPTY;
        }

        MapId active = atlas.get(DataComponents.MAP_ID);
        int index = -1;
        if (active != null) {
            for (int i = 0; i < maps.size(); i++) {
                if (active.equals(maps.get(i).get(DataComponents.MAP_ID))) {
                    index = i;
                    break;
                }
            }
        }

        if (index < 0) {
            index = maps.size() - 1;
        }

        ItemStack removed = maps.remove(index);
        saveMaps(atlas, maps);
        atlas.remove(DataComponents.MAP_ID);
        return removed;
    }

    private static List<ItemStack> getMaps(ItemStack atlas) {
        ItemContainerContents contents = atlas.get(DataComponents.CONTAINER);
        if (contents == null) {
            return new ArrayList<>();
        }

        return new ArrayList<>(contents.nonEmptyStream()
                .filter(stack -> stack.is(Items.FILLED_MAP) && stack.has(DataComponents.MAP_ID))
                .map(ItemStack::copy)
                .toList());
    }

    private static void saveMaps(ItemStack atlas, List<ItemStack> maps) {
        if (maps.isEmpty()) {
            atlas.remove(DataComponents.CONTAINER);
        } else {
            atlas.set(DataComponents.CONTAINER, ItemContainerContents.fromItems(maps));
        }
    }

    private enum AddResult {
        ADDED,
        DUPLICATE,
        FULL
    }
}
