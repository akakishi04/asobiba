package io.github.akakishi04.minecraftdatalogger.capture;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import io.github.akakishi04.minecraftdatalogger.LoggerConfig;
import io.github.akakishi04.minecraftdatalogger.io.AsyncJsonlWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicLong;
import net.minecraft.server.level.ServerPlayer;

public final class PlayerLogSession implements AutoCloseable {
    public static final int SCHEMA_VERSION = 1;
    private static final Gson GSON = new GsonBuilder().disableHtmlEscaping().create();
    private static final DateTimeFormatter SESSION_TIME = DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss");

    private final String sessionId;
    private final AtomicLong sequence = new AtomicLong();
    private final AsyncJsonlWriter observations;
    private final AsyncJsonlWriter events;

    public PlayerLogSession(ServerPlayer player) throws IOException {
        String stamp = SESSION_TIME.format(LocalDateTime.now());
        this.sessionId = stamp + "_" + player.getUUID();

        Path root = Path.of("minecraft-data-logger").resolve(sessionId);
        Files.createDirectories(root);

        writeMetadata(root.resolve("metadata.json"), player);

        int capacity = LoggerConfig.WRITER_QUEUE_CAPACITY.getAsInt();
        this.observations = new AsyncJsonlWriter(root.resolve("observations.jsonl"), capacity);
        this.events = new AsyncJsonlWriter(root.resolve("events.jsonl"), capacity);
    }

    public String sessionId() {
        return sessionId;
    }

    public long nextSequence() {
        return sequence.incrementAndGet();
    }

    public void observation(JsonObject object) {
        observations.offer(GSON.toJson(object));
    }

    public void event(JsonObject object) {
        events.offer(GSON.toJson(object));
    }

    private void writeMetadata(Path path, ServerPlayer player) throws IOException {
        JsonObject meta = new JsonObject();
        meta.addProperty("schema_version", SCHEMA_VERSION);
        meta.addProperty("session_id", sessionId);
        meta.addProperty("minecraft_version", "1.21.1");
        meta.addProperty("neoforge_version", "21.1.219");
        meta.addProperty("player_uuid", player.getUUID().toString());
        meta.addProperty("started_at_local", LocalDateTime.now().toString());
        meta.addProperty("initial_dimension", player.level().dimension().location().toString());

        Files.writeString(
                path,
                GSON.toJson(meta),
                StandardCharsets.UTF_8,
                java.nio.file.StandardOpenOption.CREATE,
                java.nio.file.StandardOpenOption.TRUNCATE_EXISTING
        );
    }

    @Override
    public void close() {
        observations.close();
        events.close();
    }
}
