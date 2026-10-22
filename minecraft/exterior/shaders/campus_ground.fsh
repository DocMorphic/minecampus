#version 150
uniform sampler2D Sampler0;
uniform vec4 ColorModulator;
uniform vec3 CampusFogColor;
uniform vec3 CameraPosition;
uniform float MaterialDetail;
in vec2 texCoord0;
in vec3 worldPosition;
in float viewDistance;
out vec4 fragColor;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1,311.7))) * 43758.5453); }
float noise(vec2 p) {
    vec2 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f);
    return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1)),f.x),f.y);
}
void main() {
    vec4 color=texture(Sampler0,texCoord0);
    if(color.a<0.1)discard;
    // The aerial image supplies surveyed colour and markings. Only close-range
    // material grain is reconstructed; it does not invent additional geometry.
    float detail=(MaterialDetail<1.5?MaterialDetail:0.0)*(1.0-smoothstep(12.0,35.0,viewDistance));
    float grass=smoothstep(0.005,0.055,color.g-max(color.r,color.b));
    float grain=noise(worldPosition.xz*42.0)-0.5;
    float blades=noise(worldPosition.xz*vec2(70.0,11.0))-0.5;
    color.rgb*=1.0+detail*mix(grain*0.16,blades*0.30+grain*0.10,grass);
    if(MaterialDetail>1.5) {
        vec3 n=normalize(cross(dFdx(worldPosition),dFdy(worldPosition)));
        vec3 view=normalize(CameraPosition-worldPosition);
        if(dot(n,view)<0.0)n=-n;
        if(abs(n.y)<0.7) {
            vec3 sun=normalize(vec3(-0.5,0.8,-0.3));
            float diffuse=0.46+0.54*max(dot(n,sun),0.0);
            float lum=dot(color.rgb,vec3(0.2126,0.7152,0.0722));
            float glass=MaterialDetail<2.5?1.0:0.0;
            vec3 reflected=reflect(-view,n);
            float sky=smoothstep(-0.08,0.18,reflected.y);
            vec3 environment=mix(vec3(0.08,0.14,0.10),vec3(0.42,0.55,0.68),sky);
            environment*=0.8+0.2*noise(reflected.xz*8.0);
            float fresnel=0.04+0.96*pow(1.0-max(dot(n,view),0.0),5.0);
            vec3 glazing=vec3(0.025,0.038,0.045)+environment*(0.5+0.5*fresnel);
            float highlight=pow(max(dot(reflect(-sun,n),view),0.0),180.0);
            glazing+=vec3(0.8,0.75,0.62)*highlight;
            vec3 metal=color.rgb*0.82*diffuse;
            color.rgb=mix(metal,glazing,glass);
        }
    }
    color*=ColorModulator;
    color.rgb=mix(color.rgb,CampusFogColor,smoothstep(650.0,1000.0,viewDistance));
    fragColor=color;
}
