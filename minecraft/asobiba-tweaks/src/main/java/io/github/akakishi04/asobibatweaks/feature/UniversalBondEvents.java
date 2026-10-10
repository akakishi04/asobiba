package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.PathfinderMob;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.living.LivingChangeTargetEvent;
import net.neoforged.neoforge.event.entity.living.LivingIncomingDamageEvent;
import net.neoforged.neoforge.event.entity.player.PlayerInteractEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;

public final class UniversalBondEvents {
    @SubscribeEvent
    public void onInteract(PlayerInteractEvent.EntityInteract event) {
        if (!AsobibaTweaksConfig.UNIVERSAL_BOND_ENABLED.getAsBoolean()) {
            return;
        }
        if (event.getLevel().isClientSide() || event.getHand() != InteractionHand.MAIN_HAND) {
            return;
        }
        if (!(event.getEntity() instanceof ServerPlayer player) || !player.isShiftKeyDown()) {
            return;
        }
        if (!(event.getTarget() instanceof Mob mob)) {
            return;
        }

        if (UniversalBondData.isBoss(mob) && !AsobibaTweaksConfig.UNIVERSAL_BOND_ALLOW_BOSSES.getAsBoolean()) {
            return;
        }

        ItemStack held = event.getItemStack();

        if (UniversalBondData.isBonded(mob)) {
            if (UniversalBondData.isOwner(mob, player.getUUID()) && held.isEmpty()) {
                boolean stay = UniversalBondData.toggleStay(mob);
                player.sendSystemMessage(Component.literal(
                        mob.getName().getString() + ": " + (stay ? "Stay" : "Follow")
                ).withStyle(ChatFormatting.AQUA));
                succeed(event);
            }
            return;
        }

        if (!UniversalBondData.isBondingGift(mob, held)) {
            return;
        }

        String candidate = UniversalBondData.candidate(mob);
        if (!candidate.isEmpty() && !candidate.equals(player.getUUID().toString())) {
            player.sendSystemMessage(Component.literal(
                    mob.getName().getString() + " is already getting used to someone else."
            ).withStyle(ChatFormatting.YELLOW));
            succeed(event);
            return;
        }

        if (candidate.isEmpty()) {
            UniversalBondData.setCandidate(mob, player.getUUID());
        }

        int bond = Math.min(100, UniversalBondData.getBond(mob) + AsobibaTweaksConfig.UNIVERSAL_BOND_PER_GIFT.getAsInt());
        UniversalBondData.setBond(mob, bond);

        if (!player.getAbilities().instabuild) {
            held.shrink(1);
        }

        if (bond >= 100) {
            UniversalBondData.completeBond(mob, player.getUUID());
            player.sendSystemMessage(Component.literal(
                    mob.getName().getString() + " is now bonded to you."
            ).withStyle(ChatFormatting.GREEN));
        } else {
            player.sendSystemMessage(Component.literal(
                    mob.getName().getString() + " Bond: " + bond + "/100"
            ).withStyle(ChatFormatting.LIGHT_PURPLE));
        }

        succeed(event);
    }

    @SubscribeEvent
    public void onChangeTarget(LivingChangeTargetEvent event) {
        if (!AsobibaTweaksConfig.UNIVERSAL_BOND_ENABLED.getAsBoolean()) {
            return;
        }
        if (!(event.getEntity() instanceof Mob mob) || !UniversalBondData.isBonded(mob)) {
            return;
        }

        if (event.getNewAboutToBeSetTarget() instanceof Player player
                && UniversalBondData.isOwner(mob, player.getUUID())) {
            event.setNewAboutToBeSetTarget(null);
        }
    }

    @SubscribeEvent
    public void onIncomingDamage(LivingIncomingDamageEvent event) {
        if (!AsobibaTweaksConfig.UNIVERSAL_BOND_ENABLED.getAsBoolean()
                || AsobibaTweaksConfig.UNIVERSAL_BOND_FRIENDLY_FIRE.getAsBoolean()) {
            return;
        }

        Entity attacker = event.getSource().getEntity();

        if (event.getEntity() instanceof Player owner
                && attacker instanceof Mob bondedMob
                && UniversalBondData.isBonded(bondedMob)
                && UniversalBondData.isOwner(bondedMob, owner.getUUID())) {
            event.setCanceled(true);
            return;
        }

        if (event.getEntity() instanceof Mob bondedMob
                && UniversalBondData.isBonded(bondedMob)
                && attacker instanceof Player owner
                && UniversalBondData.isOwner(bondedMob, owner.getUUID())) {
            event.setCanceled(true);
        }
    }

    @SubscribeEvent
    public void onEntityTick(EntityTickEvent.Post event) {
        if (!AsobibaTweaksConfig.UNIVERSAL_BOND_ENABLED.getAsBoolean()
                || !AsobibaTweaksConfig.UNIVERSAL_BOND_FOLLOW.getAsBoolean()) {
            return;
        }
        if (!(event.getEntity() instanceof PathfinderMob mob)
                || !UniversalBondData.isBonded(mob)
                || UniversalBondData.isStay(mob)
                || mob.level().isClientSide()) {
            return;
        }
        if (mob.level().getGameTime() % 10L != Math.floorMod(mob.getId(), 10)) {
            return;
        }

        String ownerId = mob.getPersistentData().getString("asobibatweaks_bond_owner");
        if (ownerId.isEmpty()) {
            return;
        }

        ServerPlayer owner;
        try {
            owner = mob.getServer() == null ? null : mob.getServer().getPlayerList().getPlayer(java.util.UUID.fromString(ownerId));
        } catch (IllegalArgumentException ignored) {
            return;
        }

        if (owner == null || owner.level() != mob.level()) {
            return;
        }

        double distance = mob.distanceToSqr(owner);
        if (distance > 16.0D) {
            mob.getNavigation().moveTo(owner, 1.1D);
        } else if (distance < 6.25D) {
            mob.getNavigation().stop();
        }
    }

    private static void succeed(PlayerInteractEvent.EntityInteract event) {
        event.setCancellationResult(InteractionResult.SUCCESS);
        event.setCanceled(true);
    }
}
