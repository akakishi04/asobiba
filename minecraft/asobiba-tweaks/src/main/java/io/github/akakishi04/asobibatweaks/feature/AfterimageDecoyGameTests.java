package io.github.akakishi04.asobibatweaks.feature;

import com.mojang.authlib.GameProfile;
import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.entity.AfterimageDecoyEntity;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.ExperienceOrb;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.monster.Zombie;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.Vec3;
import net.neoforged.neoforge.event.entity.player.PlayerEvent;
import net.neoforged.neoforge.event.entity.living.LivingChangeTargetEvent;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.common.util.FakePlayer;
import net.neoforged.bus.api.EventPriority;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class AfterimageDecoyGameTests {
    private static final BlockPos MARK = new BlockPos(6, 1, 4);
    private AfterimageDecoyGameTests() {}

    @GameTest(template = "empty16x6x9", batch = "afterimage")
    public static void sprintEdgeAndMeasuredDepartureAreRequiredAndCooldownSurvivesLogout(GameTestHelper helper) {
        ServerPlayer owner = player(helper);
        var events = new AfterimageDecoyEvents();
        long now = helper.getLevel().getGameTime();
        Vec3 start = owner.position();
        events.tickPlayer(owner, now);
        owner.setSprinting(true);
        events.tickPlayer(owner, ++now);
        events.tickPlayer(owner, ++now);
        require(helper, events.active(owner.getUUID()) == null, "Stationary sprint toggling created an afterimage");
        owner.setSprinting(false);
        events.tickPlayer(owner, ++now);
        owner.setSprinting(true);
        for (int i = 1; i <= 4; i++) {
            owner.setPos(start.add(0.6D * i, 0.0D, 0.0D));
            events.tickPlayer(owner, ++now);
        }
        AfterimageDecoyEntity decoy = events.active(owner.getUUID());
        require(helper, decoy != null && decoy.position().distanceToSqr(start) < 0.0001D,
                "A genuine sprint departure did not leave the target at its departure point");
        owner.setSprinting(false);
        events.tickPlayer(owner, ++now);
        owner.setSprinting(true);
        for (int i = 1; i <= 4; i++) {
            owner.setPos(start.add(2.4D + 0.6D * i, 0.0D, 0.0D));
            events.tickPlayer(owner, ++now);
        }
        require(helper, events.active(owner.getUUID()) == decoy, "A second sprint bypassed the one-decoy/cooldown limit");
        events.onLogout(new PlayerEvent.PlayerLoggedOutEvent(owner));
        require(helper, decoy.isRemoved(), "Logout left an active target behind");
        owner.setSprinting(false);
        owner.setPos(start);
        events.tickPlayer(owner, ++now);
        owner.setSprinting(true);
        for (int i = 1; i <= 4; i++) {
            owner.setPos(start.add(0.6D * i, 0.0D, 0.0D));
            events.tickPlayer(owner, ++now);
        }
        require(helper, events.active(owner.getUUID()) == null, "Logout/relogin cleared the already-earned cooldown");
        now += AsobibaTweaksConfig.AFTERIMAGE_COOLDOWN_TICKS.getAsInt();
        owner.setPos(start);
        owner.setSprinting(false);
        events.tickPlayer(owner, ++now);
        owner.setSprinting(true);
        for (int i = 1; i <= 4; i++) {
            owner.setPos(start.add(0.6D * i, 0.0D, 0.0D));
            events.tickPlayer(owner, ++now);
        }
        require(helper, events.active(owner.getUUID()) != null, "A fresh sprint remained blocked after the configured cooldown");
        boolean enabled = AsobibaTweaksConfig.AFTERIMAGE_DECOY_ENABLED.getAsBoolean();
        var nextDecoy = events.active(owner.getUUID());
        try {
            AsobibaTweaksConfig.AFTERIMAGE_DECOY_ENABLED.set(false);
            events.tickPlayer(owner, ++now);
            require(helper, nextDecoy.isRemoved() && events.active(owner.getUUID()) == null,
                    "Disabling Afterimage retained its active target");
        } finally {
            AsobibaTweaksConfig.AFTERIMAGE_DECOY_ENABLED.set(enabled);
        }
        events.clear();
        owner.discard();
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "afterimage")
    public static void teleportWalkingFlyingAndWrongEquipmentCannotTrigger(GameTestHelper helper) {
        ServerPlayer owner = player(helper);
        var events = new AfterimageDecoyEvents();
        Vec3 start = owner.position();
        long now = helper.getLevel().getGameTime();
        events.tickPlayer(owner, now);
        for (int i = 1; i <= 4; i++) {
            owner.setPos(start.add(0.6D * i, 0.0D, 0.0D));
            events.tickPlayer(owner, ++now);
        }
        require(helper, events.active(owner.getUUID()) == null, "Walking triggered the sprint enchantment");
        owner.setSprinting(true);
        owner.setPos(start.add(6.0D, 0.0D, 0.0D));
        events.tickPlayer(owner, ++now);
        owner.setPos(start.add(6.6D, 0.0D, 0.0D));
        events.tickPlayer(owner, ++now);
        require(helper, events.active(owner.getUUID()) == null, "A position jump/teleport counted as departure");
        events.clear();
        owner.setPos(start);
        owner.setSprinting(false);
        owner.getAbilities().flying = true;
        events.tickPlayer(owner, ++now);
        owner.setSprinting(true);
        for (int i = 1; i <= 4; i++) {
            owner.setPos(start.add(0.6D * i, 0.0D, 0.0D));
            events.tickPlayer(owner, ++now);
        }
        require(helper, events.active(owner.getUUID()) == null, "Flying counted as a grounded sprint");
        owner.getAbilities().flying = false;
        ItemStack enchanted = owner.getItemBySlot(EquipmentSlot.CHEST);
        owner.setItemSlot(EquipmentSlot.CHEST, ItemStack.EMPTY);
        owner.setItemSlot(EquipmentSlot.HEAD, enchanted);
        events.clear();
        owner.setPos(start);
        owner.setSprinting(false);
        events.tickPlayer(owner, ++now);
        owner.setSprinting(true);
        for (int i = 1; i <= 4; i++) {
            owner.setPos(start.add(0.6D * i, 0.0D, 0.0D));
            events.tickPlayer(owner, ++now);
        }
        require(helper, events.active(owner.getUUID()) == null, "Afterimage operated outside the chest slot");
        events.clear();
        owner.discard();
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "afterimage")
    public static void realHostileTargetsAreBoundedAndExpiryPreservesNewerTargets(GameTestHelper helper) {
        ServerPlayer owner = player(helper);
        Vec3 origin = owner.position().add(-2.0D, 0.0D, 0.0D);
        List<Zombie> zombies = new ArrayList<>();
        for (int i = 0; i < 6; i++) {
            Zombie mob = spawn(helper, EntityType.ZOMBIE, origin.add(0.0D, 0.0D, 1.0D + i * 0.2D));
            mob.setTarget(owner);
            mob.setLastHurtByMob(owner);
            zombies.add(mob);
        }
        var decoy = AfterimageDecoyEvents.spawnDecoy(owner, origin, 0.0F);
        require(helper, decoy != null, "Could not create server decoy");
        long leased = zombies.stream().filter(mob -> mob.getTarget() == decoy).count();
        require(helper, leased == Math.min(4, AsobibaTweaksConfig.AFTERIMAGE_MAX_TARGETS.getAsInt())
                && decoy.leaseCount() == leased, "The real target lease count did not obey its cap");
        require(helper, zombies.stream().allMatch(mob -> mob.getLastHurtByMob() == owner),
                "Afterimage rewrote durable retaliation history");
        Zombie changed = zombies.stream().filter(mob -> mob.getTarget() == decoy).findFirst().orElseThrow();
        var pig = spawn(helper, EntityType.PIG, origin.add(0.0D, 0.0D, -2.0D));
        changed.setTarget(pig);
        decoy.discard();
        require(helper, changed.getTarget() == pig && zombies.stream().noneMatch(mob -> mob.getTarget() == decoy),
                "Cleanup restored a stale target or left a removed decoy targeted");
        zombies.forEach(Entity::discard);
        pig.discard();
        owner.discard();
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "afterimage")
    public static void canceledTargetChangeKeepsLeaseUntilActualCleanup(GameTestHelper helper) {
        ServerPlayer owner = player(helper);
        Vec3 origin = owner.position().add(-2.0D, 0.0D, 0.0D);
        Zombie zombie = spawn(helper, EntityType.ZOMBIE, origin.add(0.0D, 0.0D, 1.0D));
        zombie.setTarget(owner);
        var decoy = AfterimageDecoyEvents.spawnDecoy(owner, origin, 0.0F);
        require(helper, decoy != null && zombie.getTarget() == decoy, "No initial target lease");
        var pig = spawn(helper, EntityType.PIG, origin.add(0.0D, 0.0D, -2.0D));
        var cancellation = new CancelPigTarget(zombie, pig);
        NeoForge.EVENT_BUS.register(cancellation);
        try {
            zombie.setTarget(pig);
            require(helper, zombie.getTarget() == decoy && decoy.leaseCount() == 1,
                    "A cancelled target-change event prematurely lost the active lease");
            decoy.discard();
            require(helper, zombie.getTarget() == null, "Expiry forgot a lease after a cancelled target change");
        } finally {
            NeoForge.EVENT_BUS.unregister(cancellation);
            decoy.discard();
            zombie.discard();
            pig.discard();
            owner.discard();
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "afterimage", timeoutTicks = 100)
    public static void ordinaryZombieActuallyPursuesDecoyAndThenReleasesIt(GameTestHelper helper) {
        ServerPlayer owner = player(helper);
        Vec3 origin = owner.position().add(-2.0D, 0.0D, 0.0D);
        Zombie zombie = spawn(helper, EntityType.ZOMBIE, origin.add(-1.5D, 0.0D, 0.0D));
        zombie.setTarget(owner);
        var decoy = AfterimageDecoyEvents.spawnDecoy(owner, origin, 0.0F);
        require(helper, decoy != null && zombie.getTarget() == decoy, "Zombie never acquired the real decoy");
        helper.runAfterDelay(3, () -> {
            require(helper, !decoy.isRemoved() && zombie.getTarget() == decoy,
                    "Vanilla zombie AI immediately rejected the supposedly real server target");
            require(helper, zombie.getLookControl().getWantedX() < owner.getX(),
                    "Vanilla zombie look/attack AI continued aiming at the owner instead of the decoy");
        });
        helper.runAfterDelay(AsobibaTweaksConfig.AFTERIMAGE_LIFETIME_TICKS.getAsInt() + 2L, () -> {
            require(helper, decoy.isRemoved() && zombie.getTarget() != decoy,
                    "Timed entity expiry did not release the actual mob target");
            zombie.discard();
            owner.discard();
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", batch = "afterimage")
    public static void wallsAlliesBossesAndUnrelatedMobsAreNeverRetargeted(GameTestHelper helper) {
        ServerPlayer owner = player(helper);
        Vec3 origin = owner.position().add(-2.0D, 0.0D, 0.0D);
        Zombie blocked = spawn(helper, EntityType.ZOMBIE, origin.add(0.0D, 0.0D, -2.0D));
        blocked.setTarget(owner);
        BlockPos wall = BlockPos.containing(origin.add(0.0D, 0.0D, -1.0D));
        for (int dx = -1; dx <= 2; dx++) {
            for (int dy = 0; dy < 3; dy++) helper.getLevel().setBlockAndUpdate(wall.offset(dx, dy, 0), Blocks.STONE.defaultBlockState());
        }
        Zombie bonded = spawn(helper, EntityType.ZOMBIE, origin.add(1.0D, 0.0D, 1.0D));
        bonded.setTarget(owner);
        UniversalBondData.completeBond(bonded, owner.getUUID());
        Zombie idle = spawn(helper, EntityType.ZOMBIE, origin.add(2.0D, 0.0D, 1.0D));
        var pig = spawn(helper, EntityType.PIG, origin.add(0.0D, 0.0D, 1.0D));
        pig.setTarget(owner);
        var witch = EntityType.WITCH.create(helper.getLevel());
        var wither = EntityType.WITHER.create(helper.getLevel());
        require(helper, witch != null && wither != null, "Could not instantiate excluded mob types");
        witch.setTarget(owner);
        wither.setTarget(owner);
        var decoy = AfterimageDecoyEvents.spawnDecoy(owner, origin, 0.0F);
        require(helper, decoy != null && blocked.getTarget() == owner && bonded.getTarget() == owner
                && idle.getTarget() == null && pig.getTarget() == owner
                && !AfterimageDecoyEvents.eligibleHostile(witch, owner)
                && !AfterimageDecoyEvents.eligibleHostile(wither, owner),
                "Decoy retargeted through a wall, stole unrelated aggro, or accepted an excluded mob");
        idle.setTarget(decoy); // Real global target-change event must refuse incidental acquisition.
        require(helper, idle.getTarget() == null, "An unleased mob acquired the decoy independently");
        decoy.discard();
        List.of(blocked, bonded, idle, pig).forEach(Entity::discard);
        owner.discard();
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "afterimage")
    public static void decoyIsNonphysicalUnsavedUnarmedAndHasNoDrops(GameTestHelper helper) {
        ServerPlayer owner = player(helper);
        var decoy = AfterimageDecoyEvents.spawnDecoy(owner, owner.position().add(-2.0D, 0.0D, 0.0D), 0.0F);
        require(helper, decoy != null, "Could not create safety-test decoy");
        int dropsBefore = helper.getLevel().getEntitiesOfClass(ItemEntity.class, decoy.getBoundingBox().inflate(2)).size();
        int xpBefore = helper.getLevel().getEntitiesOfClass(ExperienceOrb.class, decoy.getBoundingBox().inflate(2)).size();
        float health = decoy.getHealth();
        decoy.setItemSlot(EquipmentSlot.MAINHAND, new ItemStack(Items.DIAMOND_SWORD));
        boolean damaged = decoy.hurt(helper.getLevel().damageSources().playerAttack(owner), 100.0F);
        CompoundTag saved = new CompoundTag();
        boolean persisted = decoy.save(saved);
        require(helper, !damaged && health == decoy.getHealth() && !decoy.isPickable() && !decoy.isPushable()
                && !decoy.canBeCollidedWith() && decoy.isIgnoringBlockTriggers() && !persisted
                && !decoy.shouldBeSaved() && decoy.getItemBySlot(EquipmentSlot.MAINHAND).isEmpty(),
                "Decoy accepted damage/equipment, physical collision, block triggers or serialization");
        decoy.die(helper.getLevel().damageSources().generic());
        require(helper, decoy.isRemoved()
                && helper.getLevel().getEntitiesOfClass(ItemEntity.class, decoy.getBoundingBox().inflate(2)).size() == dropsBefore
                && helper.getLevel().getEntitiesOfClass(ExperienceOrb.class, decoy.getBoundingBox().inflate(2)).size() == xpBefore,
                "Decoy death created farmable drops or XP");
        var orphan = AfterimageDecoyRegistration.DECOY.get().create(helper.getLevel());
        require(helper, orphan != null, "Could not create reload safety probe");
        orphan.load(decoy.saveWithoutId(new CompoundTag()));
        orphan.tick();
        require(helper, orphan.isRemoved(), "An unowned/reloaded afterimage survived");
        Vec3 remote = owner.position().add(1_000_000.0D, 0.0D, 1_000_000.0D);
        require(helper, !helper.getLevel().hasChunkAt(BlockPos.containing(remote))
                && !AfterimageDecoyEvents.loadedBetween(helper.getLevel(), owner.position(), remote)
                && !helper.getLevel().hasChunkAt(BlockPos.containing(remote)), "Decoy inspection force-loaded distant terrain");
        owner.discard();
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "afterimage")
    public static void ownerDeathAndServerShutdownReleaseRealTargets(GameTestHelper helper) {
        ServerPlayer owner = player(helper);
        Zombie zombie = spawn(helper, EntityType.ZOMBIE, owner.position().add(-2.0D, 0.0D, 1.0D));
        zombie.setTarget(owner);
        var decoy = AfterimageDecoyEvents.spawnDecoy(owner, owner.position().add(-2.0D, 0.0D, 0.0D), 0.0F);
        require(helper, decoy != null && zombie.getTarget() == decoy, "No initial target lease for death test");
        owner.setHealth(0.0F);
        decoy.tick();
        require(helper, decoy.isRemoved() && zombie.getTarget() != decoy, "Owner death left a targeted orphan");
        zombie.discard();
        owner.discard();
        ServerPlayer second = player(helper);
        var events = new AfterimageDecoyEvents();
        long now = helper.getLevel().getGameTime();
        Vec3 start = second.position();
        events.tickPlayer(second, now);
        second.setSprinting(true);
        for (int i = 1; i <= 4; i++) {
            second.setPos(start.add(i * 0.6D, 0.0D, 0.0D));
            events.tickPlayer(second, ++now);
        }
        var active = events.active(second.getUUID());
        require(helper, active != null, "Could not create tracked shutdown probe");
        events.clear(); // The exact service cleanup called by ServerStoppingEvent.
        require(helper, active.isRemoved() && events.active(second.getUUID()) == null, "Server shutdown retained an active entity");
        second.discard();
        helper.succeed();
    }

    public static final class CancelPigTarget {
        private final Mob mob;
        private final Mob rejected;
        CancelPigTarget(Mob mob, Mob rejected) { this.mob = mob; this.rejected = rejected; }
        @SubscribeEvent(priority = EventPriority.LOWEST)
        public void onTarget(LivingChangeTargetEvent event) {
            if (event.getEntity() == mob && event.getNewAboutToBeSetTarget() == rejected) event.setCanceled(true);
        }
    }

    private static ServerPlayer player(GameTestHelper helper) {
        var player = new FakePlayer(helper.getLevel(), new GameProfile(UUID.randomUUID(), "afterimage-test"));
        player.setGameMode(GameType.SURVIVAL);
        player.getAbilities().invulnerable = false;
        player.getAbilities().instabuild = false;
        player.getAbilities().mayfly = false;
        player.getAbilities().flying = false;
        BlockPos at = helper.absolutePos(MARK);
        for (int x = -5; x <= 8; x++) {
            for (int z = -3; z <= 3; z++) helper.getLevel().setBlockAndUpdate(at.offset(x, -1, z), Blocks.STONE.defaultBlockState());
        }
        player.setPos(at.getX() + 0.5D, at.getY(), at.getZ() + 0.5D);
        player.setOnGround(true);
        ItemStack chest = new ItemStack(Items.IRON_CHESTPLATE);
        chest.enchant(helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(NewEnchantments.AFTERIMAGE), 1);
        player.setItemSlot(EquipmentSlot.CHEST, chest);
        return player;
    }

    private static <T extends Mob> T spawn(GameTestHelper helper, EntityType<T> type, Vec3 position) {
        T mob = type.create(helper.getLevel());
        if (mob == null) throw new IllegalStateException("Cannot create actual test mob");
        mob.setPos(position);
        mob.setOnGround(true);
        mob.setPersistenceRequired();
        mob.setItemSlot(EquipmentSlot.HEAD, new ItemStack(Items.IRON_HELMET));
        // Keep real goals/targeting enabled while avoiding unrelated test-area movement.
        var speed = mob.getAttribute(Attributes.MOVEMENT_SPEED);
        if (speed != null) speed.setBaseValue(0.0D);
        if (!helper.getLevel().addFreshEntity(mob)) throw new IllegalStateException("Cannot add actual test mob");
        return mob;
    }

    private static void require(GameTestHelper helper, boolean condition, String message) {
        if (!condition) helper.fail(message, MARK);
    }
}
