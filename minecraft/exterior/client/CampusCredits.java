package dev.realworldmc.client;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.network.chat.Component;

/** Full map attribution, sized independently of oversized automatic HUD scales. */
public final class CampusCredits {
    private CampusCredits() {}

    /** Returns the panel top in ordinary GUI coordinates for controls above it. */
    public static int render(GuiGraphics graphics, String attribution, int color) {
        var mc = Minecraft.getInstance();
        var font = mc.font;
        // Integer physical pixels keep large automatic GUI scales from turning
        // several lines of licensing text into a substantial part of the view.
        double guiScale = mc.getWindow().getGuiScale();
        float scale = (float)(Math.min(3.0, guiScale) / guiScale);
        int width = (int)Math.floor(graphics.guiWidth() / scale);
        int bottom = (int)Math.floor(graphics.guiHeight() / scale) - 3;
        var lines = font.split(Component.literal(attribution), Math.max(1, width - 12));
        int top = bottom - lines.size() * font.lineHeight - 4;
        graphics.pose().pushPose();
        graphics.pose().scale(scale, scale, 1);
        graphics.fill(2, top, width - 2, bottom, 0x80000000);
        for (int i = 0; i < lines.size(); i++) {
            graphics.drawString(font, lines.get(i), 6, top + 2 + i * font.lineHeight, color, false);
        }
        graphics.pose().popPose();
        return (int)Math.floor(top * scale);
    }
}
