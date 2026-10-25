#version 150
uniform sampler2D Sampler0;
uniform sampler2D Sampler1;
uniform sampler2D Sampler2;
uniform sampler2D Sampler3;
uniform sampler2D Sampler4;
uniform sampler2D Sampler5;
uniform sampler2D Sampler6;
uniform sampler2D Sampler7;
uniform sampler2D Sampler8;
uniform sampler2D Sampler9;
uniform sampler2D Sampler10;
uniform sampler2D ReactorGroundTexture;
uniform vec4 ColorModulator;
uniform vec3 CampusFogColor;
uniform vec3 CameraPosition;
uniform float MaterialDetail;
in vec2 texCoord0;
in vec3 worldPosition;
in float viewDistance;
out vec4 fragColor;
// BEGIN GENERATED REACTOR GROUND MAPPING
vec2 reactorGroundUv(vec2 position) { return vec2(position.x-208.0,-0.0-position.y)/256.0; }
// END GENERATED REACTOR GROUND MAPPING
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1,311.7))) * 43758.5453); }
float noise(vec2 p) {
    vec2 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f);
    return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1)),f.x),f.y);
}
vec3 groundTexture(sampler2D source,vec3 p,vec3 weights) {
    // Three world-space projections keep grain at a consistent metre scale
    // on banks as well as flat ground. Tile UVs still locate the real imagery.
    vec3 dx=dFdx(p),dy=dFdy(p),value=vec3(0);
    if(weights.x>0.0)value+=textureGrad(source,p.zy,dx.zy,dy.zy).rgb*weights.x;
    if(weights.y>0.0)value+=textureGrad(source,p.xz,dx.xz,dy.xz).rgb*weights.y;
    if(weights.z>0.0)value+=textureGrad(source,p.xy,dx.xy,dy.xy).rgb*weights.z;
    return value;
}
vec3 groundNormalDetail(sampler2D source,vec3 p,vec3 weights) {
    vec3 dx=dFdx(p),dy=dFdy(p),detail=vec3(0);
    // Blend tangent perturbations, not axis normals: a neutral normal map
    // must leave the actual surface normal unchanged at every slope.
    if(weights.x>0.0){vec3 n=textureGrad(source,p.zy,dx.zy,dy.zy).xyz*2.0-1.0;detail+=vec3(0,n.y,n.x)*weights.x;}
    if(weights.y>0.0){vec3 n=textureGrad(source,p.xz,dx.xz,dy.xz).xyz*2.0-1.0;detail+=vec3(n.x,0,n.y)*weights.y;}
    if(weights.z>0.0){vec3 n=textureGrad(source,p.xy,dx.xy,dy.xy).xyz*2.0-1.0;detail+=vec3(n.x,n.y,0)*weights.z;}
    return detail;
}
uniform vec3 CampusSunDirection;
uniform sampler2D Sampler11;
uniform mat4 CampusShadowMatrix;
uniform float CampusShadowStrength;
// Canopy frames encode a constant face normal in each triangle's UVs.
// Screen derivatives of world positions are unstable on centimetre-wide faces.
vec3 canopyFrameNormal() {
    vec2 oct=texCoord0*2.0-1.0;
    vec3 n=vec3(oct.x,1.0-abs(oct.x)-abs(oct.y),oct.y);
    if(n.y<0.0)n.xz=(1.0-abs(n.zx))*mix(vec2(-1),vec2(1),greaterThanEqual(n.xz,vec2(0)));
    return normalize(n);
}
float campusShadow(vec3 p) {
    if(CampusShadowStrength<=0.0)return 0.0;
    vec3 n=(MaterialDetail>=29.9&&MaterialDetail<=33.1)?canopyFrameNormal():normalize(cross(dFdx(p),dFdy(p)));
    if(dot(n,CameraPosition-p)<0.0)n=-n;
    // A nearly parallel receiver has an ill-conditioned light-space plane.
    // Fade shadow reception over the last three degrees, where direct solar
    // irradiance already tends to zero, instead of inventing depth gradients.
    float grazingWeight=smoothstep(.005,.05,abs(dot(n,CampusSunDirection)));
    if(grazingWeight<=0.0)return 0.0;
    vec4 projected=CampusShadowMatrix*vec4(p+n*.01,1.0);
    vec3 at=projected.xyz/projected.w*.5+.5;
    if(any(lessThan(at,vec3(0)))||any(greaterThan(at,vec3(1))))return 0.0;
    vec3 dx=dFdx(at),dy=dFdy(at);
    float determinant=dx.x*dy.y-dx.y*dy.x;
    vec2 plane=abs(determinant)>1e-12?vec2(dx.z*dy.y-dy.z*dx.y,dx.x*dy.z-dy.x*dx.z)/determinant:vec2(0);
    if(MaterialDetail>=29.9&&MaterialDetail<=33.1) {
        // The orthographic light-space plane follows the stable face normal.
        // This also avoids unstable derivative ratios on thin triangles.
        vec3 lightNormal=transpose(inverse(mat3(CampusShadowMatrix)))*n;
        if(abs(lightNormal.z)>1e-8)plane=-lightNormal.xy/lightNormal.z;
    }
    float shade=0.0;
    for(int y=-1;y<=1;y++)for(int x=-1;x<=1;x++){
        vec2 sampleUv=(floor(at.xy*4096.0)+vec2(x,y)+.5)/4096.0;
        float nearest=textureLod(Sampler11,sampleUv,0.0).r;
        float compare=at.z+dot(plane,sampleUv-at.xy)-.00003;
        shade+=compare>nearest?1.0:0.0;
    }
    float edge=1.0-smoothstep(.80,.98,max(abs(at.x*2.0-1.0),abs(at.y*2.0-1.0)));
    return shade/9.0*edge*grazingWeight;
}


