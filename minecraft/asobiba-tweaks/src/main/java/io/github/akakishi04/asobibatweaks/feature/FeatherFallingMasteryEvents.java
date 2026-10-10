package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.tags.DamageTypeTags;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.enchantment.EnchantmentHelper;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.common.damagesource.DamageContainer;
import net.neoforged.neoforge.event.entity.living.LivingDamageEvent;
import net.neoforged.neoforge.event.entity.living.LivingFallEvent;

/** Each equipped specialization uses its strongest item, never summed mastery. */
public final class FeatherFallingMasteryEvents {
    private static final String ENCHANTMENT = "minecraft:feather_falling";
    private static final String FALL_DISTANCE = "asobibatweaks_feather_landing_distance";
    private static final String FALL_TIME = "asobibatweaks_feather_landing_time";

    @SubscribeEvent
    public void onFall(LivingFallEvent event) {
        if (!(event.getEntity() instanceof ServerPlayer player) || event.isCanceled()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) return;
        player.getPersistentData().putFloat(FALL_DISTANCE, event.getDistance());
        player.getPersistentData().putLong(FALL_TIME, player.level().getGameTime());
    }

    @SubscribeEvent
    public void onFallDamage(LivingDamageEvent.Pre event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || !(player.level() instanceof ServerLevel level)
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || !event.getSource().is(DamageTypeTags.IS_FALL)
                || event.getSource().is(DamageTypeTags.BYPASSES_ENCHANTMENTS)) return;

        int soft = strongestMastery(player.getArmorSlots(), 0);
        if (soft >= 50 && event.getNewDamage() > 0.0F)
            event.setNewDamage((float)(event.getNewDamage() * (1.0D - softReduction(soft))));

        var state = player.getPersistentData();
        float fall = state.getFloat(FALL_DISTANCE);
        boolean sameLanding = state.contains(FALL_TIME)
                && state.getLong(FALL_TIME) == level.getGameTime();
        state.remove(FALL_DISTANCE);
        state.remove(FALL_TIME);
        int impact = strongestMastery(player.getArmorSlots(), 1);
        if (!sameLanding || fall < 5.0F || impact < 50) return;

        // Attribute only the marginal enchantment reduction due to ordinary
        // Feather Falling. Protection/custom enchantments do not become free
        // impact power; the shared vanilla 20-point protection cap still applies.
        float enchantmentPrevented = event.getContainer().getReduction(DamageContainer.Reduction.ENCHANTMENTS);
        float totalProtection = EnchantmentHelper.getDamageProtection(level, player, event.getSource());
        double featherProtection = 0.0D;
        for (ItemStack armor : player.getArmorSlots())
            featherProtection += 3.0D * EnchantedArrowImpactEvents.level(armor, ENCHANTMENT);
        double prevented = attributablePrevention(enchantmentPrevented, totalProtection, featherProtection);
        float damage = (float)impactDamage(prevented, impact);
        if (damage <= 0.0F) return;
        double radius = impactRadius(impact);
        for (LivingEntity target : level.getEntitiesOfClass(LivingEntity.class,
                player.getBoundingBox().inflate(radius), candidate -> candidate != player
                    && candidate.isAlive() && !(candidate instanceof Player)
                    && !candidate.isAlliedTo(player)
                    && candidate.distanceToSqr(player) <= radius * radius)) {
            // Attribute the shock to its wearer without masquerading as a
            // direct weapon strike (and retriggering unrelated melee mastery).
            target.hurt(level.damageSources().indirectMagic(null, player), damage);
        }
    }

    /** Called at vanilla input acceleration, on both simulation sides. */
    public static float aerialInputSpeed(Player player, float vanilla) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || vanilla <= 0.0F || player.onGround() || player.getDeltaMovement().y >= -0.01D
                || player.isInWater() || player.isInLava() || player.onClimbable()
                || player.isFallFlying() || player.isAutoSpinAttack() || player.isPassenger()
                || player.getAbilities().flying || player.isSpectator()) return vanilla;
        int mastery = strongestMastery(player.getArmorSlots(), 2);
        return mastery < 50 ? vanilla : (float)(vanilla * (1.10D + 0.25D * progress(mastery)));
    }

    static int strongestMastery(Iterable<ItemStack> armor, int wantedBranch) {
        int highest = -1;
        for (ItemStack stack : armor) {
            for (var holder : EnchantmentMasteryData.enchantments(stack).keySet()) {
                if (!ENCHANTMENT.equals(EnchantmentMasteryData.id(holder))
                        || EnchantmentMasteryData.getBranch(stack, holder) != wantedBranch) continue;
                int mastery = EnchantmentMasteryData.getMastery(stack, holder);
                if (mastery >= 50) highest = Math.max(highest, Math.min(100, mastery));
            }
        }
        return highest;
    }

    static double softReduction(int mastery) { return 0.10D + 0.20D * progress(mastery); }
    static double impactRadius(int mastery) { return 2.0D + 2.0D * progress(mastery); }
    static double impactDamage(double prevented, int mastery) {
        return Math.min(6.0D, Math.max(0.0D, prevented) * (0.10D + 0.15D * progress(mastery)));
    }
    static double attributablePrevention(double reduction, double total, double feather) {
        double capped = Math.min(20.0D, Math.max(0.0D, total));
        double without = Math.min(20.0D, Math.max(0.0D, total - feather));
        return capped <= 0.0D ? 0.0D : Math.max(0.0D, reduction) * Math.max(0.0D, capped - without) / capped;
    }
    private static double progress(int mastery) {
        return Math.max(0.0D, Math.min(1.0D, (mastery - 50) / 50.0D));
    }
}
