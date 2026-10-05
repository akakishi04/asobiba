package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.living.LivingDeathEvent;
import net.neoforged.neoforge.event.entity.player.PlayerEvent;
import net.neoforged.neoforge.event.level.BlockDropsEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

public final class DailyFavorEvents {
    private final Map<UUID, Long> announcedDay = new HashMap<>();

    @SubscribeEvent
    public void onPlayerTick(PlayerTickEvent.Post event) {
        if (!AsobibaTweaksConfig.DAILY_FAVOR_ENABLED.getAsBoolean()) {
            return;
        }
        if (!(event.getEntity() instanceof ServerPlayer player)) {
            return;
        }
        if (player.level().getGameTime() % 20L != 0L) {
            return;
        }

        long day = dayNumber(player);
        Long previous = announcedDay.put(player.getUUID(), day);
        if (previous == null || previous.longValue() != day) {
            DailyFavorType favor = currentFavor(player);
            player.sendSystemMessage(Component.literal(
                    "Today's favor: " + favor.displayName() + " — " + favor.hint() + " for a small XP chance."
            ).withStyle(ChatFormatting.AQUA));
        }
    }

    @SubscribeEvent
    public void onBlockDrops(BlockDropsEvent event) {
        if (!AsobibaTweaksConfig.DAILY_FAVOR_ENABLED.getAsBoolean()) {
            return;
        }
        if (!(event.getBreaker() instanceof ServerPlayer player)) {
            return;
        }

        DailyFavorType favor = currentFavor(player);
        if (favor.matchesBlock(event.getState())) {
            maybeReward(player);
        }
    }

    @SubscribeEvent
    public void onLivingDeath(LivingDeathEvent event) {
        if (!AsobibaTweaksConfig.DAILY_FAVOR_ENABLED.getAsBoolean()) {
            return;
        }
        if (!(event.getSource().getEntity() instanceof ServerPlayer player)) {
            return;
        }
        if (currentFavor(player) == DailyFavorType.HUNTING) {
            maybeReward(player);
        }
    }

    @SubscribeEvent
    public void onLogout(PlayerEvent.PlayerLoggedOutEvent event) {
        announcedDay.remove(event.getEntity().getUUID());
    }

    private static void maybeReward(ServerPlayer player) {
        if (player.getRandom().nextDouble() < AsobibaTweaksConfig.DAILY_FAVOR_REWARD_CHANCE.getAsDouble()) {
            player.giveExperiencePoints(AsobibaTweaksConfig.DAILY_FAVOR_XP.getAsInt());
        }
    }

    private static DailyFavorType currentFavor(ServerPlayer player) {
        DailyFavorType[] values = DailyFavorType.values();
        long day = dayNumber(player);
        long mixed = player.serverLevel().getSeed() ^ (day * 0x9E3779B97F4A7C15L);
        int index = Math.floorMod(Long.hashCode(mixed), values.length);
        return values[index];
    }

    private static long dayNumber(ServerPlayer player) {
        return Math.floorDiv(player.level().getDayTime(), 24000L);
    }
}