uniform sampler2D PlanarTexture;
uniform mat4 PlanarMatrix;
uniform vec4 PlanarPlane;
uniform float PlanarStrength;
uniform float PlanarBaseWeight;

// Exact normals of the twelve surveyed hall roof triangles, upward-facing.
// Snapping the derivative estimate prevents metre-scale UV drift from per-pixel
// normal roundoff; geometry and its silhouette are not altered.
const vec3 PhysicsHallNormals[12]=vec3[12](
    vec3(0.665328984,0.555913342,0.498294791),
    vec3(0.172264259,0.571918430,-0.802018911),
    vec3(0.012341618,0.801714132,0.597580233),
    vec3(0.475835860,0.671028351,-0.568595803),
    vec3(0.391378111,0.654636412,0.646741326),
    vec3(-0.519656512,0.635160541,0.571426458),
    vec3(0.880119923,0.420527729,-0.220330093),
    vec3(-0.258440343,0.537826865,0.802465484),
    vec3(-0.179182528,0.746108499,-0.641261046),
    vec3(-0.167090001,0.958358591,-0.231580964),
    vec3(0.721755615,0.587186019,-0.366444281),
    vec3(-0.276288148,0.955604285,0.102397804)
);

// BEGIN GENERATED PHYSICS GROUND MAPPING
vec2 physicsGroundUv(vec2 position) { return vec2(position.x-256.0,-112.0-position.y)/256.0; }
float physicsGroundBlend(vec2 position) {
    vec2 local=mat2(0.9993971583,0.0347926405,0.0347926334,-0.9993969108)*(position-vec2(270.6240320653,-127.2232715119));
    float edge=min(min(local.x,220.0-local.x),min(local.y,180.0-local.y));
    return smoothstep(0.0,8.0,edge);
}
// END GENERATED PHYSICS GROUND MAPPING

