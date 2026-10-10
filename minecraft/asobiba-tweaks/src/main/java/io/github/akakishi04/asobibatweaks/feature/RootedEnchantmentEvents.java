package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.tags.ItemTags;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.CropBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.neoforged.bus.api.EventPriority;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.common.util.BlockSnapshot;
import net.neoforged.neoforge.common.util.FakePlayer;
import net.neoforged.neoforge.event.EventHooks;
import net.neoforged.neoforge.event.level.BlockDropsEvent;
import net.neoforged.neoforge.event.level.BlockEvent;
import net.neoforged.neoforge.event.level.LevelEvent;
import net.neoforged.neoforge.event.tick.LevelTickEvent;

/** A single real player harvest buys at most one same-crop replant, after vanilla finishes. */
public final class RootedEnchantmentEvents {
    private static final int MAX_PENDING = 256;
    private static final Map<HarvestKey, Harvest> pending = new LinkedHashMap<>();

    @SubscribeEvent(priority = EventPriority.LOWEST)
    public void onBreak(BlockEvent.BreakEvent event) {
        if (!(event.getLevel() instanceof ServerLevel level)
                || !(event.getPlayer() instanceof ServerPlayer player)) return;
        HarvestKey key = new HarvestKey(level, player.getUUID(), event.getPos().immutable());
        pending.remove(key);
        if (!AsobibaTweaksConfig.ROOTED_ENABLED.getAsBoolean() || event.isCanceled()
                || !eligiblePlayer(player) || seedFor(event.getState()) == null
                || !rootedHoe(player.getMainHandItem(), level) || pending.size() >= MAX_PENDING) return;
        pending.put(key, new Harvest(event, level.getGameTime()));
    }

    @SubscribeEvent(priority = EventPriority.LOWEST)
    public void onDrops(BlockDropsEvent event) {
        if (!(event.getBreaker() instanceof ServerPlayer player)) return;
        HarvestKey key = new HarvestKey(event.getLevel(), player.getUUID(), event.getPos());
        Harvest harvest = pending.get(key);
        if (harvest == null || harvest.drops != null || event.isCanceled()
                || harvest.attempt.isCanceled() || harvest.tick != event.getLevel().getGameTime()
                || !harvest.attempt.getState().equals(event.getState())
                || !rootedHoe(event.getTool(), event.getLevel())) return;
        // Keep the actual events until dispatch is over, so later cancellation
        // cannot accidentally turn a rejected harvest into a paid replant.
        harvest.drops = event;
    }

    @SubscribeEvent
    public void onLevelTick(LevelTickEvent.Post event) {
        if (event.getLevel() instanceof ServerLevel level) finishHarvests(level);
    }

    @SubscribeEvent
    public void onLevelUnload(LevelEvent.Unload event) {
        pending.keySet().removeIf(key -> key.level == event.getLevel());
    }

    static void finishHarvests(ServerLevel level) {
        // Remove first: placement callbacks cannot replay or recursively commit a receipt.
        var ready = new ArrayList<Harvest>();
        pending.entrySet().removeIf(entry -> {
            if (entry.getKey().level != level) return false;
            ready.add(entry.getValue());
            return true;
        });
        if (!AsobibaTweaksConfig.ROOTED_ENABLED.getAsBoolean()) return;
        for (Harvest harvest : ready) {
            if (harvest.drops == null || harvest.drops.isCanceled()
                    || harvest.attempt.isCanceled()
                    || level.getGameTime() - harvest.tick > 1L) continue;
            ServerPlayer player = (ServerPlayer) harvest.attempt.getPlayer();
            if (player.serverLevel() != level || !eligiblePlayer(player)) continue;
            replant(level, player, harvest.attempt.getPos(), harvest.attempt.getState());
        }
    }

    private static boolean eligiblePlayer(ServerPlayer player) {
        // Creative deliberately gets no free replacement or fake harvesting drops.
        return !(player instanceof FakePlayer) && player.isAlive() && !player.isRemoved()
                && !player.isSpectator() && !player.isCreative() && player.getAbilities().mayBuild;
    }

