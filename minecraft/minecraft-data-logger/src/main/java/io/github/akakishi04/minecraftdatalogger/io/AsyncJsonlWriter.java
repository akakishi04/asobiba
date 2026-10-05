package io.github.akakishi04.minecraftdatalogger.io;

import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

public final class AsyncJsonlWriter implements AutoCloseable {
    private final ArrayBlockingQueue<String> queue;
    private final AtomicBoolean running = new AtomicBoolean(true);
    private final AtomicLong dropped = new AtomicLong();
    private final Thread worker;

    public AsyncJsonlWriter(Path path, int capacity) throws IOException {
        Files.createDirectories(path.getParent());
        this.queue = new ArrayBlockingQueue<>(capacity);

        BufferedWriter writer = Files.newBufferedWriter(
                path,
                StandardCharsets.UTF_8,
                StandardOpenOption.CREATE,
                StandardOpenOption.TRUNCATE_EXISTING,
                StandardOpenOption.WRITE
        );

        this.worker = Thread.ofPlatform()
                .name("minecraft-data-logger-" + path.getFileName())
                .daemon(true)
                .start(() -> runWriter(writer));
    }

    public void offer(String jsonLine) {
        if (!running.get()) {
            return;
        }
        if (!queue.offer(jsonLine)) {
            dropped.incrementAndGet();
        }
    }

    public long getDroppedCount() {
        return dropped.get();
    }

    private void runWriter(BufferedWriter writer) {
        List<String> batch = new ArrayList<>(256);
        try (writer) {
            while (running.get() || !queue.isEmpty()) {
                String first = queue.poll(250, TimeUnit.MILLISECONDS);
                if (first == null) {
                    writer.flush();
                    continue;
                }

                batch.clear();
                batch.add(first);
                queue.drainTo(batch, 255);

                for (String line : batch) {
                    writer.write(line);
                    writer.newLine();
                }
                writer.flush();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } catch (IOException ignored) {
            // Capture must never crash the game. Dropped/error counters will be surfaced in later schema revisions.
        }
    }

    @Override
    public void close() {
        running.set(false);
        try {
            worker.join(3000L);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
