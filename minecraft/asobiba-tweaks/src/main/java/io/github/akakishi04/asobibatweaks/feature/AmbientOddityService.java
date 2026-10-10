package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.WeakHashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.tags.BiomeTags;
import net.minecraft.tags.BlockTags;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.PathfinderMob;
import net.minecraft.world.entity.TamableAnimal;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.entity.ai.goal.LookAtPlayerGoal;
import net.minecraft.world.entity.ai.goal.RandomLookAroundGoal;
import net.minecraft.world.entity.ai.memory.MemoryModuleType;
import net.minecraft.world.entity.animal.Animal;
import net.minecraft.world.entity.animal.Chicken;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.entity.schedule.Activity;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.CampfireBlock;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.entity.EntityTypeTest;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** Small transient, server-authoritative ambience. Never owns world blocks, AI goals or rewards. */
public final class AmbientOddityService {
    public enum Kind { BELL, FOOTSTEPS, KNOCK, EMBER, GLANCE, BREEZE, CHORD, CHICKEN, GATHERING, NOD }
    static final int MAX_QUERY_RESULTS = 24;
    static final int MAX_BLOCK_PROBES = 96;
    static final int MAX_ACTIVE_LOOKS = 12;
    static final int MAX_QUEUED_SOUNDS = 12;
    static final int MAX_COOLDOWNS = 2048;
    static final int GLOBAL_COOLDOWN = 100;
    static final int PLAYER_COOLDOWN = 1200;
    static final int AREA_COOLDOWN = 2400;
    private static final Map<ServerLevel, State> STATES = new WeakHashMap<>();
    private static final EquipmentSlot[] ARMOR = {
            EquipmentSlot.HEAD, EquipmentSlot.CHEST, EquipmentSlot.LEGS, EquipmentSlot.FEET };

    static final class State {
        long nextEvent;
        long bellProbeAfter;
        long probeTick = Long.MIN_VALUE;
        int probeCount;
        int playerCursor;
        final Map<UUID, Long> players = new HashMap<>();
        final Map<Long, Long> areas = new HashMap<>();
        final Map<UUID, Long> probes = new HashMap<>();
        final Map<UUID, Look> looks = new HashMap<>();
        final List<Sound> sounds = new ArrayList<>();
    }
    record Look(Kind kind, Vec3 target, long until, Vec3 origin) {}
    record Sound(Kind kind, Vec3 position, SoundEvent sound, float volume, float pitch, long due) {}

    private AmbientOddityService() {}
    static State state(ServerLevel level) { return STATES.computeIfAbsent(level, ignored -> new State()); }

    static boolean enabled(Kind kind) {
        return switch (kind) {
            case BELL -> AsobibaTweaksConfig.OE_REPLYING_BELL_ENABLED.getAsBoolean();
            case FOOTSTEPS -> AsobibaTweaksConfig.OE_UNSEEN_FOOTSTEPS_ENABLED.getAsBoolean();
            case KNOCK -> AsobibaTweaksConfig.OE_EMPTY_KNOCK_ENABLED.getAsBoolean();
            case EMBER -> AsobibaTweaksConfig.OE_COLD_EMBER_ENABLED.getAsBoolean();
            case GLANCE -> AsobibaTweaksConfig.OE_UNUSUAL_GLANCE_ENABLED.getAsBoolean();
            case BREEZE -> AsobibaTweaksConfig.OE_BACKWARD_BREEZE_ENABLED.getAsBoolean();
            case CHORD -> AsobibaTweaksConfig.OE_UNCLAIMED_CHORD_ENABLED.getAsBoolean();
            case CHICKEN -> AsobibaTweaksConfig.CHICKEN_CONSPIRACY_ENABLED.getAsBoolean();
            case GATHERING -> AsobibaTweaksConfig.MOB_GATHERINGS_ENABLED.getAsBoolean();
            case NOD -> AsobibaTweaksConfig.NOD_ENABLED.getAsBoolean();
        };
    }

    /** Presence, not summed levels/pieces/wearers: one armor piece and four both yield exactly +25%. */
    public static double chance(ServerPlayer player, double naturalChance) {
        return chance(player, naturalChance, false);
    }

