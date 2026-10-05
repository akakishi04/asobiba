package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.FloatTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.NbtUtils;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Display;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.boss.enderdragon.EnderDragon;
import net.minecraft.world.entity.boss.wither.WitherBoss;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.monster.Slime;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.CropBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.EntityJoinLevelEvent;
import net.neoforged.neoforge.event.entity.living.LivingDropsEvent;
import net.neoforged.neoforge.event.level.BlockDropsEvent;
import net.neoforged.neoforge.event.level.block.CropGrowEvent;

public final class GiantOrganismEvents {
    private static final String GIANT_MOB = "asobibatweaks_giant_mob";
    private static final String GIANT_CROP = "asobibatweaks_giant_crop";
    private static final String GIANT_CROP_X = "asobibatweaks_giant_crop_x";
    private static final String GIANT_CROP_Y = "asobibatweaks_giant_crop_y";
    private static final String GIANT_CROP_Z = "asobibatweaks_giant_crop_z";

    @SubscribeEvent
    public void onEntityJoin(EntityJoinLevelEvent event) {
        if (!AsobibaTweaksConfig.GIANT_MOBS_ENABLED.getAsBoolean()
                || event.getLevel().isClientSide()
                || event.loadedFromDisk()
                || !(event.getEntity() instanceof Mob mob)
                || mob instanceof EnderDragon
                || mob instanceof WitherBoss
                || mob instanceof Slime
                || mob.getPersistentData().getBoolean(GIANT_MOB)) {
            return;
        }

        if (mob.getRandom().nextDouble() >= AsobibaTweaksConfig.GIANT_MOB_CHANCE.getAsDouble()) {
            return;
        }

        double scale = 1.45D + mob.getRandom().nextDouble() * 0.75D;
        var scaleAttribute = mob.getAttribute(Attributes.SCALE);
        if (scaleAttribute == null) return;

        scaleAttribute.setBaseValue(scale);
        mob.getPersistentData().putBoolean(GIANT_MOB, true);
        mob.getPersistentData().putDouble("asobibatweaks_giant_scale", scale);
        mob.setPersistenceRequired();

        var maxHealth = mob.getAttribute(Attributes.MAX_HEALTH);
        if (maxHealth != null) {
            maxHealth.setBaseValue(Math.min(maxHealth.getBaseValue() * (1.25D + (scale - 1.0D) * 0.35D), 2048.0D));
            mob.setHealth(mob.getMaxHealth());
        }

        var attack = mob.getAttribute(Attributes.ATTACK_DAMAGE);
        if (attack != null) {
            attack.setBaseValue(attack.getBaseValue() * (1.08D + (scale - 1.0D) * 0.18D));
        }

        var knockback = mob.getAttribute(Attributes.KNOCKBACK_RESISTANCE);
        if (knockback != null) {
            knockback.setBaseValue(Math.min(1.0D, knockback.getBaseValue() + 0.18D + (scale - 1.0D) * 0.16D));
        }

        var step = mob.getAttribute(Attributes.STEP_HEIGHT);
        if (step != null) {
            step.setBaseValue(Math.min(2.0D, step.getBaseValue() + (scale - 1.0D) * 0.45D));
        }

        var speed = mob.getAttribute(Attributes.MOVEMENT_SPEED);
        if (speed != null && scale > 1.75D) {
            speed.setBaseValue(speed.getBaseValue() * 0.94D);
        }
    }

    @SubscribeEvent
    public void onLivingDrops(LivingDropsEvent event) {
        if (!AsobibaTweaksConfig.GIANT_MOBS_ENABLED.getAsBoolean()
                || !event.getEntity().getPersistentData().getBoolean(GIANT_MOB)) {
            return;
        }

        List<ItemEntity> bonus = new ArrayList<>();
        for (ItemEntity drop : event.getDrops()) {
            if (drop.getItem().isEmpty()) continue;
            var copy = drop.getItem().copy();
            copy.setCount(Math.max(1, Math.min(copy.getMaxStackSize(), (copy.getCount() + 1) / 2)));
            ItemEntity extra = new ItemEntity(
                    drop.level(),
                    drop.getX() + (drop.getRandom().nextDouble() - 0.5D) * 0.25D,
                    drop.getY(),
                    drop.getZ() + (drop.getRandom().nextDouble() - 0.5D) * 0.25D,
                    copy
            );
            bonus.add(extra);
        }
        event.getDrops().addAll(bonus);
    }

