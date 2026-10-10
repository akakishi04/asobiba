package io.github.akakishi04.asobibatweaks.client;

import io.github.akakishi04.asobibatweaks.feature.FletchingCopyPreviewPayload;
import io.github.akakishi04.asobibatweaks.feature.FletchingCopyRequestPayload;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;
import net.neoforged.neoforge.network.PacketDistributor;

/**
 * A quantity selector and live XP-price preview for enchanted Arrow copying.
 * The GUI never mutates inventories: the server does all validation and
 * transactions, then returns an updated authoritative quote.
 */
public final class FletchingCopyScreen extends Screen {
    private FletchingCopyPreviewPayload quote;
    private int quantity = 1;
    private int refreshTicks;
    private boolean awaitingReply;
    private Button copyButton;

    private FletchingCopyScreen(FletchingCopyPreviewPayload quote) {
        super(Component.literal("Fletching Table - Enchanted Arrows"));
        this.quote = quote;
    }

    public static void open(FletchingCopyPreviewPayload payload) {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.screen instanceof FletchingCopyScreen current
                && current.quote.tablePos().equals(payload.tablePos())) {
            current.quote = payload;
            current.awaitingReply = false;
            current.quantity = Math.max(1,
                    Math.min(current.quantity, Math.max(1, payload.availableCount())));
            current.updateButtons();
            return;
        }
        minecraft.setScreen(new FletchingCopyScreen(payload));
    }

    @Override
    protected void init() {
        int cx = this.width / 2;
        int top = this.height / 2 - 94;

        addRenderableWidget(Button.builder(Component.literal("-10"),
                b -> change(-10)).bounds(cx - 145, top + 92, 54, 20).build());
        addRenderableWidget(Button.builder(Component.literal("-1"),
                b -> change(-1)).bounds(cx - 86, top + 92, 49, 20).build());
        addRenderableWidget(Button.builder(Component.literal("+1"),
                b -> change(1)).bounds(cx - 32, top + 92, 49, 20).build());
        addRenderableWidget(Button.builder(Component.literal("+10"),
                b -> change(10)).bounds(cx + 22, top + 92, 49, 20).build());
        addRenderableWidget(Button.builder(Component.literal("Max"),
                b -> {
                    quantity = maximumAffordable();
                    updateButtons();
                }).bounds(cx + 76, top + 92, 69, 20).build());

        copyButton = addRenderableWidget(Button.builder(
                Component.literal("Copy " + quantity + " arrows"),
                b -> purchase()
        ).bounds(cx - 145, top + 134, 190, 22).build());
        addRenderableWidget(Button.builder(Component.literal("Close"),
                b -> onClose()).bounds(cx + 52, top + 134, 93, 22).build());
        updateButtons();
    }

    private void change(int amount) {
        quantity = Math.max(1, Math.min(
                Math.max(1, quote.availableCount()), quantity + amount));
        updateButtons();
    }

    private int maximumAffordable() {
        if (quote.perArrowXp() <= 0L) return Math.max(1, quote.availableCount());
        return Math.max(1, (int)Math.min(
                Math.min(quote.availableCount(), 64),
                Math.min(quote.playerXp() / quote.perArrowXp(),
                        Integer.MAX_VALUE / quote.perArrowXp())));
    }

    private long totalXp() {
        return (long)quantity * quote.perArrowXp();
    }

    private void updateButtons() {
        if (copyButton == null) return;
        copyButton.setMessage(Component.literal("Copy " + quantity + " arrows"));
        copyButton.active = !awaitingReply && quote.error().isEmpty()
                && quote.availableCount() >= quantity
                && totalXp() <= quote.playerXp()
                && totalXp() <= Integer.MAX_VALUE;
    }

    private void purchase() {
        if (copyButton == null || !copyButton.active) return;
        awaitingReply = true;
        updateButtons();
        PacketDistributor.sendToServer(
                new FletchingCopyRequestPayload(quote.tablePos(), quantity));
    }

    @Override
    public void tick() {
        super.tick();
        if (++refreshTicks >= 40 && !awaitingReply) {
            refreshTicks = 0;
            if (minecraft != null && minecraft.player != null) {
                PacketDistributor.sendToServer(
                        new FletchingCopyRequestPayload(quote.tablePos(), 0));
            }
        }
    }

    @Override
    public void renderBackground(
            GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
        this.renderTransparentBackground(graphics);
    }

    @Override
    public void render(GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
        this.renderBackground(graphics, mouseX, mouseY, partialTick);

        int cx = this.width / 2;
        int top = this.height / 2 - 94;
        graphics.fill(cx - 158, top - 12, cx + 158, top + 177, 0xDF17191B);
        graphics.fill(cx - 158, top - 12, cx + 158, top - 10, 0xFFD6BD7C);
        graphics.drawCenteredString(this.font, "Enchanted Arrow Copies", cx,
                top - 3, 0xFFFFE5AB);

        if (minecraft != null && minecraft.player != null) {
            graphics.renderItem(minecraft.player.getMainHandItem(), cx - 140, top + 18);
        }
        graphics.drawString(this.font, quote.templateName(), cx - 119,
                top + 22, 0xFFEAEAEA, false);
        graphics.drawString(this.font, "Available material: " + quote.availableCount(),
                cx - 144, top + 46, 0xFFFFFFFF, false);
        graphics.drawString(this.font, "XP available: " + quote.playerXp()
                + "     Per arrow: " + quote.perArrowXp(),
                cx - 144, top + 60, 0xFFFFFFFF, false);

        int totalColor = quote.error().isEmpty() && totalXp() <= quote.playerXp()
                && totalXp() <= Integer.MAX_VALUE ? 0xFF98E0AA : 0xFFFF8888;
        graphics.drawCenteredString(this.font,
                "Selected: " + quantity + "     Total XP: " + totalXp(),
                cx, top + 79, totalColor);
        if (!quote.error().isEmpty()) {
            graphics.drawCenteredString(this.font, quote.error(),
                    cx, top + 120, 0xFFFF9393);
        } else if (totalXp() > quote.playerXp()) {
            graphics.drawCenteredString(this.font, "Insufficient experience",
                    cx, top + 120, 0xFFFF9393);
        } else {
            graphics.drawCenteredString(this.font,
                    "Source arrow is retained; ordinary arrows are consumed.",
                    cx, top + 120, 0xFFBFC6C9);
        }
        super.render(graphics, mouseX, mouseY, partialTick);
    }

    @Override
    public boolean isPauseScreen() {
        return false;
    }
}
