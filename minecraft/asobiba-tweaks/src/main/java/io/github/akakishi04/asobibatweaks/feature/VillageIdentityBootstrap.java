package io.github.akakishi04.asobibatweaks.feature;

import java.util.Comparator;
import java.util.Optional;
import java.util.UUID;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.phys.AABB;

/**
 * Conservative V1 bootstrap from vanilla village membership into stable Asobiba village IDs.
 *
 * <p>This is intentionally not the final dynamic-boundary/merge algorithm. It only establishes
 * durable identity for loaded vanilla-village residents so later passes have stable records to
 * reconcile. Existing IDs are never cleared merely because a villager temporarily leaves a
 * vanilla village.</p>
 */
public final class VillageIdentityBootstrap {
    private static final double ADOPTION_RADIUS = 48.0D;

    private VillageIdentityBootstrap() {
    }

    public static Optional<UUID> ensure(Villager villager, ServerLevel level) {
        VillagerSimData.ensureInitialized(villager);
        VillageSavedData data = VillageSavedData.get(level);

        Optional<UUID> existingId = VillagerSimData.villageId(villager);
        if (existingId.isPresent()) {
            UUID id = existingId.get();
            VillageSavedData.VillageRecord existing = data.village(id).orElse(null);
            if (existing != null) {
                if ("merged".equals(existing.lifecycle()) && existing.mergedIntoVillageId() != null
                        && data.village(existing.mergedIntoVillageId()).isPresent()) {
                    UUID redirected = existing.mergedIntoVillageId();
                    VillagerSimData.setVillageId(villager, redirected);
                    data.registerResident(redirected, villager.getUUID());
                    return Optional.of(redirected);
                }
                data.registerResident(id, villager.getUUID());
                return existingId;
            }

            // Preserve the villager-carried ID, but only reconstruct a missing shared record when
            // the entity is currently inside vanilla-recognized village space. A transported
            // villager must not create a phantom settlement at an arbitrary temporary location.
            if (level.isVillage(villager.blockPosition())) {
                data.ensureVillage(id, villager.blockPosition(), level.getGameTime());
                data.registerResident(id, villager.getUUID());
                return existingId;
            }
            return Optional.empty();
        }

        // Do not assign a permanent settlement ID to wandering/transported unassigned villagers.
        if (!level.isVillage(villager.blockPosition())) {
            return Optional.empty();
        }

        Optional<UUID> nearby = level.getEntitiesOfClass(
                        Villager.class,
                        new AABB(villager.blockPosition()).inflate(ADOPTION_RADIUS),
                        other -> other != villager
                                && level.isVillage(other.blockPosition())
                                && VillagerSimData.villageId(other).isPresent()
                ).stream()
                .sorted(Comparator.comparingDouble(villager::distanceToSqr))
                .map(VillagerSimData::villageId)
                .flatMap(Optional::stream)
                .filter(id -> data.village(id).isPresent())
                .findFirst();

        UUID id = nearby.orElseGet(() -> data.createVillage(villager.blockPosition(), level.getGameTime()).id());
        VillagerSimData.setVillageId(villager, id);
        data.registerResident(id, villager.getUUID());
        return Optional.of(id);
    }
}
