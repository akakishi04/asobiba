package io.github.akakishi04.asobibatweaks.feature;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.HolderLookup;
import net.minecraft.core.registries.Registries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.util.datafix.DataFixTypes;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.saveddata.SavedData;

/**
 * Server-persistent, consumable claims for curse-related death behavior.
 * Claims are removed from the SavedData before they are delivered, so a
 * respawn callback and a player tick never mint duplicate copies.
 *
 * This is stored in the overworld rather than on the old player entity:
 * death-cloning must not erase pending returns or mastery inheritance.
 */
public final class CurseLegacySavedData extends SavedData {
    private static final String NAME = "asobibatweaks_curse_legacy_v1";
    private static final int MAX_RECORDS = 1024;
    private static final Factory<CurseLegacySavedData> FACTORY =
            new Factory<>(CurseLegacySavedData::new, CurseLegacySavedData::load,
                    DataFixTypes.SAVED_DATA_RANDOM_SEQUENCES);

    private final List<Claim> claims = new ArrayList<>();

    public static CurseLegacySavedData get(ServerLevel world) {
        ServerLevel overworld = world.getServer().getLevel(Level.OVERWORLD);
        return (overworld == null ? world : overworld)
                .getDataStorage().computeIfAbsent(FACTORY, NAME);
    }

    public boolean addReturn(UUID owner, ItemStack item, String slot, long due) {
        if (item.isEmpty() || claims.size() >= MAX_RECORDS) return false;
        claims.add(new Claim(owner, "return", item.copy(), slot,
                due, "", "", 0L, new CompoundTag()));
        setDirty();
        return true;
    }

    public void addEcho(UUID owner, String dimension, BlockPos position, long expiry) {
        if (claims.size() >= MAX_RECORDS) return;
        claims.add(new Claim(owner, "echo", ItemStack.EMPTY, "", expiry,
                "", dimension, position.asLong(), new CompoundTag()));
        setDirty();
    }

    public void addLegacy(UUID owner, String itemId, CompoundTag inheritedMastery) {
        if (inheritedMastery.isEmpty() || claims.size() >= MAX_RECORDS) return;
        claims.add(new Claim(owner, "legacy", ItemStack.EMPTY, "", 0L,
                itemId, "", 0L, inheritedMastery.copy()));
        setDirty();
    }

    public void deliverDue(ServerPlayer owner, long now) {
        for (Iterator<Claim> iterator = claims.iterator(); iterator.hasNext();) {
            Claim claim = iterator.next();
            if (!"return".equals(claim.kind()) || !owner.getUUID().equals(claim.owner())
                    || now < claim.due()) continue;

            // Consume the claim before materializing an item. A callback that
            // re-enters the tick or respawn flow cannot repeat it.
            iterator.remove();
            setDirty();

            ItemStack returned = claim.item().copy();
            boolean equipped = false;
            if (!claim.slot().isBlank()) {
                for (EquipmentSlot slot : EquipmentSlot.values()) {
                    if (slot.getName().equals(claim.slot())
                            && owner.getItemBySlot(slot).isEmpty()) {
                        owner.setItemSlot(slot, returned);
                        equipped = true;
                        break;
                    }
                }
            }
            if (!equipped) {
                owner.getInventory().add(returned);
                if (!returned.isEmpty()) owner.drop(returned, false);
            }
        }
    }

    /** Called when an actual replacement is equipped, not simply picked up. */
    public void applyLegacy(ServerPlayer owner, ItemStack replacement) {
        if (replacement.isEmpty()) return;
        String itemId = net.minecraft.core.registries.BuiltInRegistries.ITEM
                .getKey(replacement.getItem()).toString();
        for (Iterator<Claim> iterator = claims.iterator(); iterator.hasNext();) {
            Claim claim = iterator.next();
            if (!"legacy".equals(claim.kind()) || !owner.getUUID().equals(claim.owner())
                    || !itemId.equals(claim.itemId())) continue;

            boolean received = false;
            for (var enchantment : EnchantmentMasteryData.enchantments(replacement).keySet()) {
                int gain = claim.mastery().getInt(EnchantmentMasteryData.id(enchantment));
                if (gain > 0) {
                    EnchantmentMasteryData.addMastery(replacement, enchantment, gain);
                    received = true;
                }
            }
            if (received) {
                iterator.remove();
                setDirty();
                owner.displayClientMessage(
                        net.minecraft.network.chat.Component.literal(
                                "A vanished item's mastery has passed to its successor."), true);
            }
            return;
        }
    }

    public void renderNearbyEchoes(ServerPlayer owner, long now) {
        for (Iterator<Claim> iterator = claims.iterator(); iterator.hasNext();) {
            Claim claim = iterator.next();
            if (!"echo".equals(claim.kind())) continue;
            if (now > claim.due()) {
                iterator.remove();
                setDirty();
                continue;
            }

            ResourceLocation id = ResourceLocation.tryParse(claim.dimension());
            if (id == null || !owner.level().dimension().location().equals(id)) continue;
            BlockPos position = BlockPos.of(claim.position());
            if (!owner.level().hasChunkAt(position)
                    || owner.distanceToSqr(position.getCenter()) > 40.0D * 40.0D) continue;

            owner.serverLevel().sendParticles(
                    net.minecraft.core.particles.ParticleTypes.SOUL,
                    position.getX() + 0.5D, position.getY() + 0.7D, position.getZ() + 0.5D,
                    5, 0.4D, 0.8D, 0.4D, 0.01D);
        }
    }

    public static CurseLegacySavedData load(CompoundTag tag, HolderLookup.Provider registries) {
        CurseLegacySavedData result = new CurseLegacySavedData();
        ListTag entries = tag.getList("claims", Tag.TAG_COMPOUND);
        for (int i = 0; i < Math.min(MAX_RECORDS, entries.size()); i++) {
            CompoundTag row = entries.getCompound(i);
            if (!row.hasUUID("owner")) continue;
            String kind = row.getString("kind");
            if (!kind.equals("return") && !kind.equals("echo") && !kind.equals("legacy")) continue;
            ItemStack item = ItemStack.parseOptional(registries, row.getCompound("item"));
            result.claims.add(new Claim(row.getUUID("owner"), kind, item,
                    row.getString("slot"), row.getLong("due"), row.getString("itemId"),
                    row.getString("dimension"), row.getLong("position"),
                    row.getCompound("mastery").copy()));
        }
        return result;
    }

    @Override
    public CompoundTag save(CompoundTag tag, HolderLookup.Provider registries) {
        ListTag list = new ListTag();
        for (Claim claim : claims) {
            CompoundTag row = new CompoundTag();
            row.putUUID("owner", claim.owner());
            row.putString("kind", claim.kind());
            if (!claim.item().isEmpty()) {
                row.put("item", claim.item().saveOptional(registries));
            }
            row.putString("slot", claim.slot());
            row.putLong("due", claim.due());
            row.putString("itemId", claim.itemId());
            row.putString("dimension", claim.dimension());
            row.putLong("position", claim.position());
            row.put("mastery", claim.mastery());
            list.add(row);
        }
        tag.put("claims", list);
        return tag;
    }

    private record Claim(UUID owner, String kind, ItemStack item,
                         String slot, long due, String itemId, String dimension,
                         long position, CompoundTag mastery) {}
}
