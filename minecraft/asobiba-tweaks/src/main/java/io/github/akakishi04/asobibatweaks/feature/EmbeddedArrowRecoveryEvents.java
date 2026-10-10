package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.projectile.AbstractArrow;
import net.minecraft.world.item.ItemStack;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.living.LivingDamageEvent;
import net.neoforged.neoforge.event.entity.living.LivingDropsEvent;

/**
 * A non-piercing projectile that actually wounds a living target can be
 * recovered when the target subsequently dies. Its exact source ItemStack is
 * retained in the target's persistent data. No secondary Multishot, creative
 * or Infinity-generated arrow may create a recovery item.
 */
public final class EmbeddedArrowRecoveryEvents {
    private static final String EMBEDDED = "asobibatweaks_recoverable_embedded_arrows";
    private static final String STORED = "asobibatweaks_embedded_arrow_recorded";
    private static final int MAX_TRACKED_PER_ENTITY = 48;

    @SubscribeEvent
    public void onSuccessfulHit(LivingDamageEvent.Post event) {
        if (!AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                || event.getNewDamage() <= 0.0F
                || !(event.getSource().getDirectEntity() instanceof AbstractArrow arrow)
                || !(arrow.level() instanceof ServerLevel level)
                || arrow.pickup != AbstractArrow.Pickup.ALLOWED
                || arrow.getPierceLevel() > 0
                || LoyaltyArrowEvents.isLoyaltyArrow(arrow)) {
            return;
        }

        CompoundTag projectileData = arrow.getPersistentData();
        if (projectileData.getBoolean(STORED)) return;

        ItemStack source = arrow.getPickupItemStackOrigin();
        if (source.isEmpty() || !ExtendedEnchantingTargets.isExtendedArrowTarget(source)) return;

        LivingEntity victim = event.getEntity();
        CompoundTag target = victim.getPersistentData();
        ListTag arrows = target.getList(EMBEDDED, Tag.TAG_COMPOUND);
        if (arrows.size() >= MAX_TRACKED_PER_ENTITY) return;

        ItemStack exact = source.copyWithCount(1);
        arrows.add(exact.saveOptional(level.registryAccess()));
        target.put(EMBEDDED, arrows);
        projectileData.putBoolean(STORED, true);
    }

    @SubscribeEvent
    public void onDrops(LivingDropsEvent event) {
        if (!AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                || !(event.getEntity().level() instanceof ServerLevel server)
                || event.isCanceled()) return;

        CompoundTag tag = event.getEntity().getPersistentData();
        if (!tag.contains(EMBEDDED, Tag.TAG_LIST)) return;
        ListTag arrows = tag.getList(EMBEDDED, Tag.TAG_COMPOUND);
        if (arrows.isEmpty()) {
            tag.remove(EMBEDDED);
            return;
        }

        for (int i = 0; i < Math.min(MAX_TRACKED_PER_ENTITY, arrows.size()); i++) {
            ItemStack original = ItemStack.parseOptional(server.registryAccess(), arrows.getCompound(i));
            if (original.isEmpty() || !ExtendedEnchantingTargets.isExtendedArrowTarget(original)) {
                continue;
            }
            event.getDrops().add(new ItemEntity(
                    server,
                    event.getEntity().getX(),
                    event.getEntity().getY() + 0.35D,
                    event.getEntity().getZ(),
                    original.copyWithCount(1)
            ));
        }

        // Death-drop records are consumed once, so repeated event calls cannot
        // emit the same stored arrow again.
        tag.remove(EMBEDDED);
    }
}
