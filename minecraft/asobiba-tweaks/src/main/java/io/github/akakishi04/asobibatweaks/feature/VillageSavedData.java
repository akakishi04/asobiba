package io.github.akakishi04.asobibatweaks.feature;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.HolderLookup;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.datafix.DataFixTypes;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.saveddata.SavedData;

/**
 * Persistent village-simulation state.
 *
 * <p>The physical world remains authoritative. These records are durable identities,
 * indexes, caches and planning state that later passes can reconcile against loaded chunks.</p>
 */
public final class VillageSavedData extends SavedData {
    public static final int SCHEMA_VERSION = 1;

    private static final String NAME = "asobibatweaks_villages";
    private static final Factory<VillageSavedData> FACTORY =
            new Factory<>(VillageSavedData::new, VillageSavedData::load, DataFixTypes.SAVED_DATA_RANDOM_SEQUENCES);

    private final Map<UUID, VillageRecord> villages = new HashMap<>();
    private final Map<UUID, BuildingRecord> buildings = new HashMap<>();
    private final Map<UUID, StorageRecord> storages = new HashMap<>();
    private final Map<UUID, WorkSiteRecord> workSites = new HashMap<>();
    private final Map<UUID, RouteRecord> routes = new HashMap<>();
    private final Map<UUID, ProjectRecord> projects = new HashMap<>();
    private final Map<UUID, MigrationRecord> migrations = new HashMap<>();

    /**
     * Derived runtime index. It is rebuilt from persistent records after load so a stale
     * serialized index can never make physical records unreachable.
     */
    private final Map<Long, ChunkIndexEntry> chunkIndex = new HashMap<>();

    public static VillageSavedData get(ServerLevel level) {
        return level.getDataStorage().computeIfAbsent(FACTORY, NAME);
    }

    public Optional<VillageRecord> village(UUID id) {
        return Optional.ofNullable(villages.get(id));
    }

    public Optional<BuildingRecord> building(UUID id) {
        return Optional.ofNullable(buildings.get(id));
    }

    public Optional<StorageRecord> storage(UUID id) {
        return Optional.ofNullable(storages.get(id));
    }

    public Optional<WorkSiteRecord> workSite(UUID id) {
        return Optional.ofNullable(workSites.get(id));
    }

    public Optional<RouteRecord> route(UUID id) {
        return Optional.ofNullable(routes.get(id));
    }

    public Optional<ProjectRecord> project(UUID id) {
        return Optional.ofNullable(projects.get(id));
    }

    public Optional<MigrationRecord> migration(UUID id) {
        return Optional.ofNullable(migrations.get(id));
    }

    public Map<UUID, VillageRecord> villagesView() {
        return Collections.unmodifiableMap(villages);
    }

    public Map<UUID, ProjectRecord> projectsView() {
        return Collections.unmodifiableMap(projects);
    }

    public VillageRecord createVillage(BlockPos center, long createdGameTime) {
        return ensureVillage(nextId(villages), center, createdGameTime);
    }

    /**
     * Creates a missing record with a caller-supplied stable ID, or returns the existing one.
     * This is used by conservative bootstrap/recovery when a Villager already carries a
     * persistent Village ID but the shared record has not yet been materialized.
     */
    public VillageRecord ensureVillage(UUID id, BlockPos center, long createdGameTime) {
        VillageRecord existing = villages.get(id);
        if (existing != null) return existing;

        VillageRecord record = new VillageRecord(id, center.immutable(), createdGameTime);
        villages.put(id, record);
        setDirty();
        return record;
    }

    public BuildingRecord createBuilding(UUID villageId, BlockPos min, BlockPos max, boolean villageBuilt) {
        requireVillage(villageId);
        UUID id = nextId(buildings);
        BuildingRecord record = new BuildingRecord(id, villageId, normalizeMin(min, max), normalizeMax(min, max), villageBuilt);
        buildings.put(id, record);
        villages.get(villageId).buildingIds.add(id);
        indexBuilding(record);
        setDirty();
        return record;
    }

    public StorageRecord createStorage(UUID villageId, BlockPos pos, String category) {
        requireVillage(villageId);
        UUID id = nextId(storages);
        StorageRecord record = new StorageRecord(id, villageId, pos.immutable(), safeText(category, "general"));
        storages.put(id, record);
        villages.get(villageId).storageIds.add(id);
        indexOne(pos, entryFor(pos).storageIds, id);
        setDirty();
        return record;
    }

