package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.AABB;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.player.PlayerEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

public final class FolkloreAndMoonEvents {
    private static final String OFFERING_OWNER = "asobibatweaks_moon_owner";
    private static final String RETURN_AT = "asobibatweaks_moon_return_at";
    private static final String RETURN_ITEM = "asobibatweaks_moon_return_item";
    private final Map<UUID, RitualState> rituals = new HashMap<>();

    @SubscribeEvent
    public void onLogin(PlayerEvent.PlayerLoggedInEvent event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || !AsobibaTweaksConfig.WORLD_FOLKLORE_ENABLED.getAsBoolean()) return;

        long seed = player.serverLevel().getSeed();
        int rule = Math.floorMod(Long.hashCode(seed ^ 0x52A5F1A7D34BL), 5);
        if (player.getRandom().nextDouble() < 0.28D) {
            String rumor = switch (rule) {
                case 0 -> "Old rumor: red beds are said to sleep more quietly during storms.";
                case 1 -> "Old rumor: bells rung before dawn sometimes bring better luck underground.";
                case 2 -> "Old rumor: bread left near a campfire is said to keep wanderers from getting lost.";
                case 3 -> "Old rumor: flowers placed beside a lodestone are said to point travelers home.";
                default -> "Old rumor: some worlds seem to favor those who greet the moon with an empty hand.";
            };
            player.sendSystemMessage(Component.literal(rumor).withStyle(ChatFormatting.DARK_GRAY, ChatFormatting.ITALIC));
        }
    }

    @SubscribeEvent
    public void onPlayerTick(PlayerTickEvent.Post event) {
        if (!(event.getEntity() instanceof ServerPlayer player)) return;

        if (AsobibaTweaksConfig.WORLD_FOLKLORE_ENABLED.getAsBoolean()
                && player.level().getGameTime() % 20L == Math.floorMod(player.getId(), 20)) {
            tickRitual(player);
        }

        if (AsobibaTweaksConfig.WORLD_FOLKLORE_ENABLED.getAsBoolean()) {
            deliverMoonReturn(player);
        }
    }

    @SubscribeEvent
    public void onItemTick(EntityTickEvent.Post event) {
        if (!(event.getEntity() instanceof ItemEntity item)
                || item.level().isClientSide()
                || !AsobibaTweaksConfig.WORLD_FOLKLORE_ENABLED.getAsBoolean()
                || item.getPersistentData().getBoolean("asobibatweaks_moon_checked")) return;

        if (item.tickCount < 15 || item.getDeltaMovement().y <= 0.05D) return;

        Level level = item.level();
        long dayTime = Math.floorMod(level.getDayTime(), 24000L);
        long day = Math.floorDiv(level.getDayTime(), 24000L);
        int moonPhase = level.getMoonPhase();

        if (moonPhase != 0 || dayTime < 13000L || dayTime > 23000L) return;
        if (!level.canSeeSky(item.blockPosition()) || item.getY() < level.getSeaLevel() + 12) return;

        ServerPlayer owner = nearestOwner(item);
        if (owner == null) {
            item.getPersistentData().putBoolean("asobibatweaks_moon_checked", true);
            return;
        }

        ItemStack stack = item.getItem();
        if (!isOffering(stack.getItem())) {
            item.getPersistentData().putBoolean("asobibatweaks_moon_checked", true);
            return;
        }

        Item returned = chooseReturn(level.getSeed(), day, stack.getItem());
        owner.getPersistentData().putLong(RETURN_AT, level.getGameTime() + (2L + Math.floorMod(Long.hashCode(level.getSeed() ^ day), 5)) * 24000L);
        owner.getPersistentData().putString(RETURN_ITEM,
                net.minecraft.core.registries.BuiltInRegistries.ITEM.getKey(returned).toString());
        item.discard();
        owner.sendSystemMessage(Component.literal("The offering vanished into the moonlight.")
                .withStyle(ChatFormatting.LIGHT_PURPLE, ChatFormatting.ITALIC));
    }

    private void tickRitual(ServerPlayer player) {
        RitualState state = rituals.computeIfAbsent(player.getUUID(), ignored -> new RitualState());
        long now = player.level().getGameTime();

        BlockPos feet = player.blockPosition();
        boolean nearBell = !player.level().getBlockStates(new AABB(feet).inflate(4.0D))
                .filter(s -> s.is(Blocks.BELL)).toList().isEmpty();
        boolean nearCampfire = !player.level().getBlockStates(new AABB(feet).inflate(4.0D))
                .filter(s -> s.is(Blocks.CAMPFIRE)).toList().isEmpty();

        if (nearBell) state.lastBellVicinity = now;
        if (nearCampfire && player.getMainHandItem().is(Items.BREAD)) state.lastBreadFire = now;

        long seed = player.serverLevel().getSeed();
        int hiddenRule = Math.floorMod(Long.hashCode(seed ^ 0x52A5F1A7D34BL), 5);
        boolean triggered = switch (hiddenRule) {
            case 0 -> player.level().isThundering() && player.getRespawnPosition() != null
                    && now - state.lastReward > 2400L;
            case 1 -> now - state.lastBellVicinity < 100L
                    && Math.floorMod(player.level().getDayTime(), 24000L) < 1000L
                    && player.getY() < 50.0D;
            case 2 -> now - state.lastBreadFire < 100L
                    && player.getFoodData().getFoodLevel() < 18;
            case 3 -> player.getMainHandItem().is(Items.COMPASS)
                    && nearBlock(player, Blocks.LODESTONE, 4);
            default -> player.getMainHandItem().isEmpty()
                    && player.level().getMoonPhase() == 0
                    && Math.floorMod(player.level().getDayTime(), 24000L) > 13000L;
        };

        if (triggered && now - state.lastReward > 2400L) {
            state.lastReward = now;
            player.giveExperiencePoints(1);
            player.displayClientMessage(Component.literal("Something about that felt... right.")
                    .withStyle(ChatFormatting.DARK_PURPLE), true);
        }
    }

    private static boolean nearBlock(ServerPlayer player, net.minecraft.world.level.block.Block block, int radius) {
        BlockPos center = player.blockPosition();
        for (BlockPos pos : BlockPos.betweenClosed(center.offset(-radius, -2, -radius), center.offset(radius, 2, radius))) {
            if (player.level().getBlockState(pos).is(block)) return true;
        }
        return false;
    }

    private static boolean isOffering(Item item) {
        return item == Items.AMETHYST_SHARD
                || item == Items.GOLD_INGOT
                || item == Items.ENDER_PEARL
                || item == Items.HONEY_BOTTLE
                || item == Items.FEATHER
                || item == Items.NAUTILUS_SHELL;
    }

    private static Item chooseReturn(long seed, long day, Item offered) {
        Item[] pool;
        if (offered == Items.AMETHYST_SHARD) pool = new Item[]{Items.GLOW_INK_SAC, Items.QUARTZ, Items.ECHO_SHARD};
        else if (offered == Items.GOLD_INGOT) pool = new Item[]{Items.GOLDEN_CARROT, Items.GILDED_BLACKSTONE, Items.CLOCK};
        else if (offered == Items.ENDER_PEARL) pool = new Item[]{Items.CHORUS_FRUIT, Items.ENDER_EYE, Items.ENDER_PEARL};
        else if (offered == Items.HONEY_BOTTLE) pool = new Item[]{Items.HONEYCOMB, Items.SLIME_BALL, Items.GLOW_BERRIES};
        else if (offered == Items.FEATHER) pool = new Item[]{Items.PHANTOM_MEMBRANE, Items.ARROW, Items.RABBIT_FOOT};
        else pool = new Item[]{Items.PRISMARINE_CRYSTALS, Items.HEART_OF_THE_SEA, Items.TURTLE_SCUTE};
        int index = Math.floorMod(Long.hashCode(seed ^ day ^ offered.hashCode()), pool.length);
        return pool[index];
    }

    private static ServerPlayer nearestOwner(ItemEntity item) {
        ServerPlayer nearest = null;
        double best = 64.0D * 64.0D;
        for (ServerPlayer player : ((net.minecraft.server.level.ServerLevel)item.level()).players()) {
            double distance = player.distanceToSqr(item);
            if (distance < best) {
                best = distance;
                nearest = player;
            }
        }
        return nearest;
    }

    private static void deliverMoonReturn(ServerPlayer player) {
        long at = player.getPersistentData().getLong(RETURN_AT);
        if (at <= 0L || player.level().getGameTime() < at) return;

        String id = player.getPersistentData().getString(RETURN_ITEM);
        var key = net.minecraft.resources.ResourceLocation.tryParse(id);
        Item item = key == null ? Items.STICK : net.minecraft.core.registries.BuiltInRegistries.ITEM.get(key);
        if (item == Items.AIR) item = Items.STICK;

        int count = 1 + Math.floorMod(Long.hashCode(player.serverLevel().getSeed() ^ at), 3);
        ItemEntity drop = new ItemEntity(player.level(), player.getX(), player.getY() + 8.0D, player.getZ(), new ItemStack(item, count));
        drop.setDeltaMovement(0.0D, -0.1D, 0.0D);
        player.level().addFreshEntity(drop);

        player.getPersistentData().remove(RETURN_AT);
        player.getPersistentData().remove(RETURN_ITEM);
        player.sendSystemMessage(Component.literal("Something has fallen from the sky.")
                .withStyle(ChatFormatting.LIGHT_PURPLE));
    }

    @SubscribeEvent
    public void onLogout(PlayerEvent.PlayerLoggedOutEvent event) {
        rituals.remove(event.getEntity().getUUID());
    }

    private static final class RitualState {
        long lastBellVicinity = Long.MIN_VALUE / 2;
        long lastBreadFire = Long.MIN_VALUE / 2;
        long lastReward = Long.MIN_VALUE / 2;
    }
}
