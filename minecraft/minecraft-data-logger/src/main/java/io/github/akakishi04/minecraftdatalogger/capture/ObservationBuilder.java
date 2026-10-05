package io.github.akakishi04.minecraftdatalogger.capture;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import io.github.akakishi04.minecraftdatalogger.LoggerConfig;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.phys.Vec3;

public final class ObservationBuilder {
    private ObservationBuilder() {
    }

    public static JsonObject build(PlayerLogSession session, ServerPlayer player) {
        JsonObject root = base(session, player, "observation");

        Vec3 velocity = player.getDeltaMovement();

        JsonObject position = new JsonObject();
        position.addProperty("x", player.getX());
        position.addProperty("y", player.getY());
        position.addProperty("z", player.getZ());
        root.add("position", position);

        JsonObject motion = new JsonObject();
        motion.addProperty("x", velocity.x);
        motion.addProperty("y", velocity.y);
        motion.addProperty("z", velocity.z);
        root.add("velocity", motion);

        root.addProperty("yaw", player.getYRot());
        root.addProperty("pitch", player.getXRot());
        root.addProperty("health", player.getHealth());
        root.addProperty("food", player.getFoodData().getFoodLevel());
        root.addProperty("on_ground", player.onGround());
        root.addProperty("dimension", player.level().dimension().location().toString());

        root.add("main_hand", stack(player.getMainHandItem()));
        root.add("off_hand", stack(player.getOffhandItem()));

        if (LoggerConfig.CAPTURE_INVENTORY.getAsBoolean()) {
            JsonArray inventory = new JsonArray();
            for (int slot = 0; slot < player.getInventory().getContainerSize(); slot++) {
                ItemStack item = player.getInventory().getItem(slot);
                if (item.isEmpty()) {
                    continue;
                }
                JsonObject entry = stack(item);
                entry.addProperty("slot", slot);
                inventory.add(entry);
            }
            root.add("inventory", inventory);
        }

        return root;
    }

    public static JsonObject base(PlayerLogSession session, ServerPlayer player, String type) {
        JsonObject root = new JsonObject();
        root.addProperty("schema_version", PlayerLogSession.SCHEMA_VERSION);
        root.addProperty("session_id", session.sessionId());
        root.addProperty("sequence", session.nextSequence());
        root.addProperty("record_type", type);
        root.addProperty("game_tick", player.level().getGameTime());
        root.addProperty("player_uuid", player.getUUID().toString());
        return root;
    }

    public static JsonObject stack(ItemStack stack) {
        JsonObject object = new JsonObject();
        if (stack.isEmpty()) {
            object.addProperty("item", "minecraft:air");
            object.addProperty("count", 0);
            return object;
        }

        object.addProperty("item", BuiltInRegistries.ITEM.getKey(stack.getItem()).toString());
        object.addProperty("count", stack.getCount());
        if (stack.isDamageableItem()) {
            object.addProperty("damage", stack.getDamageValue());
            object.addProperty("max_damage", stack.getMaxDamage());
        }
        return object;
    }
}
