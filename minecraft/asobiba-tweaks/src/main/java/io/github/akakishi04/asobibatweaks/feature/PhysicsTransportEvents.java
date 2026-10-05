package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.List;
import java.util.UUID;
import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.vehicle.AbstractMinecart;
import net.minecraft.world.item.Items;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.player.PlayerInteractEvent;
import net.neoforged.neoforge.event.level.ExplosionEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;

public final class PhysicsTransportEvents {
    private static final String LINK_SELECT = "asobibatweaks_cart_link_select";
    private static final String LINK = "asobibatweaks_cart_link";

    @SubscribeEvent
    public void onCartInteract(PlayerInteractEvent.EntityInteract event) {
        if (!AsobibaTweaksConfig.MINECART_COUPLING_ENABLED.getAsBoolean()
                || event.getLevel().isClientSide()
                || event.getHand() != InteractionHand.MAIN_HAND
                || !(event.getEntity() instanceof ServerPlayer player)
                || !(event.getTarget() instanceof AbstractMinecart cart)
                || !event.getItemStack().is(Items.CHAIN)) {
            return;
        }

        String selected = player.getPersistentData().getString(LINK_SELECT);
        if (selected.isEmpty()) {
            player.getPersistentData().putString(LINK_SELECT, cart.getUUID().toString());
            player.displayClientMessage(Component.literal("Minecart selected for coupling.").withStyle(ChatFormatting.GRAY), true);
            succeed(event);
            return;
        }

        UUID firstId;
        try {
            firstId = UUID.fromString(selected);
        } catch (IllegalArgumentException ex) {
            player.getPersistentData().remove(LINK_SELECT);
            return;
        }

        Entity first = player.serverLevel().getEntity(firstId);
        player.getPersistentData().remove(LINK_SELECT);
        if (!(first instanceof AbstractMinecart firstCart) || firstCart == cart) {
            player.displayClientMessage(Component.literal("Coupling selection expired.").withStyle(ChatFormatting.YELLOW), true);
            succeed(event);
            return;
        }

        firstCart.getPersistentData().putString(LINK, cart.getUUID().toString());
        cart.getPersistentData().putString(LINK, firstCart.getUUID().toString());
        if (!player.getAbilities().instabuild) {
            event.getItemStack().shrink(1);
        }
        player.displayClientMessage(Component.literal("Minecarts coupled.").withStyle(ChatFormatting.GREEN), true);
        succeed(event);
    }

    @SubscribeEvent
    public void onEntityTick(EntityTickEvent.Post event) {
        if (!(event.getEntity() instanceof AbstractMinecart cart) || cart.level().isClientSide()) {
            return;
        }

        if (AsobibaTweaksConfig.MINECART_COUPLING_ENABLED.getAsBoolean()) {
            tickCoupling(cart);
        }
        if (AsobibaTweaksConfig.MINECART_COLLISION_ENABLED.getAsBoolean()) {
            tickCollision(cart);
        }
        if (AsobibaTweaksConfig.WIND_PRESSURE_ENABLED.getAsBoolean()) {
            tickSlipstream(cart);
        }
    }

    @SubscribeEvent
    public void onExplosion(ExplosionEvent.Detonate event) {
        if (!AsobibaTweaksConfig.WIND_PRESSURE_ENABLED.getAsBoolean() || event.getLevel().isClientSide()) {
            return;
        }

        Vec3 center = event.getExplosion().center();
        double sourceMultiplier = 1.0D;
        Entity direct = event.getExplosion().getDirectSourceEntity();
        if (direct != null && direct.getPersistentData().contains("asobibatweaks_tnt_wind")) {
            sourceMultiplier = Math.max(0.1D, direct.getPersistentData().getDouble("asobibatweaks_tnt_wind"));
        }
        double radius = Math.max(3.0D, event.getExplosion().radius() * 2.25D * Math.sqrt(sourceMultiplier));
        List<Entity> entities = event.getLevel().getEntities(
                event.getExplosion().getDirectSourceEntity(),
                new AABB(center, center).inflate(radius)
        );

        for (Entity entity : entities) {
            if (!entity.isAlive()) continue;
            Vec3 delta = entity.position().subtract(center);
            double distance = Math.max(0.75D, delta.length());
            if (distance > radius) continue;

            double strength = (1.0D - distance / radius) * event.getExplosion().radius() * 0.18D * sourceMultiplier;
            strength *= massFactor(entity) * windResistanceFactor(entity);
            if (strength <= 0.01D) continue;

            Vec3 impulse = delta.normalize().scale(strength).add(0.0D, strength * 0.22D, 0.0D);
            entity.setDeltaMovement(entity.getDeltaMovement().add(impulse));
            entity.hurtMarked = true;
        }
    }