    private static boolean rootedHoe(ItemStack tool, ServerLevel level) {
        return tool.is(ItemTags.HOES) && NewEnchantments.has(tool, level.registryAccess(), NewEnchantments.ROOTED);
    }

    /** Explicit vanilla allowlist: stems, berries, wart and modded crops need separate rules. */
    static Item seedFor(BlockState state) {
        if (!(state.getBlock() instanceof CropBlock crop) || !crop.isMaxAge(state)) return null;
        if (state.is(Blocks.WHEAT)) return Items.WHEAT_SEEDS;
        if (state.is(Blocks.CARROTS)) return Items.CARROT;
        if (state.is(Blocks.POTATOES)) return Items.POTATO;
        if (state.is(Blocks.BEETROOTS)) return Items.BEETROOT_SEEDS;
        return null;
    }

    private static boolean replant(ServerLevel level, ServerPlayer player, BlockPos pos, BlockState harvested) {
        Item seed = seedFor(harvested);
        if (seed == null || !level.hasChunkAt(pos) || !level.hasChunkAt(pos.below())
                || !level.getWorldBorder().isWithinBounds(pos) || !level.mayInteract(player, pos)
                || !level.getBlockState(pos).isAir() || !level.getFluidState(pos).isEmpty()
                || level.getBlockEntity(pos) != null || !level.getBlockState(pos.below()).is(Blocks.FARMLAND)) return false;
        BlockState young = ((CropBlock)harvested.getBlock()).getStateForAge(0);
        if (!young.canSurvive(level, pos)) return false;
        int slot = seedSlot(player, seed);
        if (slot < 0) return false;
        ItemStack owned = player.getInventory().getItem(slot);
        if (!player.mayUseItemAt(pos, Direction.UP, owned)) return false;

        // Reserve the exact real planting item before any placement callbacks.
        // Drops from the harvested plant are never inspected, removed or replaced.
        ItemStack payment = owned.split(1);
        BlockSnapshot before = BlockSnapshot.create(level.dimension(), level, pos);
        boolean placed = level.setBlock(pos, young, Block.UPDATE_KNOWN_SHAPE);
        if (!placed) {
            refund(player, slot, payment);
            return false;
        }
        if (EventHooks.onBlockPlace(player, before, Direction.UP)) {
            // Only undo our own tentative plant, never a block installed by a hook.
            if (level.getBlockState(pos).equals(young) && before.restore()) {
                refund(player, slot, payment);
            }
            return false;
        }
        level.sendBlockUpdated(pos, before.getState(), level.getBlockState(pos), Block.UPDATE_ALL);
        level.updateNeighborsAt(pos, young.getBlock());
        player.getInventory().setChanged();
        return true;
    }

    private static int seedSlot(ServerPlayer player, Item seed) {
        // Ordinary inventory and offhand only, not armor, nearby drops or containers.
        for (int slot = 0; slot < player.getInventory().items.size(); slot++) {
            if (player.getInventory().getItem(slot).is(seed)) return slot;
        }
        int offhand = player.getInventory().items.size() + player.getInventory().armor.size();
        return player.getInventory().getItem(offhand).is(seed) ? offhand : -1;
    }

    private static void refund(ServerPlayer player, int slot, ItemStack payment) {
        ItemStack current = player.getInventory().getItem(slot);
        if (current.isEmpty()) player.getInventory().setItem(slot, payment);
        else if (ItemStack.isSameItemSameComponents(current, payment) && current.getCount() < current.getMaxStackSize())
            current.grow(1);
        else if (!player.getInventory().add(payment)) player.drop(payment, false);
        player.getInventory().setChanged();
    }

    private record HarvestKey(ServerLevel level, UUID player, BlockPos pos) {}

    private static final class Harvest {
        final BlockEvent.BreakEvent attempt;
        final long tick;
        BlockDropsEvent drops;
        Harvest(BlockEvent.BreakEvent attempt, long tick) {
            this.attempt = attempt;
            this.tick = tick;
        }
    }
}
