package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.mixin.AbstractArrowPierceAccessor;
import net.minecraft.core.BlockPos;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.projectile.AbstractArrow;
import net.minecraft.world.item.ArrowItem;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.phys.Vec3;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.bus.api.EventPriority;
import net.neoforged.neoforge.event.entity.ProjectileImpactEvent;
import net.minecraft.world.phys.HitResult;
import net.neoforged.neoforge.event.entity.living.LivingDamageEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;

/**
 * Returning projectiles preserve exact item components and always consume
 * the original projectile. A returning arrow is never manually pickable.
 *
 * For normal non-piercing entity hits, vanilla discards the arrow after
 * dealing damage; we replace it with one non-colliding return projectile.
 * Piercing arrows remain physical until they embed or cease moving.
 */
public final class LoyaltyArrowEvents {
    public static final String QUIVER_SLOT_TAG = "asobibatweaks_loyalty_origin_quiver_slot";
    private static final String RETURN_ACTIVE = "asobibatweaks_loyalty_return_active";
    private static final String RETURN_QUEUED = "asobibatweaks_loyalty_return_queued";
    private static final String SPAWNED_RETURN = "asobibatweaks_loyalty_return_spawned";
    private static final String RETURN_READY = "asobibatweaks_loyalty_return_ready";
    private static final String SUCCESSFUL_PIERCE_HITS =
            "asobibatweaks_loyalty_successful_pierce_hits";

    public static boolean isLoyaltyArrow(AbstractArrow arrow) {
        return EnchantedArrowImpactEvents.level(
                arrow.getPickupItemStackOrigin(), "minecraft:loyalty") > 0;
    }

    @SubscribeEvent
    public void onSuccessfulLivingHit(LivingDamageEvent.Post event) {
        if (!AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                || event.getNewDamage() <= 0.0F
                || !(event.getSource().getDirectEntity() instanceof AbstractArrow original)
                || !(original.level() instanceof ServerLevel server)
                || !(original.getOwner() instanceof ServerPlayer shooter)
                || original.pickup != AbstractArrow.Pickup.ALLOWED
                || !isLoyaltyArrow(original)) return;

        // A Piercing+Loyalty projectile retains its identity and continues
        // normal flight. Record successful targets only; reaching the limit
        // does not begin return while the projectile is still traveling.
        if (original.getPierceLevel() > 0) {
            CompoundTag pierced = original.getPersistentData();
            pierced.putInt(SUCCESSFUL_PIERCE_HITS, Math.min(128,
                    pierced.getInt(SUCCESSFUL_PIERCE_HITS) + 1));
            return;
        }

        CompoundTag originalData = original.getPersistentData();
        if (originalData.getBoolean(SPAWNED_RETURN)) return;

        ItemStack firedAmmo = original.getPickupItemStackOrigin();
        if (!(firedAmmo.getItem() instanceof ArrowItem arrowItem)) return;

        // Copy the exact physical ammunition; do not hand the player an item
        // until this new return projectile reaches them. The vanilla original
        // will be discarded at the end of its successful non-piercing hit.
        AbstractArrow returning = arrowItem.createArrow(server,
                firedAmmo.copyWithCount(1), shooter, null);
        if (returning == null) return;
        returning.setPos(original.getX(), original.getY(), original.getZ());
        returning.setDeltaMovement(Vec3.ZERO);
        returning.setNoPhysics(true);
        returning.pickup = AbstractArrow.Pickup.DISALLOWED;
        CompoundTag data = returning.getPersistentData();
        startReturn(returning, data, server);
        if (server.addFreshEntity(returning)) {
            originalData.putBoolean(SPAWNED_RETURN, true);
            original.pickup = AbstractArrow.Pickup.DISALLOWED;
        }
    }