    static double chance(ServerPlayer player, double naturalChance, boolean excludeHelmet) {
        double base = Mth.clamp(naturalChance, 0.0D, 1.0D);
        if (!AsobibaTweaksConfig.OMINOUS_ENABLED.getAsBoolean()) return base;
        for (EquipmentSlot slot : ARMOR) {
            if (excludeHelmet && slot == EquipmentSlot.HEAD) continue;
            if (player.getItemBySlot(slot).is(net.minecraft.tags.ItemTags.ARMOR_ENCHANTABLE)
                    && NewEnchantments.has(player.getItemBySlot(slot), player.registryAccess(), NewEnchantments.OMINOUS))
                return Math.min(1.0D, base * 1.25D);
        }
        return base;
    }

    static boolean safePlayer(ServerPlayer player) {
        return player.isAlive() && !player.isSpectator() && !player.isSleeping()
                && !player.isPassenger() && !player.isOnFire() && !player.isInWaterOrBubble()
                && !player.isSprinting() && !player.isUsingItem() && player.hurtTime == 0
                && (player.getLastHurtByMob() == null
                    || player.tickCount - player.getLastHurtByMobTimestamp() >= 100);
    }

    /** A finite result budget; saturated areas fail closed instead of hiding an unknown threat. */
    static <T extends Entity> List<T> nearby(ServerLevel level, Class<T> type, AABB bounds) {
        List<T> result = new ArrayList<>();
        level.getEntities(EntityTypeTest.forClass(type), bounds, Entity::isAlive, result, MAX_QUERY_RESULTS);
        return result;
    }

    static ServerPlayer nearestPlayer(ServerLevel level, Entity entity, double radius) {
        List<ServerPlayer> players = new ArrayList<>();
        level.getEntities(EntityTypeTest.forClass(ServerPlayer.class), entity.getBoundingBox().inflate(radius),
                player -> player.isAlive() && !player.isSpectator() && player.distanceToSqr(entity) <= radius * radius,
                players, MAX_QUERY_RESULTS);
        return players.stream().min(java.util.Comparator.comparingDouble(entity::distanceToSqr)).orElse(null);
    }

    static boolean quiet(ServerPlayer player) {
        if (!safePlayer(player)) return false;
        List<Mob> mobs = nearby(player.serverLevel(), Mob.class, player.getBoundingBox().inflate(12));
        if (mobs.size() >= MAX_QUERY_RESULTS) return false;
        return mobs.stream().noneMatch(mob -> mob instanceof Monster || mob.getTarget() != null
                || mob.isOnFire() || mob.hurtTime > 0);
    }

    static boolean cave(ServerLevel level, BlockPos pos) {
        if (!level.hasChunkAt(pos)) return false;
        if (pos.getY() < level.getSeaLevel() - 6 && !level.canSeeSky(pos)) return true;
        // Hillside caves and flat/custom worlds need not be below their generator's sea level.
        // Recognize real nearby natural-stone overburden with eight loaded-column probes.
        // This physical cover is authoritative even while the asynchronous skylight cache updates.
        int stone = 0;
        for (int y = 3; y <= 10; y++) {
            BlockState roof = level.getBlockState(pos.above(y));
            if (roof.is(BlockTags.BASE_STONE_OVERWORLD) || roof.is(BlockTags.BASE_STONE_NETHER)) stone++;
        }
        return stone >= 4;
    }

    /** Reject vanilla and modded priority movement/look/combat rather than disabling their AI. */
    static boolean idle(PathfinderMob mob) { return idle(mob, false); }

