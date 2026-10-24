#version 150
uniform sampler2D Sampler0;
uniform vec4 ClipPlane;
uniform float AlphaCutoff;
uniform float WorldLight;
uniform vec3 SunDirection;
uniform vec3 ReflectedEye;
in vec2 texCoord0;
in vec3 worldPosition;
out vec4 fragColor;
void main(){
    if(dot(ClipPlane,vec4(worldPosition,1.0))<.025)discard;
    vec4 color=texture(Sampler0,texCoord0);
    if(color.a<AlphaCutoff)discard;
    vec3 n=normalize(cross(dFdx(worldPosition),dFdy(worldPosition)));
    if(dot(n,ReflectedEye-worldPosition)<0)n=-n;
    color.rgb*=(.72+.28*max(dot(n,SunDirection),0.0))*WorldLight;
    fragColor=vec4(color.rgb,1.0);
}