    private static void tickCoupling(AbstractMinecart cart) {
        String partnerId = cart.getPersistentData().getString(LINK);
        if (partnerId.isEmpty() || !(cart.level() instanceof ServerLevel level)) return;

        Entity otherEntity;
        try {
            otherEntity = level.getEntity(UUID.fromString(partnerId));
        } catch (IllegalArgumentException ex) {
            cart.getPersistentData().remove(LINK);
            return;
        }
        if (!(otherEntity instanceof AbstractMinecart other) || !other.isAlive()) return;

        Vec3 delta = other.position().subtract(cart.position());
        double distance = delta.length();
        if (distance > 16.0D) {
            cart.getPersistentData().remove(LINK);
            other.getPersistentData().remove(LINK);
            return;
        }

        Vec3 average = cart.getDeltaMovement().add(other.getDeltaMovement()).scale(0.5D);
        if (distance > 1.8D && distance > 0.001D) {
            Vec3 pull = delta.normalize().scale(Math.min(0.12D, (distance - 1.8D) * 0.05D));
            cart.setDeltaMovement(cart.getDeltaMovement().scale(0.88D).add(average.scale(0.12D)).add(pull));
        } else if (distance < 1.1D && distance > 0.001D) {
            cart.setDeltaMovement(cart.getDeltaMovement().add(delta.normalize().scale(-0.03D)));
        } else {
            cart.setDeltaMovement(cart.getDeltaMovement().scale(0.94D).add(average.scale(0.06D)));
        }
    }

    private static void tickCollision(AbstractMinecart cart) {
        double speed = cart.getDeltaMovement().horizontalDistance();
        if (speed < 0.65D || cart.tickCount % 2 != 0) return;

        long now = cart.level().getGameTime();
        for (LivingEntity target : cart.level().getEntitiesOfClass(
                LivingEntity.class,
                cart.getBoundingBox().inflate(0.35D),
                e -> e.isAlive() && !cart.hasPassenger(e))) {
            long until = target.getPersistentData().getLong("asobibatweaks_cart_hit_until");
            if (until > now) continue;

            float damage = (float)Math.min(24.0D, Math.max(1.0D, (speed - 0.55D) * 9.0D));
            target.hurt(cart.damageSources().generic(), damage);
            Vec3 push = cart.getDeltaMovement();
            if (push.horizontalDistanceSqr() > 0.0001D) {
                Vec3 impulse = new Vec3(push.x, 0.0D, push.z).normalize().scale(Math.min(2.5D, speed * 0.9D));
                target.setDeltaMovement(target.getDeltaMovement().add(impulse).add(0.0D, 0.12D, 0.0D));
                target.hurtMarked = true;
            }
            target.getPersistentData().putLong("asobibatweaks_cart_hit_until", now + 10L);
        }
    }

    private static void tickSlipstream(AbstractMinecart cart) {
        double speed = cart.getDeltaMovement().horizontalDistance();
        if (speed < 1.0D || cart.tickCount % 3 != 0) return;

        Vec3 velocity = cart.getDeltaMovement();
        Vec3 forward = new Vec3(velocity.x, 0.0D, velocity.z);
        if (forward.lengthSqr() < 0.0001D) return;
        forward = forward.normalize();

        for (Entity entity : cart.level().getEntities(cart, cart.getBoundingBox().inflate(2.5D))) {
            Vec3 relative = entity.position().subtract(cart.position());
            double side = Math.abs(relative.x * -forward.z + relative.z * forward.x);
            if (side > 2.1D) continue;

            double strength = Math.min(0.55D, (speed - 0.8D) * 0.12D) * massFactor(entity) * windResistanceFactor(entity);
            entity.setDeltaMovement(entity.getDeltaMovement().add(forward.scale(strength)));
            entity.hurtMarked = true;
        }
    }

    private static double massFactor(Entity entity) {
        double area = Math.max(0.25D, entity.getBbWidth() * entity.getBbHeight());
        return 1.0D / Math.max(0.65D, Math.sqrt(area));
    }

    private static double windResistanceFactor(Entity entity) {
        if (!AsobibaTweaksConfig.WIND_PRESSURE_RESISTANCE_ENABLED.getAsBoolean()
                || !(entity instanceof LivingEntity living)) {
            return 1.0D;
        }

        int total = 0;
        for (var armor : living.getArmorSlots()) {
            for (var entry : net.minecraft.world.item.enchantment.EnchantmentHelper.getEnchantmentsForCrafting(armor).entrySet()) {
                if ("asobibatweaks:wind_pressure_resistance".equals(EnchantmentMasteryData.id(entry.getKey()))) {
                    total += entry.getIntValue();
                }
            }
        }
        return 1.0D / (1.0D + total * 0.32D);
    }

    private static void succeed(PlayerInteractEvent.EntityInteract event) {
        event.setCancellationResult(InteractionResult.SUCCESS);
        event.setCanceled(true);
    }
}
