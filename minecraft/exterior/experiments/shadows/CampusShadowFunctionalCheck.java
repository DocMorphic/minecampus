package dev.realworldmc.client;

import com.google.gson.*;
import com.mojang.blaze3d.pipeline.TextureTarget;
import com.mojang.blaze3d.platform.GlStateManager;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.block.state.BlockState;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import org.joml.Vector4f;
import org.lwjgl.opengl.*;
import java.nio.file.*;
import java.util.*;

/** Destructive fixtures are confined to the existing native QA save. */
public final class CampusShadowFunctionalCheck {
    private static final String PACK="file/campus-shadow-functional";
    private static final Path ROOT=Path.of("resourcepacks/campus-shadow-functional");
    private static final BlockPos TARGET=new BlockPos(44,64,-63);
    private static boolean started,reloading,checking;
    private static volatile Throwable failure;
    private static volatile boolean verified,restored;
    private static Map<Long,BlockState> priorEdits;
    private static int phase,ticks,newEdits,changed;
    private static List<String> originalPacks;
    private static float[] before;
    private static Matrix4f beforeMatrix;
    private static int cropX,cropY;
    private static long nightUpdates=-1;
    private static int nightReadyTick;
    private static double dayLuminance;
    private static final JsonObject report=new JsonObject();
    private static final JsonArray lighting=new JsonArray();