    public WorkSiteRecord createWorkSite(UUID villageId, String type, BlockPos min, BlockPos max) {
        requireVillage(villageId);
        UUID id = nextId(workSites);
        WorkSiteRecord record = new WorkSiteRecord(id, villageId, safeText(type, "generic"),
                normalizeMin(min, max), normalizeMax(min, max));
        workSites.put(id, record);
        villages.get(villageId).workSiteIds.add(id);
        indexBounds(record.min, record.max, IndexKind.WORK_SITE, id);
        setDirty();
        return record;
    }

    public RouteRecord createRoute(UUID villageId, String type, BlockPos from, BlockPos to) {
        requireVillage(villageId);
        UUID id = nextId(routes);
        RouteRecord record = new RouteRecord(id, villageId, safeText(type, "path"), from.immutable(), to.immutable());
        routes.put(id, record);
        villages.get(villageId).routeIds.add(id);
        indexOne(from, entryFor(from).routeIds, id);
        indexOne(to, entryFor(to).routeIds, id);
        setDirty();
        return record;
    }

    public ProjectRecord createProject(UUID villageId, String type, int priority, BlockPos site) {
        requireVillage(villageId);
        UUID id = nextId(projects);
        ProjectRecord record = new ProjectRecord(id, villageId, safeText(type, "generic"), priority, site.immutable());
        projects.put(id, record);
        villages.get(villageId).projectIds.add(id);
        indexOne(site, entryFor(site).projectIds, id);
        setDirty();
        return record;
    }

    public MigrationRecord createMigration(UUID originVillageId, UUID destinationVillageId, List<UUID> members) {
        requireVillage(originVillageId);
        if (destinationVillageId != null) {
            requireVillage(destinationVillageId);
        }

        UUID id = nextId(migrations);
        MigrationRecord record = new MigrationRecord(id, originVillageId, destinationVillageId);
        record.members.addAll(members);
        migrations.put(id, record);
        setDirty();
        return record;
    }

    public void registerResident(UUID villageId, UUID villagerId) {
        requireVillage(villageId);
        VillageRecord target = villages.get(villageId);
        if (target.residentIds.contains(villagerId)) return;

        boolean changed = false;
        for (VillageRecord village : villages.values()) {
            if (!village.id.equals(villageId)) {
                changed |= village.residentIds.remove(villagerId);
            }
        }
        changed |= target.residentIds.add(villagerId);
        if (changed) setDirty();
    }

    public void unregisterResident(UUID villageId, UUID villagerId) {
        VillageRecord village = villages.get(villageId);
        if (village != null && village.residentIds.remove(villagerId)) {
            setDirty();
        }
    }

    public ChunkIndexView recordsForChunk(ChunkPos chunk) {
        ChunkIndexEntry entry = chunkIndex.get(chunk.toLong());
        if (entry == null) {
            return ChunkIndexView.EMPTY;
        }
        return entry.snapshot();
    }

    public void touch() {
        setDirty();
    }

    public static VillageSavedData load(CompoundTag tag, HolderLookup.Provider registries) {
        VillageSavedData data = new VillageSavedData();

        int version = tag.contains("schema", Tag.TAG_INT) ? tag.getInt("schema") : 0;
        if (version > SCHEMA_VERSION) {
            // Forward-compatible best effort: known fields remain readable; physical world state
            // stays authoritative and later validation can repair incomplete cached records.
        }

        loadRows(tag, "villages", row -> {
            VillageRecord record = VillageRecord.load(row);
            if (record != null) data.villages.put(record.id, record);
        });
        loadRows(tag, "buildings", row -> {
            BuildingRecord record = BuildingRecord.load(row);
            if (record != null) data.buildings.put(record.id, record);
        });
        loadRows(tag, "storages", row -> {
            StorageRecord record = StorageRecord.load(row);
            if (record != null) data.storages.put(record.id, record);
        });
        loadRows(tag, "work_sites", row -> {
            WorkSiteRecord record = WorkSiteRecord.load(row);
            if (record != null) data.workSites.put(record.id, record);
        });
        loadRows(tag, "routes", row -> {
            RouteRecord record = RouteRecord.load(row);
            if (record != null) data.routes.put(record.id, record);
        });
        loadRows(tag, "projects", row -> {
            ProjectRecord record = ProjectRecord.load(row);
            if (record != null) data.projects.put(record.id, record);
        });
        loadRows(tag, "migrations", row -> {
            MigrationRecord record = MigrationRecord.load(row);
            if (record != null) data.migrations.put(record.id, record);
        });

        data.repairReferences();
        data.rebuildChunkIndex();
        return data;
    }

