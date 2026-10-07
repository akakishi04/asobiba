package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.Optional;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.GlobalPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.Mth;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.ai.memory.MemoryModuleType;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.npc.VillagerProfession;
import net.minecraft.world.item.trading.MerchantOffer;
import net.minecraft.world.phys.AABB;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.player.PlayerInteractEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;

/**
 * Active-time villager welfare sampling and trading-hall refusal behavior.
 */
public final class VillagerWelfareService {
    private static final int SAMPLE_TICKS = 200;

    private VillagerWelfareService() {
    }

    @SubscribeEvent
    public void onVillagerTick(EntityTickEvent.Post event) {
        if (!AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof Villager villager)
                || villager.level().isClientSide()
                || villager.isBaby()
                || villager.tickCount % SAMPLE_TICKS != Math.floorMod(villager.getId(), SAMPLE_TICKS)) {
            return;
        }

        ServerLevel level = (ServerLevel)villager.level();
        VillageIdentityBootstrap.ensure(villager, level);
        sample(villager, level);
    }

    @SubscribeEvent
    public void onEntityInteract(PlayerInteractEvent.EntityInteract event) {
        if (!(event.getTarget() instanceof Villager villager)
                || villager.level().isClientSide()
                || !VillagerSimData.refusal(villager)) {
            return;
        }

        event.setCanceled(true);
        event.setCancellationResult(InteractionResult.SUCCESS);
        event.getEntity().displayClientMessage(
                Component.literal("This villager refuses to trade until its living conditions improve."),
                true
        );
    }

    public static void sample(Villager villager, ServerLevel level) {
        VillagerSimData.ensureInitialized(villager);

        long before = VillagerSimData.activeObservedTicks(villager);
        VillagerSimData.addActiveObservedTicks(villager, SAMPLE_TICKS);
        long active = VillagerSimData.activeObservedTicks(villager);
        BlockPos currentPos = villager.blockPosition();

        if (before == 0L) {
            VillagerSimData.setLastMoveActive(villager, active);
            VillagerSimData.setLastSleepActive(villager, active);
            VillagerSimData.setLastWorkActive(villager, active);
            VillagerSimData.setLastOpenActive(villager, active);
            VillagerSimData.setLastSocialActive(villager, active);
        }

        VillagerSimData.lastSamplePos(villager).ifPresent(last -> {
            if (last.distManhattan(currentPos) >= 2) {
                VillagerSimData.setLastMoveActive(villager, active);
            }
        });
        VillagerSimData.setLastSamplePos(villager, currentPos);

        if (villager.isSleeping()) {
            VillagerSimData.setLastSleepActive(villager, active);
        }

        VillagerProfession profession = villager.getVillagerData().getProfession();
        if (profession == VillagerProfession.NONE || profession == VillagerProfession.NITWIT) {
            VillagerSimData.setLastWorkActive(villager, active);
        } else if (isWorkTime(level) && hasNearbyJobSite(villager, level)) {
            VillagerSimData.setLastWorkActive(villager, active);
        }

        if (level.canSeeSky(currentPos)) {
            VillagerSimData.setLastOpenActive(villager, active);
        }

        Optional<UUID> villageId = VillagerSimData.villageId(villager);
        boolean social = !level.getEntitiesOfClass(
                Villager.class,
                new AABB(currentPos).inflate(8.0D),
                other -> other != villager
                        && other.isAlive()
                        && villageId.equals(VillagerSimData.villageId(other))
        ).isEmpty();
        if (social) {
            VillagerSimData.setLastSocialActive(villager, active);
        }

        int mobility = recencyScore(active, VillagerSimData.lastMoveActive(villager), 12_000L, 48_000L);
        int sleep = recencyScore(active, VillagerSimData.lastSleepActive(villager), 30_000L, 72_000L);
        int work = profession == VillagerProfession.NONE || profession == VillagerProfession.NITWIT
                ? 100
                : recencyScore(active, VillagerSimData.lastWorkActive(villager), 12_000L, 48_000L);
        int openSpace = recencyScore(active, VillagerSimData.lastOpenActive(villager), 12_000L, 48_000L);
        int socialScore = recencyScore(active, VillagerSimData.lastSocialActive(villager), 12_000L, 48_000L);

        int target = Mth.clamp(Math.round(
                mobility * 0.30F
                        + sleep * 0.20F
                        + work * 0.20F
                        + openSpace * 0.15F
                        + socialScore * 0.15F
        ), 0, 100);

        int current = VillagerSimData.welfare(villager);
        int delta = Mth.clamp(target - current, -2, 2);
        int next = Mth.clamp(current + delta, 0, 100);
        VillagerSimData.setWelfare(villager, next);

        boolean refusing = VillagerSimData.refusal(villager);
        if (!refusing && next < 20) {
            VillagerSimData.setRefusal(villager, true);
        } else if (refusing && next >= 40) {
            VillagerSimData.setRefusal(villager, false);
        }
    }

    /**
     * Called after vanilla updateSpecialPrices so this is additive to reputation/Hero pricing.
     */
    public static void applyTradePriceModifier(Villager villager) {
        int percent = welfarePricePercent(VillagerSimData.welfare(villager));
        if (percent <= 0) return;

        for (MerchantOffer offer : villager.getOffers()) {
            int base = Math.max(1, offer.getBaseCostA().getCount());
            int welfareDiff = Math.max(1, Mth.ceil(base * (percent / 100.0F)));
            offer.addToSpecialPriceDiff(welfareDiff);
        }
    }

    public static int welfarePricePercent(int welfare) {
        if (welfare < 20) return 50;
        if (welfare < 40) return 25;
        if (welfare < 60) return 10;
        return 0;
    }

    private static boolean hasNearbyJobSite(Villager villager, ServerLevel level) {
        Optional<GlobalPos> job = villager.getBrain().getMemory(MemoryModuleType.JOB_SITE);
        if (job.isEmpty() || !job.get().dimension().equals(level.dimension())) return false;
        return villager.distanceToSqr(job.get().pos().getCenter()) <= 16.0D * 16.0D;
    }

    private static int recencyScore(long active, long lastSuccess, long fullUntil, long zeroAt) {
        if (lastSuccess <= 0L) return active <= fullUntil ? 100 : 0;
        long age = Math.max(0L, active - lastSuccess);
        if (age <= fullUntil) return 100;
        if (age >= zeroAt) return 0;

        double span = Math.max(1.0D, zeroAt - fullUntil);
        double remaining = 1.0D - (age - fullUntil) / span;
        return Mth.clamp((int)Math.round(remaining * 100.0D), 0, 100);
    }

    private static boolean isWorkTime(ServerLevel level) {
        long t = Math.floorMod(level.getDayTime(), 24000L);
        return t >= 1500L && t <= 10500L && !level.isThundering();
    }
}
