package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.player.PlayerEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

public final class PlayTimeLimitEvents {
    private final Map<UUID, Long> sessionTicks = new HashMap<>();
    private final Set<UUID> warned = new HashSet<>();
    private final Set<UUID> reachedLimit = new HashSet<>();

    @SubscribeEvent
    public void onPlayerTick(PlayerTickEvent.Post event) {
        if (!AsobibaTweaksConfig.PLAY_TIME_LIMIT_ENABLED.getAsBoolean()) {
            return;
        }
        if (!(event.getEntity() instanceof ServerPlayer player)) {
            return;
        }

        UUID id = player.getUUID();
        long used = sessionTicks.merge(id, 1L, Long::sum);
        long limit = AsobibaTweaksConfig.PLAY_TIME_LIMIT_MINUTES.getAsInt() * 20L * 60L;
        long warning = AsobibaTweaksConfig.PLAY_TIME_WARNING_MINUTES.getAsInt() * 20L * 60L;

        if (warning > 0L && warning < limit && used >= limit - warning && warned.add(id)) {
            long minutes = Math.max(1L, warning / (20L * 60L));
            player.sendSystemMessage(Component.literal(
                    "Play time limit: about " + minutes + " minute(s) remaining."
            ).withStyle(ChatFormatting.YELLOW));
        }

        if (used < limit || !reachedLimit.add(id)) {
            return;
        }

        String mode = AsobibaTweaksConfig.PLAY_TIME_LIMIT_MODE.get();
        if ("DISCONNECT".equalsIgnoreCase(mode)) {
            player.connection.disconnect(Component.literal("Play time limit reached."));
        } else {
            player.sendSystemMessage(Component.literal("Play time limit reached.")
                    .withStyle(ChatFormatting.RED));
        }
    }

    @SubscribeEvent
    public void onLogout(PlayerEvent.PlayerLoggedOutEvent event) {
        UUID id = event.getEntity().getUUID();
        sessionTicks.remove(id);
        warned.remove(id);
        reachedLimit.remove(id);
    }
}