    @Override
    public CompoundTag save(CompoundTag tag, HolderLookup.Provider registries) {
        tag.putInt("schema", SCHEMA_VERSION);
        tag.put("villages", saveRows(villages.values().stream().map(VillageRecord::save).toList()));
        tag.put("buildings", saveRows(buildings.values().stream().map(BuildingRecord::save).toList()));
        tag.put("storages", saveRows(storages.values().stream().map(StorageRecord::save).toList()));
        tag.put("work_sites", saveRows(workSites.values().stream().map(WorkSiteRecord::save).toList()));
        tag.put("routes", saveRows(routes.values().stream().map(RouteRecord::save).toList()));
        tag.put("projects", saveRows(projects.values().stream().map(ProjectRecord::save).toList()));
        tag.put("migrations", saveRows(migrations.values().stream().map(MigrationRecord::save).toList()));
        return tag;
    }

    private void repairReferences() {
        // Drop orphan child records first, then clean each VillageRecord's ID sets.
        // Physical world state is never deleted by this cache repair.
        buildings.values().removeIf(record -> !villages.containsKey(record.villageId));
        storages.values().removeIf(record -> !villages.containsKey(record.villageId));
        workSites.values().removeIf(record -> !villages.containsKey(record.villageId));
        routes.values().removeIf(record -> !villages.containsKey(record.villageId));
        projects.values().removeIf(record -> !villages.containsKey(record.villageId));
        migrations.values().removeIf(record -> !villages.containsKey(record.originVillageId)
                || (record.destinationVillageId != null && !villages.containsKey(record.destinationVillageId)));

        for (VillageRecord village : villages.values()) {
            village.buildingIds.removeIf(id -> !buildings.containsKey(id));
            village.storageIds.removeIf(id -> !storages.containsKey(id));
            village.workSiteIds.removeIf(id -> !workSites.containsKey(id));
            village.routeIds.removeIf(id -> !routes.containsKey(id));
            village.projectIds.removeIf(id -> !projects.containsKey(id));
        }
    }

    private void rebuildChunkIndex() {
        chunkIndex.clear();
        for (BuildingRecord record : buildings.values()) indexBuilding(record);
        for (StorageRecord record : storages.values()) indexOne(record.pos, entryFor(record.pos).storageIds, record.id);
        for (WorkSiteRecord record : workSites.values()) indexBounds(record.min, record.max, IndexKind.WORK_SITE, record.id);
        for (RouteRecord record : routes.values()) {
            indexOne(record.from, entryFor(record.from).routeIds, record.id);
            indexOne(record.to, entryFor(record.to).routeIds, record.id);
        }
        for (ProjectRecord record : projects.values()) indexOne(record.site, entryFor(record.site).projectIds, record.id);
    }

    private void indexBuilding(BuildingRecord record) {
        indexBounds(record.min, record.max, IndexKind.BUILDING, record.id);
    }

    private void indexBounds(BlockPos min, BlockPos max, IndexKind kind, UUID id) {
        int minChunkX = min.getX() >> 4;
        int maxChunkX = max.getX() >> 4;
        int minChunkZ = min.getZ() >> 4;
        int maxChunkZ = max.getZ() >> 4;

        for (int chunkX = minChunkX; chunkX <= maxChunkX; chunkX++) {
            for (int chunkZ = minChunkZ; chunkZ <= maxChunkZ; chunkZ++) {
                ChunkIndexEntry entry = chunkIndex.computeIfAbsent(ChunkPos.asLong(chunkX, chunkZ), ignored -> new ChunkIndexEntry());
                if (kind == IndexKind.BUILDING) entry.buildingIds.add(id);
                if (kind == IndexKind.WORK_SITE) entry.workSiteIds.add(id);
            }
        }
    }

    private ChunkIndexEntry entryFor(BlockPos pos) {
        return chunkIndex.computeIfAbsent(new ChunkPos(pos).toLong(), ignored -> new ChunkIndexEntry());
    }

    private static void indexOne(BlockPos pos, Set<UUID> set, UUID id) {
        set.add(id);
    }

