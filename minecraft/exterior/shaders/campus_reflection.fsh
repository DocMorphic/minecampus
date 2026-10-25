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
    color.rgb*=(.72+.28*max(dot(n,SunDirection),0.0))*WorldLight;
    fragColor=vec4(color.rgb,1.0);
}
