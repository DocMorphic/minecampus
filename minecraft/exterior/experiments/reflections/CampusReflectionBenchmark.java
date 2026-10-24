package dev.realworldmc.client;

import com.google.gson.*;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import java.nio.file.*;
import java.util.*;

/** Same-scene off/on/off comparison in the private experiment world. */
public final class CampusReflectionBenchmark {
    private static boolean started;
    private static volatile boolean reloading;
    private static volatile Throwable failure;
    private static int phase,ticks;
    private static final String[] NAMES={"west-off","west-on","west-off-again","southwest-on","east-on","north-on","north-night","north-reload-night","west-return-day"};
    private static final String[] CAMERAS={null,null,null,"50 65 -20 -90 -12","145 65 -115 90 -12","104 65 -156 0 -20",null,null,"72 65 -125 -90 -14"};
    private static boolean reflecting(){return phase!=0&&phase!=2;}
    private static void preparePhase(Minecraft mc){
        if(CAMERAS[phase]!=null||phase==6||phase==8){
            int next=phase;reloading=true;
            mc.getSingleplayerServer().execute(()->{
                try{
                    var server=mc.getSingleplayerServer();var commands=server.getCommands();var source=server.createCommandSourceStack().withSuppressedOutput();
                    if(CAMERAS[next]!=null)commands.performPrefixedCommand(source,"tp @a "+CAMERAS[next]);
                    if(next==6||next==8)commands.performPrefixedCommand(source,"time set "+(next==6?18000:6000));
                }catch(Throwable e){failure=e;}finally{reloading=false;}
            });
        }
        if(phase==7){reloading=true;mc.reloadResourcePacks().whenComplete((ignored,error)->{failure=error;reloading=false;});}
    }
    private static final JsonArray phases=new JsonArray();
    private static final List<Integer> fps=new ArrayList<>();
    private static List<String> original;
    public static void tick(Minecraft mc)throws Exception{
        if(failure!=null)throw new IllegalStateException("Reflection pack reload",failure);
        if(reloading)return;
        if(!started){
            started=true;reloading=true;
            var repository=mc.getResourcePackRepository();repository.reload();original=new ArrayList<>(repository.getSelectedIds());
            var selected=new ArrayList<>(original);selected.remove("file/campus-planar-reflection");selected.add("file/campus-planar-reflection");repository.setSelected(selected);
            mc.reloadResourcePacks().whenComplete((ignored,error)->{failure=error;reloading=false;});return;
        }
        CampusReflectionTrial.enabled=reflecting();
        if(++ticks==1){
            var resource=mc.getResourceManager().getResourceOrThrow(net.minecraft.resources.ResourceLocation.fromNamespaceAndPath("realworldmc","shaders/core/campus_ground.fsh"));
            try(var stream=resource.open()){
                if(!Arrays.equals(stream.readAllBytes(),Files.readAllBytes(Path.of("resourcepacks/campus-planar-reflection/assets/realworldmc/shaders/core/campus_ground.fsh"))))throw new AssertionError("Reflection shader override not active");
            }
        }
        if(ticks>120&&ticks%20==0)fps.add(mc.getFps());
        if(ticks<240)return;
        if(reflecting()&&(CampusReflectionTrial.selected==null||CampusReflectionTrial.updates==0||CampusReflectionTrial.stateChecks!=CampusReflectionTrial.updates))throw new AssertionError("No valid state-restored reflection was rendered");
        var result=new JsonObject();result.addProperty("phase",NAMES[phase]);result.addProperty("dayTime",mc.level.getDayTime());result.add("fpsSamples",new Gson().toJsonTree(fps));
        var sorted=new ArrayList<>(fps);Collections.sort(sorted);result.addProperty("medianFps",(sorted.get(2)+sorted.get(3))/2.0);
        result.addProperty("reflectionUpdates",CampusReflectionTrial.updates);result.addProperty("stateChecks",CampusReflectionTrial.stateChecks);result.addProperty("drawCalls",CampusReflectionTrial.draws);result.addProperty("lastSubmissionMilliseconds",CampusReflectionTrial.lastMilliseconds);result.addProperty("availableTextureUnits",CampusReflectionTrial.textureUnits);
        if(CampusReflectionTrial.selected!=null){
            var p=CampusReflectionTrial.selected;result.addProperty("planeTile",p.tile);result.add("plane",new Gson().toJsonTree(new float[]{p.equation.x,p.equation.y,p.equation.z,p.equation.w}));
        }
        var field=MapRenderer.class.getDeclaredField("campusGroundShader");field.setAccessible(true);
        var shader=(net.minecraft.client.renderer.ShaderInstance)field.get(null);
        var gpu=new JsonObject();
        for(String name:new String[]{"PlanarStrength","MaterialDetail","CampusShadowStrength","PlanarTexture"}){
            int loc=org.lwjgl.opengl.GL20.glGetUniformLocation(shader.getId(),name);
            gpu.addProperty(name,loc<0?-999:org.lwjgl.opengl.GL20.glGetUniformf(shader.getId(),loc));
        }
        result.add("gpuUniforms",gpu);
        if(Math.abs(gpu.get("PlanarStrength").getAsFloat()-(reflecting()?1:0))>.001||gpu.get("PlanarTexture").getAsInt()!=12)throw new AssertionError("Reflection GPU uniform mismatch");
        int active=org.lwjgl.opengl.GL11.glGetInteger(org.lwjgl.opengl.GL13.GL_ACTIVE_TEXTURE);
        org.lwjgl.opengl.GL13.glActiveTexture(org.lwjgl.opengl.GL13.GL_TEXTURE0+12);
        int binding=org.lwjgl.opengl.GL11.glGetInteger(org.lwjgl.opengl.GL11.GL_TEXTURE_BINDING_2D);
        org.lwjgl.opengl.GL13.glActiveTexture(active);
        result.addProperty("reflectionTextureBinding",binding);
        int error=org.lwjgl.opengl.GL11.glGetError();result.addProperty("glError",error);
        if(error!=0||reflecting()&&binding==0)throw new AssertionError("Invalid reflection texture or GL state: "+error);
        phases.add(result);
        try(var image=Screenshot.takeScreenshot(mc.getMainRenderTarget())){image.writeToFile(Path.of("campus-reflection-phase-"+phase+".png"));}
        if(reflecting())CampusReflectionTrial.capture(Path.of("campus-reflection-target-"+phase+".png"));
        Files.writeString(Path.of("campus-reflection-phase-"+phase+".json"),new GsonBuilder().setPrettyPrinting().create().toJson(result));
        if(++phase<NAMES.length){ticks=0;fps.clear();preparePhase(mc);return;}
        CampusReflectionTrial.enabled=false;mc.getResourcePackRepository().setSelected(original);
        var report=new JsonObject();report.addProperty("status","PASS: isolated reflection toggle, four stationary viewpoints, night and resource reload controls completed");
        report.addProperty("rendererJar",Path.of(MapRenderer.class.getProtectionDomain().getCodeSource().getLocation().toURI()).getFileName().toString());
        report.addProperty("scope","One nearby Galileo pane plane; callback prototype; map meshes only. Stationary viewpoint changes, night and reload tested. Continuous movement, gameplay, damage, provider coverage and production integration remain unverified.");report.add("phases",phases);
        Files.writeString(Path.of("campus-reflection-benchmark.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));mc.stop();
    }
}
