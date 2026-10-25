import dev.realworldmc.client.CampusFoliage;
import java.nio.*;
import java.nio.file.*;
import java.util.*;
public class FoliageCheck {
 static void check(boolean ok,String text){if(!ok)throw new AssertionError(text);}
 static double distance(float[] p,int a,int b,int size){double total=0;for(int i=0;i<size;i++)total+=Math.pow((double)p[a+i]-p[b+i],2);return Math.sqrt(total);}
 public static void main(String[] args)throws Exception{
  int cards=0,groups=0;double maximumScaleError=0;boolean textureChecked=false;
  for(String row:Files.readAllLines(Path.of(args[0]))){
   String[] fields=row.split("\\|",3);int id=Integer.parseInt(fields[1]);boolean vegetation=fields[0].equals("vegetation");check(CampusFoliage.isTree(id)==vegetation,"Tile material classification: "+row);if(!vegetation)continue;String file=fields[2];check(CampusFoliage.applies(id,1)&&!CampusFoliage.applies(id,0),"Leaf/wood classification");
   ByteBuffer b=ByteBuffer.wrap(Files.readAllBytes(Path.of(file))).order(ByteOrder.LITTLE_ENDIAN);b.position(4);int parts=b.getInt();check(parts==2,"two tree materials");b.position(32);
   for(int part=0;part<parts;part++){
    int n=b.getInt(),w=b.getInt(),h=b.getInt();b.getInt();float[] p=new float[n*5];for(int i=0;i<p.length;i++)p[i]=b.getFloat();int[] pixels=new int[w*h];for(int i=0;i<pixels.length;i++)pixels[i]=b.getInt();if(part!=1)continue;
    float[] saved=p.clone(),uv=CampusFoliage.cards(p);check(Arrays.equals(p,saved),"Input geometry mutated");check(uv.length==p.length*3,"bounded triangle count");
    for(int o=0;o<p.length;o+=30){
     int out=o*3;double[] x=new double[3],y=new double[3],normal=new double[3];double xx=0,yy=0;
     for(int axis=0;axis<3;axis++){x[axis]=(double)p[o+5+axis]-p[o+axis];y[axis]=(double)p[o+25+axis]-p[o+axis];xx+=x[axis]*x[axis];yy+=y[axis]*y[axis];}
     normal[0]=x[1]*y[2]-x[2]*y[1];normal[1]=x[2]*y[0]-x[0]*y[2];normal[2]=x[0]*y[1]-x[1]*y[0];double planeLength=Math.sqrt(xx*yy);double area=0;
     for(int i=out;i<out+90;i+=5){double u=0,v=0,plane=0;for(int axis=0;axis<3;axis++){double delta=(double)uv[i+axis]-p[o+axis];u+=delta*x[axis];v+=delta*y[axis];plane+=delta*normal[axis];}check(u/xx>=-.0001&&u/xx<=1.0001&&v/yy>=-.0001&&v/yy<=1.0001,"Foliage expanded beyond source card");check(Math.abs(plane/planeLength)<.00005,"Leaf plane moved");}
     for(int i=out;i<out+90;i+=15){
      for(int[]edge:new int[][]{{i,i+5},{i+5,i+10}}){double world=distance(uv,edge[0],edge[1],3),atlas=distance(uv,edge[0]+3,edge[1]+3,2);double error=Math.abs(world-atlas*CampusFoliage.ATLAS_METRES);maximumScaleError=Math.max(error,maximumScaleError);check(error<.00005,"physical atlas scale "+error+" world="+world+" uv="+atlas+" file="+file+" source="+p[o]+","+p[o+1]+","+p[o+2]);}
      double ax=uv[i+5]-uv[i],ay=uv[i+6]-uv[i+1],az=uv[i+7]-uv[i+2],bx=uv[i+10]-uv[i],by=uv[i+11]-uv[i+1],bz=uv[i+12]-uv[i+2];area+=.5*Math.sqrt(Math.pow(ay*bz-az*by,2)+Math.pow(az*bx-ax*bz,2)+Math.pow(ax*by-ay*bx,2));
     }
     check(area/planeLength>.56&&area/planeLength<.72,"Rounded patch area outside declared range");cards++;
    }
    groups++;
    if(!textureChecked){
     long covered=Arrays.stream(pixels).filter(x->(x>>>24)>=115).count();double target=(double)covered/pixels.length;System.out.println("Original coverage="+target);
     for(var mip:CampusFoliage.mipmaps(w,h,pixels)){
      long count=Arrays.stream(mip.pixels()).filter(x->(x>>>24)>=115).count();double coverage=(double)count/mip.pixels().length;
      check(count>0,"Foliage disappeared at mip "+mip.width());if(mip.pixels().length>=256)check(Math.abs(target-coverage)<.03,"Mip coverage drift");System.out.println("Mip "+mip.width()+"x"+mip.height()+" coverage="+coverage);
     }
     textureChecked=true;
    }
   }
  }
  var transparent=CampusFoliage.mipmaps(2,2,new int[]{0,0,0,0});check(transparent.get(0).pixels()[0]==0,"Transparent atlas gained coverage");
  var colour=CampusFoliage.mipmaps(2,2,new int[]{0xff00ff00,0x00ff0000,0x00ff0000,0x00ff0000});check((colour.get(0).pixels()[0]&0xffffff)==0x00ff00,"Transparent colour bled into opaque mip");
  int[] opaque={0xff112233,0xff112233,0xff112233,0xff112233};check(CampusFoliage.mipmaps(2,2,opaque).get(0).pixels()[0]==opaque[0],"Opaque atlas changed");
  check(!CampusFoliage.applies(1000010000,0)&&!CampusFoliage.applies(1000030000,1),"Other materials included");
  System.out.println("PASS groups="+groups+" cards="+cards+" maximumPhysicalScaleErrorMetres="+maximumScaleError);
 }
}
