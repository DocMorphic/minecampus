package dev.realworldmc.client;

import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/** Same loaded scene, baseline/candidate/baseline; isolated QA resource pack only. */
public final class CampusMaterialBenchmark {
    private static final String PACK="file/campus-material-benchmark";
    private static final Path ROOT=Path.of("resourcepacks/campus-material-benchmark");
    private static final String[] PHASES={"baseline","candidate","baseline"};
    private static final List<com.google.gson.JsonObject> results=new ArrayList<>();
    private static List<String> original;
    private static int phase,ticks;
    private static boolean started;
    private static volatile boolean reloading;
    private static volatile Throwable failure;
    private static final List<Integer> samples=new ArrayList<>();

    public static void tick(Minecraft mc) throws Exception {
        if(failure!=null)throw new IllegalStateException("Benchmark reload failed",failure);
        if(reloading)return;
        if(!started){
            if(original==null){original=new ArrayList<>(mc.getResourcePackRepository().getSelectedIds());original.remove(PACK);}
            var shader=ROOT.resolve("assets/realworldmc/shaders/core/campus_ground.fsh");
            Files.createDirectories(shader.getParent());
            Files.writeString(ROOT.resolve("pack.mcmeta"),"{\"pack\":{\"pack_format\":34,\"description\":\"Isolated campus material comparison\"}}");
            Files.writeString(shader,Files.readString(Path.of("benchmark-"+PHASES[phase]+".fsh")));
            var repository=mc.getResourcePackRepository();repository.reload();
            var selected=new ArrayList<>(original);selected.remove(PACK);selected.add(PACK);repository.setSelected(selected);
            reloading=true;started=true;ticks=0;samples.clear();
            mc.reloadResourcePacks().whenComplete((ignored,error)->mc.execute(()->{
                failure=error;
                try{
                    // Resource reload can reuse GL texture ids; force the same
                    // mipmap/anisotropic setup for every comparison phase.
                    var prepared=CampusMaterials.class.getDeclaredField("prepared");prepared.setAccessible(true);
                    java.util.Arrays.fill((int[])prepared.get(null),-1);
                }catch(Throwable setup){failure=setup;}
                reloading=false;
            }));
            return;
        }
        // Six seconds for shader compilation/upload, then six one-second FPS samples.
        ++ticks;
        if(ticks==1){
            var location=net.minecraft.resources.ResourceLocation.fromNamespaceAndPath("realworldmc","shaders/core/campus_ground.fsh");
            try(var input=mc.getResourceManager().getResource(location).orElseThrow().open()){
                if(!java.util.Arrays.equals(input.readAllBytes(),Files.readAllBytes(Path.of("benchmark-"+PHASES[phase]+".fsh"))))
                    throw new IllegalStateException("Benchmark shader override was not applied");
            }
        }
        if(ticks>120&&ticks%20==0)samples.add(mc.getFps());
        if(ticks<240)return;
        var result=new com.google.gson.JsonObject();result.addProperty("phase",PHASES[phase]);
        var values=new com.google.gson.JsonArray();for(int fps:samples)values.add(fps);result.add("fpsSamples",values);
        var sorted=new ArrayList<>(samples);sorted.sort(Integer::compareTo);
        result.addProperty("medianFps",(sorted.get(2)+sorted.get(3))/2.0);
        results.add(result);
        Files.writeString(Path.of("campus-material-benchmark-phase-"+phase+".json"),result.toString());
        try(var image=Screenshot.takeScreenshot(mc.getMainRenderTarget())){image.writeToFile(Path.of("campus-benchmark-"+phase+".png"));}
        if(++phase<PHASES.length){started=false;return;}
        mc.getResourcePackRepository().setSelected(original);
        var report=new com.google.gson.JsonObject();report.addProperty("status","PASS: same-scene baseline/candidate/baseline samples captured");
        report.addProperty("note","Six one-second FPS readings per phase after six seconds of warmup; a local comparison, not a universal performance guarantee.");
        var phases=new com.google.gson.JsonArray();for(var item:results)phases.add(item);report.add("phases",phases);
        Files.writeString(Path.of("campus-material-benchmark.json"),report.toString());mc.stop();
    }
}
