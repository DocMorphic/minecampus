package dev.realworldmc.client;

import com.google.gson.*;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.ShaderInstance;
import org.lwjgl.opengl.*;
import java.nio.file.*;

/** GPU state recorded alongside all established native-route screenshots. */
public final class CampusReflectionChecks {
    private static final JsonArray frames=new JsonArray();
    public static void record(Minecraft mc,int stage,int expected)throws Exception{
        if(stage!=frames.size())throw new AssertionError("Reflection route is not sequential");
        var source=CampusReflections.class.getProtectionDomain().getCodeSource().getLocation();
        if(!source.toString().endsWith(".jar"))throw new AssertionError("Requires packaged reflection renderer");
        var field=MapRenderer.class.getDeclaredField("campusGroundShader");field.setAccessible(true);var shader=(ShaderInstance)field.get(null);
        float strength=GL20.glGetUniformf(shader.getId(),GL20.glGetUniformLocation(shader.getId(),"PlanarStrength"));
        if(strength!=0&&strength!=1)throw new AssertionError("Invalid reflection strength");
        if((stage==42||stage==43||stage==44||stage==46)&&strength!=1)throw new AssertionError("No active reflection on Galileo route camera "+stage);
        if(strength>0&&(CampusReflections.selected==null||CampusReflections.updates==0||CampusReflections.stateChecks!=CampusReflections.updates))throw new AssertionError("Unverified reflection pass");
        int active=GL11.glGetInteger(GL13.GL_ACTIVE_TEXTURE);GL13.glActiveTexture(GL13.GL_TEXTURE0+12);
        int binding=GL11.glGetInteger(GL11.GL_TEXTURE_BINDING_2D);GL13.glActiveTexture(active);
        int error=GL11.glGetError();if(error!=0||strength>0&&binding==0)throw new AssertionError("Reflection GL state invalid at route camera "+stage+": "+error);
        var frame=new JsonObject();frame.addProperty("stage",stage);frame.addProperty("gpuStrength",strength);frame.addProperty("textureBinding",binding);frame.addProperty("glError",error);frame.addProperty("reflectionUpdates",CampusReflections.updates);frame.addProperty("stateChecks",CampusReflections.stateChecks);frame.addProperty("fps",mc.getFps());
        if(strength>0){var p=CampusReflections.selected;frame.addProperty("planeTile",p.tile);frame.add("plane",new Gson().toJsonTree(new float[]{p.equation.x,p.equation.y,p.equation.z,p.equation.w}));}
        frames.add(frame);var result=new JsonObject();result.addProperty("status",frames.size()==expected?"PASS: packaged reflection state checked across the full native route":"RUNNING");result.addProperty("rendererJar",Path.of(source.toURI()).getFileName().toString());result.add("frames",frames);
        Files.writeString(Path.of("campus-reflection-route-result.json"),new GsonBuilder().setPrettyPrinting().create().toJson(result));
    }
}