// BEGIN GENERATED WOODLAND GROUND MAPPING
vec2 woodlandGroundUv(vec2 position) { return vec2(position.x-352.0,32.0-position.y)/512.0; }
// END GENERATED WOODLAND GROUND MAPPING
// BEGIN GENERATED LABORATORY SITE MAPPING
vec2 laboratorySiteUv(vec2 position) { return vec2(position.x-336.0,-272.0-position.y)/128.0; }
// END GENERATED LABORATORY SITE MAPPING
// BEGIN GENERATED PHYSICS II SITE MAPPING
vec2 physicsIISiteUv(vec2 position) { return vec2(position.x-224.0,-272.0-position.y)/224.0; }
// END GENERATED PHYSICS II SITE MAPPING
// BEGIN GENERATED NORTH GROUND MAPPING
vec2 northGroundUv(vec2 position) { return vec2(position.x-256.0,-304.0-position.y)/192.0; }
// END GENERATED NORTH GROUND MAPPING
void main() {
    vec3 planarRadiance=vec3(0); float planarWeight=0.;
    float frameDirect=0.0;
    vec4 color=texture(Sampler0,texCoord0);
    if(abs(MaterialDetail-13.0)<.1){
        // Average fine timber boards over a slightly wider pixel footprint.
        // MapTile must also lift Minecraft's initial level-zero sampling clamp.
        vec2 size=vec2(textureSize(Sampler0,0));
        float footprint=max(length(dFdx(texCoord0)*size),length(dFdy(texCoord0)*size));
        color=textureLod(Sampler0,texCoord0,max(0.0,log2(max(footprint,1.0))+1.5));
    }
    if(color.a<(MaterialDetail>3.5&&MaterialDetail<4.5?0.45:0.1))discard;
    // Atom-Ei dome: smooth source-derived normals are octahedrally encoded
    // in this solid-colour part's UVs. Panel pitch and patina are estimates.
    if(abs(MaterialDetail-27.0)<.1) {
        vec2 oct=texCoord0*2.0-1.0;
        vec3 n=vec3(oct.x,1.0-abs(oct.x)-abs(oct.y),oct.y);
        if(n.y<0.0)n.xz=(1.0-abs(n.zx))*sign(n.xz);
        n=normalize(n);
        vec3 view=normalize(CameraPosition-worldPosition);
        vec2 radial=worldPosition.xz-vec2(245.514882351,-96.722567877);
        float angle=atan(radial.y,radial.x);
        float bands=(angle/6.28318530718+.5)*192.0;
        float width=max(fwidth(bands),.0001);
        float seamDistance=abs(fract(bands+.5)-.5);
        float seams=(1.0-smoothstep(.018,.018+width,seamDistance))*(1.0-smoothstep(.25,.8,width));
        // The documented top cap avoids converging hundreds of dark lines.
        seams*=smoothstep(2.4,4.0,length(radial));
        // The 2017 TUM exterior photo shows staggered sheet ends, local
        // reflectance changes and shallow panel waviness. Dimensions and
        // weathering below are estimates, not projected reference pixels.
        float panel=floor(bands+.5);
        float course=(worldPosition.y-69.0)/2.1+hash(vec2(panel,19.0));
        vec2 sheet=vec2(panel,floor(course+.5));
        float sheetVisibility=1.0-smoothstep(.25,.9,width);
        float jointWidth=max(fwidth(course),.0001);
        float joints=(1.0-smoothstep(.004,.004+jointWidth,abs(fract(course+.5)-.5)))
            *(1.0-smoothstep(.15,.6,jointWidth))*smoothstep(2.4,4.0,length(radial));
        float reflectance=mix(1.0,.95+.10*hash(sheet),sheetVisibility);
        float patina=(.94+.12*noise(vec2(bands*.21,worldPosition.y*.31)))
            *(.96+.08*noise(vec2(bands*1.7,worldPosition.y*1.9)))*reflectance;
        vec3 across=normalize(vec3(-radial.y,0,radial.x));
        vec3 uphill=normalize(cross(n,across));
        vec2 waviness=vec2(hash(sheet+vec2(17,5)),hash(sheet+vec2(3,29)))-.5;
        vec3 metalNormal=normalize(n+(across*waviness.x*.06+uphill*waviness.y*.035)*sheetVisibility);
        float diffuse=.60+.12*max(n.y,0.0)+.28*max(dot(metalNormal,CampusSunDirection),0.0);
        vec3 reflected=reflect(-view,metalNormal);
        vec3 environment=mix(vec3(.31,.34,.34),vec3(.66,.74,.81),smoothstep(-.12,.55,reflected.y));
        float roughnessPower=mix(20.0,65.0,hash(sheet+vec2(13,41)));
        float highlight=pow(max(dot(reflect(-CampusSunDirection,metalNormal),view),0.0),roughnessPower);
        float fresnel=pow(1.0-max(dot(metalNormal,view),0.0),4.0);
        color.rgb=vec3(.78,.79,.79)*patina*diffuse*(1.0-.18*seams-.075*joints)
            +environment*(.12+.08*fresnel)+vec3(.19)*highlight;

    }
    // Observed tan brick lower base. Original procedural mortar and subtle
    // brick variation; no copyrighted reference-photo pixels are embedded.
    if(abs(MaterialDetail-28.0)<.1) {
        vec2 radial=worldPosition.xz-vec2(245.514882351,-96.722567877);
        vec2 masonry=vec2(atan(radial.y,radial.x)*24.5,worldPosition.y-63.923447343);
        float row=floor(masonry.y/.075);
        vec2 brick=vec2(masonry.x/.25+.5*mod(row,2.0),masonry.y/.075);
        vec2 dist=min(fract(brick),1.0-fract(brick));
        vec2 aa=max(fwidth(brick),vec2(.0001));
        vec2 fill=smoothstep(vec2(.018,.04)-aa*.5,vec2(.018,.04)+aa*.5,dist);
        float mortar=(1.0-fill.x*fill.y)*(1.0-smoothstep(.35,1.2,max(aa.x,aa.y)));
        float variation=.94+.08*hash(vec2(floor(brick.x),row));
        color.rgb=mix(color.rgb*variation,vec3(.61,.58,.50),mortar*.72);
        vec3 n=normalize(cross(dFdx(worldPosition),dFdy(worldPosition)));
        if(dot(n,CameraPosition-worldPosition)<0.0)n=-n;
        color.rgb*=.68+.32*max(dot(n,CampusSunDirection),0.0);
    }
    if(MaterialDetail>=29.9&&MaterialDetail<=33.1) {
        vec3 n=canopyFrameNormal();
        if(abs(MaterialDetail-33.0)<.1) {
            // East hall: estimated 110 mm horizontal rib pitch. Fade the
            // perturbation below pixel resolution to avoid distant shimmer.
            float ribs=(worldPosition.y-63.92)/.11;
            float fade=1.0-smoothstep(.2,.8,fwidth(ribs));
            n=normalize(n+vec3(0.0,sin(ribs*6.2831853)*.38*fade,0.0));
        }
        if(dot(n,CameraPosition-worldPosition)<0.0)n=-n;
        frameDirect=.32*max(dot(n,CampusSunDirection),0.0);
        color.rgb*=.68+frameDirect;
    }
    // FRM II: estimated panel pitch on the surveyed facade. The normal is
    // analytic, so thin frames and large surfaces share stable lighting.
    if(abs(MaterialDetail-31.0)<.1) {
        vec3 n=canopyFrameNormal();
        vec2 east=normalize(vec2(.9855,.1697)),north=vec2(east.y,-east.x);
        float u=abs(dot(n.xz,east))>.7?dot(worldPosition.xz,north):dot(worldPosition.xz,east);
        float pitch=worldPosition.y>75.0?.9:3.3;
        vec2 panel=vec2(u/2.4,(worldPosition.y-63.93)/pitch);
        vec2 aa=max(fwidth(panel),vec2(.00001));
        vec2 distance=min(fract(panel),1.0-fract(panel));
        vec2 seam=(1.0-smoothstep(vec2(.004),vec2(.004)+aa,distance))
            *(1.0-smoothstep(vec2(.20),vec2(.65),aa));
        float variation=.98+.04*hash(floor(panel));
        color.rgb*=variation*(1.0-.20*max(seam.x,seam.y));
    }
    if(abs(MaterialDetail-32.0)<.1) {
        vec3 n=canopyFrameNormal(),view=normalize(CameraPosition-worldPosition);
        vec3 reflected=reflect(-view,n);
        vec3 environment=mix(vec3(.28,.32,.33),vec3(.64,.73,.80),smoothstep(-.1,.6,reflected.y));
        float seamCoordinate=dot(worldPosition.xz,normalize(vec2(.9855,.1697)))/1.2;
        float aa=max(fwidth(seamCoordinate),.0001);
        float seams=(1.0-smoothstep(.008,.008+aa,abs(fract(seamCoordinate+.5)-.5)))*(1.0-smoothstep(.2,.8,aa));
        color.rgb=color.rgb*(1.0-.14*seams)+environment*.13;
    }
    // Open canopy roof glazing, composited after opaque geometry. Its frame
    // casts shadows; glass does not cast the old solid-survey-volume shadow.
    if(abs(MaterialDetail-29.0)<.1) {
        vec3 n=normalize(cross(dFdx(worldPosition),dFdy(worldPosition)));
        vec3 view=normalize(CameraPosition-worldPosition);
        if(dot(n,view)<0.0)n=-n;
        vec3 reflected=reflect(-view,n);
        float fresnel=.04+.96*pow(1.0-max(dot(n,view),0.0),5.0);
        vec3 environment=mix(vec3(.29,.34,.28),vec3(.64,.73,.80),smoothstep(-.05,.3,reflected.y));
        float highlight=pow(max(dot(reflect(-CampusSunDirection,n),view),0.0),130.0);
        color.rgb=mix(color.rgb,environment,.75)+vec3(.30)*highlight;
        color.a=.20+.62*fresnel;
    }
    // The aerial image supplies surveyed colour and markings. Only close-range
    // material grain is reconstructed; it does not invent additional geometry.
    float proximity=1.0-smoothstep(10.0,28.0,viewDistance);
    // Only the twelve surveyed slopes of the middle Physics courtyard halls.
    // Other Physics roof surfaces retain their photographic ground treatment.
    bool physicsRoof=abs(MaterialDetail-18.0)<.1;
    vec3 physicsRoofNormal=normalize(cross(dFdx(worldPosition),dFdy(worldPosition)));
    if(physicsRoofNormal.y<0.0)physicsRoofNormal=-physicsRoofNormal;
    bool physicsHall=physicsRoof&&physicsRoofNormal.y>.2&&physicsRoofNormal.y<.97
        &&all(greaterThanEqual(worldPosition,vec3(352.68,65.93,-267.59)))
        &&all(lessThanEqual(worldPosition,vec3(374.17,73.14,-241.28)));
    bool calaGround=abs(MaterialDetail-26.0)<.1;
    bool northGround=abs(MaterialDetail-25.0)<.1;
    bool physicsIIGround=abs(MaterialDetail-24.0)<.1||northGround||calaGround;
    bool laboratoryGround=abs(MaterialDetail-23.0)<.1;
    bool woodlandGround=abs(MaterialDetail-20.0)<.1;
    bool physicsGround=abs(MaterialDetail-19.0)<.1||woodlandGround||laboratoryGround||physicsIIGround;
    if(((MaterialDetail>0.5&&MaterialDetail<1.5)||abs(MaterialDetail-15.0)<.1||(physicsRoof&&!physicsHall)||physicsGround)&&viewDistance<(physicsGround?160.0:110.0)) {
        vec3 geometric=normalize(cross(dFdx(worldPosition),dFdy(worldPosition)));
        if(geometric.y<0.0)geometric=-geometric;
        vec3 weights=pow(abs(geometric),vec3(4.0));
        // Flat terrain needs only its top projection. Fade negligible axes
        // to zero before sampling instead of paying for three maps everywhere.
        weights=max(weights-vec3(.002),vec3(0));
        weights/=max(weights.x+weights.y+weights.z,.0001);
        float grass=smoothstep(0.005,0.055,color.g-max(color.r,color.b));
        vec3 materialPosition=worldPosition*.5;
        vec3 concrete=groundTexture(Sampler1,materialPosition,weights), lawn=groundTexture(Sampler3,materialPosition,weights);
        float cLum=dot(concrete,vec3(.299,.587,.114)),gLum=dot(lawn,vec3(.299,.587,.114));
        float micro=mix(cLum/.5112,gLum/.3782,grass);
        color.rgb*=mix(1.0,clamp(micro,.65,1.35),proximity*.55);
        // Mapped land cover provides a sharp material boundary independently
        // of tree shadows and canopy colours baked into the aerial photograph.
        vec2 surfaceUv=vec2(worldPosition.x+352.0,256.0-worldPosition.z)/672.0;
        vec4 surfaceMask=texture(Sampler5,clamp(surfaceUv,0.0,1.0));
        vec3 mapped=surfaceMask.rgb;float soil=1.0-surfaceMask.a;float gravel=0.0;
        if(any(lessThan(surfaceUv,vec2(0)))||any(greaterThan(surfaceUv,vec2(1)))){mapped=vec3(0);soil=0.0;}
        if(physicsGround){
            vec2 physicsUv=calaGround?vec2(worldPosition.x-192.0,-432.0-worldPosition.z)/128.0:northGround?northGroundUv(worldPosition.xz):physicsIIGround?physicsIISiteUv(worldPosition.xz):laboratoryGround?laboratorySiteUv(worldPosition.xz):woodlandGround?woodlandGroundUv(worldPosition.xz):physicsGroundUv(worldPosition.xz);
            if(all(greaterThanEqual(physicsUv,vec2(0)))&&all(lessThanEqual(physicsUv,vec2(1)))){
                vec4 overlay=texture(Sampler6,physicsUv);
                float blend=(woodlandGround||laboratoryGround||physicsIIGround)?1.0:physicsGroundBlend(worldPosition.xz),woodland=1.0-overlay.a;
                float coverage=clamp(dot(overlay.rgb,vec3(1))+woodland,0.0,1.0)*blend;
                if(physicsIIGround){gravel=overlay.g*blend;overlay.g=0.0;}
                mapped=mapped*(1.0-coverage)+overlay.rgb*blend;
                soil=soil*(1.0-coverage)+woodland*blend;
            }
        }
        if(abs(MaterialDetail-15.0)<.1){mapped=vec3(0,1,0);soil=0.0;}
        float mappedTotal=mapped.r+mapped.g+mapped.b+soil+gravel;
        float mappedAmount=clamp(mappedTotal,0.0,1.0);
        float materialRange=1.0-smoothstep(35.0,110.0,viewDistance);
        vec3 aerial=texture(Sampler0,texCoord0).rgb;
        float aerialLum=dot(aerial,vec3(.299,.587,.114));
        float lawnShade=clamp(aerialLum/.29,.38,1.25);
        // A near-vertical face has almost no footprint in an aerial image.
        // Reduce its stretched photographic shading within mapped lawns;
        // real surface lighting and correctly scaled grain supply the detail.
        float steep=1.0-smoothstep(.25,.65,geometric.y);
        lawnShade=mix(lawnShade,.9,steep*.8);
        vec3 lawnColor=vec3(.24,.31,.145)*clamp(gLum/.3782,.45,1.65)*lawnShade;
        // Approximate small concrete paving units, only within a mapped paved
        // area. Derivative antialiasing avoids distant crawling joint lines.
        vec2 paving=worldPosition.xz/vec2(.4,.2);
        paving.x+=mod(floor(paving.y),2.0)*.5;
        vec2 edge=min(fract(paving),1.0-fract(paving))*vec2(.4,.2);
        float jointDistance=min(edge.x,edge.y),aa=max(fwidth(jointDistance),.001);
        float joint=1.0-smoothstep(.003-aa,.006+aa,jointDistance);
        float unitVariation=.95+.1*hash(floor(paving));
        vec3 pavingColor=vec3(.55,.54,.51)*clamp(aerialLum/.5,.4,1.2)*clamp(cLum/.5112,.7,1.3)*unitVariation*(1.0-.3*joint);
        vec3 gravelColor=vec3(0);
        if(gravel>.001){
            // The inferred parking aggregate uses the scan's three-metre scale.
            gravelColor=groundTexture(Sampler9,worldPosition/3.0,weights)*clamp(aerialLum/.5,.65,1.15);
        }
        vec3 asphaltColor=aerial;
        if(mapped.b>.001){
            // Four-metre scanned aggregate detail. Keep broad aerial shade,
            // with bounded highlights so washed-out pixels do not erase grain.
            vec3 asphalt=groundTexture(Sampler7,worldPosition*.25,weights);
            asphaltColor=asphalt*(calaGround?.85:clamp(aerialLum/.55,.4,1.2));
        }
        // The inferred planting bed uses a scanned leaf/soil material. Old
        // construction highlights must not wash this new surface white.
        vec3 soilColor=vec3(0);
        if(soil>.001)soilColor=groundTexture(Sampler9,worldPosition/1.3,weights)*.92;
        vec3 material=(mapped.r*lawnColor+mapped.g*pavingColor+mapped.b*asphaltColor+soil*soilColor+gravel*gravelColor)/max(mappedTotal,.0001);
        color.rgb=mix(color.rgb,material,mappedAmount*materialRange);
        grass=mix(grass,mapped.r/max(mappedTotal,.0001),mappedAmount);
        // Locally mapped reactor pavement/lawns use clean scanned materials:
        // photographic cars and cast shadows are not part of their albedo.
        if(physicsGround){
            vec2 reactorUv=reactorGroundUv(worldPosition.xz);
            if(all(greaterThanEqual(reactorUv,vec2(0)))&&all(lessThanEqual(reactorUv,vec2(1)))){
                vec4 overlay=texture(ReactorGroundTexture,reactorUv);
                float total=dot(overlay.rgb,vec3(1));
                float coverage=clamp(total,0.0,1.0)*overlay.a;
                float range=1.0-smoothstep(90.0,160.0,viewDistance);
                vec3 cleanGrass=vec3(.24,.31,.145)*clamp(gLum/.3782,.45,1.65)*.95;
                vec3 cleanPaving=vec3(.55,.54,.51)*clamp(cLum/.5112,.7,1.3)*unitVariation*(1.0-.3*joint);
                vec3 cleanAsphalt=vec3(0);
                if(overlay.b>.001)cleanAsphalt=groundTexture(Sampler7,worldPosition*.25,weights)*.85;
                vec3 clean=(overlay.r*cleanGrass+overlay.g*cleanPaving+overlay.b*cleanAsphalt)/max(total,.0001);
                color.rgb=mix(color.rgb,clean,coverage*range);
                grass=mix(grass,overlay.r/max(total,.0001),coverage);
                mapped.b=mix(mapped.b,overlay.b/max(total,.0001),coverage);
                soil*=1.0-coverage;gravel*=1.0-coverage;
            }
        }
        if(proximity>0.0){
            vec3 cn=groundNormalDetail(Sampler2,materialPosition,weights),gn=groundNormalDetail(Sampler4,materialPosition,weights);
            vec3 detail=mix(cn,gn,grass);
            if(mapped.b>.001){
                vec3 asphaltNormal=groundNormalDetail(Sampler8,worldPosition*.25,weights);
                detail=mix(detail,asphaltNormal,clamp(mapped.b,0.0,1.0));
            }
            if(gravel>.001)
                detail=mix(detail,groundNormalDetail(Sampler10,worldPosition/3.0,weights),gravel);
            if(soil>.001)detail=mix(detail,groundNormalDetail(Sampler10,worldPosition/1.3,weights),soil);
            detail-=geometric*dot(detail,geometric);
            vec3 n=normalize(geometric+detail*.35);
            vec3 sun=CampusSunDirection;
            color.rgb*=mix(1.0,(.55+.45*max(dot(n,sun),0.0))/.91,proximity);
        }
    }
    if(physicsHall) {
        // Source photograph supports seamed grey cladding, but the 0.5 m
        // panel spacing and fine surface response are reconstruction estimates.
        vec3 n=physicsRoofNormal;
        float alignment=-1.0;
        for(int i=0;i<12;i++){
            float match=dot(physicsRoofNormal,PhysicsHallNormals[i]);
            if(match>alignment){alignment=match;n=PhysicsHallNormals[i];}
        }
        vec3 across=normalize(cross(vec3(0,1,0),n));
        float u=dot(worldPosition-vec3(363,68,-254),across),panel=u/.5;
        float signedEdge=(fract(panel+.5)-.5)*.5;
        float aa=max(fwidth(u),.001);
        float ridge=1.0-smoothstep(.006-aa,.014+aa,abs(signedEdge));
        float visibility=1.0-smoothstep(.04,.15,aa);
        ridge*=visibility;
        n=normalize(n+across*sign(signedEdge)*ridge*.85);
        float variation=.96+.08*hash(vec2(floor(panel+.5),floor(n.x*100.0)));
        float aerialLum=dot(color.rgb,vec3(.299,.587,.114));
        vec3 metal=vec3(.43,.45,.46)*clamp(aerialLum/.5,.65,1.2)*variation;
        metal*=.985+.03*noise(worldPosition.xz*35.0);
        metal*=1.0-.18*ridge;
        metal*=.60+.40*max(dot(n,CampusSunDirection),0.0);
        vec3 view=normalize(CameraPosition-worldPosition);
        vec3 halfVector=normalize(view+CampusSunDirection);
        metal+=vec3(.08)*pow(max(dot(n,halfVector),0.0),35.0)*max(dot(n,CampusSunDirection),0.0);
        float range=1.0-smoothstep(45.0,110.0,viewDistance);
        color.rgb=mix(color.rgb,metal,range);
    }
    if(abs(MaterialDetail-17.0)<.1) {
        // Physics I: generic CC0 exposed aggregate at its 2.4 m scan scale.
        // Retain the estimated building colour; this is material grain, not
        // claimed photographic coverage of the actual facade.
        vec3 n=normalize(cross(dFdx(worldPosition),dFdy(worldPosition)));
        if(dot(n,CameraPosition-worldPosition)<0.0)n=-n;
        vec3 weights=pow(abs(n),vec3(4.0));weights/=max(dot(weights,vec3(1)),.0001);
        vec3 p=worldPosition/2.4;
        vec3 grain=groundTexture(Sampler1,p,weights);
        float lum=dot(grain,vec3(.299,.587,.114));
        color.rgb*=mix(1.0,clamp(lum/.40425466,.4,1.6),.85);
        vec3 detail=groundNormalDetail(Sampler2,p,weights);detail-=n*dot(detail,n);
        n=normalize(n+detail*.30*proximity);
        color.rgb*=.68+.32*max(dot(n,CampusSunDirection),0.0);
    }
    if(abs(MaterialDetail-14.0)<.1) {
        vec3 n=normalize(cross(dFdx(worldPosition),dFdy(worldPosition)));
        if(dot(n,CameraPosition-worldPosition)<0.0)n=-n;
        vec3 weights=pow(abs(n),vec3(4.0));weights/=max(dot(weights,vec3(1)),.0001);
        vec3 grain=groundTexture(Sampler1,worldPosition*.5,weights);
        float lum=dot(grain,vec3(.299,.587,.114));
        color.rgb*=mix(1.0,clamp(lum/.5112,.72,1.22),.7);
        vec3 detail=groundNormalDetail(Sampler2,worldPosition*.5,weights);detail-=n*dot(detail,n);
        n=normalize(n+detail*.18*proximity);
        color.rgb*=.68+.32*max(dot(n,CampusSunDirection),0.0);
    }
    if(abs(MaterialDetail-12.0)<.1) {
        vec3 dx=dFdx(worldPosition),dy=dFdy(worldPosition);
        vec2 ux=dFdx(texCoord0),uy=dFdy(texCoord0);
        vec3 n=normalize(cross(dx,dy));
        if(dot(n,CameraPosition-worldPosition)<0.0)n=-n;
        float determinant=ux.x*uy.y-ux.y*uy.x;
        if(abs(determinant)>1e-12&&viewDistance<50.0){
            vec3 tangent=(dx*uy.y-dy*ux.y)/determinant;
            vec3 bitangent=(-dx*uy.x+dy*ux.x)/determinant;
            tangent=normalize(tangent-n*dot(n,tangent));
            bitangent=normalize(bitangent-n*dot(n,bitangent));
            vec3 detail=texture(Sampler6,texCoord0).xyz*2.0-1.0;
            float strength=.45*(1.0-smoothstep(20.0,50.0,viewDistance));
            n=normalize(n+strength*(tangent*detail.x+bitangent*detail.y));
        }
        color.rgb*=.65+.35*max(dot(n,CampusSunDirection),0.0);
    }
    if(abs(MaterialDetail-9.0)<.1) {
        vec3 roofN=normalize(cross(dFdx(worldPosition),dFdy(worldPosition)));
        if(dot(roofN,CameraPosition-worldPosition)<0.0)roofN=-roofN;
        if(roofN.y<-.05)color.rgb=vec3(.25,.27,.28);
    }
    if((MaterialDetail>1.5&&MaterialDetail<3.5)||(MaterialDetail>5.5&&MaterialDetail<8.5)||abs(MaterialDetail-11.0)<.1||abs(MaterialDetail-13.0)<.1||abs(MaterialDetail-16.0)<.1) {
        vec3 n=normalize(cross(dFdx(worldPosition),dFdy(worldPosition)));
        vec3 view=normalize(CameraPosition-worldPosition);
        if(dot(n,view)<0.0)n=-n;
        if(abs(n.y)<0.7) {
            vec3 sun=CampusSunDirection;
            if(MaterialDetail>6.5&&MaterialDetail<8.5) {
                vec2 uv=abs(n.x)>abs(n.z)?worldPosition.zy*.5:worldPosition.xy*.5;
                vec3 nm=texture(Sampler2,uv).xyz*2.0-1.0;
                vec3 tangent=abs(n.x)>abs(n.z)?vec3(0,0,1):vec3(1,0,0);
                n=normalize(n+proximity*.23*(tangent*nm.x+vec3(0,1,0)*nm.y));
            }
            float diffuse=0.68+0.32*max(dot(n,sun),0.0);
            float lum=dot(color.rgb,vec3(0.2126,0.7152,0.0722));
            float glass=(MaterialDetail<2.5||abs(MaterialDetail-6.0)<0.1)?1.0:0.0;
            vec3 reflected=reflect(-view,n);
            float sky=smoothstep(-0.08,0.18,reflected.y);
            vec3 environment=mix(vec3(0.08,0.14,0.10),vec3(0.42,0.55,0.68),sky);
            environment*=0.8+0.2*noise(reflected.xz*8.0);
            float fresnel=0.04+0.96*pow(1.0-max(dot(n,view),0.0),5.0);
            vec3 glazing=vec3(0.025,0.038,0.045)+environment*(0.5+0.5*fresnel);
            float highlight=pow(max(dot(reflect(-sun,n),view),0.0),180.0);
            glazing+=vec3(0.8,0.75,0.62)*highlight;
            glazing=mix(glazing,color.rgb*(.82+.18*diffuse),.45*(1.0-.45*fresnel));
// Insert after the analytic glazing colour is computed, before final lighting.
if(glass>.5&&PlanarStrength>0.0&&abs(dot(PlanarPlane,vec4(worldPosition,1.0)))<.03&&abs(dot(n,PlanarPlane.xyz))>.999){
    vec4 projected=PlanarMatrix*vec4(worldPosition,1.0);
    vec2 uv=projected.xy/projected.w*.5+.5;
    if(projected.w>0.0&&all(greaterThanEqual(uv,vec2(0)))&&all(lessThanEqual(uv,vec2(1)))){
        vec3 scene=texture(PlanarTexture,uv).rgb;
        planarRadiance=scene*vec3(.90,.96,1.0);
        planarWeight=(PlanarBaseWeight+(.95-PlanarBaseWeight)*fresnel)*PlanarStrength;
    }
}

            vec3 metal=color.rgb*(abs(MaterialDetail-16.0)<.1?1.0:(MaterialDetail>6.5&&MaterialDetail<8.5?1.08:0.82))*diffuse;
            // Smooth powder-coated Galileo aluminium, without concrete normals.
            if(abs(MaterialDetail-16.0)<.1)metal*=.994+.006*noise(worldPosition.xz*70.0);
            if(MaterialDetail>6.5&&MaterialDetail<8.5){
                vec2 materialUv=abs(n.x)>abs(n.z)?worldPosition.zy*.5:worldPosition.xy*.5;
                vec3 grain=texture(Sampler1,materialUv).rgb;
                float lum=dot(grain,vec3(.299,.587,.114));
                metal*=mix(1.0,clamp(lum/.5112,.7,1.2),proximity*.4);
            }
            color.rgb=mix(metal,glazing,glass);
        }
    }
    // New Physics laboratory: CC0 photographed zinc and visually perforated screens.
    // Generic material by Sisters.seamless; the1m repeat is an estimate.
    if(abs(MaterialDetail-21.0)<.1||abs(MaterialDetail-22.0)<.1) {
        vec3 n=normalize(cross(dFdx(worldPosition),dFdy(worldPosition)));
        vec3 view=normalize(CameraPosition-worldPosition);
        if(dot(n,view)<0.0)n=-n;
        vec3 tangent=abs(n.y)<.8?normalize(vec3(-n.z,0,n.x)):vec3(1,0,0);
        vec2 uv=vec2(dot(worldPosition,tangent),worldPosition.y);
        vec3 zinc=texture(Sampler1,uv).rgb;
        vec3 grain=clamp(zinc/vec3(.58248867,.60249385,.60750355),vec3(.65),vec3(1.35));
        float diffuse=.84+.16*max(dot(n,CampusSunDirection),0.0);
        float highlight=pow(max(dot(reflect(-CampusSunDirection,n),view),0.0),18.0);
        color.rgb=color.rgb*grain*diffuse+vec3(.075)*highlight;
        if(abs(MaterialDetail-22.0)<.1) {
            vec2 grid=uv/.032;
            grid.x+=.5*mod(floor(grid.y),2.0);
            float hole=length(fract(grid)-.5);
            float aa=max(fwidth(hole),.025);
            float dots=1.0-smoothstep(.15-aa,.15+aa,hole);
            float resolved=1.0-smoothstep(.35,.9,max(fwidth(grid.x),fwidth(grid.y)));
            color.rgb*=1.0-.38*mix(.071,dots,resolved);
        }
    }
    if(MaterialDetail>3.5&&MaterialDetail<5.5) {
        vec3 n=normalize(cross(dFdx(worldPosition),dFdy(worldPosition)));
        vec3 sun=CampusSunDirection;
        float lighting=0.58+0.42*abs(dot(n,sun));
        if(MaterialDetail<4.5) {
            // Double-sided leaf transmission; cutout atlas preserves holes between leaves.
            lighting=0.66+0.34*abs(dot(n,sun));
            lighting*=0.9+0.1*noise(worldPosition.xz*1.7);
        }
        color.rgb*=lighting;
    }
    // Thin frames already receive ambient plus explicit direct irradiance.
    // Shadow only that direct term: shadow-map edge samples must not dapple
    // an underside whose normal already excludes direct sunlight.
    float shadowReception=(MaterialDetail>=29.9&&MaterialDetail<=33.1)?frameDirect/(.68+frameDirect):1.0;
    if(shadowReception>0.0001)color.rgb*=1.0-CampusShadowStrength*shadowReception*campusShadow(worldPosition);
    color*=ColorModulator;
    color.rgb=mix(color.rgb,planarRadiance,planarWeight);
    color.rgb=mix(color.rgb,CampusFogColor,smoothstep(650.0,1000.0,viewDistance));
    fragColor=color;
}
