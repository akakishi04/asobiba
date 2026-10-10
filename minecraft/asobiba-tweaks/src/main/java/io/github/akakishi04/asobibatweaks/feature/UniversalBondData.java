package io.github.akakishi04.asobibatweaks.feature;

import java.util.UUID;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.animal.Animal;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;

public final class UniversalBondData {
    private static final String BOND_KEY = "asobibatweaks_bond";
    private static final String CANDIDATE_KEY = "asobibatweaks_bond_candidate";
    private static final String OWNER_KEY = "asobibatweaks_bond_owner";
    private static final String STAY_KEY = "asobibatweaks_bond_stay";

    private UniversalBondData() {
    }

    public static int getBond(Mob mob) {
        return mob.getPersistentData().getInt(BOND_KEY);
    }

    public static void setBond(Mob mob, int bond) {
        mob.getPersistentData().putInt(BOND_KEY, Math.max(0, Math.min(100, bond)));
    }

    public static boolean isBonded(Mob mob) {
        return !mob.getPersistentData().getString(OWNER_KEY).isEmpty();
    }

    public static boolean isOwner(Mob mob, UUID playerId) {
        return playerId.toString().equals(mob.getPersistentData().getString(OWNER_KEY));
    }

    public static String candidate(Mob mob) {
        return mob.getPersistentData().getString(CANDIDATE_KEY);
    }

    public static void setCandidate(Mob mob, UUID playerId) {
        mob.getPersistentData().putString(CANDIDATE_KEY, playerId.toString());
    }

    public static void completeBond(Mob mob, UUID playerId) {
        CompoundTag tag = mob.getPersistentData();
        tag.putString(OWNER_KEY, playerId.toString());
        tag.remove(CANDIDATE_KEY);
        tag.putInt(BOND_KEY, 100);
        tag.putBoolean(STAY_KEY, false);
        mob.setPersistenceRequired();
    }

    public static boolean isStay(Mob mob) {
        return mob.getPersistentData().getBoolean(STAY_KEY);
    }

    public static boolean toggleStay(Mob mob) {
        boolean next = !isStay(mob);
        mob.getPersistentData().putBoolean(STAY_KEY, next);
        return next;
    }

    public static boolean isBoss(Mob mob) {
        return mob.getType() == EntityType.ENDER_DRAGON || mob.getType() == EntityType.WITHER;
    }

    public static boolean isBondingGift(Mob mob, ItemStack stack) {
        if (stack.isEmpty()) {
            return false;
        }

        if (mob instanceof Animal animal && animal.isFood(stack)) {
            return true;
        }

        String path = BuiltInRegistries.ENTITY_TYPE.getKey(mob.getType()).getPath();

        if (path.contains("zombie") || path.equals("husk") || path.equals("drowned")) return stack.is(Items.ROTTEN_FLESH);
        if (path.contains("skeleton")) return stack.is(Items.BONE);
        if (path.contains("creeper")) return stack.is(Items.GUNPOWDER);
        if (path.contains("spider")) return stack.is(Items.STRING);
        if (path.contains("enderman")) return stack.is(Items.ENDER_PEARL);
        if (path.contains("piglin")) return stack.is(Items.GOLD_INGOT);
        if (path.equals("slime")) return stack.is(Items.SLIME_BALL);
        if (path.equals("magma_cube")) return stack.is(Items.MAGMA_CREAM);
        if (path.equals("blaze")) return stack.is(Items.BLAZE_POWDER);
        if (path.equals("ghast")) return stack.is(Items.GHAST_TEAR);
        if (path.contains("guardian")) return stack.is(Items.PRISMARINE_SHARD);
        if (path.equals("witch")) return stack.is(Items.GLASS_BOTTLE);
        if (path.equals("phantom")) return stack.is(Items.PHANTOM_MEMBRANE);
        if (path.equals("allay")) return stack.is(Items.AMETHYST_SHARD);
        if (path.equals("iron_golem")) return stack.is(Items.IRON_INGOT);
        if (path.equals("snow_golem")) return stack.is(Items.SNOWBALL);
        if (path.equals("bat")) return stack.is(Items.SWEET_BERRIES);

        return stack.is(Items.EMERALD);
    }
}
