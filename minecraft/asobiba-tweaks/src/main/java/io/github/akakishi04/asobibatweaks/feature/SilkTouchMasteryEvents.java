package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.Property;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.level.BlockDropsEvent;
import net.neoforged.neoforge.event.level.BlockEvent;
import net.minecraft.world.InteractionHand;

/**
 * Silk Touch's reviewed non-progression block families. Batch Harvest always
 * routes each extra break through ServerPlayerGameMode.destroyBlock to retain
 * all normal drops, item damage, game rules, protection and advancement logic.
 */
public final class SilkTouchMasteryEvents {
    private static final ThreadLocal<Boolean> IN_BATCH =
            ThreadLocal.withInitial(() -> false);
    private static final String STATE = "asobibatweaks_silk_state";

    private static LauncherReloadMasteryEvents.Branch branch(ItemStack tool) {
        return LauncherReloadMasteryEvents.branch(tool, "minecraft:silk_touch");
    }

    private static boolean safeBatch(BlockState state) {
        return state.is(Blocks.GLASS) || state.is(Blocks.GLASS_PANE)
                || state.is(Blocks.ICE) || state.is(Blocks.PACKED_ICE)
                || state.is(Blocks.BLUE_ICE) || state.is(BlockTags.LEAVES);
    }

    @SubscribeEvent
    public void onBreakBatch(BlockEvent.BreakEvent event) {
        if (IN_BATCH.get() || event.isCanceled()
                || !(event.getPlayer() instanceof ServerPlayer player)
                || !(event.getLevel() instanceof ServerLevel world)) return;
        var b = branch(player.getMainHandItem());
        if (b == null || b.choice() != 1 || !safeBatch(event.getState())) return;

        int total = (int)Math.round(3.0D + 5.0D * b.progress());
        int maxExtra = Math.max(0, total - 1);
        BlockPos source = event.getPos();
        BlockState original = event.getState();
        ArrayDeque<BlockPos> queue = new ArrayDeque<>();
        Set<Long> seen = new HashSet<>();
        queue.add(source);
        seen.add(source.asLong());
        int broken = 0;

        IN_BATCH.set(true);
        try {
            while (!queue.isEmpty() && broken < maxExtra && seen.size() < 96) {
                BlockPos center = queue.removeFirst();
                for (Direction dir : Direction.values()) {
                    if (broken >= maxExtra || seen.size() >= 96) break;
                    BlockPos pos = center.relative(dir);
                    if (!seen.add(pos.asLong()) || !world.hasChunkAt(pos)
                            || pos.equals(source) || !world.getBlockState(pos).is(original)
                            || !safeBatch(original)) continue;
                    ItemStack tool = player.getMainHandItem();
                    if (tool.isEmpty() || branch(tool) == null) break;

                    // Exactly one normal block transaction per accepted
                    // extra position. No direct setBlock(AIR) bypass.
                    if (player.gameMode.destroyBlock(pos)) {
                        broken++;
                        queue.addLast(pos);
                    }
                }
            }
        } finally {
            IN_BATCH.remove();
        }
    }

    @SubscribeEvent
    public void onSilkDrops(BlockDropsEvent event) {
        if (event.isCanceled() || !(event.getBreaker() instanceof ServerPlayer player)) return;
        var branch = branch(event.getTool());
        if (branch == null) return;
        BlockState state = event.getState();
        if (branch.choice() == 0) {
            int tier = branch.mastery() >= 100 ? 3 : branch.mastery() >= 75 ? 2 : 1;
            boolean allowed = state.is(Blocks.CAKE)
                    || tier >= 2 && state.is(Blocks.TALL_GRASS)
                    || tier >= 3 && state.is(Blocks.SEAGRASS);
            if (!allowed || state.getBlock().asItem() == net.minecraft.world.item.Items.AIR) return;
            event.getDrops().clear();
            event.setDroppedExperience(0);
            event.getDrops().add(new ItemEntity(event.getLevel(),
                    event.getPos().getX() + 0.5D,
                    event.getPos().getY() + 0.5D,
                    event.getPos().getZ() + 0.5D,
                    new ItemStack(state.getBlock().asItem())));
        } else if (branch.choice() == 2) {
            boolean logs = state.is(BlockTags.LOGS);
            boolean stairs = state.is(BlockTags.STAIRS);
            if (!logs && !stairs) return;
            int mastery = branch.mastery();
            for (ItemEntity drop : event.getDrops()) {
                ItemStack stack = drop.getItem();
                if (!stack.is(state.getBlock().asItem())) continue;
                CompoundTag properties = new CompoundTag();
                for (Property<?> property : state.getProperties()) {
                    String name = property.getName();
                    if (logs && "axis".equals(name) ||
                            stairs && ("facing".equals(name)
                                    || mastery >= 75 && "half".equals(name)
                                    || mastery >= 100 && ("shape".equals(name)
                                            || "waterlogged".equals(name)))) {
                        properties.putString(name, valueName(state, property));
                    }
                }
                if (!properties.isEmpty()) {
                    CustomData.update(DataComponents.CUSTOM_DATA, stack,
                            tag -> tag.put(STATE, properties));
                }
            }
        }
    }

    @SubscribeEvent
    public void onStatePreservation(BlockEvent.EntityPlaceEvent event) {
        if (event.isCanceled() || !(event.getEntity() instanceof ServerPlayer player)
                || !(event.getLevel() instanceof ServerLevel world)) return;
        BlockState placed = event.getPlacedBlock();
        if (!placed.is(BlockTags.LOGS) && !placed.is(BlockTags.STAIRS)) return;
        ItemStack hand = player.getMainHandItem();
        if (!hand.is(placed.getBlock().asItem())) hand = player.getOffhandItem();
        if (!hand.is(placed.getBlock().asItem())) return;

        CustomData custom = hand.get(DataComponents.CUSTOM_DATA);
        if (custom == null || !custom.contains(STATE)) return;
        CompoundTag state = custom.copyTag().getCompound(STATE);
        BlockState updated = placed;
        for (Property<?> property : placed.getProperties()) {
            if (state.contains(property.getName())) {
                updated = withProperty(updated, property,
                        state.getString(property.getName()));
            }
        }
        if (updated != placed && updated.canSurvive(world, event.getPos())) {
            world.setBlockAndUpdate(event.getPos(), updated);
        }
    }

    private static <T extends Comparable<T>> String valueName(
            BlockState state, Property<T> property) {
        return property.getName(state.getValue(property));
    }

    private static <T extends Comparable<T>> BlockState withProperty(
            BlockState state, Property<T> property, String value) {
        return property.getValue(value).map(v -> state.setValue(property, v)).orElse(state);
    }
}
