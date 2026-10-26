#version 150
uniform sampler2D Sampler0;
uniform sampler2D Sampler1;
uniform sampler2D Sampler3;
uniform sampler2D Sampler7;
uniform sampler2D ReactorGroundTexture;
uniform float SurveyedGround;
uniform vec4 ClipPlane;
uniform float AlphaCutoff;
uniform float WorldLight;
uniform vec3 SunDirection;
uniform vec3 ReflectedEye;
in vec2 texCoord0;
in vec3 worldPosition;
out vec4 fragColor;
// BEGIN GENERATED GALILEO EAST MATERIAL
// Bounded, inferred asphalt finish. Source: galileo-east-material.json.
// Restricted by the caller to terrain and the two ramp floor/collar parts.
const vec2 GalileoEastBoundary[4]=vec2[4](vec2(134.106582354,-143.750793024),vec2(119.479577941,-64.298269030),vec2(136.457533985,-61.172670083),vec2(150.284137384,-140.772545888));
float galileoEastCoverage(vec3 position) {
    if(position.y<59.0||position.y>66.0)return 0.0;
    float signedDistance=1e6;
    for(int i=0;i<4;i++){
        vec2 a=GalileoEastBoundary[i],b=GalileoEastBoundary[(i+1)%4];
        vec2 edge=b-a,p=position.xz-a;
        signedDistance=min(signedDistance,-1.0*(edge.x*p.y-edge.y*p.x)/length(edge));
    }
    // Entirely inward blending keeps the neighbouring planting untouched.
    return smoothstep(0.0,max(0.1200,fwidth(signedDistance)),signedDistance);
}
vec3 galileoEastAlbedo(vec3 position) {
    vec2 uv=position.xz/4.0000;
    return textureGrad(Sampler7,uv,dFdx(uv),dFdy(uv)).rgb*0.8500;
}
// END GENERATED GALILEO EAST MATERIAL
// BEGIN GENERATED LOW BUILDING PAVING
// DOP20 patio/path interpretation; hidden edges, slab size and finish are inferred.
float courtyardPatch0(vec2 p) {
    const vec2 boundary[10]=vec2[10](vec2(166.550338198,-29.185033768),vec2(171.540346046,-28.811193497),vec2(172.712792433,-26.849215547),vec2(172.931388058,-25.080541175),vec2(172.497846760,-22.974352234),vec2(169.294221547,-22.925784686),vec2(167.764393609,-23.819551219),vec2(166.104896628,-24.437662656),vec2(165.679463885,-26.013416795),vec2(166.057720831,-27.681264298));
    bool inside=false;float edgeDistance=1e6;
    for(int i=0;i<10;i++) {
        vec2 a=boundary[i],b=boundary[(i+1)%10],v=b-a;
        edgeDistance=min(edgeDistance,length(p-a-v*clamp(dot(p-a,v)/dot(v,v),0.0,1.0)));
        if((a.y>p.y)!=(b.y>p.y)) {
            float crossX=a.x+(p.y-a.y)*(b.x-a.x)/(b.y-a.y);
            if(p.x<crossX)inside=!inside;
        }
    }
    return inside?smoothstep(0.0,0.1800,edgeDistance):0.0;
}
float courtyardPatch1(vec2 p) {
    const vec2 boundary[12]=vec2[12](vec2(167.403703544,-16.907923424),vec2(168.721510958,-16.822021829),vec2(169.818564326,-16.143442610),vec2(171.279957710,-16.732953502),vec2(172.249117093,-16.979383054),vec2(172.164607189,-15.701551094),vec2(170.778990187,-14.989329598),vec2(169.932541382,-14.818676447),vec2(168.581716702,-15.105848431),vec2(167.226716943,-15.273093196),vec2(166.682365338,-15.732310023),vec2(166.907294463,-16.444914865));
    bool inside=false;float edgeDistance=1e6;
    for(int i=0;i<12;i++) {
        vec2 a=boundary[i],b=boundary[(i+1)%12],v=b-a;
        edgeDistance=min(edgeDistance,length(p-a-v*clamp(dot(p-a,v)/dot(v,v),0.0,1.0)));
        if((a.y>p.y)!=(b.y>p.y)) {
            float crossX=a.x+(p.y-a.y)*(b.x-a.x)/(b.y-a.y);
            if(p.x<crossX)inside=!inside;
        }
    }
    return inside?smoothstep(0.0,0.1800,edgeDistance):0.0;
}
float courtyardPatch2(vec2 p) {
    const vec2 boundary[10]=vec2[10](vec2(172.198916309,-23.585121862),vec2(172.955671803,-23.478728224),vec2(174.038808242,-22.400391613),vec2(173.910772494,-18.722623612),vec2(173.405629892,-16.859072490),vec2(171.989395645,-15.267384733),vec2(171.410635081,-15.887896210),vec2(172.629774061,-17.566493908),vec2(172.898612394,-21.839722919),vec2(172.114406406,-22.307289902));
    bool inside=false;float edgeDistance=1e6;
    for(int i=0;i<10;i++) {
        vec2 a=boundary[i],b=boundary[(i+1)%10],v=b-a;
        edgeDistance=min(edgeDistance,length(p-a-v*clamp(dot(p-a,v)/dot(v,v),0.0,1.0)));
        if((a.y>p.y)!=(b.y>p.y)) {
            float crossX=a.x+(p.y-a.y)*(b.x-a.x)/(b.y-a.y);
            if(p.x<crossX)inside=!inside;
        }
    }
    return inside?smoothstep(0.0,0.1800,edgeDistance):0.0;
}
float courtyardPavingCoverage(vec3 position) {
    if(position.y<60.0000||position.y>66.0000
       ||position.x<165.679463885||position.x>174.038808242
       ||position.z<-29.185033768||position.z>-14.818676447)return 0.0;
    return max(max(max(0.0,courtyardPatch0(position.xz)),courtyardPatch1(position.xz)),courtyardPatch2(position.xz));
}
vec3 courtyardPavingAlbedo(vec3 position) {
    vec2 axis=vec2(0.984396299,0.175965696);
    vec2 local=vec2(dot(position.xz,axis),dot(position.xz,vec2(-axis.y,axis.x)));
    vec2 uv=local/2.0000;
    vec3 grain=textureGrad(Sampler1,uv,dFdx(uv),dFdy(uv)).rgb;
    float luminance=dot(grain,vec3(.299,.587,.114));
    vec2 slabs=local/1.0000;
    vec2 edge=min(fract(slabs),1.0-fract(slabs))*1.0000;
    float distance=min(edge.x,edge.y),aa=max(fwidth(distance),.001);
    float joint=1.0-smoothstep(0.00300-aa,0.00600+aa,distance);
    float variation=.97+.06*fract(sin(dot(floor(slabs),vec2(127.1,311.7)))*43758.5453);
    return vec3(.55,.54,.51)*clamp(luminance/.5112,.75,1.25)*variation*(1.0-.25*joint);
}
// END GENERATED LOW BUILDING PAVING
// BEGIN GENERATED REACTOR GROUND MAPPING
vec2 reactorGroundUv(vec2 position) { return vec2(position.x-208.0,-0.0-position.y)/256.0; }
// END GENERATED REACTOR GROUND MAPPING
// BEGIN SHARED REACTOR MATERIAL
// Shared albedo calculation for the main and planar-reflection passes.
// Inputs are world-space metres; estimated paving sizes are not surveyed units.
float reactorGroundHash(vec2 p) { return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
vec3 reactorGroundTexture(sampler2D source,vec3 p,vec3 weights) {
    vec3 dx=dFdx(p),dy=dFdy(p),value=vec3(0);
    if(weights.x>0.0)value+=textureGrad(source,p.zy,dx.zy,dy.zy).rgb*weights.x;
    if(weights.y>0.0)value+=textureGrad(source,p.xz,dx.xz,dy.xz).rgb*weights.y;
    if(weights.z>0.0)value+=textureGrad(source,p.xy,dx.xy,dy.xy).rgb*weights.z;
    return value;
}
vec4 reactorGroundMaterial(vec3 position,vec3 weights,float distance,float concreteLum,float lawnLum,out vec4 classification) {
    classification=vec4(0);
    vec2 uv=reactorGroundUv(position.xz);
    if(any(lessThan(uv,vec2(0)))||any(greaterThan(uv,vec2(1))))return vec4(0);
    vec4 overlay=texture(ReactorGroundTexture,uv);
    float total=dot(overlay.rgb,vec3(1));
    float coverage=clamp(total,0.0,1.0)*overlay.a;
    if(coverage<=0.0)return vec4(0);
    classification=vec4(overlay.rgb/max(total,.0001),coverage);
    vec2 paving=position.xz/vec2(.4,.2);
    paving.x+=mod(floor(paving.y),2.0)*.5;
    vec2 edge=min(fract(paving),1.0-fract(paving))*vec2(.4,.2);
    float jointDistance=min(edge.x,edge.y),aa=max(fwidth(jointDistance),.001);
    float joint=1.0-smoothstep(.003-aa,.006+aa,jointDistance);
    float unitVariation=.95+.1*reactorGroundHash(floor(paving));
    vec3 grass=vec3(.24,.31,.145)*clamp(lawnLum/.3782,.45,1.65)*.95;
    vec3 paved=vec3(.55,.54,.51)*clamp(concreteLum/.5112,.7,1.3)*unitVariation*(1.0-.3*joint);
    vec3 asphalt=vec3(0);
    if(overlay.b>.001)asphalt=reactorGroundTexture(Sampler7,position*.25,weights)*.85;
    vec3 clean=classification.r*grass+classification.g*paved+classification.b*asphalt;
    return vec4(clean,coverage*(1.0-smoothstep(90.0,160.0,distance)));
}
// END SHARED REACTOR MATERIAL
void main(){
    if(dot(ClipPlane,vec4(worldPosition,1.0))<.025)discard;
    vec4 color=texture(Sampler0,texCoord0);
    if(color.a<AlphaCutoff)discard;
    vec3 n=normalize(cross(dFdx(worldPosition),dFdy(worldPosition)));
    if(dot(n,ReflectedEye-worldPosition)<0)n=-n;
    float distance=length(ReflectedEye-worldPosition);
    if(SurveyedGround>.5&&distance<160.0){
        vec3 weights=pow(abs(n),vec3(4.0));
        weights=max(weights-vec3(.002),vec3(0));
        weights/=max(dot(weights,vec3(1)),.0001);
        vec3 concrete=reactorGroundTexture(Sampler1,worldPosition*.5,weights);
        vec3 lawn=reactorGroundTexture(Sampler3,worldPosition*.5,weights);
        vec4 classification;
        vec4 clean=reactorGroundMaterial(worldPosition,weights,distance,
            dot(concrete,vec3(.299,.587,.114)),dot(lawn,vec3(.299,.587,.114)),classification);
        color.rgb=mix(color.rgb,clean.rgb,clean.a);
    }
    if(SurveyedGround>.5) {
        float courtyardCoverage=courtyardPavingCoverage(worldPosition);
        if(courtyardCoverage>0.0)color.rgb=mix(color.rgb,courtyardPavingAlbedo(worldPosition),courtyardCoverage);
        float coverage=galileoEastCoverage(worldPosition);
        if(coverage>0.0)color.rgb=mix(color.rgb,galileoEastAlbedo(worldPosition),coverage);
    }
    color.rgb*=(.72+.28*max(dot(n,SunDirection),0.0))*WorldLight;
    fragColor=vec4(color.rgb,1.0);
}