    static boolean idle(PathfinderMob mob, boolean ownsNavigation) {
        if (!mob.isAlive() || mob.isRemoved() || mob.isNoAi() || mob.isSleeping()
                || !mob.onGround() || mob.isPassenger() || mob.isVehicle() || mob.isLeashed()
                || mob.isOnFire() || mob.isInWaterOrBubble() || mob.getTarget() != null
                || mob.hurtTime > 0 || !ownsNavigation && mob.getNavigation().isInProgress()
                || !ownsNavigation && mob.getDeltaMovement().horizontalDistanceSqr() > 0.0025D
                || mob.getLastHurtByMob() != null && mob.tickCount - mob.getLastHurtByMobTimestamp() < 200
                || mob.getBrain().hasMemoryValue(MemoryModuleType.WALK_TARGET)
                || mob.getBrain().hasMemoryValue(MemoryModuleType.ATTACK_TARGET)
                || mob.getBrain().hasMemoryValue(MemoryModuleType.HURT_BY)
                || mob.getBrain().hasMemoryValue(MemoryModuleType.AVOID_TARGET)
                || mob.getBrain().hasMemoryValue(MemoryModuleType.BREED_TARGET)
                || mob.getBrain().hasMemoryValue(MemoryModuleType.TEMPTING_PLAYER)
                || mob.getBrain().hasMemoryValue(MemoryModuleType.NEAREST_HOSTILE)
                || mob.getBrain().hasMemoryValue(MemoryModuleType.IS_PANICKING)) return false;
        if (mob.goalSelector.getAvailableGoals().stream().anyMatch(goal -> goal.isRunning()
                && !(goal.getGoal() instanceof LookAtPlayerGoal)
                && !(goal.getGoal() instanceof RandomLookAroundGoal)
                && (goal.getFlags().contains(Goal.Flag.MOVE) || goal.getFlags().contains(Goal.Flag.LOOK)
                    || goal.getFlags().contains(Goal.Flag.TARGET) || goal.getFlags().contains(Goal.Flag.JUMP)))) return false;
        if (mob instanceof Animal animal && (animal.isInLove()
                || !ownsNavigation && animal.getPersistentData().getLong("asobibatweaks_gather_until") > mob.level().getGameTime())) return false;
        if (mob instanceof Chicken chicken && chicken.eggTime <= 100) return false;
        if (mob instanceof TamableAnimal animal && animal.isOrderedToSit()) return false;
        if (mob instanceof Villager villager) {
            return !villager.isTrading() && villager.getUnhappyCounter() <= 0 && !villager.getBrain().isActive(Activity.WORK)
                    && !villager.getBrain().isActive(Activity.REST)
                    && !villager.getBrain().isActive(Activity.PANIC)
                    && !villager.getBrain().isActive(Activity.RAID)
                    && !villager.getBrain().isActive(Activity.PRE_RAID)
                    && !villager.getBrain().isActive(Activity.HIDE)
                    && "none".equals(VillagerSimData.emergencyDuty(villager))
                    && VillagerSimData.migrationId(villager).isEmpty()
                    && VillagerSimData.riverHaul(villager).isEmpty()
                    && !VillagerSimData.hasWorkCargo(villager, mob.registryAccess(), 16);
        }
        return true;
    }

    static boolean claimProbe(ServerLevel level) {
        State s = state(level);
        if (s.probeTick != level.getGameTime()) { s.probeTick = level.getGameTime(); s.probeCount = 0; }
        if (s.probeCount >= 2) return false;
        s.probeCount++;
        return true;
    }

    static boolean ready(ServerLevel level, ServerPlayer player, BlockPos pos, Kind kind) {
        State s = state(level);
        long now = level.getGameTime();
        if (!enabled(kind) || !safePlayer(player) || !level.hasChunkAt(pos)
                || s.nextEvent > now || s.players.getOrDefault(player.getUUID(), 0L) > now
                || s.players.size() >= MAX_COOLDOWNS || s.areas.size() >= MAX_COOLDOWNS) return false;
        int x = pos.getX() >> 5, z = pos.getZ() >> 5;
        for (int dx = -1; dx <= 1; dx++) for (int dz = -1; dz <= 1; dz++)
            if (s.areas.getOrDefault(areaKey(x + dx, z + dz), 0L) > now) return false;
        return true;
    }

    static void reserve(ServerLevel level, ServerPlayer player, BlockPos pos) {
        State s = state(level);
        long now = level.getGameTime();
        s.nextEvent = now + GLOBAL_COOLDOWN;
        s.players.put(player.getUUID(), now + PLAYER_COOLDOWN);
        s.areas.put(areaKey(pos.getX() >> 5, pos.getZ() >> 5), now + AREA_COOLDOWN);
    }

    private static long areaKey(int x, int z) { return (long)x << 32 ^ (z & 0xffffffffL); }

    static boolean clearSpot(ServerLevel level, Vec3 point) {
        BlockPos pos = BlockPos.containing(point);
        return level.hasChunkAt(pos) && level.getBlockState(pos).isAir()
                && nearby(level, Entity.class, new AABB(pos).inflate(0.4D)).isEmpty();
    }

    static BlockPos findBlock(ServerPlayer player, Kind kind) {
        ServerLevel level = player.serverLevel();
        BlockPos center = player.blockPosition();
        int width = 13, volume = width * width * 5;
        int start = Math.floorMod((int)(level.getGameTime() / 20) * 97 + player.getId(), volume);
        for (int i = 0; i < MAX_BLOCK_PROBES; i++) {
            int cell = Math.floorMod(start + i * 83, volume);
            BlockPos pos = center.offset(cell % width - 6, cell / (width * width) - 2,
                    cell / width % width - 6);
            if (!level.hasChunkAt(pos)) continue;
            if (eligibleBlock(level.getBlockState(pos), kind)) return pos;
        }
        return null;
    }

