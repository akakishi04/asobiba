package io.github.akakishi04.asobibatweaks.client;

import io.github.akakishi04.asobibatweaks.feature.DailyPlayTimeHudState;
import io.github.akakishi04.asobibatweaks.feature.DailyPlayTimeNetworking;
import io.github.akakishi04.asobibatweaks.feature.DailyPlayTimePayload;
import net.minecraft.client.Minecraft;
import net.minecraft.network.Connection;
import net.minecraft.network.chat.Component;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.client.event.ClientPlayerNetworkEvent;
import net.neoforged.neoforge.client.event.ClientTickEvent;
import net.neoforged.neoforge.client.event.RenderGuiEvent;
import net.neoforged.neoforge.common.NeoForge;

/** Quiet top-left HUD; every displayed day/allowance originates at the server. */
public final class DailyPlayTimeClient {
    private final DailyPlayTimeHudState state = new DailyPlayTimeHudState();
    private static boolean registered;

    private DailyPlayTimeClient() {}

    public static void register() {
        if (registered) return;
        registered = true;
        DailyPlayTimeClient client = new DailyPlayTimeClient();
        DailyPlayTimeNetworking.installClientHandler(client::accept);
        NeoForge.EVENT_BUS.register(client);
    }

    private void accept(DailyPlayTimePayload payload, Connection source) {
        Minecraft minecraft = Minecraft.getInstance();
        synchronizeContext(minecraft);
        state.accept(source, payload.enabled(), payload.playedDays(), payload.remainingMillis(),
                payload.limitMillis(), payload.resetAtEpochMillis(), payload.paused(), System.nanoTime());
        state.advance(System.nanoTime(), minecraft.isPaused());
    }

    private void synchronizeContext(Minecraft minecraft) {
        Connection connection = minecraft.getConnection() == null
                ? null : minecraft.getConnection().getConnection();
        state.context(connection, minecraft.level);
    }

    @SubscribeEvent
    public void onLogout(ClientPlayerNetworkEvent.LoggingOut event) {
        state.clear();
    }

    @SubscribeEvent
    public void onClientTick(ClientTickEvent.Post event) {
        Minecraft minecraft = Minecraft.getInstance();
        synchronizeContext(minecraft);
        state.advance(System.nanoTime(), minecraft.isPaused());
    }

    @SubscribeEvent
    public void onRender(RenderGuiEvent.Post event) {
        Minecraft minecraft = Minecraft.getInstance();
        synchronizeContext(minecraft);
        state.advance(System.nanoTime(), minecraft.isPaused());
        if (!state.visible() || minecraft.player == null || minecraft.options.hideGui
                || minecraft.getDebugOverlay().showDebugScreen()) return;

        Component days = Component.translatable("hud.asobibatweaks.daily_play_time.days", state.playedDays());
        Component time = Component.translatable("hud.asobibatweaks.daily_play_time.remaining",
                DailyPlayTimeHudState.formatCountdown(state.remainingMillis()));
        if (state.paused()) time = time.copy().append(Component.translatable("hud.asobibatweaks.daily_play_time.paused"));
        else if (state.stale()) time = time.copy().append(Component.translatable("hud.asobibatweaks.daily_play_time.syncing"));
        int width = Math.max(minecraft.font.width(days), minecraft.font.width(time));
        var graphics = event.getGuiGraphics();
        graphics.fill(4, 4, width + 12, 29, 0x66101010);
        graphics.drawString(minecraft.font, days, 8, 7, 0xFFE0E0E0, false);
        graphics.drawString(minecraft.font, time, 8, 18,
                state.remainingMillis() <= 60_000 ? 0xFFFFC080 : 0xFFE0E0E0, false);
    }
}
