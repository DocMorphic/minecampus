package dev.realworldmc.client;

import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.rendering.v1.CoreShaderRegistrationCallback;
import net.fabricmc.fabric.api.client.rendering.v1.WorldRenderEvents;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.client.renderer.ShaderInstance;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import org.joml.Vector3f;
import java.util.ArrayList;
import java.util.Map;
import java.util.List;

/** Isolated hook; production MapRenderer is unmodified during comparison. */
public final class CampusShadowTrial implements ClientModInitializer {
    public static boolean enabled;
    public static boolean dynamicSun;
    public static final Vector3f sunlight=new Vector3f(-.5f,.8f,-.3f).normalize();
    public static float strength;
    public static long stateChecks;
    private static ShaderInstance depthShader;
    public void onInitializeClient(){
        CoreShaderRegistrationCallback.EVENT.register(context->context.register(
            ResourceLocation.fromNamespaceAndPath("realworldmc","campus_shadow"),DefaultVertexFormat.POSITION_TEX,s->depthShader=s));
        WorldRenderEvents.AFTER_ENTITIES.register(context->{
            try{
                var renderer=MapRenderer.INSTANCE;
                var field=MapRenderer.class.getDeclaredField("campusGroundShader");field.setAccessible(true);
                ShaderInstance ground=(ShaderInstance)field.get(null);
                strength=enabled?.28f:0f;
                if(dynamicSun){
                    float partial=context.tickCounter().getGameTimeDeltaPartialTick(false);
                    float angle=context.world().getTimeOfDay(partial)*(float)(Math.PI*2);
                    sunlight.set(-(float)Math.sin(angle),(float)Math.cos(angle),0);
                    float horizon=Math.max(0,Math.min(1,(sunlight.y-.04f)/.16f));
                    strength*=horizon*(1-context.world().getRainLevel(partial));
                    var materialLight=new Vector3f(sunlight);if(materialLight.y<0)materialLight.negate();
                    if(ground!=null)ground.safeGetUniform("CampusSunDirection").set(materialLight.x,materialLight.y,materialLight.z);
                }
                if(strength>0){
                    var loadedField=MapRenderer.class.getDeclaredField("loaded");loadedField.setAccessible(true);
                    var displayedField=MapRenderer.class.getDeclaredField("displayed");displayedField.setAccessible(true);
                    var loaded=(Map<Integer,MapTile>)loadedField.get(renderer);
                    var displayed=(List<Integer>)displayedField.get(renderer);
                    List<MapTile> tiles=new ArrayList<>();
                    for(int id:displayed){var tile=loaded.get(id);if(tile!=null)tiles.add(tile);}
                    int[] before=state();
                    CampusShadows.render(tiles,context.camera().getPosition(),sunlight,depthShader);
                    if(!java.util.Arrays.equals(before,state()))throw new IllegalStateException("Shadow pass leaked framebuffer, viewport or depth/cull/blend state");
                    stateChecks++;
                }
                CampusShadows.bind(ground,strength);
            }catch(Exception e){throw new IllegalStateException("Runtime shadow trial",e);}
        });
    }
    private static int[] state(){
        int[] viewport=new int[4];org.lwjgl.opengl.GL11.glGetIntegerv(org.lwjgl.opengl.GL11.GL_VIEWPORT,viewport);
        return new int[]{org.lwjgl.opengl.GL11.glGetInteger(org.lwjgl.opengl.GL30.GL_DRAW_FRAMEBUFFER_BINDING),org.lwjgl.opengl.GL11.glGetInteger(org.lwjgl.opengl.GL30.GL_READ_FRAMEBUFFER_BINDING),viewport[0],viewport[1],viewport[2],viewport[3],org.lwjgl.opengl.GL11.glGetInteger(org.lwjgl.opengl.GL11.GL_DEPTH_FUNC),org.lwjgl.opengl.GL11.glGetBoolean(org.lwjgl.opengl.GL11.GL_DEPTH_WRITEMASK)?1:0,org.lwjgl.opengl.GL11.glIsEnabled(org.lwjgl.opengl.GL11.GL_DEPTH_TEST)?1:0,org.lwjgl.opengl.GL11.glIsEnabled(org.lwjgl.opengl.GL11.GL_CULL_FACE)?1:0,org.lwjgl.opengl.GL11.glIsEnabled(org.lwjgl.opengl.GL11.GL_BLEND)?1:0,org.lwjgl.opengl.GL11.glIsEnabled(org.lwjgl.opengl.GL11.GL_POLYGON_OFFSET_FILL)?1:0};
    }
}
