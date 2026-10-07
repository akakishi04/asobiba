package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.ChatFormatting;
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
import net.minecraft.tags.DamageTypeTags;
import net.minecraft.tags.EntityTypeTags;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.LivingEntity;
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
import net.neoforged.neoforge.event.entity.living.LivingDamageEvent;
import net.neoforged.neoforge.event.entity.living.LivingDeathEvent;
import net.neoforged.neoforge.event.entity.living.LivingHurtEvent;
import net.neoforged.neoforge.event.entity.living.LivingFallEvent;
import net.neoforged.neoforge.event.entity.player.AnvilRepairEvent;
import net.neoforged.neoforge.event.entity.player.ItemTooltipEvent;
import net.neoforged.neoforge.event.entity.player.PlayerEvent;
import net.neoforged.neoforge.event.level.BlockDropsEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

public final class EnchantmentTweaksEvents {
    private static final int BRANCH_THRESHOLD = 50;
    private static final String FORTUNE = "minecraft:fortune";
    private static final String SILK_TOUCH = "minecraft:silk_touch";
    private static final String RESPIRATION = "minecraft:respiration";
    private static final String PROTECTION = "minecraft:protection";
    private static final String PROJECTILE_PROTECTION = "minecraft:projectile_protection";
    private static final String SHARPNESS = "minecraft:sharpness";
    private static final String SMITE = "minecraft:smite";
    private static final String BANE_OF_ARTHROPODS = "minecraft:bane_of_arthropods";
    private static final String FIRE_PROTECTION = "minecraft:fire_protection";
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

    @SubscribeEvent
    public void onBlockDrops(BlockDropsEvent event) {
        if (!(event.getBreaker() instanceof ServerPlayer player)
                || !AsobibaTweaksConfig.GROWING_ENCHANTMENTS_ENABLED.getAsBoolean()) return;

        ItemStack tool = event.getTool();
        gain(player, tool, 1);

        if (AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) {
            applyFortuneBranch(event, tool, player);
        }
    }

    @SubscribeEvent
    public void onSharpnessHurt(LivingHurtEvent event) {
        if (!(event.getSource().getEntity() instanceof ServerPlayer player)
                || event.getSource().getDirectEntity() != player
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
    public void onBaneHurt(LivingHurtEvent event) {
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
    public void onSmiteHurt(LivingHurtEvent event) {
        if (!(event.getSource().getEntity() instanceof ServerPlayer player)
                || event.getSource().getDirectEntity() != player
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
    public void onHolyStrikeOutgoingDamage(LivingHurtEvent event) {
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
    public void onBreakSpeed(PlayerEvent.BreakSpeed event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) return;
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
    public void onAntivenomDamage(LivingDamageEvent event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()
                || event.getAmount() <= 0.0F
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
            event.setAmount((float)(event.getAmount() * (1.0D - reduction)));
        }
    }

    @SubscribeEvent
    public void onFireProtectionDamage(LivingDamageEvent event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getAmount() <= 0.0F
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
            event.setAmount((float)(event.getAmount() * (1.0D - reduction)));
        }
    }

    @SubscribeEvent
    public void onLivingDamage(LivingDamageEvent event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getAmount() <= 0.0F
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
            event.setAmount((float)(event.getAmount() * Math.max(0.0D, 1.0D - reduction)));
        }
    }

    @SubscribeEvent
    public void onProjectileProtectionDamage(LivingDamageEvent event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || player.level().isClientSide()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getAmount() <= 0.0F
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
            event.setAmount((float)(event.getAmount() * Math.max(0.0D, 1.0D - reduction)));
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

    private static int enchantmentLevel(ItemStack stack, String enchantmentId) {
        for (var entry : EnchantmentMasteryData.enchantments(stack).entrySet()) {
            if (enchantmentId.equals(EnchantmentMasteryData.id(entry.getKey()))) {
                return entry.getIntValue();
            }
        }
        return 0;
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
        return "minecraft:efficiency".equals(enchantmentId)
                || "minecraft:feather_falling".equals(enchantmentId)
                || FORTUNE.equals(enchantmentId)
                || RESPIRATION.equals(enchantmentId)
                || PROTECTION.equals(enchantmentId)
                || PROJECTILE_PROTECTION.equals(enchantmentId)
                || SHARPNESS.equals(enchantmentId)
                || SMITE.equals(enchantmentId)
                || BANE_OF_ARTHROPODS.equals(enchantmentId)
                || FIRE_PROTECTION.equals(enchantmentId);
    }

    private static String branchName(String enchantmentId, int branch) {
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
