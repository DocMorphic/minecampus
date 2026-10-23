package dev.realworldmc.client;

import com.mojang.blaze3d.pipeline.TextureTarget;
import com.mojang.blaze3d.platform.GlStateManager;
import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.VertexBuffer;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.ShaderInstance;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import org.lwjgl.opengl.GL11;
import org.lwjgl.opengl.GL30;
import java.util.List;

/** Local map-mesh shadows, refreshed after damage and aligned with Minecraft sunlight. */
public final class CampusShadows {
    public static final int SIZE=4096;
    private static final float RADIUS=64f;
    private static TextureTarget target;
    private static final Matrix4f matrix=new Matrix4f();
    private static boolean ready;
    private static long nextUpdate;
    private static Vec3 lastCamera=Vec3.ZERO;
    private static final Vector3f lastSun=new Vector3f();
    public static long updates;
    public static int draws;
    public static void clear(){
        if(target!=null){target.destroyBuffers();target=null;}
        ready=false;RenderSystem.setShaderTexture(11,0);
    }
    private CampusShadows(){}
    public static void invalidate(){ready=false;nextUpdate=0;}
    public static void update(List<MapTile> tiles,Vec3 camera,net.minecraft.client.multiplayer.ClientLevel level,float partial,ShaderInstance caster,ShaderInstance material){
        float angle=level.getTimeOfDay(partial)*(float)(Math.PI*2);
        Vector3f sun=new Vector3f(-(float)Math.sin(angle),(float)Math.cos(angle),0);
        float horizon=Math.max(0,Math.min(1,(sun.y-.04f)/.16f));
        float strength=.28f*horizon*(1-level.getRainLevel(partial));
        Vector3f lighting=new Vector3f(sun);if(lighting.y<0)lighting.negate();
        material.safeGetUniform("CampusSunDirection").set(lighting.x,lighting.y,lighting.z);
        if(strength>0)render(tiles,camera,sun,caster);
        bind(material,strength);
    }


