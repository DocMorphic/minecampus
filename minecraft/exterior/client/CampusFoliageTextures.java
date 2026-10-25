package dev.realworldmc.client;

import org.lwjgl.opengl.GL11;
import org.lwjgl.system.MemoryUtil;

/** Render-thread upload; the repeated texture is shared by main, shadow and reflection passes. */
public final class CampusFoliageTextures {
    private CampusFoliageTextures() {}
    public static void configure(int width,int height,int[] pixels) {
        GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_WRAP_S,GL11.GL_REPEAT);
        GL11.glTexParameteri(GL11.GL_TEXTURE_2D,GL11.GL_TEXTURE_WRAP_T,GL11.GL_REPEAT);
        int level=1;
        for (var mip:CampusFoliage.mipmaps(width,height,pixels)) {
            var buffer=MemoryUtil.memAllocInt(mip.pixels().length);
            try {
                buffer.put(mip.pixels()).flip();
                GL11.glTexImage2D(GL11.GL_TEXTURE_2D,level++,GL11.GL_RGBA8,mip.width(),mip.height(),0,GL11.GL_RGBA,GL11.GL_UNSIGNED_BYTE,buffer);
            } finally { MemoryUtil.memFree(buffer); }
        }
    }
}
