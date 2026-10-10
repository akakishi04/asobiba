package io.github.akakishi04.asobibatweaks.client;

import io.github.akakishi04.asobibatweaks.feature.VillageStatusPayload;
import io.github.akakishi04.asobibatweaks.feature.VillageStatusRequestPayload;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;
import net.neoforged.neoforge.network.PacketDistributor;

public final class VillageStatusScreen extends Screen {
    private VillageStatusPayload snapshot;
    private int tab;
    private int refreshTicks;

    public VillageStatusScreen(VillageStatusPayload snapshot) {
        super(Component.literal(snapshot.title()));
        this.snapshot = snapshot;
    }

    public static void open(VillageStatusPayload snapshot) {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.screen instanceof VillageStatusScreen current
                && current.snapshot.villageId().equals(snapshot.villageId())) {
            current.snapshot = snapshot;
            return;
        }
        minecraft.setScreen(new VillageStatusScreen(snapshot));
    }

    @Override
    protected void init() {
        int buttonWidth = 86;
        int gap = 4;
        int total = buttonWidth * 3 + gap * 2;
        int x = (this.width - total) / 2;
        int y = Math.max(26, this.height / 2 - 96);

        addRenderableWidget(Button.builder(Component.literal("Overview"), button -> tab = 0)
                .bounds(x, y, buttonWidth, 20).build());
        addRenderableWidget(Button.builder(Component.literal("Needs"), button -> tab = 1)
                .bounds(x + buttonWidth + gap, y, buttonWidth, 20).build());
        addRenderableWidget(Button.builder(Component.literal("Projects"), button -> tab = 2)
                .bounds(x + (buttonWidth + gap) * 2, y, buttonWidth, 20).build());
    }

    @Override
    public void tick() {
        super.tick();
        if (++refreshTicks < 40) return;
        refreshTicks = 0;

        if (this.minecraft != null && this.minecraft.player != null) {
            PacketDistributor.sendToServer(new VillageStatusRequestPayload(snapshot.villageId()));
        }
    }

    @Override
    public void renderBackground(GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
        this.renderTransparentBackground(graphics);
    }

    @Override
    public void render(GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
        this.renderBackground(graphics, mouseX, mouseY, partialTick);

        int panelWidth = Math.min(330, this.width - 24);
        int panelHeight = Math.min(230, this.height - 24);
        int left = (this.width - panelWidth) / 2;
        int top = (this.height - panelHeight) / 2;

        graphics.fill(left, top, left + panelWidth, top + panelHeight, 0xD0181818);
        graphics.fill(left, top, left + panelWidth, top + 2, 0xFF8A8A8A);
        graphics.drawCenteredString(this.font, snapshot.title(), this.width / 2, top + 8, 0xFFFFFF);

        int contentY = top + 48;
        if (tab == 0) renderOverview(graphics, left + 14, contentY);
        else if (tab == 1) renderList(graphics, left + 14, contentY, "Current needs", snapshot.needs());
        else renderList(graphics, left + 14, contentY, "Active projects", snapshot.projects());

        super.render(graphics, mouseX, mouseY, partialTick);
    }

    private void renderOverview(GuiGraphics graphics, int x, int y) {
        int line = 13;
        draw(graphics, x, y, "Population: " + snapshot.population()
                + " / sustainable " + snapshot.sustainablePopulation());
        draw(graphics, x, y += line, "Housing: " + snapshot.housingCapacity()
                + " (" + snapshot.spareHousing() + " spare)");
        draw(graphics, x, y += line, "Food reserve: " + formatTenths(snapshot.foodDaysTenths()) + " days");
        draw(graphics, x, y += line, "Average Welfare: " + snapshot.averageWelfare()
                + " [" + welfareBand(snapshot.averageWelfare()) + "]");
        draw(graphics, x, y += line, "Viability: " + snapshot.viability()
                + " [" + viabilityBand(snapshot.viability()) + "]");
        draw(graphics, x, y += line, "State: " + snapshot.lifecycle());
        draw(graphics, x, y += line, "Emergency: " + snapshot.emergency());
        draw(graphics, x, y += line, "Districts: " + snapshot.districtCount()
                + "   Outposts: " + snapshot.outpostCount());
    }

    private void renderList(GuiGraphics graphics, int x, int y, String heading, java.util.List<String> lines) {
        graphics.drawString(this.font, heading, x, y, 0xFFE7C86B, false);
        y += 16;

        if (lines.isEmpty()) {
            graphics.drawString(this.font, "None", x, y, 0xFFA0A0A0, false);
            return;
        }

        for (String line : lines) {
            graphics.drawString(this.font, "- " + line, x, y, 0xFFFFFFFF, false);
            y += 16;
        }
    }

    private void draw(GuiGraphics graphics, int x, int y, String text) {
        graphics.drawString(this.font, text, x, y, 0xFFFFFFFF, false);
    }

    private static String formatTenths(int tenths) {
        return (tenths / 10) + "." + Math.abs(tenths % 10);
    }

    private static String welfareBand(int welfare) {
        if (welfare < 20) return "Refusing";
        if (welfare < 40) return "Poor";
        if (welfare < 60) return "Strained";
        if (welfare < 80) return "Good";
        return "Healthy";
    }

    private static String viabilityBand(int viability) {
        if (viability < 20) return "Collapse";
        if (viability < 40) return "Migration pressure";
        if (viability < 60) return "Strained";
        return "Stable";
    }

    @Override
    public boolean isPauseScreen() {
        return false;
    }
}
