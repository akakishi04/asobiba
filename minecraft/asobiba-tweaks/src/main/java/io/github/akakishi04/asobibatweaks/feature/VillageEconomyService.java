package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.List;
import java.util.UUID;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.trading.MerchantOffer;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;

/**
 * Daily inventory-backed village market state and demographic summary.
 */
public final class VillageEconomyService {
    private static final long DAILY_TICKS = 24_000L;

    @SubscribeEvent
    public void onVillagerTick(EntityTickEvent.Post event) {
        if (!AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof Villager villager)
                || villager.level().isClientSide()
                || villager.tickCount % 200 != Math.floorMod(villager.getId(), 200)) {
            return;
        }

        ServerLevel level = (ServerLevel)villager.level();
        VillageIdentityBootstrap.ensure(villager, level);
        VillagerSimData.villageId(villager).ifPresent(villageId -> scheduleDailyRefresh(level, villageId));
    }

    public static void scheduleDailyRefresh(ServerLevel level, UUID villageId) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null) return;

        long now = level.getGameTime();
        if (now < village.nextMarketUpdateGameTime()) return;
        village.setNextMarketUpdateGameTime(now + DAILY_TICKS);
        data.touch();

        VillageSimulationScheduler.enqueuePlanning(
                level,
                "economy:" + villageId,
                () -> refreshVillage(level, villageId)
        );
    }

    public static void refreshVillage(ServerLevel level, UUID villageId) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null) return;

        VillageStorageService.reconcileVillage(villageId, level);
        int previousPopulation = village.lastKnownPopulation();
        int population = Math.max(1, village.residentIds().size());

        int food = count(village, Items.BREAD, Items.CARROT, Items.POTATO, Items.BEETROOT, Items.WHEAT);
        int wood = count(village,
                Items.OAK_LOG, Items.SPRUCE_LOG, Items.BIRCH_LOG, Items.JUNGLE_LOG, Items.ACACIA_LOG,
                Items.DARK_OAK_LOG, Items.MANGROVE_LOG, Items.CHERRY_LOG,
                Items.OAK_PLANKS, Items.SPRUCE_PLANKS, Items.BIRCH_PLANKS, Items.JUNGLE_PLANKS,
                Items.ACACIA_PLANKS, Items.DARK_OAK_PLANKS, Items.MANGROVE_PLANKS, Items.CHERRY_PLANKS);
        int stone = count(village, Items.COBBLESTONE, Items.STONE, Items.ANDESITE, Items.DIORITE,
                Items.GRANITE, Items.STONE_BRICKS, Items.BRICKS);
        int metal = count(village, Items.IRON_INGOT, Items.GOLD_INGOT, Items.COPPER_INGOT);
        int farming = count(village, Items.WHEAT_SEEDS, Items.BEETROOT_SEEDS, Items.PUMPKIN_SEEDS,
                Items.MELON_SEEDS, Items.BONE_MEAL);
        int fishing = count(village, Items.COD, Items.SALMON, Items.TROPICAL_FISH, Items.PUFFERFISH);

        village.setMarketPermille("food", band(food, Math.max(24, population * 24)));
        village.setMarketPermille("wood", band(wood, Math.max(96, population * 16)));
        village.setMarketPermille("stone", band(stone, Math.max(96, population * 16)));
        village.setMarketPermille("metal", band(metal, Math.max(24, population * 4)));
        village.setMarketPermille("farming", band(farming, Math.max(32, population * 4)));
        village.setMarketPermille("fishing", band(fishing, Math.max(24, population * 3)));
        village.setMarketPermille("luxury", 1000);

        int recordedHousing = 0;
        for (UUID buildingId : village.buildingIds()) {
            VillageSavedData.BuildingRecord building = data.building(buildingId).orElse(null);
            if (building != null && "valid".equals(building.validationState())
                    && "residential".equals(building.classification())) {
                recordedHousing += building.validatedCapacity();
            }
        }

        // Existing vanilla villages can predate BuildingRecords. Do not declare them collapsed
        // solely because V5 has not yet adopted every old house.
        int housingCapacity = recordedHousing > 0 ? recordedHousing : population + 2;
        int foodCapacity = village.storageIds().isEmpty() ? population : Math.max(0, food / 12);
        int workSiteCapacity = 0;
        for (VillageSavedData.WorkSiteRecord site : data.workSitesForVillage(villageId)) {
            if (!"active".equals(site.state())) continue;
            workSiteCapacity += "river_corridor".equals(site.type()) ? 2 : 4;
        }
        int infrastructureCapacity = Math.max(4,
                village.storageIds().size() * 8 + workSiteCapacity + 4);

        int sustainable = Math.max(0, Math.min(housingCapacity,
                Math.min(Math.max(population, foodCapacity), Math.max(population, infrastructureCapacity))));
        village.setSustainablePopulation(sustainable);

        int housingScore = scoreCapacity(housingCapacity, population);
        int foodScore = village.storageIds().isEmpty() ? 80 : scoreCapacity(foodCapacity, population);
        int infrastructureScore = scoreCapacity(infrastructureCapacity, population);
        int welfareScore = averageLoadedWelfare(level, villageId, village.center());
        int safetyScore = loadedSafetyScore(level, villageId, village.center());

        int viability = Mth.clamp(Math.round(
                housingScore * 0.25F
                        + foodScore * 0.25F
                        + safetyScore * 0.20F
                        + infrastructureScore * 0.15F
                        + welfareScore * 0.15F
        ), 0, 100);
        village.setSettlementViability(viability);

        boolean meaningfulPopulationLoss = previousPopulation > 0
                && previousPopulation - population >= Math.max(2, previousPopulation / 4);
        boolean recoveredFromStrain = ("strained".equals(village.lifecycle())
                || "evacuating".equals(village.lifecycle()))
                && viability >= 60;

        if ((meaningfulPopulationLoss || recoveredFromStrain)
                && viability >= 60 && sustainable > population
                && population * 4 <= sustainable * 3) {
            village.setRecoveryGrowthUntil(Math.max(
                    village.recoveryGrowthUntil(),
                    level.getGameTime() + 7L * DAILY_TICKS
            ));
        }

        village.setLastKnownPopulation(population);
        data.touch();
    }

    public static void applyTradePriceModifier(Villager villager) {
        if (!AsobibaTweaksConfig.REGIONAL_TRADE_VALUE_ENABLED.getAsBoolean()) return;
        for (MerchantOffer offer : villager.getOffers()) {
            int adjustment = tradePriceAdjustment(villager, offer);
            if (adjustment != 0) offer.addToSpecialPriceDiff(adjustment);
        }
    }

    public static int tradePriceAdjustment(Villager villager, MerchantOffer offer) {
        if (!AsobibaTweaksConfig.REGIONAL_TRADE_VALUE_ENABLED.getAsBoolean()
                || !(villager.level() instanceof ServerLevel level)) {
            return 0;
        }

        VillageSavedData.VillageRecord village = VillagerSimData.villageId(villager)
                .flatMap(id -> VillageSavedData.get(level).village(id))
                .orElse(null);
        if (village == null) return 0;

        ItemStack cost = offer.getBaseCostA();
        ItemStack result = offer.getResult();
        int base = Math.max(1, cost.getCount());

        if (result.is(Items.EMERALD) && !cost.is(Items.EMERALD)) {
            int permille = effectivePermille(village, cost.getItem(), villager);
            int desired = Mth.clamp((int)Math.ceil(base * 1000.0D / permille), 1, Math.max(1, cost.getMaxStackSize()));
            return desired - base;
        }

        if (cost.is(Items.EMERALD) && !result.is(Items.EMERALD)) {
            int permille = effectivePermille(village, result.getItem(), villager);
            int desired = Math.max(1, (int)Math.ceil(base * permille / 1000.0D));
            return desired - base;
        }
        return 0;
    }

    /**
     * Goods sold into the village become real simulation stock when recognized storage has room.
     */
    public static void acceptCompletedTrade(Villager villager, MerchantOffer offer) {
        if (!(villager.level() instanceof ServerLevel level)) return;
        ItemStack result = offer.getResult();
        ItemStack paid = offer.getCostA();

        if (result.is(Items.EMERALD) && !paid.is(Items.EMERALD)
                && category(paid.getItem()) != null) {
            VillageStorageService.insert(villager, level, paid.copy());
        }
    }

    public static String category(Item item) {
        if (item == Items.BREAD || item == Items.CARROT || item == Items.POTATO
                || item == Items.BEETROOT || item == Items.WHEAT) return "food";

        if (item == Items.OAK_LOG || item == Items.SPRUCE_LOG || item == Items.BIRCH_LOG
                || item == Items.JUNGLE_LOG || item == Items.ACACIA_LOG || item == Items.DARK_OAK_LOG
                || item == Items.MANGROVE_LOG || item == Items.CHERRY_LOG
                || item == Items.OAK_PLANKS || item == Items.SPRUCE_PLANKS || item == Items.BIRCH_PLANKS
                || item == Items.JUNGLE_PLANKS || item == Items.ACACIA_PLANKS || item == Items.DARK_OAK_PLANKS
                || item == Items.MANGROVE_PLANKS || item == Items.CHERRY_PLANKS) return "wood";

        if (item == Items.COBBLESTONE || item == Items.STONE || item == Items.ANDESITE
                || item == Items.DIORITE || item == Items.GRANITE || item == Items.STONE_BRICKS
                || item == Items.BRICKS) return "stone";

        if (item == Items.IRON_INGOT || item == Items.GOLD_INGOT || item == Items.COPPER_INGOT) return "metal";
        if (item == Items.WHEAT_SEEDS || item == Items.BEETROOT_SEEDS || item == Items.PUMPKIN_SEEDS
                || item == Items.MELON_SEEDS || item == Items.BONE_MEAL) return "farming";
        if (item == Items.COD || item == Items.SALMON || item == Items.TROPICAL_FISH || item == Items.PUFFERFISH) return "fishing";
        if (item == Items.CACTUS || item == Items.SNOW_BLOCK || item == Items.ICE
                || item == Items.PACKED_ICE || item == Items.RED_SAND || item == Items.TERRACOTTA) return "luxury";
        return null;
    }

    private static int effectivePermille(VillageSavedData.VillageRecord village, Item item, Villager villager) {
        String category = category(item);
        int market = category == null ? 1000 : village.marketPermille(category);
        int regional = regionalPermille(item, villager);
        return Mth.clamp((market * regional) / 1000, 800, 1800);
    }

    private static int regionalPermille(Item item, Villager villager) {
        String biome = villager.level().getBiome(villager.blockPosition())
                .unwrapKey().map(k -> k.location().getPath()).orElse("");
        boolean cold = biome.contains("snow") || biome.contains("frozen") || biome.contains("taiga");
        boolean dry = biome.contains("desert") || biome.contains("badlands") || biome.contains("savanna");

        if (cold && (item == Items.CACTUS || item == Items.SAND || item == Items.TERRACOTTA)) return 1150;
        if (dry && (item == Items.SNOW_BLOCK || item == Items.ICE || item == Items.SPRUCE_LOG)) return 1150;
        if (!cold && !dry && (item == Items.PACKED_ICE || item == Items.RED_SAND)) return 1150;
        return 1000;
    }

    private static int band(int stock, int target) {
        if (target <= 0) return 1000;
        double ratio = stock / (double)target;
        if (ratio >= 1.50D) return 800;
        if (ratio >= 1.00D) return 1000;
        if (ratio >= 0.60D) return 1150;
        if (ratio >= 0.30D) return 1350;
        return 1600;
    }

    private static int scoreCapacity(int capacity, int population) {
        if (population <= 0) return 100;
        return Mth.clamp((int)Math.round(capacity * 100.0D / population), 0, 100);
    }

    private static int loadedSafetyScore(ServerLevel level, UUID villageId, net.minecraft.core.BlockPos center) {
        List<Villager> villagers = level.getEntitiesOfClass(
                Villager.class,
                new net.minecraft.world.phys.AABB(center).inflate(128.0D, 64.0D, 128.0D),
                v -> v.isAlive() && VillagerSimData.villageId(v).filter(villageId::equals).isPresent()
        );
        if (villagers.isEmpty()) return 100;

        long now = level.getGameTime();
        int distressed = 0;
        for (Villager villager : villagers) {
            if (now < villager.getPersistentData().getLong("asobibatweaks_village_distress")) distressed++;
        }
        if (distressed == 0) return 100;

        double ratio = distressed / (double)villagers.size();
        if (ratio >= 0.50D) return 25;
        if (ratio >= 0.25D) return 50;
        return 70;
    }

    private static int averageLoadedWelfare(ServerLevel level, UUID villageId, net.minecraft.core.BlockPos center) {
        List<Villager> villagers = level.getEntitiesOfClass(
                Villager.class,
                new net.minecraft.world.phys.AABB(center).inflate(128.0D, 64.0D, 128.0D),
                v -> v.isAlive() && VillagerSimData.villageId(v).filter(villageId::equals).isPresent()
        );
        if (villagers.isEmpty()) return 100;
        int total = 0;
        for (Villager villager : villagers) total += VillagerSimData.welfare(villager);
        return Mth.clamp(Math.round(total / (float)villagers.size()), 0, 100);
    }

    private static int count(VillageSavedData.VillageRecord village, Item... items) {
        int total = 0;
        for (Item item : items) total += village.ledgerCount(VillageStorageService.itemKey(item));
        return total;
    }
}
