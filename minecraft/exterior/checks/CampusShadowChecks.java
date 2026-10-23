package dev.realworldmc.client;

import com.google.gson.*;
import net.minecraft.client.Minecraft;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import org.lwjgl.opengl.GL20;
import java.nio.file.*;

/** Reads the packaged shader's GPU uniforms along the normal native route. */
public final class CampusShadowChecks {
    private static final JsonArray frames=new JsonArray();
    public static void record(Minecraft mc,int stage,int expected)throws Exception{
        if(stage!=frames.size())throw new AssertionError("Shadow route is not sequential");
        var source=CampusShadows.class.getProtectionDomain().getCodeSource().getLocation();
        if(!source.toString().endsWith(".jar"))throw new AssertionError("Shadow renderer must come from the packaged JAR: "+source);
        var f=MapRenderer.class.getDeclaredField("campusGroundShader");f.setAccessible(true);var shader=(net.minecraft.client.renderer.ShaderInstance)f.get(null);
        float angle=mc.level.getTimeOfDay(1)*(float)(Math.PI*2);
        Vector3f light=new Matrix4f().rotateY(-(float)Math.PI/2).rotateX(angle).transformDirection(new Vector3f(0,1,0));
        float strength=.28f*Math.max(0,Math.min(1,(light.y-.04f)/.16f))*(1-mc.level.getRainLevel(1));
        if(light.y<0)light.negate();float[] actual=new float[3];GL20.glGetUniformfv(shader.getId(),GL20.glGetUniformLocation(shader.getId(),"CampusSunDirection"),actual);
        float shadow=GL20.glGetUniformf(shader.getId(),GL20.glGetUniformLocation(shader.getId(),"CampusShadowStrength"));
        if(light.distance(new Vector3f(actual[0],actual[1],actual[2]))>.0001f||Math.abs(shadow-strength)>.0001f||CampusShadows.updates==0)throw new AssertionError("Packaged route lighting mismatch at camera "+stage);
        var frame=new JsonObject();frame.addProperty("stage",stage);frame.addProperty("dayTime",mc.level.getDayTime());frame.add("gpuSunDirection",new Gson().toJsonTree(actual));frame.addProperty("gpuShadowStrength",shadow);frame.addProperty("shadowUpdates",CampusShadows.updates);frame.addProperty("shadowDraws",CampusShadows.draws);frame.addProperty("fps",mc.getFps());frames.add(frame);
        var report=new JsonObject();report.addProperty("status",frames.size()==expected?"PASS: packaged shadows and sky-consistent material lighting verified across the native route":"RUNNING");report.addProperty("rendererJar",Path.of(source.toURI()).getFileName().toString());report.add("frames",frames);
        Files.writeString(Path.of("campus-shadow-route-result.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));
    }
}
