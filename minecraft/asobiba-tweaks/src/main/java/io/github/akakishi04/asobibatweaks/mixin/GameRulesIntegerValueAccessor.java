package io.github.akakishi04.asobibatweaks.mixin;

import java.util.function.BiConsumer;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.level.GameRules;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Invoker;

/** Reuses vanilla's bounded argument type for both the creation screen and /gamerule. */
@Mixin(GameRules.IntegerValue.class)
public interface GameRulesIntegerValueAccessor {
    @Invoker("create")
    static GameRules.Type<GameRules.IntegerValue> asobiba$createBounded(
            int defaultValue, int min, int max,
            BiConsumer<MinecraftServer, GameRules.IntegerValue> listener) {
        throw new AssertionError("Mixin did not transform bounded game-rule factory");
    }
}
