package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.UUID;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.AABB;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.player.PlayerInteractEvent;

public final class VillageStatusEvents {
    @SubscribeEvent
    public void onBell(PlayerInteractEvent.RightClickBlock event) {
        if (!AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                || event.getLevel().isClientSide()
                || event.getHand() != InteractionHand.MAIN_HAND
                || !event.getEntity().isShiftKeyDown()
                || !event.getLevel().getBlockState(event.getPos()).is(Blocks.BELL)
                || !(event.getEntity() instanceof ServerPlayer player)
                || !(event.getLevel() instanceof ServerLevel level)) {
            return;
        }

        UUID villageId = VillageStatusNetworking.nearestVisibleVillage(level, event.getPos(), 96);
        if (villageId == null) {
            // Give pre-V1 villages one opportunity to materialize their stable identity.
            for (Villager villager : level.getEntitiesOfClass(
                    Villager.class,
                    new AABB(event.getPos()).inflate(64.0D),
                    Villager::isAlive)) {
                VillageIdentityBootstrap.ensure(villager, level);
            }
            villageId = VillageStatusNetworking.nearestVisibleVillage(level, event.getPos(), 96);
        }

        if (villageId == null) {
            player.displayClientMessage(Component.literal("No recognized village status for this Bell."), true);
        } else {
            VillageStatusNetworking.sendStatus(player, villageId);
        }

        event.setCancellationResult(InteractionResult.SUCCESS);
        event.setCanceled(true);
    }
}
