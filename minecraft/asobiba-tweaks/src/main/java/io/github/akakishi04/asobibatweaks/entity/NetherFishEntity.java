package io.github.akakishi04.asobibatweaks.entity;

import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.MoverType;
import net.minecraft.world.entity.PathfinderMob;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;

public final class NetherFishEntity extends PathfinderMob {
    private Vec3 swimDirection = Vec3.ZERO;
    private int chooseDirectionIn;

    public NetherFishEntity(EntityType<? extends NetherFishEntity> type, Level level) {
        super(type, level);
        this.setNoGravity(true);
    }

    public static AttributeSupplier.Builder createAttributes() {
        return Mob.createMobAttributes()
                .add(Attributes.MAX_HEALTH, 6.0D)
                .add(Attributes.MOVEMENT_SPEED, 0.16D)
                .add(Attributes.FOLLOW_RANGE, 12.0D);
    }

    @Override
    protected void registerGoals() {
        // Motion is handled directly in lava so the fish does not depend on water pathfinding.
    }

    @Override
    public void aiStep() {
        super.aiStep();

        if (this.isInLava()) {
            this.clearFire();
            this.setAirSupply(this.getMaxAirSupply());
            this.setNoGravity(true);

            if (--chooseDirectionIn <= 0 || this.horizontalCollision || swimDirection.lengthSqr() < 0.001D) {
                chooseDirectionIn = 20 + this.getRandom().nextInt(50);
                swimDirection = new Vec3(
                        this.getRandom().nextDouble() * 2.0D - 1.0D,
                        this.getRandom().nextDouble() * 0.8D - 0.4D,
                        this.getRandom().nextDouble() * 2.0D - 1.0D
                );
                if (swimDirection.lengthSqr() > 0.001D) swimDirection = swimDirection.normalize();
            }

            Vec3 next = this.getDeltaMovement().scale(0.86D).add(swimDirection.scale(0.035D));
            this.setDeltaMovement(next);
            if (next.horizontalDistanceSqr() > 0.0001D) {
                this.setYRot((float)(Math.toDegrees(Math.atan2(-next.x, next.z))));
                this.yBodyRot = this.getYRot();
            }
        } else {
            this.setNoGravity(false);
        }
    }

    @Override
    public void travel(Vec3 travelVector) {
        if (this.isInLava()) {
            this.move(MoverType.SELF, this.getDeltaMovement());
            this.setDeltaMovement(this.getDeltaMovement().scale(0.92D));
        } else {
            super.travel(travelVector);
        }
    }

    @Override
    public boolean causeFallDamage(float fallDistance, float multiplier, net.minecraft.world.damagesource.DamageSource source) {
        return false;
    }

    @Override
    public boolean isPushedByFluid() {
        return false;
    }
}