    /** Caller supplies already damage-refreshed buffers and the material sun. */
    public static void render(List<MapTile> tiles,Vec3 camera,Vector3f sun,ShaderInstance shader){
        RenderSystem.assertOnRenderThread();
        if(shader==null||tiles.isEmpty()){ready=false;return;}
        long now=System.nanoTime();
        // Redraw at most ten times per second; MapTile refresh may add latency.
        // A large camera move bypasses the throttle.
        if(ready&&now<nextUpdate&&camera.distanceToSqr(lastCamera)<400&&lastSun.dot(sun)>.9999f)return;
        int drawFbo=GL11.glGetInteger(GL30.GL_DRAW_FRAMEBUFFER_BINDING);
        int readFbo=GL11.glGetInteger(GL30.GL_READ_FRAMEBUFFER_BINDING);
        int[] viewport=new int[4];GL11.glGetIntegerv(GL11.GL_VIEWPORT,viewport);
        boolean depth=GL11.glIsEnabled(GL11.GL_DEPTH_TEST),cull=GL11.glIsEnabled(GL11.GL_CULL_FACE),blend=GL11.glIsEnabled(GL11.GL_BLEND);
        boolean offset=GL11.glIsEnabled(GL11.GL_POLYGON_OFFSET_FILL),write=GL11.glGetBoolean(GL11.GL_DEPTH_WRITEMASK);
        int depthFunc=GL11.glGetInteger(GL11.GL_DEPTH_FUNC),texture=RenderSystem.getShaderTexture(0);
        float factor=GL11.glGetFloat(GL11.GL_POLYGON_OFFSET_FACTOR),units=GL11.glGetFloat(GL11.GL_POLYGON_OFFSET_UNITS);
        try{
            if(target==null)target=new TextureTarget(SIZE,SIZE,true,Minecraft.ON_OSX);
            target.bindWrite(true);
            RenderSystem.enableDepthTest();RenderSystem.depthMask(true);RenderSystem.depthFunc(GL11.GL_LEQUAL);
            RenderSystem.disableCull();RenderSystem.disableBlend();
            RenderSystem.enablePolygonOffset();RenderSystem.polygonOffset(.75f,2f);
            RenderSystem.clear(GL11.GL_DEPTH_BUFFER_BIT,Minecraft.ON_OSX);
            Vector3f center=new Vector3f((float)camera.x,(float)camera.y,(float)camera.z);
            Vector3f eye=new Vector3f(sun).mul(160f).add(center);
            // Minecraft's sun travels in XY. A stable Z up-vector avoids a
            // basis switch as the sun passes nearly overhead.
            Vector3f up=Math.abs(sun.z)>.99f?new Vector3f(0,1,0):new Vector3f(0,0,1);
            Matrix4f view=new Matrix4f().lookAt(eye,center,up);
            Matrix4f projection=new Matrix4f().ortho(-RADIUS,RADIUS,-RADIUS,RADIUS,1f,320f);
            matrix.set(projection).mul(view);
            var origin=matrix.transform(new org.joml.Vector4f(0,0,0,1));
            float dx=(Math.round(origin.x*SIZE*.5f)-origin.x*SIZE*.5f)*2f/SIZE;
            float dy=(Math.round(origin.y*SIZE*.5f)-origin.y*SIZE*.5f)*2f/SIZE;
            projection.m30(projection.m30()+dx);projection.m31(projection.m31()+dy);
            matrix.set(projection).mul(view);
            var frustum=new net.minecraft.client.renderer.culling.Frustum(view,projection);
            frustum.prepare(0,0,0);
            draws=0;
            for(var tile:tiles){
                // Cull against the light volume, including off-camera casters.
                if(!frustum.isVisible(tile.bounds))continue;
                Matrix4f mv=new Matrix4f(view).translate((float)tile.data.anchorX,(float)tile.data.anchorY,(float)tile.data.anchorZ);
                for(int part=0;part<tile.partCount();part++){
                    if(tile.isEmpty(part))continue;
                    boolean leaves=tile.data.id>=1_000_010_000&&tile.data.id<1_000_020_000&&part!=0;
                    shader.safeGetUniform("AlphaCutoff").set(leaves?.45f:.1f);
                    RenderSystem.setShaderTexture(0,tile.textureId(part));
                    var buffer=tile.buffer(part);buffer.bind();buffer.drawWithShader(mv,projection,shader);draws++;
                }
            }
            ready=true;updates++;nextUpdate=now+100_000_000L;lastCamera=camera;lastSun.set(sun);
        }finally{
            VertexBuffer.unbind();
            GlStateManager._glBindFramebuffer(GL30.GL_DRAW_FRAMEBUFFER,drawFbo);
            GlStateManager._glBindFramebuffer(GL30.GL_READ_FRAMEBUFFER,readFbo);
            RenderSystem.viewport(viewport[0],viewport[1],viewport[2],viewport[3]);
            RenderSystem.depthMask(write);RenderSystem.depthFunc(depthFunc);
            if(depth)RenderSystem.enableDepthTest();else RenderSystem.disableDepthTest();
            if(cull)RenderSystem.enableCull();else RenderSystem.disableCull();
            if(blend)RenderSystem.enableBlend();else RenderSystem.disableBlend();
            RenderSystem.polygonOffset(factor,units);
            if(offset)RenderSystem.enablePolygonOffset();else RenderSystem.disablePolygonOffset();
            RenderSystem.setShaderTexture(0,texture);
        }
    }
    public static void bind(ShaderInstance shader,boolean enabled){
        bind(shader,enabled?.28f:0f);
    }
    public static void bind(ShaderInstance shader,float strength){
        if(shader==null)return;
        shader.safeGetUniform("CampusShadowStrength").set(ready?strength:0f);
        if(strength>0&&ready){
            RenderSystem.setShaderTexture(11,target.getDepthTextureId());
            shader.safeGetUniform("CampusShadowMatrix").set(matrix);
        }
    }
}