    public static void tick(Minecraft mc)throws Exception{
        if(failure!=null)throw new IllegalStateException("Shadow functional check",failure);
        if(reloading)return;
        if(!started){
            if(!Path.of("").toAbsolutePath().getFileName().toString().equals("run-campus-check"))throw new AssertionError("Shadow fixtures require the isolated QA directory");
            started=true;reloading=true;
            var repo=mc.getResourcePackRepository();repo.reload();originalPacks=new ArrayList<>(repo.getSelectedIds());originalPacks.remove(PACK);
            var selected=new ArrayList<>(originalPacks);selected.add(PACK);repo.setSelected(selected);
            mc.reloadResourcePacks().whenComplete((ignored,error)->mc.execute(()->{
                failure=error;
                try{var prepared=CampusMaterials.class.getDeclaredField("prepared");prepared.setAccessible(true);Arrays.fill((int[])prepared.get(null),-1);}catch(Throwable e){failure=e;}
                CampusShadowTrial.enabled=true;CampusShadowTrial.dynamicSun=true;reloading=false;
            }));
            return;
        }
        ++ticks;
        if(phase==0&&ticks>=80){
            var location=net.minecraft.resources.ResourceLocation.fromNamespaceAndPath("realworldmc","shaders/core/campus_ground.fsh");
            try(var input=mc.getResourceManager().getResource(location).orElseThrow().open()){
                if(!Arrays.equals(input.readAllBytes(),Files.readAllBytes(ROOT.resolve("assets/realworldmc/shaders/core/campus_ground.fsh"))))throw new AssertionError("Functional shader override not applied");
            }
            if(CampusShadows.updates<3)throw new AssertionError("No live shadow updates");
            beforeMatrix=matrix();var p=beforeMatrix.transform(new Vector4f(44.5f,64.5f,-62.5f,1));p.div(p.w);
            cropX=(int)((p.x*.5f+.5f)*CampusShadows.SIZE)-256;cropY=(int)((p.y*.5f+.5f)*CampusShadows.SIZE)-256;
            before=depth();dayLuminance=capture(mc,"before");light(mc,"noon");
            mc.getSingleplayerServer().execute(()->{
                try{
                    var world=mc.getSingleplayerServer().overworld();
                    if(!dev.realworldmc.EarthBlocks.isMapBlock(world.getBlockState(TARGET)))throw new AssertionError("TNT fixture is not intact surveyed terrain");
                    priorEdits=new HashMap<>(dev.realworldmc.MapEdits.storage(world).original);
                    var player=mc.getSingleplayerServer().getPlayerList().getPlayer(mc.player.getUUID());
                    var tnt=new net.minecraft.world.entity.item.PrimedTnt(world,44.5,67,-62.5,player);tnt.setFuse(30);world.addFreshEntity(tnt);
                }catch(Throwable e){failure=e;}
            });
            phase=1;ticks=0;return;
        }
        if(phase==1&&ticks>=120){
            if(!verified){
                if(!checking){checking=true;mc.getSingleplayerServer().execute(()->{
                    try{
                        var world=mc.getSingleplayerServer().overworld();var history=dev.realworldmc.MapEdits.storage(world);
                        newEdits=(int)history.original.keySet().stream().filter(k->!priorEdits.containsKey(k)).count();
                        if(newEdits==0||!world.getBlockState(TARGET).isAir())throw new AssertionError("Actual TNT did not excavate the target");
                        verified=true;
                    }catch(Throwable e){failure=e;}
                });}
                return;
            }
            if(!beforeMatrix.equals(matrix(),1e-6f))throw new AssertionError("Camera/light matrix changed during TNT comparison");
            changed=difference(before,depth());if(changed<100)throw new AssertionError("TNT changed too few shadow depth samples: "+changed);
            report.addProperty("newTntEdits",newEdits);report.addProperty("changedDepthSamples",changed);capture(mc,"excavated");
            mc.getSingleplayerServer().execute(()->{
                try{
                    var world=mc.getSingleplayerServer().overworld();var history=dev.realworldmc.MapEdits.storage(world);
                    var guard=dev.realworldmc.CampusCollision.class.getDeclaredField("updating");guard.setAccessible(true);var applying=(ThreadLocal<Boolean>)guard.get(null);
                    applying.set(true);
                    try{for(var e:new HashMap<>(history.original).entrySet())if(!priorEdits.containsKey(e.getKey())){world.setBlock(BlockPos.of(e.getKey()),e.getValue(),18);history.original.remove(e.getKey());}}
                    finally{applying.set(false);}
                    history.setDirty();for(var player:world.players())dev.realworldmc.MapEdits.snapshot(player);
                    if(!history.original.equals(priorEdits)||!dev.realworldmc.EarthBlocks.isMapBlock(world.getBlockState(TARGET)))throw new AssertionError("TNT fixture restoration did not preserve prior edits");
                    restored=true;
                }catch(Throwable e){failure=e;}
            });
            phase=2;ticks=0;return;
        }
        if(phase==2&&ticks>=120&&restored){
            if(!beforeMatrix.equals(matrix(),1e-6f))throw new AssertionError("Matrix changed during restoration comparison");
            int residual=difference(before,depth());report.addProperty("restoredDepthResidualSamples",residual);
            if(residual>Math.max(32,changed/100))throw new AssertionError("Shadow depth did not restore: "+residual);
            capture(mc,"restored");setTime(mc,1000);phase=3;ticks=0;return;
        }
        if(phase==3&&ticks>=80){
            light(mc,"morning");if(CampusShadowTrial.sunlight.x<=0||CampusShadowTrial.strength<=0)throw new AssertionError("Morning sunlight is not eastward and active");
            capture(mc,"morning");setTime(mc,11000);phase=4;ticks=0;return;
        }
        if(phase==4&&ticks>=80){
            light(mc,"evening");if(CampusShadowTrial.sunlight.x>=0||CampusShadowTrial.strength<=0)throw new AssertionError("Evening sunlight is not westward and active");
            capture(mc,"evening");setTime(mc,18000);phase=5;ticks=0;return;
        }
        if(phase==5){
            // The server's time packet can arrive after the next client tick.
            // Start the no-update interval only after night reaches rendering.
            if(nightUpdates<0){
                if(mc.level.getDayTime()%24000==18000&&CampusShadowTrial.strength==0){nightUpdates=CampusShadows.updates;nightReadyTick=ticks;}
                if(ticks>200)throw new AssertionError("Night state did not arrive: time="+mc.level.getDayTime()+", strength="+CampusShadowTrial.strength);
                return;
            }
            if(ticks<nightReadyTick+60)return;
            light(mc,"night");
            if(CampusShadowTrial.strength!=0||CampusShadows.updates!=nightUpdates)throw new AssertionError("Daytime shadow pass continued at night: strength="+CampusShadowTrial.strength+", updates="+nightUpdates+" -> "+CampusShadows.updates+", time="+mc.level.getDayTime());
            double night=capture(mc,"night");report.addProperty("noonMeanLuminance",dayLuminance);report.addProperty("nightMeanLuminance",night);
            if(night>=dayLuminance*.6)throw new AssertionError("Night capture is not meaningfully darker than noon");
            setTime(mc,6000);phase=6;ticks=0;return;
        }
        if(phase==6&&ticks>=40){
            report.addProperty("status","PASS: actual TNT changed native shadow depth, restoration recovered it, and sky-consistent morning/evening/night lighting rendered");
            report.addProperty("depthCropSize",512);report.addProperty("depthDifferenceThreshold",.00001);report.addProperty("stateChecks",CampusShadowTrial.stateChecks);report.add("lighting",lighting);
            if(CampusShadowTrial.stateChecks<100)throw new AssertionError("Insufficient render-state checks");
            Files.writeString(Path.of("campus-shadow-functional.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));
            mc.getResourcePackRepository().setSelected(originalPacks);mc.stop();
        }
    }
    private static void setTime(Minecraft mc,long time){mc.getSingleplayerServer().execute(()->mc.getSingleplayerServer().overworld().setDayTime(time));}
    private static Matrix4f matrix()throws Exception{var f=CampusShadows.class.getDeclaredField("matrix");f.setAccessible(true);return new Matrix4f((Matrix4f)f.get(null));}
    private static float[] depth()throws Exception{
        if(cropX<0||cropY<0||cropX+512>CampusShadows.SIZE||cropY+512>CampusShadows.SIZE)throw new AssertionError("TNT crop outside shadow map");
        var f=CampusShadows.class.getDeclaredField("target");f.setAccessible(true);var target=(TextureTarget)f.get(null);
        int old=GL11.glGetInteger(GL30.GL_READ_FRAMEBUFFER_BINDING);var buffer=org.lwjgl.BufferUtils.createFloatBuffer(512*512);
        try{GlStateManager._glBindFramebuffer(GL30.GL_READ_FRAMEBUFFER,target.frameBufferId);GL11.glReadPixels(cropX,cropY,512,512,GL11.GL_DEPTH_COMPONENT,GL11.GL_FLOAT,buffer);}
        finally{GlStateManager._glBindFramebuffer(GL30.GL_READ_FRAMEBUFFER,old);}
        float[] result=new float[512*512];buffer.get(result);return result;
    }
    private static int difference(float[] a,float[] b){int changed=0;for(int i=0;i<a.length;i++)if(Math.abs(a[i]-b[i])>.00001f)changed++;return changed;}
    private static double capture(Minecraft mc,String name)throws Exception{
        report.addProperty("latestCapture",name);report.addProperty("clientDayTime",mc.level.getDayTime());report.addProperty("shadowStrength",CampusShadowTrial.strength);
        Files.writeString(Path.of("campus-shadow-functional-progress.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));
        try(var image=Screenshot.takeScreenshot(mc.getMainRenderTarget())){
            image.writeToFile(Path.of("campus-shadow-functional-"+name+".png"));
            long total=0,count=0;for(int y=image.getHeight()/10;y<image.getHeight()*3/4;y+=4)for(int x=image.getWidth()/10;x<image.getWidth()*9/10;x+=4){int c=image.getPixelRGBA(x,y);total+=(c&255)+((c>>>8)&255)+((c>>>16)&255);count+=3;}
            return (double)total/count;
        }
    }
    private static void light(Minecraft mc,String name)throws Exception{
        var f=MapRenderer.class.getDeclaredField("campusGroundShader");f.setAccessible(true);var shader=(net.minecraft.client.renderer.ShaderInstance)f.get(null);
        float angle=mc.level.getTimeOfDay(1)*(float)(Math.PI*2);
        Vector3f expected=new Matrix4f().rotateY(-(float)Math.PI/2).rotateX(angle).transformDirection(new Vector3f(0,1,0));
        if(expected.y<0)expected.negate();float[] actual=new float[3];GL20.glGetUniformfv(shader.getId(),GL20.glGetUniformLocation(shader.getId(),"CampusSunDirection"),actual);
        if(expected.distance(new Vector3f(actual[0],actual[1],actual[2]))>.0001f)throw new AssertionError("GPU material sunlight disagrees with sky rotation");
        float gpuStrength=GL20.glGetUniformf(shader.getId(),GL20.glGetUniformLocation(shader.getId(),"CampusShadowStrength"));
        if(Math.abs(gpuStrength-CampusShadowTrial.strength)>.0001f)throw new AssertionError("GPU shadow strength disagrees with day/night state");
        var item=new JsonObject();item.addProperty("phase",name);item.addProperty("dayTime",mc.level.getDayTime());item.add("gpuMaterialDirection",new Gson().toJsonTree(actual));item.addProperty("gpuShadowStrength",gpuStrength);item.addProperty("shadowUpdates",CampusShadows.updates);lighting.add(item);
    }
}
