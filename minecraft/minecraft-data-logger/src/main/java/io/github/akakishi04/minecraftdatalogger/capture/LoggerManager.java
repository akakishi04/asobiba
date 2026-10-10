package io.github.akakishi04.minecraftdatalogger.capture;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import net.minecraft.server.level.ServerPlayer;

public final class LoggerManager {
    private final Map<UUID, PlayerLogSession> sessions = new HashMap<>();

    public PlayerLogSession open(ServerPlayer player) {
        close(player.getUUID());
        try {
            PlayerLogSession session = new PlayerLogSession(player);
            sessions.put(player.getUUID(), session);
            return session;
        } catch (IOException ignored) {
            return null;
        }
    }

    public PlayerLogSession get(ServerPlayer player) {
        return sessions.get(player.getUUID());
    }

    public void close(UUID playerId) {
        PlayerLogSession session = sessions.remove(playerId);
        if (session != null) {
            session.close();
        }
    }

    public void closeAll() {
        sessions.values().forEach(PlayerLogSession::close);
        sessions.clear();
    }
}