    @SubscribeEvent
    public void onCropGrow(CropGrowEvent.Post event) {
        if (!AsobibaTweaksConfig.GIANT_CROPS_ENABLED.getAsBoolean()
                || !(event.getLevel() instanceof ServerLevel level)
                || !(event.getState().getBlock() instanceof CropBlock crop)
                || !crop.isMaxAge(event.getState())
                || level.random.nextDouble() >= AsobibaTweaksConfig.GIANT_CROP_CHANCE.getAsDouble()
                || hasGiantDisplay(level, event.getPos())) {
            return;
        }

        spawnGiantCropDisplay(level, event.getPos(), event.getState());
    }

    @SubscribeEvent
    public void onBlockDrops(BlockDropsEvent event) {
        if (!AsobibaTweaksConfig.GIANT_CROPS_ENABLED.getAsBoolean()) return;

        Display.BlockDisplay display = findGiantDisplay(event.getLevel(), event.getPos());
        if (display == null) return;

        List<ItemEntity> extra = new ArrayList<>();
        for (ItemEntity drop : event.getDrops()) {
            if (drop.getItem().isEmpty()) continue;
            var copy = drop.getItem().copy();
            copy.setCount(Math.max(1, Math.min(copy.getMaxStackSize(), copy.getCount())));
            extra.add(new ItemEntity(event.getLevel(), drop.getX(), drop.getY(), drop.getZ(), copy));
        }
        event.getDrops().addAll(extra);
        display.discard();
    }

    private static void spawnGiantCropDisplay(ServerLevel level, BlockPos pos, BlockState state) {
        CompoundTag tag = new CompoundTag();
        tag.putString("id", "minecraft:block_display");
        tag.put("block_state", NbtUtils.writeBlockState(state));

        CompoundTag transform = new CompoundTag();
        transform.put("translation", floats(-0.34F, 0.0F, -0.34F));
        transform.put("left_rotation", floats(0.0F, 0.0F, 0.0F, 1.0F));
        transform.put("scale", floats(1.68F, 1.38F, 1.68F));
        transform.put("right_rotation", floats(0.0F, 0.0F, 0.0F, 1.0F));
        tag.put("transformation", transform);
        tag.putFloat("view_range", 0.75F);
        tag.putFloat("shadow_radius", 0.0F);

        Entity entity = EntityType.loadEntityRecursive(tag, level, e -> e);
        if (!(entity instanceof Display.BlockDisplay display)) return;

        display.setPos(pos.getX(), pos.getY(), pos.getZ());
        display.getPersistentData().putBoolean(GIANT_CROP, true);
        display.getPersistentData().putInt(GIANT_CROP_X, pos.getX());
        display.getPersistentData().putInt(GIANT_CROP_Y, pos.getY());
        display.getPersistentData().putInt(GIANT_CROP_Z, pos.getZ());
        level.addFreshEntity(display);
    }

    private static boolean hasGiantDisplay(ServerLevel level, BlockPos pos) {
        return findGiantDisplay(level, pos) != null;
    }

    private static Display.BlockDisplay findGiantDisplay(Level level, BlockPos pos) {
        AABB bounds = new AABB(pos).inflate(1.0D);
        for (Display.BlockDisplay display : level.getEntitiesOfClass(
                Display.BlockDisplay.class,
                bounds,
                d -> d.getPersistentData().getBoolean(GIANT_CROP))) {
            CompoundTag data = display.getPersistentData();
            if (data.getInt(GIANT_CROP_X) == pos.getX()
                    && data.getInt(GIANT_CROP_Y) == pos.getY()
                    && data.getInt(GIANT_CROP_Z) == pos.getZ()) {
                return display;
            }
        }
        return null;
    }

    private static ListTag floats(float... values) {
        ListTag list = new ListTag();
        for (float value : values) list.add(FloatTag.valueOf(value));
        return list;
    }
}
