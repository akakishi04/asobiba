package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import net.minecraft.core.BlockPos;
import net.minecraft.core.component.DataComponents;
import net.minecraft.core.registries.Registries;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.EquipmentSlot;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;
import net.neoforged.neoforge.event.level.ExplosionKnockbackEvent;
import net.neoforged.bus.api.EventPriority;
import net.neoforged.bus.api.SubscribeEvent;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.animal.Pig;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.item.enchantment.EnchantmentHelper;
import net.minecraft.world.item.enchantment.Enchantments;
import net.minecraft.world.phys.Vec3;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class CombatRecoveryMasteryGameTests {
    private static final BlockPos MARK = new BlockPos(4, 2, 4);
    private CombatRecoveryMasteryGameTests() {}

    @GameTest(template = "empty16x6x9", batch = "combat_recovery")
    public static void reserveNegatesWholeRealDurabilityEventAndSpendsOneCharge(GameTestHelper h) {
        ServerPlayer player = player(h);
        ItemStack stack = enchanted(h, Items.DIAMOND_PICKAXE, Enchantments.UNBREAKING, 1, 100, 0);
        CompoundTag root = stack.getOrDefault(DataComponents.CUSTOM_DATA, CustomData.EMPTY).copyTag();
        CompoundTag runtime = new CompoundTag();
        runtime.putInt("branch", 0);
        runtime.putLong("last_tick", h.getLevel().getGameTime());
        runtime.putInt("reserve", 3);
        root.put("asobibatweaks_unbreaking_runtime", runtime);
        stack.set(DataComponents.CUSTOM_DATA, CustomData.of(root));
        for (int remaining = 2; remaining >= 0; remaining--) {
            stack.hurtAndBreak(100, h.getLevel(), player, item -> {});
            int reserve = stack.get(DataComponents.CUSTOM_DATA).copyTag()
                    .getCompound("asobibatweaks_unbreaking_runtime").getInt("reserve");
            if (stack.getDamageValue() != 0 || reserve != remaining) {
                h.fail("One charge must negate an entire multi-point native wear event; reserve=" + reserve, MARK);
                return;
            }
        }
        stack.hurtAndBreak(100, h.getLevel(), player, item -> {});
        if (stack.getDamageValue() <= 3) {
            h.fail("Exhausted reserve must restore ordinary multi-point Unbreaking loss", MARK); return;
        }
        h.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "combat_recovery")
    public static void windBranchesScaleActualNativeLaunchAndPreserveOtherMotion(GameTestHelper h) {
        ServerPlayer player = player(h);
        Pig target = pig(h, 6.0D, 4.5D);
        ItemStack mace = enchanted(h, Items.MACE, Enchantments.WIND_BURST, 2, 0, -1);
        player.setItemInHand(InteractionHand.MAIN_HAND, mace);
        Vec3 start = new Vec3(0.23D, -0.8D, -0.17D);
        LaunchResult vanilla = observedBurst(h, player, target, start);
        if (vanilla.nativeImpulse().y <= 0.0D) { h.fail("Native Wind Burst fixture produced no launch", MARK); return; }
        var wind = h.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT).getOrThrow(Enchantments.WIND_BURST);
        EnchantmentMasteryData.addMastery(mace, wind, 100);
        EnchantmentMasteryData.cycleBranch(mace, wind);
        LaunchResult updraft = observedBurst(h, player, target, start);
        EnchantmentMasteryData.cycleBranch(mace, wind);
        EnchantmentMasteryData.cycleBranch(mace, wind);
        LaunchResult controlled = observedBurst(h, player, target, start);
        player.fallDistance = 0.0F;
        player.setDeltaMovement(start);
        EnchantmentHelper.doPostAttackEffects(h.getLevel(), target, player.damageSources().playerAttack(player));
        Vec3 nativeImpulse = vanilla.nativeImpulse();
        // PhysicsTransportEvents applies independent wind pressure during Detonate,
        // before the native knockback event. Never multiply that pre-existing motion.
        if (!near(vanilla.total(), vanilla.otherImpulse().add(nativeImpulse))
                || !near(updraft.nativeImpulse(), nativeImpulse)
                || !near(controlled.nativeImpulse(), nativeImpulse)
                || !near(updraft.otherImpulse(), vanilla.otherImpulse())
                || !near(controlled.otherImpulse(), vanilla.otherImpulse())
                || !near(updraft.total(), vanilla.otherImpulse().add(nativeImpulse.multiply(1.0D, 1.30D, 1.0D)))
                || !near(controlled.total(), vanilla.otherImpulse().add(nativeImpulse.scale(0.90D)))
                || !player.getDeltaMovement().equals(start)) {
            h.fail("Wind branches must scale only the observed native launch and preserve independent pressure/motion: vanilla="
                    + vanilla + ", updraft=" + updraft + ", control=" + controlled
                    + ", failed=" + player.getDeltaMovement() + ", start=" + start, MARK); return;
        }
        target.discard();
        h.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "combat_recovery")
    public static void battleRhythmChangesRealAttackRecoveryNotDamageAndIsConsumed(GameTestHelper h) {
        ServerPlayer player = player(h);
        ItemStack sword = enchanted(h, Items.DIAMOND_SWORD, Enchantments.SWEEPING_EDGE, 3, 100, 2);
        player.setItemInHand(InteractionHand.MAIN_HAND, sword);
        player.getAttribute(Attributes.ATTACK_SPEED).setBaseValue(4.0D);
        player.getAttribute(Attributes.ATTACK_DAMAGE).setBaseValue(5.0D);
        player.getPersistentData().putLong("asobibatweaks_sweep_rhythm_until", h.getLevel().getGameTime() + 40L);
        player.resetAttackStrengthTicker();
        player.setOnGround(false);
        player.fallDistance = 0;
        Pig target = pig(h, 4.5D, 5.5D);
        float health = target.getHealth();
        float scale = player.getAttackStrengthScale(0.5F);
        float expected = (float)player.getAttributeValue(Attributes.ATTACK_DAMAGE) * (0.2F + scale * scale * 0.8F);
        player.attack(target);
        float loss = health - target.getHealth();
        float recovered = player.getAttackStrengthScale(0.0F);
        player.attack(target);
        if (Math.abs(loss - expected) > 0.001F || recovered <= 0.0F
                || player.getAttackStrengthScale(0.0F) != 0.0F
                || player.getPersistentData().contains("asobibatweaks_sweep_rhythm_until")) {
            h.fail("Rhythm must speed one native recovery without damage bonus, loss=" + loss + ", expected=" + expected, MARK); return;
        }
        target.discard();
        h.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "combat_recovery")
    public static void realTwoTargetSweepEarnsNonStackingRhythm(GameTestHelper h) {
        ServerPlayer player = player(h);
        player.setItemInHand(InteractionHand.MAIN_HAND,
                enchanted(h, Items.DIAMOND_SWORD, Enchantments.SWEEPING_EDGE, 3, 100, 2));
        // ServerPlayer.tick does not call Player.tick. The connection normally
        // invokes doTick, which advances the real attackStrengthTicker.
        for (int i = 0; i < 25; i++) player.doTick();
        if (player.getAttackStrengthScale(0.5F) <= 0.9F) {
            h.fail("Native player recovery fixture must be fully charged before a sweep", MARK); return;
        }
        position(h, player);
        player.setOnGround(true);
        player.setSprinting(false);
        Pig primary = pig(h, 4.5D, 5.5D);
        Pig secondary = pig(h, 5.0D, 5.5D);
        float initial = secondary.getHealth();
        player.attack(primary);
        if (secondary.getHealth() >= initial) {
            h.fail("Native two-target sweep did not hit the secondary fixture", MARK); return;
        }
        h.runAfterDelay(2, () -> {
            // A mock connection does not perform the normal player lifecycle tick.
            NeoForge.EVENT_BUS.post(new PlayerTickEvent.Post(player));
            long until = player.getPersistentData().getLong("asobibatweaks_sweep_rhythm_until");
            primary.discard(); secondary.discard();
            if (until <= h.getLevel().getGameTime() || until > h.getLevel().getGameTime() + 40L) {
                h.fail("A real primary-plus-secondary sweep must earn bounded next-attack rhythm", MARK); return;
            }
            h.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", batch = "combat_recovery")
    public static void aerialControlScalesRealInputWithoutCameraThrustOrMultiplicativeStacking(GameTestHelper h) {
        ServerPlayer player = player(h);
        player.setItemInHand(InteractionHand.MAIN_HAND,
                enchanted(h, Items.MACE, Enchantments.WIND_BURST, 2, 100, 2));
        player.setItemSlot(EquipmentSlot.FEET,
                enchanted(h, Items.DIAMOND_BOOTS, Enchantments.FEATHER_FALLING, 4, 100, 2));
        Pig target = pig(h, 6.0D, 4.5D);
        burst(h, player, target, Vec3.ZERO);
        player.setYRot(0.0F);
        player.setDeltaMovement(0.0D, -0.5D, 0.0D);
        NeoForge.EVENT_BUS.post(new PlayerTickEvent.Post(player));
        player.moveRelative(0.02F, Vec3.ZERO);
        Vec3 withoutInput = player.getDeltaMovement();
        player.moveRelative(0.02F, new Vec3(0, 0, 1));
        Vec3 withInput = player.getDeltaMovement();
        player.setDeltaMovement(0.0D, -0.5D, 0.0D);
        player.setOnGround(true);
        player.moveRelative(0.02F, new Vec3(0, 0, 1));
        Vec3 grounded = player.getDeltaMovement();
        player.setOnGround(false);
        player.getPersistentData().putLong("asobibatweaks_wind_aerial_control_until", h.getLevel().getGameTime());
        player.setDeltaMovement(0.0D, -0.5D, 0.0D);
        player.moveRelative(0.02F, new Vec3(0, 0, 1));
        Vec3 expired = player.getDeltaMovement();
        if (!near(withoutInput.x, 0) || !near(withoutInput.z, 0) || !near(withoutInput.y, -0.5D)
                || !near(withInput.z, 0.034D) || !near(withInput.y, -0.5D)
                || !near(grounded.z, 0.02D) || !near(expired.z, 0.027D)) {
            h.fail("Aerial steering must scale actual input +70%, preserve gravity/no-input, and use strongest bonus only", MARK);
            return;
        }
        target.discard();
        h.succeed();
    }

    private record LaunchResult(Vec3 nativeImpulse, Vec3 otherImpulse, Vec3 total) {}

    /** Observe the native vector before the NORMAL-priority mastery subscriber changes it. */
    public static final class NativeLaunchProbe {
        private final ServerPlayer player;
        private final Vec3 initial;
        private Vec3 nativeImpulse;
        private Vec3 otherImpulse;
        private int calls;
        private NativeLaunchProbe(ServerPlayer player, Vec3 initial) {
            this.player = player;
            this.initial = initial;
        }
        @SubscribeEvent(priority = EventPriority.HIGHEST)
        public void capture(ExplosionKnockbackEvent event) {
            if (event.getAffectedEntity() != player) return;
            calls++;
            nativeImpulse = event.getKnockbackVelocity();
            otherImpulse = player.getDeltaMovement().subtract(initial);
        }
    }

    private static LaunchResult observedBurst(GameTestHelper h, ServerPlayer player, Pig target, Vec3 initial) {
        NativeLaunchProbe probe = new NativeLaunchProbe(player, initial);
        NeoForge.EVENT_BUS.register(probe);
        try {
            Vec3 total = burst(h, player, target, initial);
            if (probe.calls != 1 || probe.nativeImpulse == null || probe.otherImpulse == null) {
                throw new IllegalStateException("Expected exactly one actual native self-launch event, saw " + probe.calls);
            }
            return new LaunchResult(probe.nativeImpulse, probe.otherImpulse, total);
        } finally {
            NeoForge.EVENT_BUS.unregister(probe);
        }
    }

    private static boolean near(Vec3 a, Vec3 b) {
        return near(a.x, b.x) && near(a.y, b.y) && near(a.z, b.z);
    }

    private static Vec3 burst(GameTestHelper h, ServerPlayer player, Pig target, Vec3 initial) {
        position(h, player);
        player.setOnGround(false);
        player.fallDistance = 4.0F;
        player.setDeltaMovement(initial);
        EnchantmentHelper.doPostAttackEffects(h.getLevel(), target, player.damageSources().playerAttack(player));
        return player.getDeltaMovement().subtract(initial);
    }
    private static boolean near(double a, double b) { return Math.abs(a - b) < 0.00001D; }
    private static ServerPlayer player(GameTestHelper h) {
        var player = h.makeMockServerPlayerInLevel();
        player.getAbilities().instabuild = false;
        player.getAbilities().flying = false;
        player.getAbilities().mayfly = false;
        position(h, player);
        return player;
    }
    private static void position(GameTestHelper h, ServerPlayer player) {
        BlockPos at = h.absolutePos(MARK);
        player.setPos(at.getX() + 0.5D, at.getY(), at.getZ() + 0.5D);
        player.setDeltaMovement(Vec3.ZERO);
    }
    private static Pig pig(GameTestHelper h, double x, double z) {
        var pig = EntityType.PIG.create(h.getLevel());
        if (pig == null) throw new IllegalStateException("No pig");
        var pos = h.absoluteVec(new Vec3(x, 2.0D, z));
        pig.setPos(pos.x, pos.y, pos.z);
        pig.setNoAi(true);
        pig.getAttribute(Attributes.MAX_HEALTH).setBaseValue(100.0D);
        pig.setHealth(100.0F);
        if (!h.getLevel().addFreshEntity(pig)) throw new IllegalStateException("No target");
        return pig;
    }
    private static ItemStack enchanted(GameTestHelper h, Item item, ResourceKey<Enchantment> key,
            int level, int mastery, int branch) {
        ItemStack stack = new ItemStack(item);
        var enchantment = h.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT).getOrThrow(key);
        stack.enchant(enchantment, level);
        if (mastery > 0) EnchantmentMasteryData.addMastery(stack, enchantment, mastery);
        for (int i = 0; i <= branch; i++) EnchantmentMasteryData.cycleBranch(stack, enchantment);
        return stack;
    }
}
