package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.Holder;
import net.minecraft.core.Registry;
import net.minecraft.resources.ResourceKey;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.tags.BlockTags;
import net.minecraft.tags.DamageTypeTags;
import net.minecraft.tags.EntityTypeTags;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.damagesource.DamageTypes;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.item.enchantment.EnchantmentHelper;
import net.minecraft.world.item.enchantment.ItemEnchantments;
import net.minecraft.world.level.block.Blocks;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.common.Tags;
import net.neoforged.neoforge.event.AnvilUpdateEvent;
import net.neoforged.neoforge.event.VanillaGameEvent;
import net.neoforged.neoforge.event.entity.living.LivingDamageEvent;
import net.neoforged.neoforge.event.entity.living.LivingDeathEvent;
import net.neoforged.neoforge.event.entity.living.LivingDropsEvent;
import net.neoforged.neoforge.event.entity.living.LivingHealEvent;
import net.neoforged.neoforge.event.entity.living.LivingIncomingDamageEvent;
import net.neoforged.neoforge.event.entity.living.LivingKnockBackEvent;
import net.neoforged.neoforge.event.entity.living.LivingShieldBlockEvent;
import net.neoforged.neoforge.event.entity.living.LivingFallEvent;
import net.neoforged.neoforge.event.entity.player.AnvilRepairEvent;
import net.neoforged.neoforge.event.entity.player.ItemTooltipEvent;
import net.neoforged.neoforge.event.entity.player.PlayerEvent;
import net.neoforged.neoforge.event.level.BlockDropsEvent;
import net.neoforged.neoforge.event.level.BlockEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

public final class EnchantmentTweaksEvents {
    private static final int BRANCH_THRESHOLD = 50;
    private static final String UNBREAKING = "minecraft:unbreaking";
    private static final String INFINITY = "minecraft:infinity";
    private static final String POWER = "minecraft:power";
    private static final String LOYALTY = "minecraft:loyalty";
    private static final String FORTUNE = "minecraft:fortune";
    private static final String SILK_TOUCH = "minecraft:silk_touch";
    private static final String RESPIRATION = "minecraft:respiration";
    private static final String PROTECTION = "minecraft:protection";
    private static final String PROJECTILE_PROTECTION = "minecraft:projectile_protection";
    private static final String SHARPNESS = "minecraft:sharpness";
    private static final String SMITE = "minecraft:smite";
    private static final String BANE_OF_ARTHROPODS = "minecraft:bane_of_arthropods";
    private static final String FIRE_PROTECTION = "minecraft:fire_protection";
    private static final String BLAST_PROTECTION = "minecraft:blast_protection";
    private static final String FIRE_ASPECT = "minecraft:fire_aspect";
    private static final String THORNS = "minecraft:thorns";
    private static final String BREACH = "minecraft:breach";
    private static final String KNOCKBACK = "minecraft:knockback";
    private static final String PUNCH = "minecraft:punch";
    private static final String IMPALING = "minecraft:impaling";
    private static final String FLAME = "minecraft:flame";
    private static final String DEPTH_STRIDER = "minecraft:depth_strider";
    private static final String AQUA_AFFINITY = "minecraft:aqua_affinity";
    private static final String LOOTING = "minecraft:looting";
    private static final String SOUL_SPEED = "minecraft:soul_speed";
    private static final String SWIFT_SNEAK = "minecraft:swift_sneak";
    private static final String RIPTIDE = "minecraft:riptide";
    private static final String CHANNELING = "minecraft:channeling";
    private static final String RESPIRATION_PREV_AIR = "asobibatweaks_respiration_prev_air";
    private static final String PROTECTION_LAST_DAMAGE = "asobibatweaks_protection_last_damage";
    private static final String PROJECTILE_LAST_DAMAGE = "asobibatweaks_projectile_last_damage";
    private static final String PROJECTILE_BARRAGE_COUNT = "asobibatweaks_projectile_barrage_count";
    private static final String SHARPNESS_DUEL_TARGET = "asobibatweaks_sharpness_duel_target";
    private static final String SHARPNESS_DUEL_TIME = "asobibatweaks_sharpness_duel_time";
    private static final String SHARPNESS_DUEL_STACKS = "asobibatweaks_sharpness_duel_stacks";
    private static final String SMITE_HOLY_UNTIL = "asobibatweaks_smite_holy_until";
    private static final String SMITE_HOLY_REDUCTION = "asobibatweaks_smite_holy_reduction";
    private static final String SMITE_ECHO_ACTIVE = "asobibatweaks_smite_echo_active";
    private static final String BANE_ANTIVENOM_UNTIL = "asobibatweaks_bane_antivenom_until";
    private static final String BANE_ANTIVENOM_REDUCTION = "asobibatweaks_bane_antivenom_reduction";
    private static final String FIRE_PROTECTION_PREV_TICKS = "asobibatweaks_fire_protection_prev_ticks";
    private static final String FIRE_EXPOSURE_START = "asobibatweaks_fire_exposure_start";
    private static final String FIRE_EXPOSURE_LAST = "asobibatweaks_fire_exposure_last";
    private static final String BLAST_ANCHOR_UNTIL = "asobibatweaks_blast_anchor_until";
    private static final String BLAST_ANCHOR_REDUCTION = "asobibatweaks_blast_anchor_reduction";
    private static final String BLAST_LAST_DAMAGE = "asobibatweaks_blast_last_damage";
    private static final String BLAST_CHAIN_COUNT = "asobibatweaks_blast_chain_count";
    private static final String FIRE_ASPECT_FLASH_UNTIL = "asobibatweaks_fire_aspect_flash_until";
    private static final String FIRE_ASPECT_FLASH_MULTIPLIER = "asobibatweaks_fire_aspect_flash_multiplier";
    private static final String FIRE_ASPECT_CAUTERIZE_UNTIL = "asobibatweaks_fire_aspect_cauterize_until";
    private static final String FIRE_ASPECT_CAUTERIZE_REDUCTION = "asobibatweaks_fire_aspect_cauterize_reduction";
    private static final String THORNS_STORED_DAMAGE = "asobibatweaks_thorns_stored_damage";
    private static final String THORNS_RELEASE_ACTIVE = "asobibatweaks_thorns_release_active";
    private static final String BREACH_FRACTURE_ATTACKER = "asobibatweaks_breach_fracture_attacker";
    private static final String BREACH_FRACTURE_UNTIL = "asobibatweaks_breach_fracture_until";
    private static final String BREACH_FRACTURE_BONUS = "asobibatweaks_breach_fracture_bonus";
    private static final String KNOCKBACK_BRANCH = "asobibatweaks_knockback_branch";
    private static final String KNOCKBACK_STRENGTH = "asobibatweaks_knockback_strength";
    private static final String KNOCKBACK_ATTACKER_ID = "asobibatweaks_knockback_attacker_id";
    private static final String KNOCKBACK_UNTIL = "asobibatweaks_knockback_until";
    private static final String PUNCH_BRANCH = "asobibatweaks_punch_branch";
    private static final String PUNCH_STRENGTH = "asobibatweaks_punch_strength";
    private static final String PUNCH_UNTIL = "asobibatweaks_punch_until";
    private static final String IMPALING_HARPOON_STRENGTH = "asobibatweaks_impaling_harpoon_strength";
    private static final String IMPALING_HARPOON_UNTIL = "asobibatweaks_impaling_harpoon_until";
    private static final String AQUA_CONSTRUCTION_UNTIL = "asobibatweaks_aqua_construction_until";
    private static final String AQUA_CURRENT_UNTIL = "asobibatweaks_aqua_current_until";
    private static final String LOOTING_HERD_TYPE = "asobibatweaks_looting_herd_type";
    private static final String LOOTING_HERD_TIME = "asobibatweaks_looting_herd_time";
    private static final String LOOTING_HERD_STREAK = "asobibatweaks_looting_herd_streak";
    private static final String SOUL_SPEED_PREV_DAMAGE = "asobibatweaks_soul_speed_prev_damage";
    private static final String SOUL_SPEED_ACTIVE_SPEED = "asobibatweaks_soul_speed_active_speed";
    private static final String SOUL_SPEED_LINGER_UNTIL = "asobibatweaks_soul_speed_linger_until";
    private static final String RIPTIDE_SPIN_ACTIVE = "asobibatweaks_riptide_spin_active";

    @SubscribeEvent
    public void onSwiftSneakVibration(VanillaGameEvent event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || !(event.getCause() instanceof ServerPlayer player)
                || player.level().isClientSide()
                || !player.isShiftKeyDown()) {
            return;
        }

        BranchRef swiftSneak = armorBranch(player, SWIFT_SNEAK);
        if (swiftSneak == null || swiftSneak.branch() != 0) return;

        String path = event.getVanillaEvent().unwrapKey()
                .map(key -> key.location().getPath())
                .orElse("");
        boolean movementEvent = "step".equals(path)
                || "swim".equals(path)
                || "flap".equals(path)
                || "hit_ground".equals(path)
                || "splash".equals(path);
        if (!movementEvent) return;

