package dev.realworldmc.client;

import com.mojang.blaze3d.pipeline.TextureTarget;
import com.mojang.blaze3d.platform.GlStateManager;
import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.VertexBuffer;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.rendering.v1.CoreShaderRegistrationCallback;
import net.fabricmc.fabric.api.client.rendering.v1.WorldRenderContext;
import net.fabricmc.fabric.api.client.rendering.v1.WorldRenderEvents;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.client.renderer.ShaderInstance;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.AABB;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import org.joml.Vector4f;
import org.lwjgl.opengl.*;
import java.nio.file.Path;
import java.util.*;

/** Isolated experiment: previous-frame reflection; no production renderer override. */
public final class CampusReflectionTrial implements ClientModInitializer {
    public static boolean enabled;
    public static long updates,stateChecks;
    public static int draws,textureUnits;
    public static double lastMilliseconds;
    public static Plane selected;
    private static ShaderInstance caster;
    private static TextureTarget target;
    private static final Matrix4f projectionToTexture=new Matrix4f();
    private static final Map<MapTile,List<Plane>> planes=new WeakHashMap<>();
    private static Object lastWorld;
    public static final class Plane {
        public final Vector4f equation;
        public AABB bounds;
        public final int tile;
        Plane(Vector4f equation,AABB bounds,int tile){this.equation=equation;this.bounds=bounds;this.tile=tile;}
    }
    @Override public void onInitializeClient(){
        CoreShaderRegistrationCallback.EVENT.register(context->{
            clear();
            context.register(ResourceLocation.fromNamespaceAndPath("realworldmc","campus_reflection"),DefaultVertexFormat.POSITION_TEX,s->caster=s);
        });
        WorldRenderEvents.AFTER_ENTITIES.register(context->{
            try{render(context);}catch(Exception e){throw new IllegalStateException("Isolated planar reflection",e);}
        });
    }
    private static void clear(){
        if(target!=null){target.destroyBuffers();target=null;}
        planes.clear();selected=null;
    }
    private static List<Plane> panes(MapTile tile){
        return planes.computeIfAbsent(tile,t->{
            var result=new ArrayList<Plane>();
            if(t.data.parts.length<2)return result;
            float[] v=t.data.parts[1].vertices;
            for(int i=0;i<v.length;i+=15){
                Vector3f a=point(t,v,i),b=point(t,v,i+5),c=point(t,v,i+10);
                var n=new Vector3f(b).sub(a).cross(new Vector3f(c).sub(a));
                if(n.lengthSquared()<1e-10)continue;n.normalize();
                if(Math.abs(n.y)>.05)continue;
                if(Math.abs(n.x)>Math.abs(n.z)?n.x<0:n.z<0)n.negate();
                float d=-n.dot(a);
                var bounds=new AABB(Math.min(a.x,Math.min(b.x,c.x)),Math.min(a.y,Math.min(b.y,c.y)),Math.min(a.z,Math.min(b.z,c.z)),Math.max(a.x,Math.max(b.x,c.x)),Math.max(a.y,Math.max(b.y,c.y)),Math.max(a.z,Math.max(b.z,c.z)));
                Plane found=null;
                for(var p:result)if(p.equation.x*n.x+p.equation.y*n.y+p.equation.z*n.z>.99999f&&Math.abs(p.equation.w-d)<.025f){found=p;break;}
                if(found==null)result.add(new Plane(new Vector4f(n,d),bounds,t.data.id));else found.bounds=found.bounds.minmax(bounds);
            }
            return result;
        });
    }
    private static Vector3f point(MapTile tile,float[] v,int i){return new Vector3f((float)(v[i]+tile.data.anchorX),(float)(v[i+1]+tile.data.anchorY),(float)(v[i+2]+tile.data.anchorZ));}
    private static void render(WorldRenderContext context)throws Exception{
        var shaderField=MapRenderer.class.getDeclaredField("campusGroundShader");shaderField.setAccessible(true);
        var material=(ShaderInstance)shaderField.get(null);if(material==null)return;
        if(lastWorld!=context.world()){clear();lastWorld=context.world();}
        material.safeGetUniform("PlanarStrength").set(0f);
        if(!enabled||caster==null)return;
        textureUnits=GL11.glGetInteger(GL20.GL_MAX_TEXTURE_IMAGE_UNITS);
        if(textureUnits<13)throw new IllegalStateException("Reflection needs a thirteenth sampler");
        var renderer=MapRenderer.INSTANCE;
        var lf=MapRenderer.class.getDeclaredField("loaded");lf.setAccessible(true);
        var df=MapRenderer.class.getDeclaredField("displayed");df.setAccessible(true);
        var loaded=(Map<Integer,MapTile>)lf.get(renderer);var displayed=(List<Integer>)df.get(renderer);
        var tiles=new ArrayList<MapTile>();for(int id:displayed){var tile=loaded.get(id);if(tile!=null)tiles.add(tile);}
        var eye=context.camera().getPosition();var eye4=new Vector4f((float)eye.x,(float)eye.y,(float)eye.z,1);
        Plane best=null;double bestScore=0;
        for(var tile:tiles){
            if(tile.data.id!=1_000_000_100&&tile.data.id!=1_000_000_101||tile.isEmpty(1))continue;
            for(var p:panes(tile)){
                double distance=Math.abs(p.equation.dot(eye4));if(distance<.6||distance>60)continue;
                if(context.frustum()!=null&&!context.frustum().isVisible(p.bounds.inflate(.1)))continue;
                double dx=Math.max(p.bounds.minX-eye.x,Math.max(0,eye.x-p.bounds.maxX));
                double dy=Math.max(p.bounds.minY-eye.y,Math.max(0,eye.y-p.bounds.maxY));
                double dz=Math.max(p.bounds.minZ-eye.z,Math.max(0,eye.z-p.bounds.maxZ));
                double area=Math.hypot(p.bounds.getXsize(),p.bounds.getZsize())*p.bounds.getYsize();
                double score=area/(36+dx*dx+dy*dy+dz*dz);
                if(score>bestScore){best=p;bestScore=score;}
            }
        }
        selected=best;if(best==null)return;
        var plane=new Vector4f(best.equation);if(plane.dot(eye4)<0)plane.negate();
        var reflection=new Matrix4f().reflection(plane.x,plane.y,plane.z,plane.w);
        var absoluteView=new Matrix4f(context.positionMatrix()).translate(-(float)eye.x,-(float)eye.y,-(float)eye.z).mul(reflection);
        var projection=new Matrix4f(context.projectionMatrix());
        projectionToTexture.set(projection).mul(absoluteView);
        int[] before=state();long start=System.nanoTime();
        int fbo=before[0],read=before[1],texture=RenderSystem.getShaderTexture(0),program=GL11.glGetInteger(GL20.GL_CURRENT_PROGRAM);
        float[] clearColor=new float[4];GL11.glGetFloatv(GL11.GL_COLOR_CLEAR_VALUE,clearColor);
        int activeTexture=GL11.glGetInteger(GL13.GL_ACTIVE_TEXTURE);
        try{
            if(target==null){target=new TextureTarget(1024,576,true,Minecraft.ON_OSX);target.setFilterMode(GL11.GL_LINEAR);}
            target.bindWrite(true);RenderSystem.disableScissor();
            RenderSystem.enableDepthTest();RenderSystem.depthMask(true);RenderSystem.depthFunc(GL11.GL_LEQUAL);
            RenderSystem.disableCull();RenderSystem.disableBlend();RenderSystem.disablePolygonOffset();
            var sky=context.world().getSkyColor(eye,context.tickCounter().getGameTimeDeltaPartialTick(false));
            RenderSystem.clearColor((float)sky.x,(float)sky.y,(float)sky.z,1f);
            RenderSystem.clear(GL11.GL_COLOR_BUFFER_BIT|GL11.GL_DEPTH_BUFFER_BIT,Minecraft.ON_OSX);
            caster.safeGetUniform("ClipPlane").set(plane.x,plane.y,plane.z,plane.w);
            float angle=context.world().getTimeOfDay(1)*(float)(Math.PI*2);
            var sun=new Vector3f(-(float)Math.sin(angle),(float)Math.cos(angle),0);if(sun.y<0)sun.negate();
            caster.safeGetUniform("SunDirection").set(sun.x,sun.y,sun.z);
            caster.safeGetUniform("WorldLight").set(context.world().getSkyDarken(context.tickCounter().getGameTimeDeltaPartialTick(false)));
            var reflectedEye=reflection.transformPosition(new Vector3f((float)eye.x,(float)eye.y,(float)eye.z));
            caster.safeGetUniform("ReflectedEye").set(reflectedEye.x,reflectedEye.y,reflectedEye.z);
            var frustum=new net.minecraft.client.renderer.culling.Frustum(absoluteView,projection);frustum.prepare(0,0,0);
            draws=0;
            for(var tile:tiles){
                if(!frustum.isVisible(tile.bounds))continue;
                var b=tile.bounds;
                double cx=plane.x>=0?b.maxX:b.minX,cy=plane.y>=0?b.maxY:b.minY,cz=plane.z>=0?b.maxZ:b.minZ;
                if(plane.x*cx+plane.y*cy+plane.z*cz+plane.w<.02)continue;
                var modelView=new Matrix4f(absoluteView).translate((float)tile.data.anchorX,(float)tile.data.anchorY,(float)tile.data.anchorZ);
                caster.safeGetUniform("TileAnchor").set((float)tile.data.anchorX,(float)tile.data.anchorY,(float)tile.data.anchorZ);
                for(int p=0;p<tile.partCount();p++){
                    if(tile.isEmpty(p))continue;
                    boolean leaves=tile.data.id>=1_000_010_000&&tile.data.id<1_000_020_000&&p!=0;
                    caster.safeGetUniform("AlphaCutoff").set(leaves?.45f:.1f);
                    RenderSystem.setShaderTexture(0,tile.textureId(p));
                    var buffer=tile.buffer(p);buffer.bind();buffer.drawWithShader(modelView,projection,caster);draws++;
                }
            }
            updates++;
        }finally{
            VertexBuffer.unbind();
            GlStateManager._glBindFramebuffer(GL30.GL_DRAW_FRAMEBUFFER,fbo);GlStateManager._glBindFramebuffer(GL30.GL_READ_FRAMEBUFFER,read);
            RenderSystem.viewport(before[2],before[3],before[4],before[5]);RenderSystem.depthFunc(before[6]);RenderSystem.depthMask(before[7]!=0);
            if(before[8]!=0)RenderSystem.enableDepthTest();else RenderSystem.disableDepthTest();
            if(before[9]!=0)RenderSystem.enableCull();else RenderSystem.disableCull();
            if(before[10]!=0)RenderSystem.enableBlend();else RenderSystem.disableBlend();
            if(before[11]!=0)RenderSystem.enablePolygonOffset();else RenderSystem.disablePolygonOffset();
            if(before[12]!=0)RenderSystem.enableScissor(before[13],before[14],before[15],before[16]);else RenderSystem.disableScissor();
            RenderSystem.clearColor(clearColor[0],clearColor[1],clearColor[2],clearColor[3]);
            RenderSystem.setShaderTexture(0,texture);GlStateManager._activeTexture(activeTexture);GlStateManager._glUseProgram(program);
        }
        if(!Arrays.equals(before,state()))throw new IllegalStateException("Reflection pass leaked graphics state");
        stateChecks++;lastMilliseconds=(System.nanoTime()-start)/1e6;
        // Minecraft 1.21.1 caches exactly twelve texture units. The extra
        // hardware unit is managed directly and never passed to that cache.
        int priorUnit=GL11.glGetInteger(GL13.GL_ACTIVE_TEXTURE);
        GL13.glActiveTexture(GL13.GL_TEXTURE0+12);
        GL11.glBindTexture(GL11.GL_TEXTURE_2D,target.getColorTextureId());
        GL13.glActiveTexture(priorUnit);
        material.safeGetUniform("PlanarTexture").set(12);
        material.safeGetUniform("PlanarPlane").set(plane.x,plane.y,plane.z,plane.w);
        material.safeGetUniform("PlanarMatrix").set(projectionToTexture);material.safeGetUniform("PlanarStrength").set(1f);
    }
    public static void capture(Path path)throws Exception{if(target==null)throw new IllegalStateException("No reflection target");try(var image=Screenshot.takeScreenshot(target)){image.writeToFile(path);}}
    private static int[] state(){
        int[] v=new int[4],s=new int[4];GL11.glGetIntegerv(GL11.GL_VIEWPORT,v);GL11.glGetIntegerv(GL11.GL_SCISSOR_BOX,s);
        return new int[]{GL11.glGetInteger(GL30.GL_DRAW_FRAMEBUFFER_BINDING),GL11.glGetInteger(GL30.GL_READ_FRAMEBUFFER_BINDING),v[0],v[1],v[2],v[3],GL11.glGetInteger(GL11.GL_DEPTH_FUNC),GL11.glGetBoolean(GL11.GL_DEPTH_WRITEMASK)?1:0,GL11.glIsEnabled(GL11.GL_DEPTH_TEST)?1:0,GL11.glIsEnabled(GL11.GL_CULL_FACE)?1:0,GL11.glIsEnabled(GL11.GL_BLEND)?1:0,GL11.glIsEnabled(GL11.GL_POLYGON_OFFSET_FILL)?1:0,GL11.glIsEnabled(GL11.GL_SCISSOR_TEST)?1:0,s[0],s[1],s[2],s[3]};
    }
}
