package io.github.akakishi04.asobibatweaks.entity;

import java.util.HashSet;
import java.util.List;
import java.util.Set;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.HumanoidArm;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;

/** A targetable silhouette, never a player, inventory, attack source or saved entity. */
public final class AfterimageDecoyEntity extends LivingEntity {
    // Server-only, transient references. None are written to NBT or sent to clients.
    private ServerPlayer owner;
    private long expiresAt;
    private Mob granting;
    private final Set<Mob> leases = new HashSet<>();

    public AfterimageDecoyEntity(EntityType<? extends AfterimageDecoyEntity> type, Level level) {
        super(type, level);
        noPhysics = true;
        setNoGravity(true);
        setSilent(true);
    }

    public static AttributeSupplier.Builder createAttributes() {
        return LivingEntity.createLivingAttributes().add(Attributes.MAX_HEALTH, 1.0D);
    }

    public void initialize(ServerPlayer player, Vec3 departure, float yaw, int lifetimeTicks) {
        owner = player;
        expiresAt = level().getGameTime() + lifetimeTicks;
        moveTo(departure.x, departure.y, departure.z, yaw, 0.0F);
        yBodyRot = yaw;
        yHeadRot = yaw;
    }

    public boolean lease(Mob mob, int maximum) {
        if (owner == null || isRemoved() || leases.size() >= Math.min(4, maximum) || mob.getTarget() != owner) return false;
        leases.add(mob); // The target-change event permits only already-issued leases.
        granting = mob;
        try {
            mob.setTarget(this);
        } finally {
            granting = null;
        }
        if (mob.getTarget() == this) return true;
        leases.remove(mob);
        return false;
    }

    public boolean permits(Mob mob) {
        return !isRemoved() && !hasExpired(level().getGameTime()) && leases.contains(mob)
                && (granting == mob || mob.getTarget() == this);
    }

    public int leaseCount() {
        return leases.size();
    }

    public boolean ownedBy(ServerPlayer player) {
        return owner == player;
    }

    public boolean hasExpired(long gameTime) {
        return owner == null || !owner.isAlive() || owner.isRemoved() || owner.level() != level()
                || gameTime >= expiresAt;
    }

    /** Clear only targets that are still ours; never restore a stale player target. */
    public void releaseTargets() {
        for (Mob mob : List.copyOf(leases)) {
            if (!mob.isRemoved() && mob.getTarget() == this) mob.setTarget(null);
        }
        leases.clear();
    }

    @Override
    public void tick() {
        super.tick();
        if (!level().isClientSide) {
            leases.removeIf(mob -> mob.isRemoved() || !mob.isAlive() || mob.getTarget() != this);
            if (hasExpired(level().getGameTime())) discard();
        }
    }

    @Override
    public void remove(Entity.RemovalReason reason) {
        releaseTargets();
        owner = null;
        super.remove(reason);
    }

    // Do not travel, push, shield projectiles, acquire equipment, emit loot or retaliate.
    @Override public void aiStep() { setDeltaMovement(Vec3.ZERO); }
    @Override public boolean hurt(DamageSource source, float amount) { return false; }
    @Override public void die(DamageSource source) { discard(); }
    @Override public void kill() { discard(); }
    @Override public boolean isPickable() { return false; }
    @Override public boolean isPushable() { return false; }
    @Override public boolean isPushedByFluid() { return false; }
    @Override public boolean canBeCollidedWith() { return false; }
    @Override public boolean isIgnoringBlockTriggers() { return true; }
    @Override public boolean canBeAffected(MobEffectInstance effect) { return false; }
    @Override public boolean causeFallDamage(float distance, float multiplier, DamageSource source) { return false; }
    @Override protected boolean canAddPassenger(Entity passenger) { return false; }
    @Override public Iterable<ItemStack> getArmorSlots() { return List.of(); }
    @Override public ItemStack getItemBySlot(EquipmentSlot slot) { return ItemStack.EMPTY; }
    @Override public void setItemSlot(EquipmentSlot slot, ItemStack stack) {}
    @Override public HumanoidArm getMainArm() { return HumanoidArm.RIGHT; }
    @Override public boolean shouldBeSaved() { return false; }

    @Override
    public void addAdditionalSaveData(CompoundTag tag) {
        // Intentionally empty. EntityType.noSave and shouldBeSaved prevent normal serialization.
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag) {
        // Even a command-created/reloaded instance has no owner or lease and expires next tick.
        owner = null;
        expiresAt = 0L;
        leases.clear();
    }
}
