package dev.realworldmc.client;

import com.mojang.blaze3d.platform.GlStateManager;
import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.VertexBuffer;
import net.minecraft.client.renderer.ShaderInstance;
import net.minecraft.client.renderer.culling.Frustum;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.lwjgl.opengl.GL11;
import org.lwjgl.opengl.GL14;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/** Transparent canopy roofs drawn after opaque campus geometry, with no depth writes. */
public final class CampusCanopyGlass {
    public static int draws;
    public static long stateChecks;
    private CampusCanopyGlass() {}
    public static boolean isCanopy(int tile) { return tile>=1_000_030_047 && tile<=1_000_030_049; }
    public static boolean isGlass(int tile,int part) { return isCanopy(tile) && part==0; }

    public static void render(List<MapTile> tiles,Vec3 camera,Frustum frustum,Matrix4f view,Matrix4f projection,ShaderInstance shader) {
        draws=0;
        var transparent=new ArrayList<MapTile>();
        for(var tile:tiles)if(tile!=null&&isCanopy(tile.data.id)&&!tile.isEmpty(0)&&(frustum==null||frustum.isVisible(tile.bounds)))transparent.add(tile);
        if(transparent.isEmpty())return;
        // These disjoint roof sections do not intersect. Whole-section ordering
        // suffices; opaque frames, the ground and the building already own depth.
        transparent.sort(Comparator.comparingDouble((MapTile t)->t.bounds.getCenter().distanceToSqr(camera)).reversed());
        boolean blend=GL11.glIsEnabled(GL11.GL_BLEND),depth=GL11.glGetBoolean(GL11.GL_DEPTH_WRITEMASK);
        int srcRGB=GL11.glGetInteger(GL14.GL_BLEND_SRC_RGB),dstRGB=GL11.glGetInteger(GL14.GL_BLEND_DST_RGB);
        int srcAlpha=GL11.glGetInteger(GL14.GL_BLEND_SRC_ALPHA),dstAlpha=GL11.glGetInteger(GL14.GL_BLEND_DST_ALPHA);
        try {
            RenderSystem.enableBlend();RenderSystem.defaultBlendFunc();RenderSystem.depthMask(false);
            shader.safeGetUniform("MaterialDetail").set(29f);
            shader.safeGetUniform("CameraPosition").set((float)camera.x,(float)camera.y,(float)camera.z);
            for(var tile:transparent) {
                shader.safeGetUniform("TileAnchor").set((float)tile.data.anchorX,(float)tile.data.anchorY,(float)tile.data.anchorZ);
                var modelView=new Matrix4f(view).translate((float)(tile.data.anchorX-camera.x),(float)(tile.data.anchorY-camera.y),(float)(tile.data.anchorZ-camera.z));
                RenderSystem.setShaderTexture(0,tile.textureId(0));
                var buffer=tile.buffer(0);buffer.bind();buffer.drawWithShader(modelView,projection,shader);draws++;
            }
        } finally {
            VertexBuffer.unbind();RenderSystem.depthMask(depth);
            GlStateManager._blendFuncSeparate(srcRGB,dstRGB,srcAlpha,dstAlpha);
            if(blend)RenderSystem.enableBlend();else RenderSystem.disableBlend();
        }
        // This narrow pass must not leak blend/depth state into vanilla rendering.
        if(GL11.glIsEnabled(GL11.GL_BLEND)!=blend||GL11.glGetBoolean(GL11.GL_DEPTH_WRITEMASK)!=depth
            ||GL11.glGetInteger(GL14.GL_BLEND_SRC_RGB)!=srcRGB||GL11.glGetInteger(GL14.GL_BLEND_DST_RGB)!=dstRGB
            ||GL11.glGetInteger(GL14.GL_BLEND_SRC_ALPHA)!=srcAlpha||GL11.glGetInteger(GL14.GL_BLEND_DST_ALPHA)!=dstAlpha)
            throw new IllegalStateException("Canopy glass render state was not restored");
        stateChecks++;
    }
}
