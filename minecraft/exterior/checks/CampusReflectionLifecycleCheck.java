package dev.realworldmc.client;

import com.google.gson.*;
import com.mojang.blaze3d.pipeline.TextureTarget;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import org.lwjgl.opengl.*;
import java.nio.file.*;
import java.util.Map;

/** Real disconnect/reopen lifecycle in the explicitly named copied QA world. */
public final class CampusReflectionLifecycleCheck implements ClientModInitializer {
    private static boolean active,opening;
    private static int ticks,ready;
    private static TextureTarget retired;
    private static JsonObject result;
    private static long beforeUpdates;
    private static volatile Throwable failure;
    @Override public void onInitializeClient(){ClientTickEvents.END_CLIENT_TICK.register(mc->{
        if(!active)return;
        try{tick(mc);}catch(Exception e){throw new IllegalStateException("Reflection lifecycle check",e);}
    });}
    public static void begin(Minecraft mc,JsonObject report)throws Exception{
        String world=System.getProperty("minecampus.checkWorld","");
        if(!world.matches("campus-check(-[a-z0-9]+)*")||!Path.of("").toAbsolutePath().getFileName().toString().equals("run-campus-check"))throw new AssertionError("Requires copied QA world");
        result=report;retired=target();beforeUpdates=CampusReflections.updates;active=true;mc.level.disconnect();mc.disconnect();
    }
    private static Object field(String name)throws Exception{var f=CampusReflections.class.getDeclaredField(name);f.setAccessible(true);return f.get(null);}
    private static TextureTarget target()throws Exception{return (TextureTarget)field("target");}
    private static void tick(Minecraft mc)throws Exception{
        if(failure!=null)throw new AssertionError("QA world did not reopen",failure);
        if(++ticks>1600)throw new AssertionError("Reflection lifecycle timed out");
        if(!opening){
            if(ticks<20)return;
            if(mc.level!=null||target()!=null||field("lastWorld")!=null||!((Map<?,?>)field("planes")).isEmpty()||retired.frameBufferId!=-1)
                throw new AssertionError("Reflection resources or world references survived disconnect");
            result.addProperty("disconnectDisposedReflectionTarget",true);result.addProperty("disconnectReleasedWorldAndPlanes",true);
            opening=true;mc.createWorldOpenFlows().openWorld(System.getProperty("minecampus.checkWorld"),()->failure=new AssertionError("QA reopen callback"));return;
        }
        if(mc.player==null||mc.level==null||mc.getOverlay()!=null)return;
        mc.setScreen(null);
        if(target()==null||CampusReflections.selected==null||CampusReflections.updates<=beforeUpdates||MapRenderer.INSTANCE.pendingTileSelection!=0){ready=0;return;}
        if(++ready<100)return;
        if(target()==retired||target().frameBufferId<0||field("lastWorld")!=mc.level)throw new AssertionError("No fresh reflection target/world after reopen");
        var f=MapRenderer.class.getDeclaredField("campusGroundShader");f.setAccessible(true);var shader=(net.minecraft.client.renderer.ShaderInstance)f.get(null);
        if(GL20.glGetUniformf(shader.getId(),GL20.glGetUniformLocation(shader.getId(),"PlanarStrength"))!=1f||GL11.glGetError()!=0)throw new AssertionError("Reflection did not resume cleanly");
        try(var image=Screenshot.takeScreenshot(mc.getMainRenderTarget())){image.writeToFile(Path.of("campus-reflection-functional-reopened.png"));}
        CampusReflections.capture(Path.of("campus-reflection-functional-target-reopened.png"));
        result.addProperty("reopenCreatedFreshReflectionTarget",true);
        result.addProperty("status","PASS: actual TNT, reflected terrain restoration, surviving glass, complete glass removal and real disconnect/reopen lifecycle verified in the copied QA world");
        Files.writeString(Path.of("campus-reflection-functional.json"),new GsonBuilder().setPrettyPrinting().create().toJson(result));
        active=false;mc.stop();
    }
}
