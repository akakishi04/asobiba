package io.github.akakishi04.minecraftdatalogger;

import net.neoforged.neoforge.common.ModConfigSpec;

public final class LoggerConfig {
    private static final ModConfigSpec.Builder BUILDER = new ModConfigSpec.Builder();

    public static final ModConfigSpec.BooleanValue ENABLED = BUILDER
            .comment("Enable data capture.")
            .define("logger.enabled", true);

    public static final ModConfigSpec.IntValue OBSERVATION_INTERVAL_TICKS = BUILDER
            .comment("Write one observation every N server-side player ticks.")
            .defineInRange("logger.observationIntervalTicks", 10, 1, 1200);

    public static final ModConfigSpec.BooleanValue CAPTURE_INVENTORY = BUILDER
            .comment("Include compact inventory snapshots in observations.")
            .define("logger.captureInventory", true);

    public static final ModConfigSpec.BooleanValue CAPTURE_EVENTS = BUILDER
            .comment("Capture event records such as block breaks and kills.")
            .define("logger.captureEvents", true);

    public static final ModConfigSpec.IntValue WRITER_QUEUE_CAPACITY = BUILDER
            .comment("Maximum queued JSONL records per output stream before records are dropped.")
            .defineInRange("logger.writerQueueCapacity", 8192, 128, 1000000);

    public static final ModConfigSpec SPEC = BUILDER.build();

    private LoggerConfig() {
    }
}