    static boolean eligibleBlock(BlockState block, Kind kind) {
        return kind == Kind.KNOCK && block.is(BlockTags.WOODEN_DOORS)
                    && block.hasProperty(DoorBlock.OPEN) && !block.getValue(DoorBlock.OPEN)
                || kind == Kind.EMBER && block.getBlock() instanceof CampfireBlock
                    && !block.getValue(CampfireBlock.LIT) && !block.getValue(CampfireBlock.WATERLOGGED);
    }

    static void probe(ServerPlayer player) {
        ServerLevel level = player.serverLevel();
        Kind[] kinds = { Kind.FOOTSTEPS, Kind.KNOCK, Kind.EMBER, Kind.GLANCE,
                Kind.BREEZE, Kind.CHORD, Kind.CHICKEN };
        Kind kind = kinds[level.random.nextInt(kinds.length)];
        if (!ready(level, player, player.blockPosition(), kind) || !quiet(player)) return;
        BlockPos source = kind == Kind.KNOCK || kind == Kind.EMBER ? findBlock(player, kind) : player.blockPosition();
        if (source == null) return;
        attempt(player, kind, source, level.random.nextDouble());
    }

    /** Shared production transaction; explicit roll makes engine tests deterministic without bypassing eligibility. */
    static boolean attempt(ServerPlayer player, Kind kind, BlockPos source, double roll) {
        ServerLevel level = player.serverLevel();
        if (!ready(level, player, source, kind) || !claimProbe(level) || !quiet(player) || player.blockPosition().distSqr(source) > 144) return false;
        boolean underground = cave(level, player.blockPosition());
        boolean outside = level.canSeeSky(player.blockPosition()) && player.onGround()
                && !level.isRainingAt(player.blockPosition());
        if (kind == Kind.FOOTSTEPS && !underground && !level.getBiome(player.blockPosition()).is(BiomeTags.IS_FOREST)) return false;
        if (kind == Kind.BREEZE && !outside) return false;
        if (kind == Kind.CHORD && !underground && (level.isVillage(player.blockPosition())
                || player.blockPosition().distSqr(level.getSharedSpawnPos()) < 256.0D * 256.0D)) return false;
        if ((kind == Kind.KNOCK || kind == Kind.EMBER) && !eligibleBlock(level.getBlockState(source), kind)) return false;
        if (kind == Kind.GLANCE || kind == Kind.CHICKEN) return startAnimals(player, kind, roll);
        if (kind == Kind.BELL || kind == Kind.GATHERING || kind == Kind.NOD) return false;
        Vec3 point = kind == Kind.KNOCK || kind == Kind.EMBER ? Vec3.atCenterOf(source)
                : player.position().subtract(player.getLookAngle().multiply(3, 0, 3)).add(0, 0.4D, 0);
        if (kind != Kind.KNOCK && kind != Kind.EMBER && !clearSpot(level, point)) return false;
        if (state(level).sounds.size() + 3 > MAX_QUEUED_SOUNDS
                || roll >= chance(player, AsobibaTweaksConfig.AMBIENT_ODDITY_CHANCE.getAsDouble())) return false;
        reserve(level, player, source);
        long now = level.getGameTime();
        switch (kind) {
            case FOOTSTEPS -> {
                SoundEvent sound = underground ? SoundEvents.STONE_STEP : SoundEvents.GRASS_STEP;
                queue(level, kind, point, sound, 0.18F, 0.9F, now + 8);
                queue(level, kind, point.add(0.45D, 0, 0), sound, 0.14F, 1.05F, now + 19);
                queue(level, kind, point.add(0.8D, 0, 0.3D), sound, 0.11F, 0.95F, now + 31);
            }
            case KNOCK -> {
                queue(level, kind, point, SoundEvents.WOOD_HIT, 0.16F, 0.75F, now + 1);
                queue(level, kind, point, SoundEvents.WOOD_HIT, 0.11F, 0.8F, now + 9);
            }
            case EMBER -> level.sendParticles(ParticleTypes.CAMPFIRE_COSY_SMOKE,
                    point.x, point.y + 0.15D, point.z, 3, 0.06D, 0.08D, 0.06D, 0.004D);
            case BREEZE -> {
                // A tiny arc moves backwards relative to the wearer's facing; no physical impulse.
                Vec3 back = player.getLookAngle().multiply(-0.035D, 0, -0.035D);
                for (int i = 0; i < 6; i++) {
                    double angle = i * Math.PI / 3;
                    level.sendParticles(ParticleTypes.ASH, point.x + Math.cos(angle) * 0.6D,
                            point.y + i * 0.06D, point.z + Math.sin(angle) * 0.6D,
                            0, back.x, 0.006D, back.z, 1.0D);
                }
            }
            case CHORD -> {
                queue(level, kind, point, SoundEvents.NOTE_BLOCK_HARP.value(), 0.12F, 0.75F, now + 1);
                queue(level, kind, point, SoundEvents.NOTE_BLOCK_HARP.value(), 0.10F, 1.0F, now + 5);
                queue(level, kind, point, SoundEvents.NOTE_BLOCK_HARP.value(), 0.08F, 1.25F, now + 9);
            }
            default -> { return false; }
        }
        return true;
    }

