package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.EnumMap;
import java.util.Map;
import java.util.WeakHashMap;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.GameRules;
import net.neoforged.bus.api.EventPriority;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.living.LivingDeathEvent;
import net.neoforged.neoforge.event.entity.living.LivingEquipmentChangeEvent;
import net.neoforged.neoforge.event.entity.player.PlayerEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

/**
 * Both vanilla curses retain their ordinary behavior; selected branches
 * add sidegrades without creating a second copy on death or re-equipping.
 */
public final class CurseMasteryEvents {
    private static final Map<ServerPlayer, EnumMap<EquipmentSlot, Wear>> WEAR =
            new WeakHashMap<>();
    private static final EquipmentSlot[] ARMOR = {
            EquipmentSlot.HEAD, EquipmentSlot.CHEST,
            EquipmentSlot.LEGS, EquipmentSlot.FEET
    };

    private static LauncherReloadMasteryEvents.Branch branch(ItemStack stack, String id) {
        return LauncherReloadMasteryEvents.branch(stack, id);
    }

    @SubscribeEvent
    public void onPlayerTick(PlayerTickEvent.Post event) {
        if (!(event.getEntity() instanceof ServerPlayer player)) return;
        long now = player.level().getGameTime();

        if (AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) {
            EnumMap<EquipmentSlot, Wear> slots =
                    WEAR.computeIfAbsent(player, p -> new EnumMap<>(EquipmentSlot.class));
            for (EquipmentSlot slot : ARMOR) {
                ItemStack equipped = player.getItemBySlot(slot);
                Wear previous = slots.get(slot);
                if (equipped.isEmpty()
                        || branch(equipped, "minecraft:binding_curse") == null) {
                    slots.remove(slot);
                } else if (previous == null || previous.item() != equipped
                        || now < previous.since()) {
                    slots.put(slot, new Wear(equipped, now));
                }
            }
        }

        if (player.tickCount % 20 == 0) {
            CurseLegacySavedData data = CurseLegacySavedData.get(player.serverLevel());
            data.deliverDue(player, now);
            data.renderNearbyEchoes(player, now);
        }
    }

    /**
     * Called after vanilla Unbreaking/mastery and Mending over-repair
     * already handled the same durability event.
     */
    public static int preserveBoundDurability(ItemStack item,
                                               LivingEntity user, int durability) {
        if (!(user instanceof ServerPlayer player) || durability <= 0
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) {
            return durability;
        }
        var branch = branch(item, "minecraft:binding_curse");
        if (branch == null || branch.choice() != 1) return durability;

        var slotMap = WEAR.get(player);
        if (slotMap == null) return durability;
        long now = player.level().getGameTime();
        boolean matured = false;
        long neededTicks = (long)Math.round(
                20.0D * 60.0D * (20.0D - 10.0D * branch.progress()));
        for (EquipmentSlot slot : ARMOR) {
            Wear state = slotMap.get(slot);
            if (state != null && state.item() == item
                    && now >= state.since() && now - state.since() >= neededTicks) {
                matured = true;
                break;
            }
        }
        if (!matured) return durability;

        double preservation = 0.05D + 0.10D * branch.progress();
        int saved = 0;
        for (int i = 0; i < Math.min(256, durability); i++) {
            if (player.getRandom().nextDouble() < preservation) saved++;
        }
        return Math.max(0, durability - saved);
    }

    @SubscribeEvent
    public void onEquipChanged(LivingEquipmentChangeEvent event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || event.getTo().isEmpty()) return;

        CurseLegacySavedData.get(player.serverLevel()).applyLegacy(player, event.getTo());
        // Vanilla Binding already prevents normal voluntary removal.
        // Forced Attachment should not clone a forcibly moved item:
        // when another mod moves it outside the player's inventory,
        // safe recovery requires that external mod's earlier API.
    }

    @SubscribeEvent(priority = EventPriority.LOWEST)
    public void onDeath(LivingDeathEvent event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || event.isCanceled()
                || player.level().getGameRules().getBoolean(GameRules.RULE_KEEPINVENTORY)
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) return;

        long now = player.level().getGameTime();
        var records = CurseLegacySavedData.get(player.serverLevel());

        for (EquipmentSlot slot : ARMOR) {
            ItemStack item = player.getItemBySlot(slot);
            var bound = branch(item, "minecraft:binding_curse");
            if (bound == null || bound.choice() != 0) continue;
            double chance = 0.25D + 0.50D * bound.progress();
            if (player.getRandom().nextDouble() >= chance) continue;

            // Take possession of the ONE real ItemStack before vanilla
            // drops run. This is not a duplicate inventory copy.
            ItemStack removed = item.copy();
            player.setItemSlot(slot, ItemStack.EMPTY);
            records.addReturn(player.getUUID(), removed, slot.getName(), now);
        }

        for (int i = 0; i < player.getInventory().getContainerSize(); i++) {
            ItemStack item = player.getInventory().getItem(i);
            var vanishing = branch(item, "minecraft:vanishing_curse");
            if (vanishing == null) continue;
            double strength = vanishing.progress();

            if (vanishing.choice() == 0
                    && player.getRandom().nextDouble() < 0.10D + 0.20D * strength) {
                ItemStack removed = item.copy();
                player.getInventory().setItem(i, ItemStack.EMPTY);
                long delay = Math.round(20.0D * 60.0D * (20.0D - 15.0D * strength));
                records.addReturn(player.getUUID(), removed, "", now + delay);
            } else if (vanishing.choice() == 1) {
                long duration = Math.round(20.0D * (60.0D + 240.0D * strength));
                records.addEcho(player.getUUID(),
                        player.level().dimension().location().toString(),
                        player.blockPosition(), now + duration);
            } else if (vanishing.choice() == 2) {
                CompoundTag inherited = new CompoundTag();
                for (var enchanted : EnchantmentMasteryData.enchantments(item).keySet()) {
                    int history = EnchantmentMasteryData.getMastery(item, enchanted);
                    int portion = (int)Math.floor(history * (0.15D + 0.25D * strength));
                    if (portion > 0) inherited.putInt(
                            EnchantmentMasteryData.id(enchanted), portion);
                }
                String itemId = net.minecraft.core.registries.BuiltInRegistries.ITEM
                        .getKey(item.getItem()).toString();
                records.addLegacy(player.getUUID(), itemId, inherited);
            }
        }
        WEAR.remove(player);
    }

    @SubscribeEvent
    public void onRespawn(PlayerEvent.PlayerRespawnEvent event) {
        if (event.getEntity() instanceof ServerPlayer player) {
            CurseLegacySavedData.get(player.serverLevel()).deliverDue(
                    player, player.level().getGameTime());
        }
    }

    @SubscribeEvent
    public void onLoggedOut(PlayerEvent.PlayerLoggedOutEvent event) {
        if (event.getEntity() instanceof ServerPlayer player) WEAR.remove(player);
    }

    private record Wear(ItemStack item, long since) {}
}