    /**
     * After Piercing has dealt damage to its final allowed living target,
     * vanilla may still let the arrow travel, then discard it upon the NEXT
     * entity collision. Cancel only that otherwise-terminal collision.
     * Do not start the return on the final successful hit itself.
     */
    @SubscribeEvent(priority = EventPriority.HIGHEST)
    public void onExhaustedPiercingCollision(ProjectileImpactEvent event) {
        if (!AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                || event.isCanceled()
                || event.getRayTraceResult().getType() != HitResult.Type.ENTITY
                || !(event.getProjectile() instanceof AbstractArrow arrow)
                || !(arrow.level() instanceof ServerLevel server)
                || !(arrow.getOwner() instanceof ServerPlayer)
                || arrow.pickup != AbstractArrow.Pickup.ALLOWED
                || arrow.getPierceLevel() <= 0
                || !isLoyaltyArrow(arrow)) return;

        CompoundTag data = arrow.getPersistentData();
        if (data.getBoolean(RETURN_ACTIVE)
                || data.getInt(SUCCESSFUL_PIERCE_HITS) < arrow.getPierceLevel() + 1) {
            return;
        }

        // This is the first collision at which vanilla would terminate the
        // arrow instead of resolving further damage. Keep the one physical
        // projectile and convert it to the returning state in-place.
        event.setCanceled(true);
        data.putBoolean(RETURN_QUEUED, true);
        arrow.setDeltaMovement(Vec3.ZERO);
        startReturn(arrow, data, server);
    }

    @SubscribeEvent
    public void onArrowPostTick(EntityTickEvent.Post event) {
        if (!AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof AbstractArrow arrow)
                || !(arrow.level() instanceof ServerLevel server)
                || arrow.isRemoved()
                || arrow.pickup != AbstractArrow.Pickup.ALLOWED
                || !isLoyaltyArrow(arrow)) return;

        CompoundTag data = arrow.getPersistentData();
        if (data.getBoolean(RETURN_ACTIVE) || data.getBoolean(RETURN_QUEUED)) return;

        // Piercing does not trigger a return at the first entity hit, or
        // merely when its entity penetration budget is exhausted.
        boolean landed = ((AbstractArrowPierceAccessor)arrow).asobibatweaks$isInGround();
        boolean stopped = arrow.tickCount > 5
                && arrow.getDeltaMovement().lengthSqr() < 0.00001D;
        if (!landed && !stopped) return;

