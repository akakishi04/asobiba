package io.github.akakishi04.asobibatweaks.feature;

import java.util.ArrayDeque;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.WeakHashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.chunk.ChunkStatus;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.tick.LevelTickEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Per-level bounded work scheduler for village/background simulation.
 *
 * <p>All queues run on the logical server thread. Work that cannot fit inside this tick's
 * budget stays queued for later; nothing here force-loads chunks.</p>
 */
public final class VillageSimulationScheduler {
    private static final Logger LOGGER = LoggerFactory.getLogger(VillageSimulationScheduler.class);

    public static final int MAX_EMERGENCY_PER_TICK = 4;
    public static final int MAX_WORKER_PER_TICK = 8;
    public static final int MAX_PLANNING_PER_TICK = 2;
    public static final int MAX_RECONCILE_PER_TICK = 4;
    public static final int MAX_VALIDATION_PER_TICK = 2;
    public static final int MAX_BACKGROUND_PROBES_PER_TICK = 256;

    private static final Map<ServerLevel, LevelState> STATES = new WeakHashMap<>();

    @SubscribeEvent
    public void onLevelTick(LevelTickEvent.Post event) {
        if (!(event.getLevel() instanceof ServerLevel level)) return;

        LevelState state = state(level);
        state.beginTick(level.getGameTime());

        drain(state.emergency, state.emergencyKeys, MAX_EMERGENCY_PER_TICK);
        drain(state.worker, state.workerKeys, MAX_WORKER_PER_TICK);
        drain(state.planning, state.planningKeys, MAX_PLANNING_PER_TICK);
        drain(state.reconcile, state.reconcileKeys, MAX_RECONCILE_PER_TICK);
        drain(state.validation, state.validationKeys, MAX_VALIDATION_PER_TICK);

        if (level.getGameTime() % 10L == 0L && event.hasTime()) {
            drain(state.route, state.routeKeys, 1);
        }
    }

    public static void enqueueEmergency(ServerLevel level, String key, Runnable work) {
        enqueue(state(level).emergency, state(level).emergencyKeys, key, work);
    }

    public static void enqueueWorker(ServerLevel level, String key, Runnable work) {
        enqueue(state(level).worker, state(level).workerKeys, key, work);
    }

    public static void enqueuePlanning(ServerLevel level, String key, Runnable work) {
        enqueue(state(level).planning, state(level).planningKeys, key, work);
    }

    public static void enqueueReconciliation(ServerLevel level, String key, Runnable work) {
        enqueue(state(level).reconcile, state(level).reconcileKeys, key, work);
    }

    public static void enqueueValidation(ServerLevel level, String key, Runnable work) {
        enqueue(state(level).validation, state(level).validationKeys, key, work);
    }

    public static void enqueueRouteSearch(ServerLevel level, String key, Runnable work) {
        enqueue(state(level).route, state(level).routeKeys, key, work);
    }

    /**
     * Shared low-priority local-probe budget. Validation/environment scans should stop
     * conservatively when this budget is exhausted and retry on a later scheduled pass.
     */
    public static boolean tryConsumeBlockProbe(ServerLevel level) {
        LevelState state = state(level);
        state.beginTick(level.getGameTime());
        if (state.backgroundProbes >= MAX_BACKGROUND_PROBES_PER_TICK) return false;
        state.backgroundProbes++;
        return true;
    }

    /**
     * Returns true only when the FULL chunk already exists. The false getChunk flag is
     * essential: village simulation must never request/generate a chunk just to inspect it.
     */
    public static boolean isChunkLoaded(ServerLevel level, BlockPos pos) {
        return level.getChunk(pos.getX() >> 4, pos.getZ() >> 4, ChunkStatus.FULL, false) != null;
    }

    public static boolean isAreaLoaded(ServerLevel level, BlockPos a, BlockPos b) {
        int minChunkX = Math.min(a.getX(), b.getX()) >> 4;
        int maxChunkX = Math.max(a.getX(), b.getX()) >> 4;
        int minChunkZ = Math.min(a.getZ(), b.getZ()) >> 4;
        int maxChunkZ = Math.max(a.getZ(), b.getZ()) >> 4;

        for (int chunkX = minChunkX; chunkX <= maxChunkX; chunkX++) {
            for (int chunkZ = minChunkZ; chunkZ <= maxChunkZ; chunkZ++) {
                if (level.getChunk(chunkX, chunkZ, ChunkStatus.FULL, false) == null) return false;
            }
        }
        return true;
    }

    public static QueueSnapshot snapshot(ServerLevel level) {
        LevelState state = state(level);
        return new QueueSnapshot(
                state.emergency.size(),
                state.worker.size(),
                state.planning.size(),
                state.reconcile.size(),
                state.validation.size(),
                state.route.size(),
                state.backgroundProbes
        );
    }

    private static LevelState state(ServerLevel level) {
        synchronized (STATES) {
            return STATES.computeIfAbsent(level, ignored -> new LevelState());
        }
    }

    private static void enqueue(ArrayDeque<ScheduledWork> queue, Set<String> keys, String key, Runnable work) {
        if (work == null || key == null || key.isBlank()) return;
        if (!keys.add(key)) return;
        queue.addLast(new ScheduledWork(key, work));
    }

    private static void drain(ArrayDeque<ScheduledWork> queue, Set<String> keys, int budget) {
        for (int i = 0; i < budget && !queue.isEmpty(); i++) {
            ScheduledWork scheduled = queue.removeFirst();
            keys.remove(scheduled.key);
            try {
                scheduled.work.run();
            } catch (RuntimeException ex) {
                LOGGER.error("Village simulation scheduled work '{}' failed", scheduled.key, ex);
            }
        }
    }

    private record ScheduledWork(String key, Runnable work) {
    }

    private static final class LevelState {
        private final ArrayDeque<ScheduledWork> emergency = new ArrayDeque<>();
        private final Set<String> emergencyKeys = new HashSet<>();
        private final ArrayDeque<ScheduledWork> worker = new ArrayDeque<>();
        private final Set<String> workerKeys = new HashSet<>();
        private final ArrayDeque<ScheduledWork> planning = new ArrayDeque<>();
        private final Set<String> planningKeys = new HashSet<>();
        private final ArrayDeque<ScheduledWork> reconcile = new ArrayDeque<>();
        private final Set<String> reconcileKeys = new HashSet<>();
        private final ArrayDeque<ScheduledWork> validation = new ArrayDeque<>();
        private final Set<String> validationKeys = new HashSet<>();
        private final ArrayDeque<ScheduledWork> route = new ArrayDeque<>();
        private final Set<String> routeKeys = new HashSet<>();

        private long budgetTick = Long.MIN_VALUE;
        private int backgroundProbes;

        private void beginTick(long gameTime) {
            if (budgetTick == gameTime) return;
            budgetTick = gameTime;
            backgroundProbes = 0;
        }
    }

    public record QueueSnapshot(
            int emergency,
            int worker,
            int planning,
            int reconciliation,
            int validation,
            int route,
            int backgroundProbes
    ) {
    }
}
