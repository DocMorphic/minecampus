package dev.realworldmc.client;

import java.util.ArrayList;
import java.util.List;

/** Physical leaf-atlas mapping and coverage-preserving mip data. No world edits. */
public final class CampusFoliage {
    // Median world/UV edge ratio measured from the original CC0 Jacaranda glTF.
    public static final double ATLAS_METRES = 0.4517374038696289;
    public static final int ALPHA_TEST = 115; // ceil(.45 * 255), shared by all three passes
    private CampusFoliage() {}
    public static boolean isTree(int tile) {
        return (tile >= 1_000_010_000 && tile < 1_000_020_000)
            || (tile >= 1_000_040_600 && tile < 1_000_040_900);
    }
    public static boolean applies(int tile, int part) { return isTree(tile) && part == 1; }

    /** Trim each estimated card to an irregular rounded patch inside its old bounds.
     * Fine atlas repeats retain source leaf scale; wood and source arrays are untouched. */
    public static float[] cards(float[] source) {
        if (source.length % 30 != 0) throw new IllegalArgumentException("Foliage requires complete six-vertex cards");
        float[] result = new float[source.length*3];
        int output=0;
        for (int o=0; o<source.length; o+=30) {
            for (int axis=0; axis<3; axis++) {
                if (source[o+axis]!=source[o+15+axis] || source[o+10+axis]!=source[o+20+axis])
                    throw new IllegalArgumentException("Unexpected foliage triangulation");
            }
            double[] axisU=new double[3],axisV=new double[3];
            double width=distance(source,o,o+5),along=0;
            for(int axis=0;axis<3;axis++) {
                axisU[axis]=((double)source[o+5+axis]-source[o+axis])/width;
                axisV[axis]=(double)source[o+25+axis]-source[o+axis];
                along+=axisV[axis]*axisU[axis];
            }
            double height=0;
            for(int axis=0;axis<3;axis++){axisV[axis]-=along*axisU[axis];height+=axisV[axis]*axisV[axis];}
            height=Math.sqrt(height);
            for(int axis=0;axis<3;axis++)axisV[axis]/=height;
            int seed=Float.floatToIntBits(source[o])*31+Float.floatToIntBits(source[o+1])*17+Float.floatToIntBits(source[o+2]);
            seed ^= seed >>> 16;
            int rotation=seed & 3;
            double phaseU=((seed>>>2)&1023)/1024.0, phaseV=((seed>>>12)&1023)/1024.0;
            double[][] vertices=new double[8][5];
            double angleOffset=((seed>>>22)&1023)/1024.0*Math.PI*2;
            for(int i=0;i<8;i++) {
                int random=seed^(i*0x9e3779b9);random^=random>>>16;
                double radius=.9+.1*((random>>>8)&1023)/1024.0;
                double angle=angleOffset+i*Math.PI/4;
                double x=(1+radius*Math.cos(angle))*.5,y=(1+radius*Math.sin(angle))*.5;
                double u=0,v=0;
                for(int axis=0;axis<3;axis++) {
                    vertices[i][axis]=(float)(source[o+axis]+x*((double)source[o+5+axis]-source[o+axis])+y*((double)source[o+25+axis]-source[o+axis]));
                    double offset=vertices[i][axis]-source[o+axis];
                    u+=offset*axisU[axis]/ATLAS_METRES;v+=offset*axisV[axis]/ATLAS_METRES;
                }
                vertices[i][3]=(rotation==0?u:rotation==1?-v:rotation==2?-u:v)+phaseU;
                vertices[i][4]=(rotation==0?v:rotation==1?u:rotation==2?-v:-u)+phaseV;
            }
            for(int triangle=1;triangle<7;triangle++) for(int i:new int[]{0,triangle,triangle+1})
                for(int axis=0;axis<5;axis++) result[output++]=(float)vertices[i][axis];
        }
        return result;
    }
    private static double distance(float[] p,int a,int b) {
        double x=(double)p[a]-p[b], y=(double)p[a+1]-p[b+1], z=(double)p[a+2]-p[b+2];
        return Math.sqrt(x*x+y*y+z*z);
    }

    public record Mip(int width,int height,int[] pixels) {}
    /** Filter colour in premultiplied-alpha space, then preserve cutout coverage. */
    public static List<Mip> mipmaps(int width,int height,int[] pixels) {
        if (width<1 || height<1 || pixels.length!=width*height) throw new IllegalArgumentException("Invalid foliage image");
        int covered=0;
        for (int pixel:pixels) if ((pixel>>>24)>=ALPHA_TEST) covered++;
        double coverage=(double)covered/pixels.length;
        int[] raw=pixels;
        var result=new ArrayList<Mip>();
        while (width>1 || height>1) {
            int w=Math.max(1,width/2), h=Math.max(1,height/2);
            int[] next=new int[w*h];
            for (int y=0;y<h;y++) for (int x=0;x<w;x++) {
                long a=0,r=0,g=0,b=0;
                for (int dy=0;dy<2;dy++) for (int dx=0;dx<2;dx++) {
                    int p=raw[Math.min(height-1,y*2+dy)*width+Math.min(width-1,x*2+dx)];
                    int alpha=p>>>24;
                    a+=alpha; r+=(p&255)*alpha; g+=((p>>>8)&255)*alpha; b+=((p>>>16)&255)*alpha;
                }
                int alpha=(int)((a+2)/4);
                next[y*w+x]=alpha<<24;
                if (a>0) next[y*w+x]|=(int)((r+a/2)/a)|(int)((g+a/2)/a)<<8|(int)((b+a/2)/a)<<16;
            }
            int[] histogram=new int[256];
            for (int p:next) histogram[p>>>24]++;
            // A final single texel cannot represent fractional coverage. Keep
            // nonempty crowns present instead of making the last LOD disappear.
            int wanted=coverage==0?0:Math.max(1,(int)Math.round(coverage*next.length));
            int present=0;
            for(int alpha=ALPHA_TEST;alpha<256;alpha++) present+=histogram[alpha];
            int count=0,best=ALPHA_TEST,error=Math.abs(present-wanted);
            for (int threshold=255;threshold>=1;threshold--) {
                count+=histogram[threshold];
                int difference=Math.abs(count-wanted);
                if (difference<error || (difference==error && Math.abs(threshold-ALPHA_TEST)<Math.abs(best-ALPHA_TEST))) {
                    error=difference;best=threshold;
                }
            }
            double scale=114.5/(best-.5);
            int[] adjusted=next.clone();
            for (int i=0;i<adjusted.length;i++) {
                int alpha=Math.min(255,(int)Math.round((next[i]>>>24)*scale));
                adjusted[i]=(next[i]&0x00ffffff)|(alpha<<24);
            }
            result.add(new Mip(w,h,adjusted));
            // Do not accumulate the coverage adjustment into the next filter.
            raw=next; width=w; height=h;
        }
        return result;
    }
}