    static boolean startAnimals(ServerPlayer player, Kind kind, double roll) {
        ServerLevel level = player.serverLevel();
        if (!ready(level, player, player.blockPosition(), kind) || !quiet(player)) return false;
        List<Animal> sampled = nearby(level, Animal.class, player.getBoundingBox().inflate(12));
        if (sampled.size() >= MAX_QUERY_RESULTS) return false;
        List<Animal> members = sampled.stream().filter(animal -> idle(animal)
                && !state(level).looks.containsKey(animal.getUUID())
                && (kind != Kind.CHICKEN || animal instanceof Chicken)
                && animal.distanceToSqr(player) >= 25 && animal.distanceToSqr(player) <= 144).limit(kind == Kind.CHICKEN ? 6 : 2).toList();
        if (members.size() < (kind == Kind.CHICKEN ? 3 : 1)
                || state(level).looks.size() + members.size() > MAX_ACTIVE_LOOKS) return false;
        Animal first = members.getFirst();
        if (kind == Kind.CHICKEN && members.stream().anyMatch(animal -> animal.distanceToSqr(first) > 36)) return false;
        double angle = level.random.nextDouble() * Math.PI * 2;
        Vec3 direction = new Vec3(Math.cos(angle) * 5, 0, Math.sin(angle) * 5);
        Vec3 shared = first.getEyePosition().add(direction);
        if (!clearSpot(level, shared) || members.stream().anyMatch(animal ->
                !level.hasChunkAt(BlockPos.containing(animal.getEyePosition().add(direction))))) return false;
        double natural = kind == Kind.CHICKEN ? AsobibaTweaksConfig.CHICKEN_CONSPIRACY_CHANCE.getAsDouble()
                : AsobibaTweaksConfig.AMBIENT_ODDITY_CHANCE.getAsDouble();
        if (roll >= chance(player, natural)) return false;
        reserve(level, player, first.blockPosition());
        for (Animal animal : members) {
            Vec3 target = kind == Kind.CHICKEN ? animal.getEyePosition().add(direction) : shared;
            if (level.hasChunkAt(BlockPos.containing(target)))
                state(level).looks.put(animal.getUUID(), new Look(kind, target, level.getGameTime() + 60, animal.position()));
        }
        return true;
    }

    /** Called by the successful vanilla bell ring, never by mere right clicks or a sound playback. */
    public static boolean bellRang(ServerLevel level, BlockPos pos, double roll) {
        State s = state(level);
        if (!enabled(Kind.BELL) || s.nextEvent > level.getGameTime() || s.bellProbeAfter > level.getGameTime()) return false;
        s.bellProbeAfter = level.getGameTime() + 20;
        long time = Math.floorMod(level.getDayTime(), 24000L);
        if (time < 12000 || time > 23000 || !level.hasChunkAt(pos)
                || !level.getBlockState(pos).is(Blocks.BELL) || !level.isVillage(pos)) return false;
        if (!claimProbe(level)) return false;
        List<ServerPlayer> observers = nearby(level, ServerPlayer.class, new AABB(pos).inflate(12));
        if (observers.size() >= MAX_QUERY_RESULTS) return false;
        ServerPlayer player = null;
        double distance = 144;
        // A bell may be rung by a projectile/redstone, but bias comes from one nearby eligible observer.
        for (ServerPlayer candidate : observers) {
            double d = candidate.position().distanceToSqr(Vec3.atCenterOf(pos));
            if (d < distance && safePlayer(candidate)) { player = candidate; distance = d; }
        }
        if (player == null || !ready(level, player, pos, Kind.BELL) || !quiet(player)
                || state(level).sounds.size() >= MAX_QUEUED_SOUNDS) return false;
        Vec3 reply = Vec3.atCenterOf(pos).add(7, 1, 0);
        if (!clearSpot(level, reply)
                || roll >= chance(player, AsobibaTweaksConfig.AMBIENT_ODDITY_CHANCE.getAsDouble())) return false;
        reserve(level, player, pos);
        queue(level, Kind.BELL, reply, SoundEvents.BELL_BLOCK, 0.18F, 0.75F, level.getGameTime() + 30);
        return true;
    }