        data.putBoolean(RETURN_QUEUED, true);
        arrow.pickup = AbstractArrow.Pickup.DISALLOWED;
        arrow.setNoPhysics(true);
        arrow.setDeltaMovement(Vec3.ZERO);
        startReturn(arrow, data, server);
    }

    @SubscribeEvent
    public void onArrowPreTick(EntityTickEvent.Pre event) {
        if (!(event.getEntity() instanceof AbstractArrow arrow)
                || !(arrow.level() instanceof ServerLevel server)) return;
        CompoundTag data = arrow.getPersistentData();
        if (!data.getBoolean(RETURN_ACTIVE)) return;

        // Never load an owner chunk, dimension, or intermediate route solely
        // to return ammunition. Suspended arrows persist with their chunk.
        if (!(arrow.getOwner() instanceof ServerPlayer owner)
                || !owner.isAlive() || owner.isSpectator()
                || owner.level() != server) {
            arrow.setDeltaMovement(Vec3.ZERO);
            return;
        }
        long readyAt = data.getLong(RETURN_READY);
        if (server.getGameTime() < readyAt) {
            arrow.setDeltaMovement(Vec3.ZERO);
            return;
        }

        Vec3 target = owner.getEyePosition();
        Vec3 delta = target.subtract(arrow.position());
        if (delta.lengthSqr() <= 2.25D) {
            ItemStack original = arrow.getPickupItemStackOrigin();
            ItemStack restored = withoutLaunchMarker(original.copyWithCount(1));
            if (!restored.isEmpty() && !data.getBoolean("asobibatweaks_loyalty_delivered")) {
                data.putBoolean("asobibatweaks_loyalty_delivered", true);
                growLoyaltyMastery(owner, restored);
                deliver(owner, restored, preferredSlot(original));
            }
            arrow.discard();
            event.setCanceled(true);
            return;
        }

        ItemStack arrowItem = arrow.getPickupItemStackOrigin();
        int level = Math.min(10, EnchantedArrowImpactEvents.level(
                arrowItem, "minecraft:loyalty"));
        double speed = 0.50D * (1.0D + 0.15D * Math.max(0, level - 1));
        double steering = 0.38D;
        Vec3 direction = delta.normalize();

        MasteryBranch mastery = masteryBranch(arrowItem);
        if (mastery != null) {
            double growth = (Math.min(100, mastery.mastery()) - 50) / 50.0D;
            if (mastery.index() == 0) {
                // Fast Return: +15% at 50 to +50% at 100.
                speed *= 1.15D + 0.35D * growth;
            } else if (mastery.index() == 1) {
                // Safe Return: stronger path correction and a conservative,
                // already-loaded 4-12-block local detour search.
                steering *= 1.25D + 0.50D * growth;
                direction = safeReturnDirection(arrow, server, direction,
                        4 + (int)Math.round(8.0D * growth));
            } else if (mastery.index() == 2
                    && owner.getDeltaMovement().dot(direction) > 0.10D) {
                // Pursuing Return: the owner is moving away from this arrow.
                // Acceleration grows 20-60%; speed cap grows only 10-30%.
                steering *= 1.20D + 0.40D * growth;
                speed *= 1.10D + 0.20D * growth;
            }
        }

        steering = Math.min(0.95D, steering);
        Vec3 desired = direction.scale(speed);
        Vec3 travel = arrow.getDeltaMovement().scale(1.0D - steering)
                .add(desired.scale(steering));
        if (travel.lengthSqr() > speed * speed) {
            travel = travel.normalize().scale(speed);
        }
        if (!server.hasChunkAt(BlockPos.containing(arrow.position().add(travel)))) {
            arrow.setDeltaMovement(Vec3.ZERO);
            return;
        }
        arrow.setNoPhysics(true);
        arrow.setDeltaMovement(travel);
        arrow.hurtMarked = true;
    }


    /**
     * Inspect a short, loaded-only segment toward the owner. If it intersects
     * solid terrain, bias the next steering target around that obstacle.
     * No chunk tickets are requested, and no distant terrain is sampled.
     */
    private static Vec3 safeReturnDirection(AbstractArrow arrow, ServerLevel server,
                                            Vec3 direction, int range) {
        Vec3 start = arrow.position();
        for (int dist = 1; dist <= Math.min(12, range); dist++) {
            BlockPos obstacle = BlockPos.containing(start.add(direction.scale(dist)));
            if (!server.hasChunkAt(obstacle)) break;
            if (server.getBlockState(obstacle).getCollisionShape(server, obstacle).isEmpty()) {
                continue;
            }

            Vec3 sideways = new Vec3(-direction.z, 0.0D, direction.x);
            if (sideways.lengthSqr() < 0.0001D) sideways = new Vec3(1.0D, 0.0D, 0.0D);
            sideways = sideways.normalize();
            CompoundTag state = arrow.getPersistentData();
            int preferred = state.getInt("asobibatweaks_loyalty_detour_side");
            if (preferred == 0) preferred = 1;

            for (int side : new int[]{preferred, -preferred}) {
                Vec3 waypoint = start
                        .add(direction.scale(Math.max(1.0D, dist - 0.5D)))
                        .add(sideways.scale(side * 1.75D));
                BlockPos sample = BlockPos.containing(waypoint);
                if (!server.hasChunkAt(sample)
                        || !server.getBlockState(sample).getCollisionShape(server, sample).isEmpty()) {
                    continue;
                }
                state.putInt("asobibatweaks_loyalty_detour_side", side);
                return waypoint.subtract(start).normalize();
            }
            break;
        }
        return direction;
    }

    private static MasteryBranch masteryBranch(ItemStack stack) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) {
            return null;
        }
        for (var enchantment : EnchantmentMasteryData.enchantments(stack).keySet()) {
            if (!"minecraft:loyalty".equals(EnchantmentMasteryData.id(enchantment))) {
                continue;
            }
            int mastery = EnchantmentMasteryData.getMastery(stack, enchantment);
            int selected = EnchantmentMasteryData.getBranch(stack, enchantment);
            return mastery >= 50 && selected >= 0 && selected <= 2
                    ? new MasteryBranch(mastery, selected) : null;
        }
        return null;
    }

    private static void growLoyaltyMastery(ServerPlayer owner, ItemStack recovered) {
        if (!AsobibaTweaksConfig.GROWING_ENCHANTMENTS_ENABLED.getAsBoolean()) {
            return;
        }
        for (var enchantment : EnchantmentMasteryData.enchantments(recovered).keySet()) {
            if (!"minecraft:loyalty".equals(EnchantmentMasteryData.id(enchantment))) {
                continue;
            }
            int previous = EnchantmentMasteryData.getMastery(recovered, enchantment);
            EnchantmentMasteryData.addMastery(recovered, enchantment, 1);
            if (previous < 50 && EnchantmentMasteryData.getMastery(recovered, enchantment) >= 50) {
                owner.displayClientMessage(
                        net.minecraft.network.chat.Component.literal(
                                "Loyalty mastery 50: specialization available at the Enchanting Table."),
                        true);
            }
            break;
        }
    }

    private record MasteryBranch(int mastery, int index) {}

    private static void startReturn(AbstractArrow arrow, CompoundTag data, ServerLevel server) {
        int level = Math.min(10, Math.max(1, EnchantedArrowImpactEvents.level(
                arrow.getPickupItemStackOrigin(), "minecraft:loyalty")));
        data.putBoolean(RETURN_ACTIVE, true);
        data.putLong(RETURN_READY, server.getGameTime() + Math.max(1, 11 - level));
        arrow.setNoPhysics(true);
        arrow.pickup = AbstractArrow.Pickup.DISALLOWED;
    }

    private static int preferredSlot(ItemStack source) {
        CustomData custom = source.get(DataComponents.CUSTOM_DATA);
        if (custom == null || !custom.contains(QUIVER_SLOT_TAG)) return -1;
        int index = custom.copyTag().getInt(QUIVER_SLOT_TAG);
        return index >= 0 && index < QuiverData.AMMO_SLOTS ? index : -1;
    }

    private static ItemStack withoutLaunchMarker(ItemStack source) {
        CustomData custom = source.get(DataComponents.CUSTOM_DATA);
        if (custom == null || !custom.contains(QUIVER_SLOT_TAG)) return source;
        CustomData.update(DataComponents.CUSTOM_DATA, source,
                tag -> tag.remove(QUIVER_SLOT_TAG));
        return source;
    }

    private static void deliver(ServerPlayer owner, ItemStack arrow, int preferred) {
        if (AsobibaTweaksConfig.QUIVER_ENABLED.getAsBoolean()
                && QuiverData.hasEquipped(owner)) {
            if (preferred >= 0 && insertIntoSlot(owner, preferred, arrow)) return;
            // Compatible mergeable and empty slots are both valid fallbacks.
            for (int index = 0; index < QuiverData.AMMO_SLOTS; index++) {
                if (index != preferred && insertIntoSlot(owner, index, arrow)) return;
            }
        }

        ItemStack remaining = arrow.copy();
        owner.getInventory().add(remaining);
        if (!remaining.isEmpty()) owner.drop(remaining, false);
    }

    private static boolean insertIntoSlot(ServerPlayer player, int index, ItemStack arrow) {
        ItemStack equipped = QuiverData.equipped(player);
        if (equipped.isEmpty() || !QuiverData.isAmmo(arrow)) return false;

        ItemStack stored = QuiverData.ammo(player, index);
        if (!stored.isEmpty()
                && (!ItemStack.isSameItemSameComponents(stored, arrow)
                        || stored.getCount() >= stored.getMaxStackSize())) {
            return false;
        }
        ItemStack newContent = stored.isEmpty()
                ? arrow.copyWithCount(1) : stored.copy();
        if (!stored.isEmpty()) newContent.grow(1);
        QuiverData.setAmmo(player, index, newContent);
        return true;
    }
}
