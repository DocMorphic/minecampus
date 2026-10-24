package dev.realworldmc.client;

import com.mojang.blaze3d.platform.GlStateManager;
import com.mojang.blaze3d.systems.RenderSystem;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import org.lwjgl.opengl.GL11;
import org.lwjgl.opengl.GL12;
import org.lwjgl.opengl.GL13;
import org.lwjgl.opengl.GL30;
import org.lwjgl.opengl.GL;
import org.lwjgl.opengl.EXTTextureFilterAnisotropic;

/** Mipmapped CC0 micro-materials and ODbL land-cover maps, loaded locally. */
public final class CampusMaterials {
    private static final String[] NAMES={"concrete_diff","concrete_normal","grass_diff","grass_normal","ground_surfaces","brick_normal","asphalt_diff","asphalt_normal","soil_diff","soil_normal","physics_concrete_diff","physics_concrete_normal","physics_ground_surfaces","woodland_ground_surfaces","galvanized_diff","laboratory_site_ground_surfaces","physics_ii_ground_surfaces","gravel_diff","gravel_normal"};
    private static final int[] prepared=new int[NAMES.length];
    static { java.util.Arrays.fill(prepared,-1); }
    private static final int[] textureIds=new int[NAMES.length];
    private static int facadeMode;
    private static int groundMode;
    private CampusMaterials(){}
    // Resource reload can replace pixel storage while retaining the GL name.
    // Reapply mipmaps and sampling even when the numeric texture ID is reused.
    public static void invalidate(){java.util.Arrays.fill(prepared,-1);}
    public static void bind(){
        int active=GL11.glGetInteger(GL13.GL_ACTIVE_TEXTURE),binding=GL11.glGetInteger(GL11.GL_TEXTURE_BINDING_2D);
        try{
        var manager=Minecraft.getInstance().getTextureManager();
        for(int i=0;i<NAMES.length;i++){
            var location=ResourceLocation.fromNamespaceAndPath("realworldmc","textures/campus/"+NAMES[i]+".png");
            int id=manager.getTexture(location).getId();
            if(prepared[i]!=id){
                boolean atlas=i==4||i==12||i==13||i==15||i==16;
                int maxLevel=i==4?12:(i==12||i==13?11:10);
                GlStateManager._bindTexture(id);
                GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL12.GL_TEXTURE_MAX_LEVEL,maxLevel);
                // Minecraft initially allocates these as level-zero textures.
                // Lift its separate sampling clamp as well as MAX_LEVEL.
                GL11.glTexParameterf(GL11.GL_TEXTURE_2D,GL12.GL_TEXTURE_MIN_LOD,0f);
                GL11.glTexParameterf(GL11.GL_TEXTURE_2D,GL12.GL_TEXTURE_MAX_LOD,maxLevel);
                GL30.glGenerateMipmap(GL11.GL_TEXTURE_2D);
                GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_MIN_FILTER,GL11.GL_LINEAR_MIPMAP_LINEAR);
                GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_MAG_FILTER,GL11.GL_LINEAR);
                GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_WRAP_S,atlas?GL12.GL_CLAMP_TO_EDGE:GL11.GL_REPEAT);
                GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_WRAP_T,atlas?GL12.GL_CLAMP_TO_EDGE:GL11.GL_REPEAT);
                if(GL.getCapabilities().GL_EXT_texture_filter_anisotropic){
                    float maximum=GL11.glGetFloat(EXTTextureFilterAnisotropic.GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT);
                    GL11.glTexParameterf(GL11.GL_TEXTURE_2D,EXTTextureFilterAnisotropic.GL_TEXTURE_MAX_ANISOTROPY_EXT,Math.min(16f,maximum));
                }
                prepared[i]=id;
            }
            textureIds[i]=id;
            if(i<10)RenderSystem.setShaderTexture(i+1,id);
        }
        facadeMode=0;
        groundMode=0;
        }finally{
            GlStateManager._activeTexture(active);GlStateManager._bindTexture(binding);
        }
    }
    /** Share existing texture units; each subsequent part restores its own material. */
    public static void bindConcrete(boolean aggregate){bindConcrete(aggregate?1:0);}
    public static void bindConcrete(int mode){
        if(facadeMode==mode)return;
        int first=mode==2?14:(mode==1?10:0);
        RenderSystem.setShaderTexture(1,textureIds[first]);
        RenderSystem.setShaderTexture(2,textureIds[mode==1?11:1]);
        facadeMode=mode;
    }
    /** Ground does not use the brick-normal unit; retain the original atlas on unit 5. */
    public static void bindGround(boolean physics){
        bindGround(physics?1:0);
    }
    /** The woodland overlay shares the ground-only sampler, keeping old tiles exact. */
    public static void bindGround(int mode){
        if(groundMode==mode)return;
        RenderSystem.setShaderTexture(6,textureIds[mode==4?16:mode==3?15:(mode==2?13:(mode==1?12:5))]);
        // Physics II uses the soil units for its inferred gravel surface.
        RenderSystem.setShaderTexture(9,textureIds[mode==4?17:8]);
        RenderSystem.setShaderTexture(10,textureIds[mode==4?18:9]);
        groundMode=mode;
    }
}