        double strength = branchScale(swiftSneak.mastery(), 0.0D, 1.0D);
        double suppression = 0.20D + 0.50D * strength;
        if (player.getRandom().nextDouble() < suppression) {
            event.setCanceled(true);
        }
    }

    @SubscribeEvent
    public void onLootingDrops(LivingDropsEvent event) {
        if (!(event.getSource().getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) {
            return;
        }

        ItemStack weapon = event.getSource().getWeaponItem();
        if (weapon == null || weapon.isEmpty()) {
            if (event.getSource().getDirectEntity() != player) return;
            weapon = player.getMainHandItem();
        }

        BranchRef looting = branch(weapon, LOOTING);
        if (looting == null) return;

        double strength = branchScale(looting.mastery(), 0.0D, 1.0D);
        if (looting.branch() == 0) {
            applyHerdHunter(event, player, strength);
        } else if (looting.branch() == 1) {
            applyStripping(event, player, strength, enchantmentLevel(weapon, LOOTING));
        } else if (looting.branch() == 2) {
            applyBigGameHunter(event, player, strength);
        }
    }

    @SubscribeEvent
    public void onBlockDrops(BlockDropsEvent event) {
        if (!(event.getBreaker() instanceof ServerPlayer player)
                || !AsobibaTweaksConfig.GROWING_ENCHANTMENTS_ENABLED.getAsBoolean()) return;

        ItemStack tool = event.getTool();
        gain(player, tool, 1);

        if (AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) {
            applyFortuneBranch(event, tool, player);
            markAquaSuccessfulWork(player, 30L, 5L);
        }
    }

    @SubscribeEvent
    public void onRiptideRamDamage(LivingIncomingDamageEvent event) {
        if (!(event.getSource().getEntity() instanceof ServerPlayer player)
                || event.getSource().getDirectEntity() != player
                || player.level().isClientSide()
                || !player.isAutoSpinAttack()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getAmount() <= 0.0F) {
            return;
        }

        BranchRef riptide = heldBranch(player, RIPTIDE);
        if (riptide == null || riptide.branch() != 2) return;

        double strength = branchScale(riptide.mastery(), 0.0D, 1.0D);
        double fraction = 0.10D + 0.20D * strength;
        double bonus = Math.min(6.0D, event.getAmount() * fraction);
        event.setAmount((float)(event.getAmount() + bonus));
    }

    @SubscribeEvent
    public void onFlameProjectileHurt(LivingIncomingDamageEvent event) {
        if (!(event.getSource().getEntity() instanceof ServerPlayer player)
                || event.getSource().getDirectEntity() == player
                || player.level().isClientSide()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getAmount() <= 0.0F) {
            return;
        }

        ItemStack weapon = event.getSource().getWeaponItem();
        if (weapon == null || weapon.isEmpty()) return;

        BranchRef flame = branch(weapon, FLAME);
        if (flame == null) return;

        double strength = branchScale(flame.mastery(), 0.0D, 1.0D);
        int current = Math.max(0, event.getEntity().getRemainingFireTicks());
        int vanillaReference = 100;

        if (flame.branch() == 0) {
            int reference = Math.max(vanillaReference, current);
            int desired = (int)Math.round(reference * (1.25D + 0.50D * strength));
            event.getEntity().setRemainingFireTicks(Math.max(current, desired));
        } else if (flame.branch() == 1 && current > 0) {
            int add = (int)Math.round(20.0D + 30.0D * strength);
            int extraCap = (int)Math.round(60.0D + 100.0D * strength);
            int cappedTarget = vanillaReference + extraCap;
            if (current < cappedTarget) {
                event.getEntity().setRemainingFireTicks(Math.min(cappedTarget, current + add));
            }
        }
    }

    @SubscribeEvent
    public void onImpalingHurt(LivingIncomingDamageEvent event) {
        if (!(event.getSource().getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getAmount() <= 0.0F) {
            return;
        }

        ItemStack weapon = event.getSource().getWeaponItem();
        if (weapon == null || weapon.isEmpty()) {
            if (event.getSource().getDirectEntity() != player) return;
            weapon = player.getMainHandItem();
        }

        BranchRef impaling = branch(weapon, IMPALING);
        if (impaling == null) return;

        int level = enchantmentLevel(weapon, IMPALING);
        if (level <= 0) return;

        double strength = branchScale(impaling.mastery(), 0.0D, 1.0D);
        double vanillaBonus = 2.5D * level;

        if (impaling.branch() == 0) {
            boolean vanillaSensitive = event.getEntity().getType().is(EntityTypeTags.SENSITIVE_TO_IMPALING);
            if (!vanillaSensitive && event.getEntity().isInWaterOrRain()) {
                double fraction = 0.50D + 0.50D * strength;
                event.setAmount(event.getAmount() + (float)(vanillaBonus * fraction));
            }
        } else if (impaling.branch() == 1) {
            var data = event.getEntity().getPersistentData();
            data.putInt(
                    IMPALING_HARPOON_STRENGTH,
                    (int)Math.round((0.15D + 0.30D * strength) * 1000.0D)
            );
            data.putLong(IMPALING_HARPOON_UNTIL, player.level().getGameTime() + 2L);
        } else if (impaling.branch() == 2
                && event.getEntity().getType().is(EntityTypeTags.SENSITIVE_TO_IMPALING)
                && player.isUnderWater()
                && underwaterDepth(player) >= 8) {
            double extra = 0.10D + 0.20D * strength;
            event.setAmount(event.getAmount() + (float)(vanillaBonus * extra));
        }
    }

    @SubscribeEvent
    public void onPunchProjectileHurt(LivingIncomingDamageEvent event) {
        if (!(event.getSource().getEntity() instanceof ServerPlayer player)
                || event.getSource().getDirectEntity() == player
                || player.level().isClientSide()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getAmount() <= 0.0F) {
            return;
        }

        ItemStack weapon = event.getSource().getWeaponItem();
        if (weapon == null || weapon.isEmpty()) return;

        BranchRef punch = branch(weapon, PUNCH);
        if (punch == null) return;

        double strength = branchScale(punch.mastery(), 0.0D, 1.0D);
        var data = event.getEntity().getPersistentData();
        data.putInt(PUNCH_BRANCH, punch.branch());
        data.putInt(PUNCH_STRENGTH, (int)Math.round(strength * 1000.0D));
        data.putLong(PUNCH_UNTIL, player.level().getGameTime() + 2L);
    }

    @SubscribeEvent
    public void onKnockbackWeaponHurt(LivingIncomingDamageEvent event) {
        if (!(event.getSource().getEntity() instanceof ServerPlayer player)
                || event.getSource().getDirectEntity() != player
                || event.getSource().is(DamageTypes.THORNS)
                || player.getPersistentData().getBoolean(SMITE_ECHO_ACTIVE)
                || player.getPersistentData().getBoolean(THORNS_RELEASE_ACTIVE)
                || player.level().isClientSide()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getAmount() <= 0.0F) {
            return;
        }

        BranchRef knockback = branch(player.getMainHandItem(), KNOCKBACK);
        if (knockback == null) return;

        double strength = branchScale(knockback.mastery(), 0.0D, 1.0D);
        var data = event.getEntity().getPersistentData();
        data.putInt(KNOCKBACK_BRANCH, knockback.branch());
        data.putInt(KNOCKBACK_STRENGTH, (int)Math.round(strength * 1000.0D));
        data.putInt(KNOCKBACK_ATTACKER_ID, player.getId());
        data.putLong(KNOCKBACK_UNTIL, player.level().getGameTime() + 2L);
    }

    @SubscribeEvent
    public void onStoredRetaliationHurt(LivingIncomingDamageEvent event) {
        if (!(event.getSource().getEntity() instanceof ServerPlayer player)
                || event.getSource().getDirectEntity() != player
                || event.getSource().is(DamageTypes.THORNS)
                || player.level().isClientSide()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getAmount() <= 0.0F
                || player.getPersistentData().getBoolean(THORNS_RELEASE_ACTIVE)) {
            return;
        }

        BranchRef thorns = armorBranch(player, THORNS);
        if (thorns == null || thorns.branch() != 2) return;

        var persistent = player.getPersistentData();
        double stored = persistent.getInt(THORNS_STORED_DAMAGE) / 1000.0D;
        if (stored <= 0.0D) return;

        persistent.remove(THORNS_STORED_DAMAGE);
        persistent.putBoolean(THORNS_RELEASE_ACTIVE, true);
        try {
            event.getEntity().hurt(player.damageSources().thorns(player), (float)stored);
        } finally {
            persistent.remove(THORNS_RELEASE_ACTIVE);
        }
    }

    @SubscribeEvent
    public void onSharpnessHurt(LivingIncomingDamageEvent event) {
        if (!(event.getSource().getEntity() instanceof ServerPlayer player)
                || event.getSource().getDirectEntity() != player
                || event.getSource().is(DamageTypes.THORNS)
                || player.getPersistentData().getBoolean(SMITE_ECHO_ACTIVE)
                || player.level().isClientSide()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getAmount() <= 0.0F) {
            return;
        }

        ItemStack weapon = player.getMainHandItem();
        BranchRef sharpness = branch(weapon, SHARPNESS);
        if (sharpness == null) return;

        double strength = branchScale(sharpness.mastery(), 0.0D, 1.0D);
        double bonus = 0.0D;

        if (sharpness.branch() == 0) {
            long now = player.level().getGameTime();
            var persistent = player.getPersistentData();
            int targetId = event.getEntity().getId();
            int previousTarget = persistent.getInt(SHARPNESS_DUEL_TARGET);
            long last = persistent.getLong(SHARPNESS_DUEL_TIME);
            int stacks = persistent.getInt(SHARPNESS_DUEL_STACKS);

            boolean continuing = persistent.contains(SHARPNESS_DUEL_TIME)
                    && previousTarget == targetId
                    && now - last <= 60L;
            int priorStacks = continuing ? Math.min(5, stacks) : 0;
            double perStack = 0.01D + 0.02D * strength;
            bonus = priorStacks * perStack;

            persistent.putInt(SHARPNESS_DUEL_TARGET, targetId);
            persistent.putLong(SHARPNESS_DUEL_TIME, now);
            persistent.putInt(SHARPNESS_DUEL_STACKS, continuing ? Math.min(5, stacks + 1) : 1);
        } else if (sharpness.branch() == 1) {
            if (player.getAttackStrengthScale(0.5F) >= 0.95F) {
                bonus = 0.05D + 0.10D * strength;
            }
        } else if (sharpness.branch() == 2) {
            float maxHealth = Math.max(1.0F, event.getEntity().getMaxHealth());
            if (event.getEntity().getHealth() / maxHealth < 0.25F) {
                bonus = 0.05D + 0.15D * strength;
            }
        }

        if (bonus > 0.0D) {
            event.setAmount((float)(event.getAmount() * (1.0D + bonus)));
        }
    }

    @SubscribeEvent
    public void onFireAspectHurt(LivingIncomingDamageEvent event) {
        if (!(event.getSource().getEntity() instanceof ServerPlayer player)
                || event.getSource().getDirectEntity() != player
                || event.getSource().is(DamageTypes.THORNS)
                || player.getPersistentData().getBoolean(SMITE_ECHO_ACTIVE)
                || player.level().isClientSide()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getAmount() <= 0.0F) {
            return;
        }

        ItemStack weapon = player.getMainHandItem();
        BranchRef fireAspect = branch(weapon, FIRE_ASPECT);
        if (fireAspect == null) return;

        int level = enchantmentLevel(weapon, FIRE_ASPECT);
        if (level <= 0) return;

        double strength = branchScale(fireAspect.mastery(), 0.0D, 1.0D);
        int baseBurnTicks = 80 * level;
        long now = player.level().getGameTime();

        if (fireAspect.branch() == 0) {
            double extension = 0.25D + 0.50D * strength;
            int desired = (int)Math.round(baseBurnTicks * (1.0D + extension));
            event.getEntity().setRemainingFireTicks(
                    Math.max(event.getEntity().getRemainingFireTicks(), desired)
            );
        } else if (fireAspect.branch() == 1) {
            int duration = Math.max(20, (int)Math.round(baseBurnTicks * 0.60D));
            event.getEntity().setRemainingFireTicks(duration);
            var data = event.getEntity().getPersistentData();
            data.putLong(FIRE_ASPECT_FLASH_UNTIL, now + duration);
            data.putInt(
                    FIRE_ASPECT_FLASH_MULTIPLIER,
                    (int)Math.round((1.20D + 0.40D * strength) * 1000.0D)
            );
        } else if (fireAspect.branch() == 2) {
            int duration = Math.max(baseBurnTicks, event.getEntity().getRemainingFireTicks());
            var data = event.getEntity().getPersistentData();
            data.putLong(FIRE_ASPECT_CAUTERIZE_UNTIL, now + duration);
            data.putInt(
                    FIRE_ASPECT_CAUTERIZE_REDUCTION,
                    (int)Math.round((0.10D + 0.20D * strength) * 1000.0D)
            );
        }
    }

    @SubscribeEvent
    public void onBaneHurt(LivingIncomingDamageEvent event) {
        if (!(event.getSource().getEntity() instanceof ServerPlayer player)
                || event.getSource().getDirectEntity() != player
                || player.level().isClientSide()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getAmount() <= 0.0F
                || !event.getEntity().getType().is(EntityTypeTags.SENSITIVE_TO_BANE_OF_ARTHROPODS)) {
            return;
        }

        ItemStack weapon = player.getMainHandItem();
        BranchRef bane = branch(weapon, BANE_OF_ARTHROPODS);
        if (bane == null) return;

        int level = enchantmentLevel(weapon, BANE_OF_ARTHROPODS);
        if (level <= 0) return;

        double strength = branchScale(bane.mastery(), 0.0D, 1.0D);

        if (bane.branch() == 0) {
            int estimatedVanillaSlow = 20 + 10 * level;
            int duration = estimatedVanillaSlow
                    + (int)Math.round(estimatedVanillaSlow * (0.25D + 0.75D * strength));
            event.getEntity().addEffect(new MobEffectInstance(
                    MobEffects.MOVEMENT_SLOWDOWN,
                    Math.max(1, duration),
                    3
            ));
        } else if (bane.branch() == 1) {
            int nearby = Math.min(3, player.level().getEntitiesOfClass(
                    LivingEntity.class,
                    event.getEntity().getBoundingBox().inflate(6.0D),
                    e -> e != event.getEntity()
                            && e.isAlive()
                            && e.getType().is(EntityTypeTags.SENSITIVE_TO_BANE_OF_ARTHROPODS)
            ).size());
            if (nearby > 0) {
                double vanillaBaneBonus = 2.5D * level;
                double extra = vanillaBaneBonus * nearby * (0.05D + 0.07D * strength);
                event.setAmount(event.getAmount() + (float)extra);
            }
        } else if (bane.branch() == 2) {
            long until = player.level().getGameTime() + 80L;
            double reduction = 0.15D + 0.35D * strength;
            player.getPersistentData().putLong(BANE_ANTIVENOM_UNTIL, until);
            player.getPersistentData().putInt(
                    BANE_ANTIVENOM_REDUCTION,
                    (int)Math.round(reduction * 1000.0D)
            );
        }
    }

    @SubscribeEvent
    public void onSmiteHurt(LivingIncomingDamageEvent event) {
        if (!(event.getSource().getEntity() instanceof ServerPlayer player)
                || event.getSource().getDirectEntity() != player
                || event.getSource().is(DamageTypes.THORNS)
                || player.getPersistentData().getBoolean(SMITE_ECHO_ACTIVE)
                || player.level().isClientSide()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getAmount() <= 0.0F
                || !event.getEntity().getType().is(EntityTypeTags.SENSITIVE_TO_SMITE)) {
            return;
        }

        ItemStack weapon = player.getMainHandItem();
        BranchRef smite = branch(weapon, SMITE);
        if (smite == null) return;

        int level = enchantmentLevel(weapon, SMITE);
        if (level <= 0) return;

        double strength = branchScale(smite.mastery(), 0.0D, 1.0D);

        if (smite.branch() == 1) {
            long duration = Math.round(40.0D + 40.0D * strength);
            double reduction = 0.05D + 0.10D * strength;
            var targetData = event.getEntity().getPersistentData();
            targetData.putLong(SMITE_HOLY_UNTIL, player.level().getGameTime() + duration);
            targetData.putInt(SMITE_HOLY_REDUCTION, (int)Math.round(reduction * 1000.0D));
        } else if (smite.branch() == 2 && event.getEntity().getArmorValue() >= 10) {
            double vanillaSmiteBonus = 2.5D * level;
            double extra = vanillaSmiteBonus * (0.10D + 0.20D * strength);
            event.setAmount(event.getAmount() + (float)extra);
        }
    }

    @SubscribeEvent
    public void onHolyStrikeOutgoingDamage(LivingIncomingDamageEvent event) {
        if (!(event.getSource().getEntity() instanceof LivingEntity attacker)
                || event.getAmount() <= 0.0F) {
            return;
        }

        var data = attacker.getPersistentData();
        long now = attacker.level().getGameTime();
        if (!data.contains(SMITE_HOLY_UNTIL) || now > data.getLong(SMITE_HOLY_UNTIL)) return;

        double reduction = Math.min(0.15D, Math.max(0.0D, data.getInt(SMITE_HOLY_REDUCTION) / 1000.0D));
        if (reduction > 0.0D) {
            event.setAmount((float)(event.getAmount() * (1.0D - reduction)));
        }
    }

    @SubscribeEvent
    public void onLivingDeath(LivingDeathEvent event) {
        if (!(event.getSource().getEntity() instanceof ServerPlayer player)
                || !AsobibaTweaksConfig.GROWING_ENCHANTMENTS_ENABLED.getAsBoolean()) return;

        ItemStack weapon = player.getMainHandItem();
        gain(player, weapon, 4);

        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || player.getPersistentData().getBoolean(SMITE_ECHO_ACTIVE)
                || event.getSource().getDirectEntity() != player
                || !event.getEntity().getType().is(EntityTypeTags.SENSITIVE_TO_SMITE)) {
            return;
        }

        BranchRef smite = branch(weapon, SMITE);
        if (smite == null || smite.branch() != 0) return;

        int level = enchantmentLevel(weapon, SMITE);
        if (level <= 0) return;

        double strength = branchScale(smite.mastery(), 0.0D, 1.0D);
        double radius = 2.5D + 1.5D * strength;
        double echoDamage = 2.5D * level * (0.15D + 0.20D * strength);
        if (echoDamage <= 0.0D) return;

        player.getPersistentData().putBoolean(SMITE_ECHO_ACTIVE, true);
        try {
            for (LivingEntity other : player.level().getEntitiesOfClass(
                    LivingEntity.class,
                    event.getEntity().getBoundingBox().inflate(radius),
                    e -> e != event.getEntity()
                            && e.isAlive()
                            && e.getType().is(EntityTypeTags.SENSITIVE_TO_SMITE))) {
                other.hurt(player.damageSources().playerAttack(player), (float)echoDamage);
            }
        } finally {
            player.getPersistentData().remove(SMITE_ECHO_ACTIVE);
        }
    }

    @SubscribeEvent
    public void onAquaAffinityPlace(BlockEvent.EntityPlaceEvent event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()) {
            return;
        }
        markAquaSuccessfulWork(player, 30L, 5L);
    }

    @SubscribeEvent
    public void onBreakSpeed(PlayerEvent.BreakSpeed event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) return;

        if (event.getEntity() instanceof ServerPlayer player && player.isUnderWater()) {
            BranchRef aqua = armorBranch(player, AQUA_AFFINITY);
            if (aqua != null) {
                double strength = branchScale(aqua.mastery(), 0.0D, 1.0D);
                if (aqua.branch() == 0 && !player.onGround()) {
                    double removedPenalty = 0.25D + 0.75D * strength;
                    double multiplier = 1.0D + 4.0D * removedPenalty;
                    event.setNewSpeed((float)(event.getNewSpeed() * multiplier));
                } else if (aqua.branch() == 2) {
                    player.getPersistentData().putLong(
                            AQUA_CURRENT_UNTIL,
                            player.level().getGameTime() + 2L
                    );
                }
            }
        }

        ItemStack stack = event.getEntity().getMainHandItem();
        for (Holder<Enchantment> enchantment : EnchantmentMasteryData.enchantments(stack).keySet()) {
            if (!"minecraft:efficiency".equals(EnchantmentMasteryData.id(enchantment))) continue;
            int mastery = EnchantmentMasteryData.getMastery(stack, enchantment);
            if (mastery < BRANCH_THRESHOLD) return;
            int branch = EnchantmentMasteryData.getBranch(stack, enchantment);
            if (branch < 0) return;
            float factor = switch (branch) {
                case 0 -> 1.05F;
                case 1 -> 1.10F;
                case 2 -> 1.075F;
                default -> 1.0F;
            };
            event.setNewSpeed(event.getNewSpeed() * factor);
            return;
        }
    }

    @SubscribeEvent
    public void onFlashBurnDamage(LivingDamageEvent.Pre event) {
        if (event.getNewDamage() <= 0.0F || !event.getSource().is(DamageTypes.ON_FIRE)) return;

        var data = event.getEntity().getPersistentData();
        long now = event.getEntity().level().getGameTime();
        if (!data.contains(FIRE_ASPECT_FLASH_UNTIL)
                || now > data.getLong(FIRE_ASPECT_FLASH_UNTIL)) {
            return;
        }

        double multiplier = Math.min(
                1.60D,
                Math.max(1.0D, data.getInt(FIRE_ASPECT_FLASH_MULTIPLIER) / 1000.0D)
        );
        event.setNewDamage((float)(event.getNewDamage() * multiplier));
    }

    @SubscribeEvent
    public void onAntivenomDamage(LivingDamageEvent.Pre event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()
                || event.getNewDamage() <= 0.0F
                || !event.getSource().is(Tags.DamageTypes.IS_POISON)) {
            return;
        }

        var persistent = player.getPersistentData();
        long now = player.level().getGameTime();
        if (!persistent.contains(BANE_ANTIVENOM_UNTIL)
                || now > persistent.getLong(BANE_ANTIVENOM_UNTIL)) {
            return;
        }

        double reduction = Math.min(
                0.50D,
                Math.max(0.0D, persistent.getInt(BANE_ANTIVENOM_REDUCTION) / 1000.0D)
        );
        if (reduction > 0.0D) {
            event.setNewDamage((float)(event.getNewDamage() * (1.0D - reduction)));
        }
    }

    @SubscribeEvent
    public void onBreachDamage(LivingDamageEvent.Pre event) {
        if (!(event.getSource().getEntity() instanceof ServerPlayer player)
                || event.getSource().getDirectEntity() != player
                || event.getSource().is(DamageTypes.THORNS)
                || player.getPersistentData().getBoolean(SMITE_ECHO_ACTIVE)
                || player.getPersistentData().getBoolean(THORNS_RELEASE_ACTIVE)
                || player.level().isClientSide()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getNewDamage() <= 0.0F) {
            return;
        }

        BranchRef breach = branch(player.getMainHandItem(), BREACH);
        if (breach == null) return;

        double strength = branchScale(breach.mastery(), 0.0D, 1.0D);

        if (breach.branch() == 0) {
            if (event.getEntity().getArmorValue() >= 10) {
                double extraRemainingDamage = 0.05D + 0.10D * strength;
                event.setNewDamage((float)(event.getNewDamage() * (1.0D + extraRemainingDamage)));
            }
            return;
        }

        if (breach.branch() == 2) {
            var targetData = event.getEntity().getPersistentData();
            long now = player.level().getGameTime();
            String attacker = player.getUUID().toString();

            boolean active = attacker.equals(targetData.getString(BREACH_FRACTURE_ATTACKER))
                    && now <= targetData.getLong(BREACH_FRACTURE_UNTIL);
            if (active) {
                double bonus = Math.min(
                        0.15D,
                        Math.max(0.0D, targetData.getInt(BREACH_FRACTURE_BONUS) / 1000.0D)
                );
                event.setNewDamage((float)(event.getNewDamage() * (1.0D + bonus)));
            }

            long duration = Math.round(40.0D + 40.0D * strength);
            double bonus = 0.05D + 0.10D * strength;
            targetData.putString(BREACH_FRACTURE_ATTACKER, attacker);
            targetData.putLong(BREACH_FRACTURE_UNTIL, now + duration);
            targetData.putInt(BREACH_FRACTURE_BONUS, (int)Math.round(bonus * 1000.0D));
        }
    }

    @SubscribeEvent
    public void onThornsDamage(LivingDamageEvent.Pre event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getNewDamage() <= 0.0F) {
            return;
        }

        // Branches 0/1 specialize an actual vanilla Thorns retaliation event.
        if (event.getSource().is(DamageTypes.THORNS)
                && event.getSource().getEntity() instanceof ServerPlayer wearer) {
            BranchRef thorns = armorBranch(wearer, THORNS);
            if (thorns == null) return;

            double strength = branchScale(thorns.mastery(), 0.0D, 1.0D);
            if (thorns.branch() == 0) {
                event.setNewDamage((float)(event.getNewDamage() * (1.15D + 0.25D * strength)));
            } else if (thorns.branch() == 1) {
                event.setNewDamage(event.getNewDamage() * 0.70F);

                int duration = (int)Math.round(20.0D + 30.0D * strength);
                int amplifier = strength >= 0.67D ? 1 : 0;
                event.getEntity().addEffect(new MobEffectInstance(
                        MobEffects.MOVEMENT_SLOWDOWN,
                        Math.max(1, duration),
                        amplifier
                ));

                var away = event.getEntity().position().subtract(wearer.position());
                double horizontal = Math.sqrt(away.x * away.x + away.z * away.z);
                if (horizontal > 1.0E-4D) {
                    double push = 0.12D + 0.10D * strength;
                    event.getEntity().push(away.x / horizontal * push, 0.08D, away.z / horizontal * push);
                }
            }
            return;
        }

        // Stored Retaliation records post-mitigation incoming damage on the wearer.
        if (event.getEntity() instanceof ServerPlayer wearer
                && !event.getSource().is(DamageTypes.THORNS)
                && !wearer.getPersistentData().getBoolean(THORNS_RELEASE_ACTIVE)) {
            BranchRef thorns = armorBranch(wearer, THORNS);
            if (thorns == null || thorns.branch() != 2) return;

            double strength = branchScale(thorns.mastery(), 0.0D, 1.0D);
            double fraction = 0.15D + 0.20D * strength;
            double cap = 3.0D + 5.0D * strength;
            double stored = wearer.getPersistentData().getInt(THORNS_STORED_DAMAGE) / 1000.0D;
            stored = Math.min(cap, stored + event.getNewDamage() * fraction);
            wearer.getPersistentData().putInt(
                    THORNS_STORED_DAMAGE,
                    (int)Math.round(stored * 1000.0D)
            );
        }
    }

    @SubscribeEvent
    public void onBlastProtectionDamage(LivingDamageEvent.Pre event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getNewDamage() <= 0.0F
                || !event.getSource().is(DamageTypeTags.IS_EXPLOSION)
                || event.getSource().is(DamageTypeTags.BYPASSES_ENCHANTMENTS)) {
            return;
        }

        BranchRef blastProtection = armorBranch(player, BLAST_PROTECTION);
        if (blastProtection == null) return;

        double strength = branchScale(blastProtection.mastery(), 0.0D, 1.0D);
        double reduction = 0.0D;
        long now = player.level().getGameTime();

        if (blastProtection.branch() == 0) {
            double knockbackReduction = 0.20D + 0.35D * strength;
            player.getPersistentData().putLong(BLAST_ANCHOR_UNTIL, now + 2L);
            player.getPersistentData().putInt(
                    BLAST_ANCHOR_REDUCTION,
                    (int)Math.round(knockbackReduction * 1000.0D)
            );
        } else if (blastProtection.branch() == 1) {
            var sourcePos = event.getSource().getSourcePosition();
            if (sourcePos != null) {
                double distance = sourcePos.distanceTo(player.position());
                if (distance <= 6.0D) {
                    double distanceRamp = distance <= 3.0D
                            ? 1.0D
                            : Math.max(0.0D, (6.0D - distance) / 3.0D);
                    double maxReduction = 0.05D + 0.15D * strength;
                    reduction = maxReduction * distanceRamp;
                }
            }
        } else if (blastProtection.branch() == 2) {
            var persistent = player.getPersistentData();
            long last = persistent.getLong(BLAST_LAST_DAMAGE);
            int previous = persistent.getInt(BLAST_CHAIN_COUNT);
            if (!persistent.contains(BLAST_LAST_DAMAGE) || now - last > 100L) previous = 0;

            if (previous > 0 && now - last <= 80L) {
                double perPriorBlast = 0.05D + 0.07D * strength;
                reduction = Math.min(3, previous) * perPriorBlast;
            }

            int next = now - last <= 80L ? Math.min(3, previous + 1) : 1;
            persistent.putLong(BLAST_LAST_DAMAGE, now);
            persistent.putInt(BLAST_CHAIN_COUNT, next);
        }

        if (reduction > 0.0D) {
            event.setNewDamage((float)(event.getNewDamage() * Math.max(0.0D, 1.0D - reduction)));
        }
    }

    @SubscribeEvent
    public void onFireProtectionDamage(LivingDamageEvent.Pre event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getNewDamage() <= 0.0F
                || !event.getSource().is(DamageTypeTags.IS_FIRE)
                || event.getSource().is(DamageTypeTags.BYPASSES_ENCHANTMENTS)) {
            return;
        }

        BranchRef fireProtection = armorBranch(player, FIRE_PROTECTION);
        if (fireProtection == null || fireProtection.branch() != 1) return;

        var persistent = player.getPersistentData();
        if (!persistent.contains(FIRE_EXPOSURE_START)) return;

        long now = player.level().getGameTime();
        long start = persistent.getLong(FIRE_EXPOSURE_START);
        long exposure = Math.max(0L, now - start);
        if (exposure < 40L) return;

        double exposureRamp = Math.min(1.0D, (exposure - 40L) / 80.0D);
        double strength = branchScale(fireProtection.mastery(), 0.0D, 1.0D);
        double maxReduction = 0.05D + 0.10D * strength;
        double reduction = maxReduction * exposureRamp;
        if (reduction > 0.0D) {
            event.setNewDamage((float)(event.getNewDamage() * (1.0D - reduction)));
        }
    }

    @SubscribeEvent
    public void onLivingDamage(LivingDamageEvent.Pre event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getNewDamage() <= 0.0F
                || event.getSource().is(DamageTypeTags.BYPASSES_ENCHANTMENTS)) {
            return;
        }

        BranchRef protection = armorBranch(player, PROTECTION);
        if (protection == null) return;

        double strength = branchScale(protection.mastery(), 0.0D, 1.0D);
        double reduction = 0.0D;

        if (protection.branch() == 0) {
            reduction = 0.03D + 0.05D * strength;
        } else if (protection.branch() == 1) {
            long now = player.level().getGameTime();
            var persistent = player.getPersistentData();
            boolean armed = !persistent.contains(PROTECTION_LAST_DAMAGE)
                    || now - persistent.getLong(PROTECTION_LAST_DAMAGE) >= 160L;
            persistent.putLong(PROTECTION_LAST_DAMAGE, now);
            if (armed) reduction = 0.10D + 0.15D * strength;
        } else if (protection.branch() == 2) {
            float maxHealth = Math.max(1.0F, player.getMaxHealth());
            double healthRatio = player.getHealth() / (double)maxHealth;
            if (healthRatio < 0.40D) {
                double healthRamp = Math.min(1.0D, Math.max(0.0D, (0.40D - healthRatio) / 0.30D));
                double maxReduction = 0.05D + 0.15D * strength;
                reduction = maxReduction * healthRamp;
            }
        }

        if (reduction > 0.0D) {
            event.setNewDamage((float)(event.getNewDamage() * Math.max(0.0D, 1.0D - reduction)));
        }
    }

    @SubscribeEvent
    public void onProjectileProtectionDamage(LivingDamageEvent.Pre event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getNewDamage() <= 0.0F
                || !event.getSource().is(DamageTypeTags.IS_PROJECTILE)
                || event.getSource().is(DamageTypeTags.BYPASSES_ENCHANTMENTS)) {
            return;
        }

        BranchRef protection = armorBranch(player, PROJECTILE_PROTECTION);
        if (protection == null) return;

        double strength = branchScale(protection.mastery(), 0.0D, 1.0D);
        double reduction = 0.0D;

        if (protection.branch() == 0) {
            var sourcePos = event.getSource().getSourcePosition();
            if (sourcePos != null) {
                var toSource = sourcePos.subtract(player.getEyePosition());
                if (toSource.lengthSqr() > 1.0E-6D) {
                    double dot = player.getLookAngle().dot(toSource.normalize());
                    if (dot >= 0.5D) reduction = 0.08D + 0.12D * strength;
                }
            }
        } else if (protection.branch() == 1) {
            var attacker = event.getSource().getEntity();
            if (attacker != null) {
                double distance = attacker.distanceTo(player);
                if (distance >= 16.0D) {
                    double distanceRamp = Math.min(1.0D, (distance - 16.0D) / 32.0D);
                    double maxReduction = 0.10D + 0.15D * strength;
                    reduction = maxReduction * distanceRamp;
                }
            }
        } else if (protection.branch() == 2) {
            long now = player.level().getGameTime();
            var persistent = player.getPersistentData();
            long last = persistent.getLong(PROJECTILE_LAST_DAMAGE);
            int previousHits = persistent.getInt(PROJECTILE_BARRAGE_COUNT);

            if (!persistent.contains(PROJECTILE_LAST_DAMAGE) || now - last > 80L) {
                previousHits = 0;
            }

            if (previousHits > 0 && now - last <= 60L) {
                double perPriorHit = 0.03D + 0.04D * strength;
                reduction = Math.min(3, previousHits) * perPriorHit;
            }

            int nextHits = now - last <= 60L ? Math.min(3, previousHits + 1) : 1;
            persistent.putLong(PROJECTILE_LAST_DAMAGE, now);
            persistent.putInt(PROJECTILE_BARRAGE_COUNT, nextHits);
        }

        if (reduction > 0.0D) {
            event.setNewDamage((float)(event.getNewDamage() * Math.max(0.0D, 1.0D - reduction)));
        }
    }

    @SubscribeEvent
    public void onFall(LivingFallEvent event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) return;

        for (ItemStack armor : player.getArmorSlots()) {
            for (Holder<Enchantment> enchantment : EnchantmentMasteryData.enchantments(armor).keySet()) {
                if (!"minecraft:feather_falling".equals(EnchantmentMasteryData.id(enchantment))) continue;
                int mastery = EnchantmentMasteryData.getMastery(armor, enchantment);
                if (mastery < BRANCH_THRESHOLD) continue;
                int branch = EnchantmentMasteryData.getBranch(armor, enchantment);
                if (branch < 0) continue;
                if (branch == 0) {
                    event.setDistance(event.getDistance() * 0.85F);
                } else if (branch == 1 && event.getDistance() > 5.0F) {
                    for (LivingEntity other : player.level().getEntitiesOfClass(
                            LivingEntity.class, player.getBoundingBox().inflate(2.5D), e -> e != player)) {
                        other.push(other.getX() - player.getX(), 0.18D, other.getZ() - player.getZ());
                    }
                } else if (branch == 2) {
                    var motion = player.getDeltaMovement();
                    player.setDeltaMovement(motion.x * 1.12D, motion.y, motion.z * 1.12D);
                }
            }
        }
    }

    @SubscribeEvent
    public void onBlastAnchorTick(PlayerTickEvent.Post event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()) {
            return;
        }

        var persistent = player.getPersistentData();
        if (!persistent.contains(BLAST_ANCHOR_UNTIL)) return;

        long now = player.level().getGameTime();
        long until = persistent.getLong(BLAST_ANCHOR_UNTIL);
        if (now > until) {
            persistent.remove(BLAST_ANCHOR_UNTIL);
            persistent.remove(BLAST_ANCHOR_REDUCTION);
            return;
        }

        double reduction = Math.min(
                0.55D,
                Math.max(0.0D, persistent.getInt(BLAST_ANCHOR_REDUCTION) / 1000.0D)
        );
        var motion = player.getDeltaMovement();
        player.setDeltaMovement(motion.scale(1.0D - reduction));
        persistent.remove(BLAST_ANCHOR_UNTIL);
        persistent.remove(BLAST_ANCHOR_REDUCTION);
    }

    @SubscribeEvent
    public void onDepthStriderTick(PlayerTickEvent.Post event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()
                || !player.isInWater()) {
            return;
        }

        BranchRef depthStrider = armorBranch(player, DEPTH_STRIDER);
        if (depthStrider == null) return;

        double strength = branchScale(depthStrider.mastery(), 0.0D, 1.0D);
        var motion = player.getDeltaMovement();

        if (depthStrider.branch() == 0) {
            BlockPos pos = player.blockPosition();
            var fluid = player.level().getFluidState(pos);
            if (!fluid.is(net.minecraft.tags.FluidTags.WATER)) return;

            var flow = fluid.getFlow(player.level(), pos);
            double horizontalFlow = Math.sqrt(flow.x * flow.x + flow.z * flow.z);
            if (horizontalFlow <= 1.0E-5D) return;

            double ux = flow.x / horizontalFlow;
            double uz = flow.z / horizontalFlow;
            double along = motion.x * ux + motion.z * uz;
            if (along <= 0.0D) return;

            double bonus = 0.10D + 0.20D * strength;
            double nx = motion.x + ux * along * bonus;
            double nz = motion.z + uz * along * bonus;
            double horizontal = Math.sqrt(nx * nx + nz * nz);
            if (horizontal > 0.40D) {
                double scale = 0.40D / horizontal;
                nx *= scale;
                nz *= scale;
            }
            player.setDeltaMovement(nx, motion.y, nz);
        } else if (depthStrider.branch() == 1 && player.onGround()) {
            double multiplier = 1.10D + 0.15D * strength;
            double nx = motion.x * multiplier;
            double nz = motion.z * multiplier;
            double horizontal = Math.sqrt(nx * nx + nz * nz);
            if (horizontal > 0.35D) {
                double scale = 0.35D / horizontal;
                nx *= scale;
                nz *= scale;
            }
            player.setDeltaMovement(nx, motion.y, nz);
        } else if (depthStrider.branch() == 2 && Math.abs(motion.y) > 0.01D) {
            double multiplier = 1.10D + 0.25D * strength;
            double ny = Math.max(-0.35D, Math.min(0.35D, motion.y * multiplier));
            player.setDeltaMovement(motion.x, ny, motion.z);
        }
    }

    @SubscribeEvent
    public void onRiptideTick(PlayerTickEvent.Post event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()) {
            return;
        }

        var persistent = player.getPersistentData();
        if (!player.isAutoSpinAttack()) {
            persistent.remove(RIPTIDE_SPIN_ACTIVE);
            return;
        }

        BranchRef riptide = heldBranch(player, RIPTIDE);
        if (riptide == null) return;

        double strength = branchScale(riptide.mastery(), 0.0D, 1.0D);
        var motion = player.getDeltaMovement();
        double speed = motion.length();
        if (speed <= 1.0E-4D) return;

        if (riptide.branch() == 0) {
            if (!persistent.getBoolean(RIPTIDE_SPIN_ACTIVE)) {
                double multiplier = 1.10D + 0.15D * strength;
                double targetSpeed = Math.min(4.5D, speed * multiplier);
                player.setDeltaMovement(motion.scale(targetSpeed / speed));
            }
        } else if (riptide.branch() == 1) {
            var look = player.getLookAngle();
            if (look.lengthSqr() > 1.0E-6D) {
                double steering = 0.25D + 0.50D * strength;
                var desired = look.normalize().scale(speed);
                var blended = motion.scale(1.0D - steering).add(desired.scale(steering));
                double blendedSpeed = blended.length();
                if (blendedSpeed > 1.0E-4D) {
                    player.setDeltaMovement(blended.scale(Math.min(4.5D, speed) / blendedSpeed));
                }
            }
        }

        persistent.putBoolean(RIPTIDE_SPIN_ACTIVE, true);
    }

    @SubscribeEvent
    public void onSwiftSneakTick(PlayerTickEvent.Post event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()
                || !player.isShiftKeyDown()) {
            return;
        }

        BranchRef swiftSneak = armorBranch(player, SWIFT_SNEAK);
        if (swiftSneak == null) return;

        double strength = branchScale(swiftSneak.mastery(), 0.0D, 1.0D);
        var motion = player.getDeltaMovement();
        double horizontal = Math.sqrt(motion.x * motion.x + motion.z * motion.z);
        if (horizontal <= 0.002D) return;

        if (swiftSneak.branch() == 1 && player.isUsingItem()) {
            double slowdownRecovery = 0.10D + 0.25D * strength;
            double multiplier = 1.0D + 4.0D * slowdownRecovery;
            double nx = motion.x * multiplier;
            double nz = motion.z * multiplier;
            double nextHorizontal = Math.sqrt(nx * nx + nz * nz);
            if (nextHorizontal > 0.22D) {
                double scale = 0.22D / nextHorizontal;
                nx *= scale;
                nz *= scale;
            }
            player.setDeltaMovement(nx, motion.y, nz);
            return;
        }

        if (swiftSneak.branch() == 2 && player.onGround() && !player.isUsingItem()
                && isSneakEdgeActive(player)) {
            double multiplier = 1.10D + 0.20D * strength;
            double nx = motion.x * multiplier;
            double nz = motion.z * multiplier;
            double nextHorizontal = Math.sqrt(nx * nx + nz * nz);
            if (nextHorizontal > 0.18D) {
                double scale = 0.18D / nextHorizontal;
                nx *= scale;
                nz *= scale;
            }
            player.setDeltaMovement(nx, motion.y, nz);
        }
    }

    @SubscribeEvent
    public void onSoulSpeedTick(PlayerTickEvent.Post event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()) {
            return;
        }

        ItemStack boots = player.getItemBySlot(EquipmentSlot.FEET);
        var persistent = player.getPersistentData();
        BranchRef soulSpeed = branch(boots, SOUL_SPEED);
        if (soulSpeed == null) {
            persistent.remove(SOUL_SPEED_PREV_DAMAGE);
            persistent.remove(SOUL_SPEED_ACTIVE_SPEED);
            persistent.remove(SOUL_SPEED_LINGER_UNTIL);
            return;
        }

        long now = player.level().getGameTime();
        double strength = branchScale(soulSpeed.mastery(), 0.0D, 1.0D);
        boolean validFooting = player.onGround()
                && player.level().getBlockState(player.blockPosition().below()).is(BlockTags.SOUL_SPEED_BLOCKS);
        var motion = player.getDeltaMovement();
        double horizontalSpeed = Math.sqrt(motion.x * motion.x + motion.z * motion.z);

        int currentDamage = boots.isDamageableItem() ? boots.getDamageValue() : 0;
        if (soulSpeed.branch() == 0) {
            if (persistent.contains(SOUL_SPEED_PREV_DAMAGE)) {
                int previousDamage = persistent.getInt(SOUL_SPEED_PREV_DAMAGE);
                int gained = Math.max(0, currentDamage - previousDamage);
                if (validFooting && horizontalSpeed > 0.01D && player.hurtTime == 0 && gained > 0) {
                    double preventionChance = 0.25D + 0.50D * strength;
                    int prevented = 0;
                    for (int i = 0; i < gained; i++) {
                        if (player.getRandom().nextDouble() < preventionChance) prevented++;
                    }
                    if (prevented > 0) {
                        boots.setDamageValue(Math.max(0, currentDamage - prevented));
                        currentDamage = boots.getDamageValue();
                    }
                }
            }
            persistent.putInt(SOUL_SPEED_PREV_DAMAGE, currentDamage);
            return;
        }

        persistent.putInt(SOUL_SPEED_PREV_DAMAGE, currentDamage);

        if (soulSpeed.branch() != 1) {
            persistent.remove(SOUL_SPEED_ACTIVE_SPEED);
            persistent.remove(SOUL_SPEED_LINGER_UNTIL);
            return;
        }

        int level = Math.max(1, enchantmentLevel(boots, SOUL_SPEED));
        double vanillaBonus = 0.03D * (1.0D + level * 0.35D);
        double retention = 0.50D + 0.25D * strength;
        long duration = Math.round(20.0D + 40.0D * strength);

        if (validFooting && horizontalSpeed > 0.01D) {
            persistent.putInt(SOUL_SPEED_ACTIVE_SPEED, (int)Math.round(horizontalSpeed * 10000.0D));
            persistent.putLong(SOUL_SPEED_LINGER_UNTIL, now + duration);
            return;
        }

        if (!persistent.contains(SOUL_SPEED_LINGER_UNTIL)
                || now > persistent.getLong(SOUL_SPEED_LINGER_UNTIL)
                || !persistent.contains(SOUL_SPEED_ACTIVE_SPEED)
                || horizontalSpeed <= 0.005D) {
            return;
        }

        double activeSpeed = persistent.getInt(SOUL_SPEED_ACTIVE_SPEED) / 10000.0D;
        double baseline = activeSpeed / Math.max(1.0D, 1.0D + vanillaBonus);
        double target = baseline + (activeSpeed - baseline) * retention;
        target = Math.min(0.45D, Math.max(0.0D, target));

        if (horizontalSpeed < target) {
            double scale = target / horizontalSpeed;
            player.setDeltaMovement(motion.x * scale, motion.y, motion.z * scale);
        }
    }

    @SubscribeEvent
    public void onAquaAffinityTick(PlayerTickEvent.Post event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()
                || !player.isInWater()) {
            return;
        }

        BranchRef aqua = armorBranch(player, AQUA_AFFINITY);
        if (aqua == null) return;

        var persistent = player.getPersistentData();
        long now = player.level().getGameTime();
        double strength = branchScale(aqua.mastery(), 0.0D, 1.0D);
        var motion = player.getDeltaMovement();

        if (aqua.branch() == 1
                && persistent.contains(AQUA_CONSTRUCTION_UNTIL)
                && now <= persistent.getLong(AQUA_CONSTRUCTION_UNTIL)) {
            double disruptionRecovery = 0.15D + 0.25D * strength;
            double multiplier = 1.0D + 0.25D * disruptionRecovery;
            double nx = motion.x * multiplier;
            double nz = motion.z * multiplier;
            double horizontal = Math.sqrt(nx * nx + nz * nz);
            if (horizontal > 0.35D) {
                double scale = 0.35D / horizontal;
                nx *= scale;
                nz *= scale;
            }
            player.setDeltaMovement(nx, motion.y, nz);
            return;
        }

        if (aqua.branch() == 2
                && persistent.contains(AQUA_CURRENT_UNTIL)
                && now <= persistent.getLong(AQUA_CURRENT_UNTIL)) {
            BlockPos pos = player.blockPosition();
            var fluid = player.level().getFluidState(pos);
            if (!fluid.is(net.minecraft.tags.FluidTags.WATER)) return;

            var flow = fluid.getFlow(player.level(), pos);
            double reduction = 0.20D + 0.40D * strength;
            // Vanilla fluid acceleration is small; remove only the current-like component,
            // not the player's own movement input.
            double currentAcceleration = 0.014D;
            player.setDeltaMovement(
                    motion.x - flow.x * currentAcceleration * reduction,
                    motion.y,
                    motion.z - flow.z * currentAcceleration * reduction
            );
        }
    }

    @SubscribeEvent
    public void onFireProtectionTick(PlayerTickEvent.Post event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()) {
            return;
        }

        BranchRef fireProtection = armorBranch(player, FIRE_PROTECTION);
        var persistent = player.getPersistentData();
        int currentFireTicks = player.getRemainingFireTicks();
        long now = player.level().getGameTime();

        boolean exposed = player.isOnFire() || player.isInLava();
        if (exposed) {
            if (!persistent.contains(FIRE_EXPOSURE_START)
                    || !persistent.contains(FIRE_EXPOSURE_LAST)
                    || now - persistent.getLong(FIRE_EXPOSURE_LAST) > 60L) {
                persistent.putLong(FIRE_EXPOSURE_START, now);
            }
            persistent.putLong(FIRE_EXPOSURE_LAST, now);
        } else if (persistent.contains(FIRE_EXPOSURE_LAST)
                && now - persistent.getLong(FIRE_EXPOSURE_LAST) > 60L) {
            persistent.remove(FIRE_EXPOSURE_START);
            persistent.remove(FIRE_EXPOSURE_LAST);
        }

        if (fireProtection == null) {
            persistent.putInt(FIRE_PROTECTION_PREV_TICKS, currentFireTicks);
            return;
        }

        double strength = branchScale(fireProtection.mastery(), 0.0D, 1.0D);

        if (fireProtection.branch() == 0) {
            if (persistent.contains(FIRE_PROTECTION_PREV_TICKS)) {
                int previous = persistent.getInt(FIRE_PROTECTION_PREV_TICKS);
                if (currentFireTicks > previous + 1) {
                    double reduction = 0.20D + 0.30D * strength;
                    int reduced = Math.max(0, (int)Math.round(currentFireTicks * (1.0D - reduction)));
                    player.setRemainingFireTicks(reduced);
                    currentFireTicks = reduced;
                }
            }
        } else if (fireProtection.branch() == 2 && player.isInLava()) {
            // Vanilla lava horizontal drag is ~0.5. Recovering 20%-60% of the lost
            // velocity corresponds to multiplying the post-drag horizontal velocity by 1+r.
            double impairmentRecovery = 0.20D + 0.40D * strength;
            var motion = player.getDeltaMovement();
            player.setDeltaMovement(
                    motion.x * (1.0D + impairmentRecovery),
                    motion.y,
                    motion.z * (1.0D + impairmentRecovery)
            );
        }

        persistent.putInt(FIRE_PROTECTION_PREV_TICKS, currentFireTicks);
    }

    @SubscribeEvent
    public void onRespirationTick(PlayerTickEvent.Post event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()) {
            return;
        }

        BranchRef respiration = armorBranch(player, RESPIRATION);
        var persistent = player.getPersistentData();
        int currentAir = player.getAirSupply();

        if (respiration == null) {
            persistent.putInt(RESPIRATION_PREV_AIR, currentAir);
            return;
        }

        if (!persistent.contains(RESPIRATION_PREV_AIR)) {
            persistent.putInt(RESPIRATION_PREV_AIR, currentAir);
            return;
        }

        int previousAir = persistent.getInt(RESPIRATION_PREV_AIR);
        int adjustedAir = currentAir;
        double strength = branchScale(respiration.mastery(), 0.0D, 1.0D);

        if (respiration.branch() == 0 && player.isUnderWater() && currentAir < previousAir) {
            int lost = previousAir - currentAir;
            double preserveChance = 0.10D + 0.20D * strength;
            for (int i = 0; i < lost; i++) {
                if (player.getRandom().nextDouble() < preserveChance) adjustedAir++;
            }
        } else if (respiration.branch() == 1 && player.isUnderWater() && currentAir < previousAir) {
            var movement = player.getDeltaMovement();
            boolean quiet = movement.horizontalDistanceSqr() < 0.0036D && Math.abs(movement.y) < 0.04D;
            if (quiet) {
                int lost = previousAir - currentAir;
                double preserveChance = 0.25D + 0.45D * strength;
                for (int i = 0; i < lost; i++) {
                    if (player.getRandom().nextDouble() < preserveChance) adjustedAir++;
                }
            }
        } else if (respiration.branch() == 2 && !player.isUnderWater()
                && currentAir > previousAir && currentAir < player.getMaxAirSupply()) {
            int vanillaRecovery = currentAir - previousAir;
            double extraFraction = 0.25D + 0.75D * strength;
            int extra = Math.max(1, (int)Math.round(vanillaRecovery * extraFraction));
            adjustedAir = Math.min(player.getMaxAirSupply(), currentAir + extra);
        }

        if (adjustedAir != currentAir) player.setAirSupply(adjustedAir);
        persistent.putInt(RESPIRATION_PREV_AIR, adjustedAir);
    }

    @SubscribeEvent
    public void onPlayerTick(PlayerTickEvent.Post event) {
        if (!AsobibaTweaksConfig.GROWING_ENCHANTMENTS_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof ServerPlayer player)
                || player.tickCount % 1200 != Math.floorMod(player.getId(), 1200)) {
            return;
        }

        for (ItemStack armor : player.getArmorSlots()) {
            if (armor.isEmpty()) continue;
            for (Holder<Enchantment> enchantment : EnchantmentMasteryData.enchantments(armor).keySet()) {
                boolean curse = EnchantmentMasteryData.isCurse(enchantment);
                if (curse && !AsobibaTweaksConfig.CURSE_GROWTH_ENABLED.getAsBoolean()) continue;
                EnchantmentMasteryData.addMastery(armor, enchantment, 1);
                int mastery = EnchantmentMasteryData.getMastery(armor, enchantment);

                if (curse && mastery >= 100 && armor.isDamaged()
                        && player.getRandom().nextDouble() < Math.min(0.12D, mastery / 2500.0D)) {
                    armor.setDamageValue(Math.max(0, armor.getDamageValue() - 1));
                    player.displayClientMessage(Component.literal(
                            armor.getHoverName().getString() + "'s curse grudgingly held it together."
                    ).withStyle(ChatFormatting.DARK_PURPLE), true);
                }
            }
        }
    }

    @SubscribeEvent
    public void onTooltip(ItemTooltipEvent event) {
        if (!AsobibaTweaksConfig.GROWING_ENCHANTMENTS_ENABLED.getAsBoolean()) return;
        ItemStack stack = event.getItemStack();
        ItemEnchantments enchantments = EnchantmentMasteryData.enchantments(stack);
        if (enchantments.isEmpty()) return;

        boolean header = false;
        for (Holder<Enchantment> enchantment : enchantments.keySet()) {
            int mastery = EnchantmentMasteryData.getMastery(stack, enchantment);
            if (mastery <= 0) continue;
            if (!header) {
                event.getToolTip().add(Component.literal("Enchantment Mastery").withStyle(ChatFormatting.DARK_AQUA));
                header = true;
            }
            String name = enchantment.value().description().getString();
            int selectedBranch = EnchantmentMasteryData.getBranch(stack, enchantment);
            String branch = mastery >= BRANCH_THRESHOLD && selectedBranch >= 0
                    ? " / " + branchName(EnchantmentMasteryData.id(enchantment), selectedBranch)
                    : "";
            ChatFormatting color = EnchantmentMasteryData.isCurse(enchantment)
                    ? ChatFormatting.DARK_RED : ChatFormatting.GRAY;
            event.getToolTip().add(Component.literal("  " + name + ": " + mastery + branch).withStyle(color));
        }

        String stored = EnchantmentMasteryData.storedExclusive(stack);
        if (!stored.isEmpty()) {
            event.getToolTip().add(Component.literal(
                    "Stored enchantment: " + stored + " " + EnchantmentMasteryData.storedExclusiveLevel(stack)
            ).withStyle(ChatFormatting.GOLD));
        }
    }

    @SubscribeEvent
    public void onEnchantingTable(PlayerEvent.PlayerLoggedInEvent event) {
        // Marker hook kept intentionally empty: mastery is item-local and needs no per-player migration.
    }

    @SubscribeEvent
    public void onRightClickBlock(net.neoforged.neoforge.event.entity.player.PlayerInteractEvent.RightClickBlock event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || event.getLevel().isClientSide()
                || event.getHand() != InteractionHand.MAIN_HAND
                || !player.isShiftKeyDown()
                || !event.getLevel().getBlockState(event.getPos()).is(Blocks.ENCHANTING_TABLE)) return;

        ItemStack stack = player.getMainHandItem();
        if (stack.isEmpty() || EnchantmentMasteryData.enchantments(stack).isEmpty()) return;

        if (AsobibaTweaksConfig.ENCHANTMENT_SWITCHING_ENABLED.getAsBoolean()
                && !EnchantmentMasteryData.storedExclusive(stack).isEmpty()) {
            if (toggleExclusive(player, stack)) {
                event.setCancellationResult(InteractionResult.SUCCESS);
                event.setCanceled(true);
                return;
            }
        }

        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || !player.getOffhandItem().is(Items.LAPIS_LAZULI)) return;

        Holder<Enchantment> best = null;
        int bestMastery = BRANCH_THRESHOLD - 1;
        for (Holder<Enchantment> enchantment : EnchantmentMasteryData.enchantments(stack).keySet()) {
            String id = EnchantmentMasteryData.id(enchantment);
            if (!supportsBranches(id)) continue;

            int mastery = EnchantmentMasteryData.getMastery(stack, enchantment);
            if (mastery > bestMastery) {
                best = enchantment;
                bestMastery = mastery;
            }
        }
        if (best == null) return;

        int branch = EnchantmentMasteryData.cycleBranch(stack, best);
        if (!player.getAbilities().instabuild) player.getOffhandItem().shrink(1);
        player.sendSystemMessage(Component.literal(
                best.value().description().getString() + " mastery branch -> "
                        + branchName(EnchantmentMasteryData.id(best), branch)
        ).withStyle(ChatFormatting.AQUA));
        event.setCancellationResult(InteractionResult.SUCCESS);
        event.setCanceled(true);
    }

    @SubscribeEvent
    public void onImpalingHarpoonKnockback(LivingKnockBackEvent event) {
        var target = event.getEntity();
        var data = target.getPersistentData();
        if (!data.contains(IMPALING_HARPOON_UNTIL)) return;

        long now = target.level().getGameTime();
        if (now > data.getLong(IMPALING_HARPOON_UNTIL)) {
            data.remove(IMPALING_HARPOON_STRENGTH);
            data.remove(IMPALING_HARPOON_UNTIL);
            return;
        }

        float strength = (float)Math.min(
                0.45D,
                Math.max(0.15D, data.getInt(IMPALING_HARPOON_STRENGTH) / 1000.0D)
        );
        data.remove(IMPALING_HARPOON_STRENGTH);
        data.remove(IMPALING_HARPOON_UNTIL);

        event.setStrength(strength);
        event.setRatioX(-event.getRatioX());
        event.setRatioZ(-event.getRatioZ());
    }

    @SubscribeEvent
    public void onPunchKnockback(LivingKnockBackEvent event) {
        var target = event.getEntity();
        var data = target.getPersistentData();
        if (!data.contains(PUNCH_UNTIL)) return;

        long now = target.level().getGameTime();
        if (now > data.getLong(PUNCH_UNTIL)) {
            data.remove(PUNCH_BRANCH);
            data.remove(PUNCH_STRENGTH);
            data.remove(PUNCH_UNTIL);
            return;
        }

        int branch = data.getInt(PUNCH_BRANCH);
        double masteryStrength = Math.min(1.0D, Math.max(0.0D, data.getInt(PUNCH_STRENGTH) / 1000.0D));

        data.remove(PUNCH_BRANCH);
        data.remove(PUNCH_STRENGTH);
        data.remove(PUNCH_UNTIL);

        if (branch == 0) {
            double multiplier = 1.15D + 0.25D * masteryStrength;
            event.setStrength((float)(event.getStrength() * multiplier));
        } else if (branch == 1) {
            double conversion = 0.30D + 0.30D * masteryStrength;
            float original = event.getStrength();
            event.setStrength((float)(original * (1.0D - conversion)));
            target.push(0.0D, original * conversion, 0.0D);
        } else if (branch == 2) {
            event.setStrength(event.getStrength() * 0.25F);
            int duration = (int)Math.round(20.0D + 30.0D * masteryStrength);
            int amplifier = masteryStrength >= 0.75D ? 2 : 1;
            target.addEffect(new MobEffectInstance(
                    MobEffects.MOVEMENT_SLOWDOWN,
                    Math.max(1, duration),
                    amplifier
            ));
        }
    }

    @SubscribeEvent
    public void onSoulFootingKnockback(LivingKnockBackEvent event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()) {
            return;
        }

        ItemStack boots = player.getItemBySlot(EquipmentSlot.FEET);
        BranchRef soulSpeed = branch(boots, SOUL_SPEED);
        if (soulSpeed == null || soulSpeed.branch() != 2) return;

        BlockPos footing = player.blockPosition().below();
        if (!player.level().getBlockState(footing).is(BlockTags.SOUL_SPEED_BLOCKS)) return;

        double strength = branchScale(soulSpeed.mastery(), 0.0D, 1.0D);
        double reduction = 0.10D + 0.25D * strength;
        event.setStrength((float)(event.getStrength() * (1.0D - reduction)));
    }

    @SubscribeEvent
    public void onKnockback(LivingKnockBackEvent event) {
        var target = event.getEntity();
        var data = target.getPersistentData();
        if (!data.contains(KNOCKBACK_UNTIL)) return;

        long now = target.level().getGameTime();
        if (now > data.getLong(KNOCKBACK_UNTIL)) {
            data.remove(KNOCKBACK_BRANCH);
            data.remove(KNOCKBACK_STRENGTH);
            data.remove(KNOCKBACK_ATTACKER_ID);
            data.remove(KNOCKBACK_UNTIL);
            return;
        }

        int branch = data.getInt(KNOCKBACK_BRANCH);
        double masteryStrength = Math.min(1.0D, Math.max(0.0D, data.getInt(KNOCKBACK_STRENGTH) / 1000.0D));
        int attackerId = data.getInt(KNOCKBACK_ATTACKER_ID);

        data.remove(KNOCKBACK_BRANCH);
        data.remove(KNOCKBACK_STRENGTH);
        data.remove(KNOCKBACK_ATTACKER_ID);
        data.remove(KNOCKBACK_UNTIL);

        if (branch == 0) {
            double conversion = 0.30D + 0.30D * masteryStrength;
            float original = event.getStrength();
            event.setStrength((float)(original * (1.0D - conversion)));
            target.push(0.0D, original * conversion, 0.0D);
        } else if (branch == 1) {
            double multiplier = 1.15D + 0.25D * masteryStrength;
            event.setStrength((float)(event.getStrength() * multiplier));
        } else if (branch == 2) {
            var attackerEntity = target.level().getEntity(attackerId);
            if (attackerEntity instanceof ServerPlayer attacker && attacker.isAlive()) {
                var away = attacker.position().subtract(target.position());
                double horizontal = Math.sqrt(away.x * away.x + away.z * away.z);
                if (horizontal > 1.0E-4D) {
                    double recoil = event.getStrength() * (0.10D + 0.20D * masteryStrength);
                    attacker.push(away.x / horizontal * recoil, 0.0D, away.z / horizontal * recoil);
                }
            }
        }
    }

    @SubscribeEvent
    public void onBreachShieldBlock(LivingShieldBlockEvent event) {
        if (!(event.getEntity() instanceof ServerPlayer blocker)
                || !(event.getDamageSource().getEntity() instanceof ServerPlayer attacker)
                || event.getDamageSource().getDirectEntity() != attacker
                || attacker.level().isClientSide()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || !event.getBlocked()
                || event.getBlockedDamage() <= 0.0F) {
            return;
        }

        BranchRef breach = branch(attacker.getMainHandItem(), BREACH);
        if (breach == null || breach.branch() != 1) return;

        ItemStack shield = blocker.getUseItem();
        if (shield.isEmpty()) return;

        double strength = branchScale(breach.mastery(), 0.0D, 1.0D);
        int extraTicks = (int)Math.round(10.0D + 20.0D * strength);
        var shieldItem = shield.getItem();

        blocker.stopUsingItem();
        blocker.getCooldowns().addCooldown(shieldItem, Math.max(1, extraTicks));
    }

    @SubscribeEvent
    public void onCauterizeHeal(LivingHealEvent event) {
        if (event.getAmount() <= 0.0F || !event.getEntity().isOnFire()) return;

        var data = event.getEntity().getPersistentData();
        long now = event.getEntity().level().getGameTime();
        if (!data.contains(FIRE_ASPECT_CAUTERIZE_UNTIL)
                || now > data.getLong(FIRE_ASPECT_CAUTERIZE_UNTIL)) {
            return;
        }

        double reduction = Math.min(
                0.30D,
                Math.max(0.0D, data.getInt(FIRE_ASPECT_CAUTERIZE_REDUCTION) / 1000.0D)
        );
        if (reduction > 0.0D) {
            event.setAmount((float)(event.getAmount() * (1.0D - reduction)));
        }
    }

    @SubscribeEvent
    public void onAnvilUpdate(AnvilUpdateEvent event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_SWITCHING_ENABLED.getAsBoolean()) return;
        ItemStack left = event.getLeft();
        ItemStack right = event.getRight();
        if (left.isEmpty() || right.isEmpty()) return;

        EnchantRef leftExclusive = findExclusive(left);
        EnchantRef rightExclusive = findExclusive(right);
        if (leftExclusive == null || rightExclusive == null || leftExclusive.id.equals(rightExclusive.id)) return;
        if (!isFortuneSilkPair(leftExclusive.id, rightExclusive.id)) return;

        ItemStack output = left.copy();
        EnchantmentMasteryData.storeExclusive(output, rightExclusive.id, rightExclusive.level);
        event.setOutput(output);
        event.setCost(Math.max(5L, event.getCost() + 5L));
        event.setMaterialCost(1);
    }

    @SubscribeEvent
    public void onAnvilRepair(AnvilRepairEvent event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_INHERITANCE_ENABLED.getAsBoolean()) return;
        EnchantmentMasteryData.mergeInherited(event.getOutput(), event.getLeft(), event.getRight());
    }

    private static void gain(ServerPlayer player, ItemStack stack, int amount) {
        if (stack.isEmpty()) return;
        ItemEnchantments enchantments = EnchantmentMasteryData.enchantments(stack);
        if (enchantments.isEmpty()) return;

        for (Holder<Enchantment> enchantment : enchantments.keySet()) {
            boolean curse = EnchantmentMasteryData.isCurse(enchantment);
            if (curse && !AsobibaTweaksConfig.CURSE_GROWTH_ENABLED.getAsBoolean()) continue;
            EnchantmentMasteryData.addMastery(stack, enchantment, amount);

            int mastery = EnchantmentMasteryData.getMastery(stack, enchantment);
            if (mastery == BRANCH_THRESHOLD && AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) {
                player.displayClientMessage(Component.literal(
                        enchantment.value().description().getString() + " can now choose a mastery branch at an enchanting table."
                ).withStyle(ChatFormatting.AQUA), true);
            }
            if ("minecraft:unbreaking".equals(EnchantmentMasteryData.id(enchantment))
                    && mastery >= 100
                    && stack.isDamaged()
                    && player.getRandom().nextDouble() < Math.min(0.08D, mastery / 5000.0D)) {
                stack.setDamageValue(Math.max(0, stack.getDamageValue() - 1));
            }
        }
    }

    private static void applyHerdHunter(LivingDropsEvent event, ServerPlayer player, double strength) {
        var data = player.getPersistentData();
        long now = player.level().getGameTime();
        String type = BuiltInRegistries.ENTITY_TYPE.getKey(event.getEntity().getType()).toString();

        long last = data.getLong(LOOTING_HERD_TIME);
        String previousType = data.getString(LOOTING_HERD_TYPE);
        int streak = type.equals(previousType) && now - last <= 400L
                ? Math.min(5, data.getInt(LOOTING_HERD_STREAK) + 1)
                : 1;

        data.putString(LOOTING_HERD_TYPE, type);
        data.putLong(LOOTING_HERD_TIME, now);
        data.putInt(LOOTING_HERD_STREAK, streak);

        ItemEntity target = largestOrdinaryDrop(event);
        if (target == null) return;

        double streakScale = streak / 5.0D;
        double chance = (0.15D + 0.15D * strength) * streakScale;
        if (player.getRandom().nextDouble() < chance) {
            addOneDrop(event.getDrops(), event.getEntity(), target);
        }
    }

    private static void applyStripping(LivingDropsEvent event, ServerPlayer player,
                                       double strength, int lootingLevel) {
        if (!(event.getEntity() instanceof Mob mob)) return;

        double multiplier = 1.25D + 0.50D * strength;
        // Vanilla's ordinary mob-equipment drop chance starts at 8.5%; Looting historically
        // contributes about one percentage point per level. Use that post-Looting baseline
        // only to calculate the branch's incremental second-chance roll.
        double vanillaAdjustedChance = Math.min(
                1.0D,
                Mob.DEFAULT_EQUIPMENT_DROP_CHANCE + Math.max(0, lootingLevel) * 0.01D
        );

        double targetChance = Math.min(1.0D, vanillaAdjustedChance * multiplier);
        double incrementalChance = vanillaAdjustedChance >= 1.0D
                ? 0.0D
                : Math.max(0.0D, (targetChance - vanillaAdjustedChance) / (1.0D - vanillaAdjustedChance));

        if (incrementalChance <= 0.0D) return;

        for (EquipmentSlot slot : EquipmentSlot.values()) {
            ItemStack equipped = mob.getItemBySlot(slot);
            if (equipped.isEmpty()
                    || enchantmentLevel(equipped, "minecraft:vanishing_curse") > 0
                    || alreadyDropped(event, equipped)) {
                continue;
            }

            if (player.getRandom().nextDouble() < incrementalChance) {
                event.getDrops().add(new ItemEntity(
                        event.getEntity().level(),
                        event.getEntity().getX(),
                        event.getEntity().getY(),
                        event.getEntity().getZ(),
                        equipped.copy()
                ));
            }
        }
    }

    private static void applyBigGameHunter(LivingDropsEvent event, ServerPlayer player, double strength) {
        List<ItemEntity> rare = event.getDrops().stream()
                .filter(drop -> isRareLoot(drop.getItem()))
                .toList();

        double rareBoost = 0.10D + 0.20D * strength;
        if (!rare.isEmpty() && player.getRandom().nextDouble() < rareBoost) {
            ItemEntity target = rare.get(player.getRandom().nextInt(rare.size()));
            addOneDrop(event.getDrops(), event.getEntity(), target);
        }

        // We cannot safely reconstruct the victim's loot table here. Approximate the accepted
        // 25% reduction of Looting's common-drop improvement by trimming at most one extra unit,
        // and never reduce a stack below one.
        ItemEntity ordinary = largestOrdinaryDrop(event);
        if (ordinary != null && ordinary.getItem().getCount() >= 2
                && player.getRandom().nextDouble() < 0.25D) {
            ordinary.getItem().shrink(1);
        }
    }

    private static ItemEntity largestOrdinaryDrop(LivingDropsEvent event) {
        ItemEntity best = null;
        int bestCount = -1;
        for (ItemEntity drop : event.getDrops()) {
            ItemStack stack = drop.getItem();
            if (stack.isEmpty() || isRareLoot(stack) || isEquipmentLike(stack)
                    || stack.getCount() <= bestCount) {
                continue;
            }
            best = drop;
            bestCount = stack.getCount();
        }
        return best;
    }

    private static boolean alreadyDropped(LivingDropsEvent event, ItemStack candidate) {
        for (ItemEntity drop : event.getDrops()) {
            if (ItemStack.isSameItemSameComponents(drop.getItem(), candidate)) return true;
        }
        return false;
    }

    private static boolean isEquipmentLike(ItemStack stack) {
        return stack.getMaxStackSize() == 1 && stack.isDamageableItem();
    }

    private static boolean isRareLoot(ItemStack stack) {
        return stack.is(Items.WITHER_SKELETON_SKULL)
                || stack.is(Items.RABBIT_FOOT)
                || stack.is(Items.TRIDENT)
                || stack.is(Items.NAUTILUS_SHELL)
                || stack.is(Items.TOTEM_OF_UNDYING)
                || stack.is(Items.GOAT_HORN)
                || stack.is(Items.MUSIC_DISC_5)
                || stack.is(Items.NETHER_STAR);
    }

    private static void addOneDrop(java.util.Collection<ItemEntity> drops,
                                   LivingEntity victim,
                                   ItemEntity target) {
        ItemStack stack = target.getItem();
        if (stack.isEmpty()) return;

        if (stack.getCount() < stack.getMaxStackSize()) {
            stack.grow(1);
            return;
        }

        drops.add(new ItemEntity(
                victim.level(),
                victim.getX(),
                victim.getY(),
                victim.getZ(),
                stack.copyWithCount(1)
        ));
    }

    private static boolean isSneakEdgeActive(ServerPlayer player) {
        BlockPos below = player.blockPosition().below();
        if (player.level().getBlockState(below).isAir()) return false;

        for (Direction direction : Direction.Plane.HORIZONTAL) {
            BlockPos support = below.relative(direction);
            if (player.level().getBlockState(support).isAir()) return true;
        }
        return false;
    }

    private static void markAquaSuccessfulWork(ServerPlayer player,
                                               long constructionTicks,
                                               long currentTicks) {
        if (!player.isUnderWater()) return;
        BranchRef aqua = armorBranch(player, AQUA_AFFINITY);
        if (aqua == null) return;

        long now = player.level().getGameTime();
        if (aqua.branch() == 1) {
            player.getPersistentData().putLong(
                    AQUA_CONSTRUCTION_UNTIL,
                    now + Math.max(1L, constructionTicks)
            );
        } else if (aqua.branch() == 2) {
            player.getPersistentData().putLong(
                    AQUA_CURRENT_UNTIL,
                    now + Math.max(1L, currentTicks)
            );
        }
    }

    private static void applyFortuneBranch(BlockDropsEvent event, ItemStack tool, ServerPlayer player) {
        BranchRef fortune = branch(tool, FORTUNE);
        if (fortune == null || event.getDrops().isEmpty()) return;

        String blockPath = BuiltInRegistries.BLOCK.getKey(event.getState().getBlock()).getPath();
        double strength = branchScale(fortune.mastery(), 0.0D, 1.0D);

        if (fortune.branch() == 0) {
            if (!isOreFortuneTarget(blockPath)) return;
            double chance = 0.10D + 0.15D * strength;
            if (player.getRandom().nextDouble() < chance) addOneDrop(event);
            return;
        }

        if (fortune.branch() == 1) {
            if (!isHarvestFortuneTarget(blockPath)) return;
            double chance = 0.10D + 0.15D * strength;
            if (player.getRandom().nextDouble() < chance) addOneDrop(event);
            return;
        }

        if (fortune.branch() == 2) {
            double chance = 0.10D + 0.20D * strength;
            if (player.getRandom().nextDouble() >= chance) return;

            ItemEntity target = largestDrop(event);
            if (target == null || target.getItem().getCount() < 2) return;

            if (player.getRandom().nextBoolean()) {
                addOneDrop(event, target);
            } else {
                target.getItem().shrink(1);
            }
        }
    }

    private static BranchRef branch(ItemStack stack, String enchantmentId) {
        if (stack.isEmpty()) return null;
        for (Holder<Enchantment> enchantment : EnchantmentMasteryData.enchantments(stack).keySet()) {
            if (!enchantmentId.equals(EnchantmentMasteryData.id(enchantment))) continue;

            int mastery = EnchantmentMasteryData.getMastery(stack, enchantment);
            int selected = EnchantmentMasteryData.getBranch(stack, enchantment);
            if (mastery < BRANCH_THRESHOLD || selected < 0) return null;
            return new BranchRef(mastery, selected);
        }
        return null;
    }

    private static int underwaterDepth(ServerPlayer player) {
        BlockPos origin = player.blockPosition();
        int depth = 0;
        for (int dy = 0; dy <= 32; dy++) {
            BlockPos pos = origin.above(dy);
            if (!player.level().getFluidState(pos).is(net.minecraft.tags.FluidTags.WATER)) break;
            depth++;
        }
        return depth;
    }

    private static int enchantmentLevel(ItemStack stack, String enchantmentId) {
        for (var entry : EnchantmentMasteryData.enchantments(stack).entrySet()) {
            if (enchantmentId.equals(EnchantmentMasteryData.id(entry.getKey()))) {
                return entry.getIntValue();
            }
        }
        return 0;
    }

    private static BranchRef heldBranch(ServerPlayer player, String enchantmentId) {
        BranchRef main = branch(player.getMainHandItem(), enchantmentId);
        BranchRef off = branch(player.getOffhandItem(), enchantmentId);
        if (main == null) return off;
        if (off == null) return main;
        return main.mastery() >= off.mastery() ? main : off;
    }

    private static BranchRef armorBranch(ServerPlayer player, String enchantmentId) {
        BranchRef best = null;
        for (ItemStack armor : player.getArmorSlots()) {
            BranchRef candidate = branch(armor, enchantmentId);
            if (candidate == null) continue;
            if (best == null || candidate.mastery() > best.mastery()) best = candidate;
        }
        return best;
    }

    private static double branchScale(int mastery, double min, double max) {
        double t = (Math.max(BRANCH_THRESHOLD, Math.min(100, mastery)) - BRANCH_THRESHOLD)
                / (double)(100 - BRANCH_THRESHOLD);
        return min + (max - min) * t;
    }

    private static boolean isOreFortuneTarget(String blockPath) {
        return blockPath.endsWith("_ore")
                || "raw_copper_block".equals(blockPath)
                || "raw_iron_block".equals(blockPath)
                || "raw_gold_block".equals(blockPath);
    }

    private static boolean isHarvestFortuneTarget(String blockPath) {
        return "wheat".equals(blockPath)
                || "carrots".equals(blockPath)
                || "potatoes".equals(blockPath)
                || "beetroots".equals(blockPath)
                || "nether_wart".equals(blockPath)
                || "melon".equals(blockPath)
                || "cocoa".equals(blockPath)
                || "sweet_berry_bush".equals(blockPath);
    }

    private static ItemEntity largestDrop(BlockDropsEvent event) {
        ItemEntity best = null;
        int bestCount = -1;
        for (ItemEntity drop : event.getDrops()) {
            ItemStack stack = drop.getItem();
            if (stack.isEmpty() || stack.getCount() <= bestCount) continue;
            best = drop;
            bestCount = stack.getCount();
        }
        return best;
    }

    private static void addOneDrop(BlockDropsEvent event) {
        ItemEntity target = largestDrop(event);
        if (target != null) addOneDrop(event, target);
    }

    private static void addOneDrop(BlockDropsEvent event, ItemEntity target) {
        ItemStack stack = target.getItem();
        if (stack.isEmpty()) return;

        if (stack.getCount() < stack.getMaxStackSize()) {
            stack.grow(1);
            return;
        }

        ItemStack extra = stack.copyWithCount(1);
        event.getDrops().add(new ItemEntity(
                event.getLevel(),
                event.getPos().getX() + 0.5D,
                event.getPos().getY() + 0.5D,
                event.getPos().getZ() + 0.5D,
                extra
        ));
    }

    private static boolean toggleExclusive(ServerPlayer player, ItemStack stack) {
        String storedId = EnchantmentMasteryData.storedExclusive(stack);
        int storedLevel = Math.max(1, EnchantmentMasteryData.storedExclusiveLevel(stack));
        EnchantRef active = findExclusive(stack);
        if (active == null || !isFortuneSilkPair(active.id, storedId)) return false;

        Holder<Enchantment> stored = holder(player, storedId);
        if (stored == null) return false;

        List<Holder<Enchantment>> toRemove = new ArrayList<>();
        for (Holder<Enchantment> enchantment : EnchantmentMasteryData.enchantments(stack).keySet()) {
            if (EnchantmentMasteryData.id(enchantment).equals(active.id)) toRemove.add(enchantment);
        }

        EnchantmentHelper.updateEnchantments(stack, mutable -> {
            mutable.removeIf(toRemove::contains);
            mutable.set(stored, storedLevel);
        });
        EnchantmentMasteryData.storeExclusive(stack, active.id, active.level);
        player.sendSystemMessage(Component.literal("Active enchantment -> " + stored.value().description().getString())
                .withStyle(ChatFormatting.GOLD));
        return true;
    }

    private static Holder<Enchantment> holder(ServerPlayer player, String id) {
        try {
            ResourceKey<Enchantment> key = ResourceKey.create(Registries.ENCHANTMENT, ResourceLocation.parse(id));
            return player.registryAccess().lookupOrThrow(Registries.ENCHANTMENT).getOrThrow(key);
        } catch (RuntimeException ex) {
            return null;
        }
    }

    private static EnchantRef findExclusive(ItemStack stack) {
        for (var entry : EnchantmentMasteryData.enchantments(stack).entrySet()) {
            String id = EnchantmentMasteryData.id(entry.getKey());
            if (FORTUNE.equals(id) || SILK_TOUCH.equals(id)) {
                return new EnchantRef(id, entry.getIntValue());
            }
        }
        return null;
    }

    private static boolean isFortuneSilkPair(String a, String b) {
        return (FORTUNE.equals(a) && SILK_TOUCH.equals(b)) || (SILK_TOUCH.equals(a) && FORTUNE.equals(b));
    }

    private static boolean supportsBranches(String enchantmentId) {
        return UNBREAKING.equals(enchantmentId)
                || INFINITY.equals(enchantmentId)
                || POWER.equals(enchantmentId)
                || LOYALTY.equals(enchantmentId)
                || "minecraft:efficiency".equals(enchantmentId)
                || "minecraft:feather_falling".equals(enchantmentId)
                || FORTUNE.equals(enchantmentId)
                || RESPIRATION.equals(enchantmentId)
                || PROTECTION.equals(enchantmentId)
                || PROJECTILE_PROTECTION.equals(enchantmentId)
                || SHARPNESS.equals(enchantmentId)
                || SMITE.equals(enchantmentId)
                || BANE_OF_ARTHROPODS.equals(enchantmentId)
                || FIRE_PROTECTION.equals(enchantmentId)
                || BLAST_PROTECTION.equals(enchantmentId)
                || FIRE_ASPECT.equals(enchantmentId)
                || THORNS.equals(enchantmentId)
                || BREACH.equals(enchantmentId)
                || KNOCKBACK.equals(enchantmentId)
                || PUNCH.equals(enchantmentId)
                || IMPALING.equals(enchantmentId)
                || FLAME.equals(enchantmentId)
                || DEPTH_STRIDER.equals(enchantmentId)
                || AQUA_AFFINITY.equals(enchantmentId)
                || LOOTING.equals(enchantmentId)
                || SOUL_SPEED.equals(enchantmentId)
                || SWIFT_SNEAK.equals(enchantmentId)
                || RIPTIDE.equals(enchantmentId)
                || CHANNELING.equals(enchantmentId);
    }

    private static String branchName(String enchantmentId, int branch) {
        if (LOYALTY.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Fast Return";
                case 1 -> "Safe Return";
                case 2 -> "Pursuing Return";
                default -> "Unselected";
            };
        } 
        if (POWER.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Sniping";
                case 1 -> "Heavy Draw";
                case 2 -> "Quick Shot";
                default -> "Unselected";
            };
        }
        if (INFINITY.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Pure Infinity";
                case 1 -> "Rapid Infinity";
                case 2 -> "Precision Infinity";
                default -> "Unselected";
            };
        }
        if (UNBREAKING.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Rested Reserve";
                case 1 -> "Continuous Operation";
                case 2 -> "Protective Mode";
                default -> "Unselected";
            };
        }
        if ("minecraft:efficiency".equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Hard-Material Breaker";
                case 1 -> "Mining Rhythm";
                case 2 -> "Generalist Tool";
                default -> "Unselected";
            };
        }
        if ("minecraft:feather_falling".equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Soft Landing";
                case 1 -> "Impact Landing";
                case 2 -> "Aerial Recovery";
                default -> "Unselected";
            };
        }
        if (FORTUNE.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Ore Specialist";
                case 1 -> "Harvest Specialist";
                case 2 -> "High Variance";
                default -> "Unselected";
            };
        }
        if (RESPIRATION.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Deep Breath";
                case 1 -> "Quiet Breath";
                case 2 -> "Rapid Ventilation";
                default -> "Unselected";
            };
        }
        if (PROTECTION.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "General Defense";
                case 1 -> "First-Hit Defense";
                case 2 -> "Crisis Defense";
                default -> "Unselected";
            };
        }
        if (PROJECTILE_PROTECTION.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Frontal Guard";
                case 1 -> "Sniper Resistance";
                case 2 -> "Barrage Resistance";
                default -> "Unselected";
            };
        }
        if (SHARPNESS.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Duel";
                case 1 -> "Heavy Strike";
                case 2 -> "Execute";
                default -> "Unselected";
            };
        }
        if (SMITE.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Exorcism";
                case 1 -> "Holy Strike";
                case 2 -> "Gravebreaker";
                default -> "Unselected";
            };
        }
        if (BANE_OF_ARTHROPODS.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Binding Venom";
                case 1 -> "Swarm Extermination";
                case 2 -> "Antivenom";
                default -> "Unselected";
            };
        }
        if (FIRE_PROTECTION.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Rapid Extinguishing";
                case 1 -> "Heat Adaptation";
                case 2 -> "Lava Adaptation";
                default -> "Unselected";
            };
        }
        if (BLAST_PROTECTION.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Blast Anchor";
                case 1 -> "Epicenter Resistance";
                case 2 -> "Chain-Blast Resistance";
                default -> "Unselected";
            };
        }
        if (FIRE_ASPECT.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Long Burn";
                case 1 -> "Flash Burn";
                case 2 -> "Cauterize";
                default -> "Unselected";
            };
        }
        if (THORNS.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Retaliatory Spikes";
                case 1 -> "Entangling Thorns";
                case 2 -> "Stored Retaliation";
                default -> "Unselected";
            };
        }
        if (BREACH.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Heavy Armor Crusher";
                case 1 -> "Shield Breaker";
                case 2 -> "Fracture";
                default -> "Unselected";
            };
        }
        if (KNOCKBACK.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Launch";
                case 1 -> "Blowback";
                case 2 -> "Recoil Step";
                default -> "Unselected";
            };
        }
        if (PUNCH.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Blowback";
                case 1 -> "Launch";
                case 2 -> "Pinning Shot";
                default -> "Unselected";
            };
        }
        if (IMPALING.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Wet Hunt";
                case 1 -> "Harpoon";
                case 2 -> "Deep Hunter";
                default -> "Unselected";
            };
        }
        if (FLAME.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Long Burn";
                case 1 -> "Stacked Ignition";
                default -> "Unselected";
            };
        }
        if (DEPTH_STRIDER.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Current Rider";
                case 1 -> "Seabed Runner";
                case 2 -> "Diver";
                default -> "Unselected";
            };
        }
        if (AQUA_AFFINITY.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Submerged Mining";
                case 1 -> "Underwater Construction";
                case 2 -> "Current Adaptation";
                default -> "Unselected";
            };
        }
        if (LOOTING.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Herd Hunter";
                case 1 -> "Stripping";
                case 2 -> "Big-Game Hunter";
                default -> "Unselected";
            };
        }
        if (SOUL_SPEED.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Soul-Sole Conservation";
                case 1 -> "Lingering Momentum";
                case 2 -> "Soul Footing";
                default -> "Unselected";
            };
        }
        if (SWIFT_SNEAK.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Silent Sneak";
                case 1 -> "Combat Stance";
                case 2 -> "Builder's Sneak";
                default -> "Unselected";
            };
        }
        if (RIPTIDE.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Long Riptide";
                case 1 -> "Steering Riptide";
                case 2 -> "Ramming Riptide";
                default -> "Unselected";
            };
        }
        if (CHANNELING.equals(enchantmentId)) {
            return switch (branch) {
                case 0 -> "Chain Lightning";
                case 1 -> "Rain Channeling";
                case 2 -> "Conductor";
                default -> "Unselected";
            };
        }
        return switch (branch) {
            case 0 -> "Branch I";
            case 1 -> "Branch II";
            case 2 -> "Branch III";
            default -> "Unselected";
        };
    }

    private record BranchRef(int mastery, int branch) {}
    private record EnchantRef(String id, int level) {}
}