    static void queue(ServerLevel level, Kind kind, Vec3 point, SoundEvent sound, float volume, float pitch, long due) {
        if (state(level).sounds.size() < MAX_QUEUED_SOUNDS)
            state(level).sounds.add(new Sound(kind, point, sound, volume, pitch, due));
    }

    static void tick(ServerLevel level) {
        State s = state(level);
        long now = level.getGameTime();
        int emitted = 0;
        for (Iterator<Sound> it = s.sounds.iterator(); it.hasNext();) {
            Sound sound = it.next();
            if (!enabled(sound.kind()) || now > sound.due() + 40 || !level.hasChunkAt(BlockPos.containing(sound.position()))) {
                it.remove(); continue;
            }
            if (sound.due() > now || emitted >= 2) continue;
            // No block event/game event: sounds cannot trigger raids, AI alerts, sculk or rewards.
            level.playSound(null, sound.position().x, sound.position().y, sound.position().z,
                    sound.sound(), SoundSource.AMBIENT, sound.volume(), sound.pitch());
            emitted++; it.remove();
        }
        // A conspiracy ends as one group when any member is approached or becomes busy.
        boolean endConspiracy = s.looks.entrySet().stream().filter(entry -> entry.getValue().kind() == Kind.CHICKEN)
                .anyMatch(entry -> !(level.getEntity(entry.getKey()) instanceof Animal animal)
                        || !idle(animal) || nearestPlayer(level, animal, 4.0D) != null);
        for (Iterator<Map.Entry<UUID, Look>> it = s.looks.entrySet().iterator(); it.hasNext();) {
            var entry = it.next();
            Entity entity = level.getEntity(entry.getKey());
            Look look = entry.getValue();
            if (!(entity instanceof Animal animal) || endConspiracy && look.kind() == Kind.CHICKEN || !enabled(look.kind()) || now >= look.until()
                    || !idle(animal) || animal.position().distanceToSqr(look.origin()) > 0.1D
                    || nearestPlayer(level, animal, 4.0D) != null
                    || !level.hasChunkAt(BlockPos.containing(look.target()))) { it.remove(); continue; }
            animal.getLookControl().setLookAt(look.target().x, look.target().y, look.target().z, 25, 20);
            // Random idle look goals are deliberately allowed. Their next-tick request may replace
            // LookControl's target, so apply the actual bounded pose after all safe vanilla AI.
            Vec3 facing = look.target().subtract(animal.getEyePosition());
            float yaw = (float)(Math.atan2(facing.z, facing.x) * 180.0D / Math.PI) - 90.0F;
            float turn = Mth.clamp(Mth.wrapDegrees(yaw - animal.getYHeadRot()), -25, 25);
            animal.setYHeadRot(animal.getYHeadRot() + turn);
            animal.setYRot(animal.getYHeadRot());
            animal.yBodyRot = animal.getYRot();
            animal.setXRot(Mth.clamp((float)(-Math.atan2(facing.y, facing.horizontalDistance())
                    * 180.0D / Math.PI), -20, 20));
        }
        if (now % 200 == 0) {
            s.players.values().removeIf(until -> until <= now);
            s.areas.values().removeIf(until -> until <= now);
            s.probes.values().removeIf(until -> until <= now);
        }
        if (now % 20 != 0 || level.players().isEmpty()) return;
        ServerPlayer player = level.players().get(Math.floorMod(s.playerCursor++, level.players().size()));
        if (s.probes.size() >= MAX_COOLDOWNS || s.probes.getOrDefault(player.getUUID(), 0L) > now) return;
        s.probes.put(player.getUUID(), now + 200);
        probe(player);
    }

    static boolean hasAmbientLook(Animal animal) {
        return animal.level() instanceof ServerLevel level && state(level).looks.containsKey(animal.getUUID());
    }

    static void clear(ServerLevel level) { STATES.remove(level); }
}
