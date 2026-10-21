package dev.realworldmc.client;

import dev.realworldmc.EarthConfig;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientLifecycleEvents;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.world.level.GameType;
import java.nio.file.Files;
import java.nio.file.Path;

/** Hidden, isolated native-client captures; not included in the distributed datapack. */
public final class MensaClientCheck implements ClientModInitializer {
    private boolean opened, moved;
    private int ticks, stage, total;
    private volatile Throwable failure;
    private static final String[] NAMES = {"mensa-exterior.png", "mensa-foyer.png", "mensa-dining.png", "mensa-courtyard.png"};
    private static final String[] CAMERAS = {
        "94 91 107 136 16",
        "49 66.6 69 180 0",
        "67 72.6 61 135 0",
        "28 66.6 57 180 -8"
    };

    @Override public void onInitializeClient() {
        ClientLifecycleEvents.CLIENT_STARTED.register(mc -> {
            org.lwjgl.glfw.GLFW.glfwHideWindow(mc.getWindow().getWindow());
            EarthConfig.get().setupComplete = true;
            EarthConfig.get().autoSpaceFlight = false;
            mc.options.pauseOnLostFocus = false;
            mc.options.renderDistance().set(10);
            mc.options.simulationDistance().set(4);
            mc.options.hideGui = true;
            mc.options.getSoundSourceOptionInstance(net.minecraft.sounds.SoundSource.MASTER).set(0.0);
        });
        ClientTickEvents.END_CLIENT_TICK.register(this::tick);
    }

    private void tick(Minecraft mc) {
        try {
            if (++total > 2400) throw new AssertionError("Native Mensa client capture timed out");
            if (failure != null) throw new AssertionError("Integrated server check failed", failure);
            if (!opened && mc.getOverlay()==null) {
                opened=true;
                mc.createWorldOpenFlows().openWorld("mensa-check", () -> fail(mc, new AssertionError("QA save did not open")));
            }
            if (mc.screen instanceof net.minecraft.client.gui.screens.ConfirmScreen
                || mc.screen instanceof net.minecraft.client.gui.screens.BackupConfirmScreen) {
                for (var child : mc.screen.children()) if (child instanceof net.minecraft.client.gui.components.Button button) {
                    String label = button.getMessage().getString();
                    if (label.equals("Proceed") || label.equals("Yes") || label.equals("I know what I'm doing!")
                        || button.getMessage().getContents() instanceof net.minecraft.network.chat.contents.TranslatableContents text
                        && text.getKey().equals("selectWorld.backupJoinSkipButton")) {
                        button.onPress(); return;
                    }
                }
            }
            if (mc.player==null || mc.getSingleplayerServer()==null || mc.getOverlay()!=null) return;
            if (!moved) {
                moved=true; ticks=0; mc.setScreen(null);
                var server=mc.getSingleplayerServer(); var playerId=mc.player.getUUID();
                String camera=CAMERAS[stage];
                server.execute(() -> {
                    try {
                        var player=server.getPlayerList().getPlayer(playerId);
                        player.setGameMode(GameType.SPECTATOR);
                        var source=player.createCommandSourceStack().withPermission(4);
                        server.getCommands().performPrefixedCommand(source, "execute in minecampus_mensa:study run tp @s " + camera);
                        server.getCommands().performPrefixedCommand(source, "time set noon");
                        server.getCommands().performPrefixedCommand(source, "weather clear");
                    } catch (Throwable error) { failure=error; }
                });
                return;
            }
            if (++ticks < 120) return;
            try (var image=Screenshot.takeScreenshot(mc.getMainRenderTarget())) {
                image.writeToFile(Path.of(NAMES[stage]));
            }
            if (++stage==NAMES.length) {
                Files.writeString(Path.of("mensa-client-result.txt"), "PASS: four native Minecraft views captured from the generated Mensa structure");
                mc.stop(); return;
            }
            moved=false;
        } catch(Throwable error) { fail(mc,error); }
    }

    private static void fail(Minecraft mc,Throwable error) {
        error.printStackTrace();
        try {Files.writeString(Path.of("mensa-client-result.txt"), "FAIL: " + error);} catch(Exception ignored) {}
        mc.stop();
    }
}
