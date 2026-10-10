package io.github.akakishi04.asobibatweaks.feature;

import net.minecraft.server.level.ServerLevel;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.level.LevelEvent;
import net.neoforged.neoforge.event.tick.LevelTickEvent;

/** One bounded scheduling pass per server dimension; all cosmetics use native tracking packets. */
public final class AmbientOddityEvents {
    @SubscribeEvent
    public void onLevelTick(LevelTickEvent.Post event) {
        if (event.getLevel() instanceof ServerLevel level) AmbientOddityService.tick(level);
    }

    @SubscribeEvent
    public void onUnload(LevelEvent.Unload event) {
        if (event.getLevel() instanceof ServerLevel level) AmbientOddityService.clear(level);
    }
}
