package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaRegistries;
import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.npc.VillagerProfession;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.Items;
import net.minecraft.world.phys.AABB;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;

/**
 * Village-level assignment of non-trading simulation duties.
 */
public final class VillageDutyScheduler {
    private static final long DUTY_REPLAN_TICKS = 24_000L;
    private static final long NON_EMERGENCY_DUTY_HOLD_TICKS = 24_000L;

    @SubscribeEvent
    public void onVillagerTick(EntityTickEvent.Post event) {
        if (!AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                || !AsobibaTweaksConfig.VILLAGE_LOGISTICS_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof Villager villager)
                || villager.level().isClientSide()
                || villager.isBaby()
                || villager.tickCount % 40 != Math.floorMod(villager.getId(), 40)) {
            return;
        }

        ServerLevel level = (ServerLevel)villager.level();
        VillageIdentityBootstrap.ensure(villager, level);
        VillagerSimData.villageId(villager).ifPresent(villageId -> scheduleVillage(level, villageId));
    }

    public static void ensureFormalDuty(Villager villager, long now) {
        VillagerProfession profession = villager.getVillagerData().getProfession();
        if (profession == AsobibaRegistries.CARPENTER.value()) {
            forceDuty(villager, "carpenter", now);
        } else if (profession == VillagerProfession.FARMER) {
            forceDuty(villager, "farmer", now);
        } else if (profession == VillagerProfession.FISHERMAN) {
            forceDuty(villager, "fisher", now);
        } else if (profession == VillagerProfession.SHEPHERD) {
            forceDuty(villager, "shepherd", now);
        } else if (profession == VillagerProfession.NITWIT || villager.isBaby()) {
            forceDuty(villager, "none", now);
        }
    }

    private static void scheduleVillage(ServerLevel level, UUID villageId) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null) return;

        long now = level.getGameTime();
        if (now < village.nextPlanningGameTime()) return;

        village.setNextPlanningGameTime(now + DUTY_REPLAN_TICKS);
        data.touch();
        VillageSimulationScheduler.enqueuePlanning(
                level,
                "duty_plan:" + villageId,
                () -> refreshVillage(level, villageId)
        );
    }

    private static void refreshVillage(ServerLevel level, UUID villageId) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null) return;

        AABB area = new AABB(village.center()).inflate(128.0D, 64.0D, 128.0D);
        List<Villager> loaded = level.getEntitiesOfClass(
                Villager.class,
                area,
                v -> v.isAlive()
                        && !v.isBaby()
                        && VillagerSimData.villageId(v).filter(villageId::equals).isPresent()
        );
        if (loaded.isEmpty()) return;

        long now = level.getGameTime();
        Map<UUID, String> desired = new HashMap<>();
        List<Villager> flexible = new ArrayList<>();

        for (Villager villager : loaded) {
            VillagerProfession profession = villager.getVillagerData().getProfession();
            if (profession == AsobibaRegistries.CARPENTER.value()) {
                desired.put(villager.getUUID(), "carpenter");
            } else if (profession == VillagerProfession.FARMER) {
                desired.put(villager.getUUID(), "farmer");
            } else if (profession == VillagerProfession.FISHERMAN) {
                desired.put(villager.getUUID(), "fisher");
            } else if (profession == VillagerProfession.SHEPHERD) {
                desired.put(villager.getUUID(), "shepherd");
            } else if (profession == VillagerProfession.NITWIT) {
                desired.put(villager.getUUID(), "none");
            } else {
                desired.put(villager.getUUID(), "none");
                flexible.add(villager);
            }
        }

        Set<UUID> claimed = new HashSet<>();

        // One coordinator is enough for most settlements. Prefer unemployed adults.
        choose(flexible, claimed, v -> v.getVillagerData().getProfession() == VillagerProfession.NONE, 1)
                .forEach(v -> {
                    desired.put(v.getUUID(), "quartermaster");
                    claimed.add(v.getUUID());
                });

        int wood = count(village,
                Items.OAK_LOG, Items.SPRUCE_LOG, Items.BIRCH_LOG, Items.JUNGLE_LOG,
                Items.ACACIA_LOG, Items.DARK_OAK_LOG, Items.MANGROVE_LOG, Items.CHERRY_LOG,
                Items.OAK_PLANKS, Items.SPRUCE_PLANKS, Items.BIRCH_PLANKS, Items.JUNGLE_PLANKS,
                Items.ACACIA_PLANKS, Items.DARK_OAK_PLANKS, Items.MANGROVE_PLANKS, Items.CHERRY_PLANKS);
        int stone = count(village, Items.COBBLESTONE, Items.STONE, Items.ANDESITE, Items.DIORITE, Items.GRANITE);

        int foresterTarget = wood < 64 ? 2 : wood < 192 ? 1 : 0;
        int quarryTarget = stone < 64 ? 2 : stone < 192 ? 1 : 0;

        chooseWithAffinity(flexible, claimed, VillagerProfession.FLETCHER, foresterTarget)
                .forEach(v -> {
                    desired.put(v.getUUID(), "forester");
                    claimed.add(v.getUUID());
                });
        chooseWithAffinity(flexible, claimed, VillagerProfession.MASON, quarryTarget)
                .forEach(v -> {
                    desired.put(v.getUUID(), "quarry");
                    claimed.add(v.getUUID());
                });

        int population = loaded.size();
        int porterCap = population < 16 ? 2 : population < 32 ? 4 : 8;
        int porterTarget = village.storageIds().size() > 1 || !village.projectIds().isEmpty()
                ? Math.min(porterCap, Math.max(1, population / 8))
                : 0;

        choose(flexible, claimed,
                v -> v.getVillagerData().getProfession() == VillagerProfession.NONE,
                porterTarget).forEach(v -> {
            desired.put(v.getUUID(), "porter");
            claimed.add(v.getUUID());
        });

        for (Villager villager : loaded) {
            String next = desired.getOrDefault(villager.getUUID(), "none");
            if (isFormal(next) || villager.getVillagerData().getProfession() == VillagerProfession.NITWIT) {
                forceDuty(villager, next, now);
            } else {
                setDutyWithHold(villager, next, now);
            }
        }
    }

    private static List<Villager> chooseWithAffinity(List<Villager> candidates, Set<UUID> claimed,
                                                      VillagerProfession affinity, int target) {
        if (target <= 0) return List.of();

        List<Villager> ordered = candidates.stream()
                .filter(v -> !claimed.contains(v.getUUID()))
                .sorted(Comparator
                        .comparingInt((Villager v) -> v.getVillagerData().getProfession() == affinity ? 0
                                : v.getVillagerData().getProfession() == VillagerProfession.NONE ? 1 : 2)
                        .thenComparing(v -> v.getUUID().toString()))
                .toList();

        List<Villager> result = new ArrayList<>();
        for (Villager villager : ordered) {
            VillagerProfession profession = villager.getVillagerData().getProfession();
            if (profession != affinity && profession != VillagerProfession.NONE) continue;
            result.add(villager);
            if (result.size() >= target) break;
        }
        return result;
    }

    private static List<Villager> choose(List<Villager> candidates, Set<UUID> claimed,
                                        java.util.function.Predicate<Villager> filter, int target) {
        if (target <= 0) return List.of();
        return candidates.stream()
                .filter(v -> !claimed.contains(v.getUUID()))
                .filter(filter)
                .sorted(Comparator.comparing(v -> v.getUUID().toString()))
                .limit(target)
                .toList();
    }

    private static void forceDuty(Villager villager, String duty, long now) {
        if (!duty.equals(VillagerSimData.duty(villager))) {
            VillagerSimData.setDuty(villager, duty, now);
        }
    }

    private static void setDutyWithHold(Villager villager, String duty, long now) {
        String current = VillagerSimData.duty(villager);
        if (current.equals(duty)) return;

        long assignedAt = VillagerSimData.dutyAssignedAt(villager);
        if (!"none".equals(current) && assignedAt > 0L && now - assignedAt < NON_EMERGENCY_DUTY_HOLD_TICKS) {
            return;
        }
        VillagerSimData.setDuty(villager, duty, now);
    }

    private static boolean isFormal(String duty) {
        return "carpenter".equals(duty)
                || "farmer".equals(duty)
                || "fisher".equals(duty)
                || "shepherd".equals(duty);
    }

    private static int count(VillageSavedData.VillageRecord village, Item... items) {
        int total = 0;
        for (Item item : items) {
            total += village.ledgerCount(VillageStorageService.itemKey(item));
        }
        return total;
    }
}