    private void requireVillage(UUID id) {
        if (!villages.containsKey(id)) {
            throw new IllegalArgumentException("Unknown village id: " + id);
        }
    }

    private static UUID nextId(Map<UUID, ?> existing) {
        UUID id;
        do {
            id = UUID.randomUUID();
        } while (existing.containsKey(id));
        return id;
    }

    private static BlockPos normalizeMin(BlockPos a, BlockPos b) {
        return new BlockPos(Math.min(a.getX(), b.getX()), Math.min(a.getY(), b.getY()), Math.min(a.getZ(), b.getZ()));
    }

    private static BlockPos normalizeMax(BlockPos a, BlockPos b) {
        return new BlockPos(Math.max(a.getX(), b.getX()), Math.max(a.getY(), b.getY()), Math.max(a.getZ(), b.getZ()));
    }

    private static String safeText(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    private static void putUuid(CompoundTag tag, String key, UUID value) {
        if (value != null) tag.putString(key, value.toString());
    }

    private static UUID readUuid(CompoundTag tag, String key) {
        if (!tag.contains(key, Tag.TAG_STRING)) return null;
        String raw = tag.getString(key);
        if (raw.isBlank()) return null;
        try {
            return UUID.fromString(raw);
        } catch (IllegalArgumentException ignored) {
            return null;
        }
    }

    private static Set<UUID> readUuidSet(CompoundTag tag, String key) {
        Set<UUID> ids = new LinkedHashSet<>();
        ListTag rows = tag.getList(key, Tag.TAG_COMPOUND);
        for (int i = 0; i < rows.size(); i++) {
            UUID id = readUuid(rows.getCompound(i), "id");
            if (id != null) ids.add(id);
        }
        return ids;
    }

    private static ListTag writeUuidSet(Set<UUID> ids) {
        ListTag rows = new ListTag();
        for (UUID id : ids) {
            CompoundTag row = new CompoundTag();
            putUuid(row, "id", id);
            rows.add(row);
        }
        return rows;
    }

    private static void loadRows(CompoundTag tag, String key, java.util.function.Consumer<CompoundTag> consumer) {
        ListTag rows = tag.getList(key, Tag.TAG_COMPOUND);
        for (int i = 0; i < rows.size(); i++) consumer.accept(rows.getCompound(i));
    }

    private static ListTag saveRows(List<CompoundTag> rows) {
        ListTag list = new ListTag();
        list.addAll(rows);
        return list;
    }

    private enum IndexKind {
        BUILDING,
        WORK_SITE
    }

    public static final class VillageRecord {
        private final UUID id;
        private BlockPos center;
        private final long createdGameTime;
        private String lifecycle = "active";
        private final Set<UUID> residentIds = new LinkedHashSet<>();
        private final Set<UUID> buildingIds = new LinkedHashSet<>();
        private final Set<UUID> storageIds = new LinkedHashSet<>();
        private final Set<UUID> workSiteIds = new LinkedHashSet<>();
        private final Set<UUID> routeIds = new LinkedHashSet<>();
        private final Set<UUID> projectIds = new LinkedHashSet<>();
        private long nextPlanningGameTime;
        private long lastValidatedGameTime;

        private VillageRecord(UUID id, BlockPos center, long createdGameTime) {
            this.id = id;
            this.center = center;
            this.createdGameTime = createdGameTime;
        }

        public UUID id() { return id; }
        public BlockPos center() { return center; }
        public String lifecycle() { return lifecycle; }
        public Set<UUID> residentIds() { return Collections.unmodifiableSet(residentIds); }
        public Set<UUID> buildingIds() { return Collections.unmodifiableSet(buildingIds); }
        public Set<UUID> storageIds() { return Collections.unmodifiableSet(storageIds); }
        public Set<UUID> workSiteIds() { return Collections.unmodifiableSet(workSiteIds); }
        public Set<UUID> routeIds() { return Collections.unmodifiableSet(routeIds); }
        public Set<UUID> projectIds() { return Collections.unmodifiableSet(projectIds); }
        public long nextPlanningGameTime() { return nextPlanningGameTime; }
        public long lastValidatedGameTime() { return lastValidatedGameTime; }

        public void setCenter(BlockPos center) { this.center = center.immutable(); }
        public void setLifecycle(String lifecycle) { this.lifecycle = safeText(lifecycle, "active"); }
        public void setNextPlanningGameTime(long value) { this.nextPlanningGameTime = value; }
        public void setLastValidatedGameTime(long value) { this.lastValidatedGameTime = value; }

        private CompoundTag save() {
            CompoundTag tag = new CompoundTag();
            putUuid(tag, "id", id);
            tag.putLong("center", center.asLong());
            tag.putLong("created", createdGameTime);
            tag.putString("lifecycle", lifecycle);
            tag.put("residents", writeUuidSet(residentIds));
            tag.put("buildings", writeUuidSet(buildingIds));
            tag.put("storages", writeUuidSet(storageIds));
            tag.put("work_sites", writeUuidSet(workSiteIds));
            tag.put("routes", writeUuidSet(routeIds));
            tag.put("projects", writeUuidSet(projectIds));
            tag.putLong("next_planning", nextPlanningGameTime);
            tag.putLong("last_validated", lastValidatedGameTime);
            return tag;
        }

        private static VillageRecord load(CompoundTag tag) {
            UUID id = readUuid(tag, "id");
            if (id == null || !tag.contains("center", Tag.TAG_LONG)) return null;

            VillageRecord record = new VillageRecord(id, BlockPos.of(tag.getLong("center")), tag.getLong("created"));
            record.lifecycle = safeText(tag.getString("lifecycle"), "active");
            record.residentIds.addAll(readUuidSet(tag, "residents"));
            record.buildingIds.addAll(readUuidSet(tag, "buildings"));
            record.storageIds.addAll(readUuidSet(tag, "storages"));
            record.workSiteIds.addAll(readUuidSet(tag, "work_sites"));
            record.routeIds.addAll(readUuidSet(tag, "routes"));
            record.projectIds.addAll(readUuidSet(tag, "projects"));
            record.nextPlanningGameTime = tag.getLong("next_planning");
            record.lastValidatedGameTime = tag.getLong("last_validated");
            return record;
        }
    }

    public static final class BuildingRecord {
        private final UUID id;
        private final UUID villageId;
        private final BlockPos min;
        private final BlockPos max;
        private final boolean villageBuilt;
        private String classification = "unassigned";
        private String validationState = "unknown";
        private int validatedCapacity;
        private long lastValidatedGameTime;
        private String templateId = "";

        private BuildingRecord(UUID id, UUID villageId, BlockPos min, BlockPos max, boolean villageBuilt) {
            this.id = id;
            this.villageId = villageId;
            this.min = min;
            this.max = max;
            this.villageBuilt = villageBuilt;
        }

        public UUID id() { return id; }
        public UUID villageId() { return villageId; }
        public BlockPos min() { return min; }
        public BlockPos max() { return max; }
        public boolean villageBuilt() { return villageBuilt; }
        public String classification() { return classification; }
        public String validationState() { return validationState; }
        public int validatedCapacity() { return validatedCapacity; }
        public long lastValidatedGameTime() { return lastValidatedGameTime; }
        public String templateId() { return templateId; }

        public void setClassification(String value) { classification = safeText(value, "unassigned"); }
        public void setValidationState(String value) { validationState = safeText(value, "unknown"); }
        public void setValidatedCapacity(int value) { validatedCapacity = Math.max(0, value); }
        public void setLastValidatedGameTime(long value) { lastValidatedGameTime = value; }
        public void setTemplateId(String value) { templateId = value == null ? "" : value; }

        private CompoundTag save() {
            CompoundTag tag = new CompoundTag();
            putUuid(tag, "id", id);
            putUuid(tag, "village", villageId);
            tag.putLong("min", min.asLong());
            tag.putLong("max", max.asLong());
            tag.putBoolean("village_built", villageBuilt);
            tag.putString("classification", classification);
            tag.putString("validation", validationState);
            tag.putInt("capacity", validatedCapacity);
            tag.putLong("last_validated", lastValidatedGameTime);
            tag.putString("template", templateId);
            return tag;
        }

        private static BuildingRecord load(CompoundTag tag) {
            UUID id = readUuid(tag, "id");
            UUID villageId = readUuid(tag, "village");
            if (id == null || villageId == null || !tag.contains("min", Tag.TAG_LONG) || !tag.contains("max", Tag.TAG_LONG)) return null;

            BuildingRecord record = new BuildingRecord(id, villageId, BlockPos.of(tag.getLong("min")),
                    BlockPos.of(tag.getLong("max")), tag.getBoolean("village_built"));
            record.classification = safeText(tag.getString("classification"), "unassigned");
            record.validationState = safeText(tag.getString("validation"), "unknown");
            record.validatedCapacity = Math.max(0, tag.getInt("capacity"));
            record.lastValidatedGameTime = tag.getLong("last_validated");
            record.templateId = tag.getString("template");
            return record;
        }
    }

    public static final class StorageRecord {
        private final UUID id;
        private final UUID villageId;
        private final BlockPos pos;
        private String category;
        private String validationState = "unknown";
        private long lastValidatedGameTime;

        private StorageRecord(UUID id, UUID villageId, BlockPos pos, String category) {
            this.id = id;
            this.villageId = villageId;
            this.pos = pos;
            this.category = category;
        }

        public UUID id() { return id; }
        public UUID villageId() { return villageId; }
        public BlockPos pos() { return pos; }
        public String category() { return category; }
        public String validationState() { return validationState; }
        public long lastValidatedGameTime() { return lastValidatedGameTime; }

        public void setCategory(String value) { category = safeText(value, "general"); }
        public void setValidationState(String value) { validationState = safeText(value, "unknown"); }
        public void setLastValidatedGameTime(long value) { lastValidatedGameTime = value; }

        private CompoundTag save() {
            CompoundTag tag = new CompoundTag();
            putUuid(tag, "id", id);
            putUuid(tag, "village", villageId);
            tag.putLong("pos", pos.asLong());
            tag.putString("category", category);
            tag.putString("validation", validationState);
            tag.putLong("last_validated", lastValidatedGameTime);
            return tag;
        }

        private static StorageRecord load(CompoundTag tag) {
            UUID id = readUuid(tag, "id");
            UUID villageId = readUuid(tag, "village");
            if (id == null || villageId == null || !tag.contains("pos", Tag.TAG_LONG)) return null;

            StorageRecord record = new StorageRecord(id, villageId, BlockPos.of(tag.getLong("pos")),
                    safeText(tag.getString("category"), "general"));
            record.validationState = safeText(tag.getString("validation"), "unknown");
            record.lastValidatedGameTime = tag.getLong("last_validated");
            return record;
        }
    }

    public static final class WorkSiteRecord {
        private final UUID id;
        private final UUID villageId;
        private String type;
        private final BlockPos min;
        private final BlockPos max;
        private String state = "active";
        private long lastUsedGameTime;

        private WorkSiteRecord(UUID id, UUID villageId, String type, BlockPos min, BlockPos max) {
            this.id = id;
            this.villageId = villageId;
            this.type = type;
            this.min = min;
            this.max = max;
        }

        public UUID id() { return id; }
        public UUID villageId() { return villageId; }
        public String type() { return type; }
        public BlockPos min() { return min; }
        public BlockPos max() { return max; }
        public String state() { return state; }
        public long lastUsedGameTime() { return lastUsedGameTime; }

        public void setType(String value) { type = safeText(value, "generic"); }
        public void setState(String value) { state = safeText(value, "active"); }
        public void setLastUsedGameTime(long value) { lastUsedGameTime = value; }

        private CompoundTag save() {
            CompoundTag tag = new CompoundTag();
            putUuid(tag, "id", id);
            putUuid(tag, "village", villageId);
            tag.putString("type", type);
            tag.putLong("min", min.asLong());
            tag.putLong("max", max.asLong());
            tag.putString("state", state);
            tag.putLong("last_used", lastUsedGameTime);
            return tag;
        }

        private static WorkSiteRecord load(CompoundTag tag) {
            UUID id = readUuid(tag, "id");
            UUID villageId = readUuid(tag, "village");
            if (id == null || villageId == null || !tag.contains("min", Tag.TAG_LONG) || !tag.contains("max", Tag.TAG_LONG)) return null;

            WorkSiteRecord record = new WorkSiteRecord(id, villageId, safeText(tag.getString("type"), "generic"),
                    BlockPos.of(tag.getLong("min")), BlockPos.of(tag.getLong("max")));
            record.state = safeText(tag.getString("state"), "active");
            record.lastUsedGameTime = tag.getLong("last_used");
            return record;
        }
    }

    public static final class RouteRecord {
        private final UUID id;
        private final UUID villageId;
        private String type;
        private final BlockPos from;
        private final BlockPos to;
        private int trafficScore;
        private String state = "active";

        private RouteRecord(UUID id, UUID villageId, String type, BlockPos from, BlockPos to) {
            this.id = id;
            this.villageId = villageId;
            this.type = type;
            this.from = from;
            this.to = to;
        }

        public UUID id() { return id; }
        public UUID villageId() { return villageId; }
        public String type() { return type; }
        public BlockPos from() { return from; }
        public BlockPos to() { return to; }
        public int trafficScore() { return trafficScore; }
        public String state() { return state; }

        public void setType(String value) { type = safeText(value, "path"); }
        public void setTrafficScore(int value) { trafficScore = Math.max(0, value); }
        public void setState(String value) { state = safeText(value, "active"); }

        private CompoundTag save() {
            CompoundTag tag = new CompoundTag();
            putUuid(tag, "id", id);
            putUuid(tag, "village", villageId);
            tag.putString("type", type);
            tag.putLong("from", from.asLong());
            tag.putLong("to", to.asLong());
            tag.putInt("traffic", trafficScore);
            tag.putString("state", state);
            return tag;
        }

        private static RouteRecord load(CompoundTag tag) {
            UUID id = readUuid(tag, "id");
            UUID villageId = readUuid(tag, "village");
            if (id == null || villageId == null || !tag.contains("from", Tag.TAG_LONG) || !tag.contains("to", Tag.TAG_LONG)) return null;

            RouteRecord record = new RouteRecord(id, villageId, safeText(tag.getString("type"), "path"),
                    BlockPos.of(tag.getLong("from")), BlockPos.of(tag.getLong("to")));
            record.trafficScore = Math.max(0, tag.getInt("traffic"));
            record.state = safeText(tag.getString("state"), "active");
            return record;
        }
    }

    public static final class ProjectRecord {
        private final UUID id;
        private final UUID villageId;
        private String type;
        private int priority;
        private final BlockPos site;
        private String templateId = "";
        private long variantSeed;
        private String phase = "planned";
        private int workCursor;
        private String pausedReason = "";
        private final Map<String, Integer> reservations = new HashMap<>();

        private ProjectRecord(UUID id, UUID villageId, String type, int priority, BlockPos site) {
            this.id = id;
            this.villageId = villageId;
            this.type = type;
            this.priority = priority;
            this.site = site;
        }

        public UUID id() { return id; }
        public UUID villageId() { return villageId; }
        public String type() { return type; }
        public int priority() { return priority; }
        public BlockPos site() { return site; }
        public String templateId() { return templateId; }
        public long variantSeed() { return variantSeed; }
        public String phase() { return phase; }
        public int workCursor() { return workCursor; }
        public String pausedReason() { return pausedReason; }
        public Map<String, Integer> reservations() { return Collections.unmodifiableMap(reservations); }

        public void setType(String value) { type = safeText(value, "generic"); }
        public void setPriority(int value) { priority = value; }
        public void setTemplateId(String value) { templateId = value == null ? "" : value; }
        public void setVariantSeed(long value) { variantSeed = value; }
        public void setPhase(String value) { phase = safeText(value, "planned"); }
        public void setWorkCursor(int value) { workCursor = Math.max(0, value); }
        public void setPausedReason(String value) { pausedReason = value == null ? "" : value; }

        public void setReservation(String itemKey, int count) {
            if (itemKey == null || itemKey.isBlank() || count <= 0) reservations.remove(itemKey);
            else reservations.put(itemKey, count);
        }

        private CompoundTag save() {
            CompoundTag tag = new CompoundTag();
            putUuid(tag, "id", id);
            putUuid(tag, "village", villageId);
            tag.putString("type", type);
            tag.putInt("priority", priority);
            tag.putLong("site", site.asLong());
            tag.putString("template", templateId);
            tag.putLong("variant_seed", variantSeed);
            tag.putString("phase", phase);
            tag.putInt("cursor", workCursor);
            tag.putString("paused_reason", pausedReason);

            ListTag reservationRows = new ListTag();
            for (var entry : reservations.entrySet()) {
                CompoundTag row = new CompoundTag();
                row.putString("item", entry.getKey());
                row.putInt("count", entry.getValue());
                reservationRows.add(row);
            }
            tag.put("reservations", reservationRows);
            return tag;
        }

        private static ProjectRecord load(CompoundTag tag) {
            UUID id = readUuid(tag, "id");
            UUID villageId = readUuid(tag, "village");
            if (id == null || villageId == null || !tag.contains("site", Tag.TAG_LONG)) return null;

            ProjectRecord record = new ProjectRecord(id, villageId, safeText(tag.getString("type"), "generic"),
                    tag.getInt("priority"), BlockPos.of(tag.getLong("site")));
            record.templateId = tag.getString("template");
            record.variantSeed = tag.getLong("variant_seed");
            record.phase = safeText(tag.getString("phase"), "planned");
            record.workCursor = Math.max(0, tag.getInt("cursor"));
            record.pausedReason = tag.getString("paused_reason");

            ListTag reservationRows = tag.getList("reservations", Tag.TAG_COMPOUND);
            for (int i = 0; i < reservationRows.size(); i++) {
                CompoundTag row = reservationRows.getCompound(i);
                String item = row.getString("item");
                int count = row.getInt("count");
                if (!item.isBlank() && count > 0) record.reservations.put(item, count);
            }
            return record;
        }
    }

    public static final class MigrationRecord {
        private final UUID id;
        private final UUID originVillageId;
        private UUID destinationVillageId;
        private final Set<UUID> members = new LinkedHashSet<>();
        private String state = "planned";
        private long createdGameTime;
        private long updatedGameTime;

        private MigrationRecord(UUID id, UUID originVillageId, UUID destinationVillageId) {
            this.id = id;
            this.originVillageId = originVillageId;
            this.destinationVillageId = destinationVillageId;
        }

        public UUID id() { return id; }
        public UUID originVillageId() { return originVillageId; }
        public UUID destinationVillageId() { return destinationVillageId; }
        public Set<UUID> members() { return Collections.unmodifiableSet(members); }
        public String state() { return state; }
        public long createdGameTime() { return createdGameTime; }
        public long updatedGameTime() { return updatedGameTime; }

        public void setDestinationVillageId(UUID value) { destinationVillageId = value; }
        public void addMember(UUID value) { members.add(value); }
        public void removeMember(UUID value) { members.remove(value); }
        public void setState(String value) { state = safeText(value, "planned"); }
        public void setCreatedGameTime(long value) { createdGameTime = value; }
        public void setUpdatedGameTime(long value) { updatedGameTime = value; }

        private CompoundTag save() {
            CompoundTag tag = new CompoundTag();
            putUuid(tag, "id", id);
            putUuid(tag, "origin", originVillageId);
            putUuid(tag, "destination", destinationVillageId);
            tag.put("members", writeUuidSet(members));
            tag.putString("state", state);
            tag.putLong("created", createdGameTime);
            tag.putLong("updated", updatedGameTime);
            return tag;
        }

        private static MigrationRecord load(CompoundTag tag) {
            UUID id = readUuid(tag, "id");
            UUID origin = readUuid(tag, "origin");
            if (id == null || origin == null) return null;

            MigrationRecord record = new MigrationRecord(id, origin, readUuid(tag, "destination"));
            record.members.addAll(readUuidSet(tag, "members"));
            record.state = safeText(tag.getString("state"), "planned");
            record.createdGameTime = tag.getLong("created");
            record.updatedGameTime = tag.getLong("updated");
            return record;
        }
    }

    private static final class ChunkIndexEntry {
        private final Set<UUID> buildingIds = new LinkedHashSet<>();
        private final Set<UUID> storageIds = new LinkedHashSet<>();
        private final Set<UUID> workSiteIds = new LinkedHashSet<>();
        private final Set<UUID> routeIds = new LinkedHashSet<>();
        private final Set<UUID> projectIds = new LinkedHashSet<>();

        private ChunkIndexView snapshot() {
            return new ChunkIndexView(
                    Set.copyOf(buildingIds),
                    Set.copyOf(storageIds),
                    Set.copyOf(workSiteIds),
                    Set.copyOf(routeIds),
                    Set.copyOf(projectIds)
            );
        }
    }

    public record ChunkIndexView(
            Set<UUID> buildingIds,
            Set<UUID> storageIds,
            Set<UUID> workSiteIds,
            Set<UUID> routeIds,
            Set<UUID> projectIds
    ) {
        public static final ChunkIndexView EMPTY =
                new ChunkIndexView(Set.of(), Set.of(), Set.of(), Set.of(), Set.of());
    }
}
