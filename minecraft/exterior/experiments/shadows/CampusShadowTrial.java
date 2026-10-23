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
    private static ShaderInstance depthShader;
    public void onInitializeClient(){
        CoreShaderRegistrationCallback.EVENT.register(context->context.register(
            ResourceLocation.fromNamespaceAndPath("realworldmc","campus_shadow"),DefaultVertexFormat.POSITION_TEX,s->depthShader=s));
        WorldRenderEvents.AFTER_ENTITIES.register(context->{
            try{
                var renderer=MapRenderer.INSTANCE;
                var field=MapRenderer.class.getDeclaredField("campusGroundShader");field.setAccessible(true);
                ShaderInstance ground=(ShaderInstance)field.get(null);
                if(enabled){
                    var loadedField=MapRenderer.class.getDeclaredField("loaded");loadedField.setAccessible(true);
                    var displayedField=MapRenderer.class.getDeclaredField("displayed");displayedField.setAccessible(true);
                    var loaded=(Map<Integer,MapTile>)loadedField.get(renderer);
                    var displayed=(List<Integer>)displayedField.get(renderer);
                    List<MapTile> tiles=new ArrayList<>();
                    for(int id:displayed){var tile=loaded.get(id);if(tile!=null)tiles.add(tile);}
                    CampusShadows.render(tiles,context.camera().getPosition(),new Vector3f(-.5f,.8f,-.3f).normalize(),depthShader);
                }
                CampusShadows.bind(ground,enabled);
            }catch(Exception e){throw new IllegalStateException("Runtime shadow trial",e);}
        });
    }
}
