#version 150
uniform sampler2D Sampler0;
uniform sampler2D Sampler1;
uniform sampler2D Sampler2;
uniform sampler2D Sampler3;
uniform sampler2D Sampler4;
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
    if(color.a<(MaterialDetail>3.5&&MaterialDetail<4.5?0.45:0.1))discard;
    // The aerial image supplies surveyed colour and markings. Only close-range
    // material grain is reconstructed; it does not invent additional geometry.
    float proximity=1.0-smoothstep(10.0,28.0,viewDistance);
    if(MaterialDetail>0.5&&MaterialDetail<1.5) {
        float grass=smoothstep(0.005,0.055,color.g-max(color.r,color.b));
        vec2 uv=worldPosition.xz*.5;
        vec3 concrete=texture(Sampler1,uv).rgb, lawn=texture(Sampler3,uv).rgb;
        float cLum=dot(concrete,vec3(.299,.587,.114)),gLum=dot(lawn,vec3(.299,.587,.114));
        float micro=mix(cLum/.5112,gLum/.3782,grass);
        color.rgb*=mix(1.0,clamp(micro,.65,1.35),proximity*.55);
        vec3 cn=texture(Sampler2,uv).xyz*2.0-1.0,gn=texture(Sampler4,uv).xyz*2.0-1.0;
        vec3 nm=normalize(mix(cn,gn,grass));
        vec3 n=normalize(vec3(nm.x*.35,1.0,nm.y*.35));
        vec3 sun=normalize(vec3(-.5,.8,-.3));
        color.rgb*=mix(1.0,(.55+.45*max(dot(n,sun),0.0))/.91,proximity);
    }
    if(abs(MaterialDetail-9.0)<.1) {
        vec3 roofN=normalize(cross(dFdx(worldPosition),dFdy(worldPosition)));
        if(dot(roofN,CameraPosition-worldPosition)<0.0)roofN=-roofN;
        if(roofN.y<-.05)color.rgb=vec3(.25,.27,.28);
    }
    if((MaterialDetail>1.5&&MaterialDetail<3.5)||(MaterialDetail>5.5&&MaterialDetail<8.5)||abs(MaterialDetail-11.0)<.1) {
        vec3 n=normalize(cross(dFdx(worldPosition),dFdy(worldPosition)));
        vec3 view=normalize(CameraPosition-worldPosition);
        if(dot(n,view)<0.0)n=-n;
        if(abs(n.y)<0.7) {
            vec3 sun=normalize(vec3(-0.5,0.8,-0.3));
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
            vec3 metal=color.rgb*(MaterialDetail>6.5&&MaterialDetail<8.5?1.08:0.82)*diffuse;
            if(MaterialDetail>6.5&&MaterialDetail<8.5){
                vec2 materialUv=abs(n.x)>abs(n.z)?worldPosition.zy*.5:worldPosition.xy*.5;
                vec3 grain=texture(Sampler1,materialUv).rgb;
                float lum=dot(grain,vec3(.299,.587,.114));
                metal*=mix(1.0,clamp(lum/.5112,.7,1.2),proximity*.4);
            }
            color.rgb=mix(metal,glazing,glass);
        }
    }
    if(MaterialDetail>3.5&&MaterialDetail<5.5) {
        vec3 n=normalize(cross(dFdx(worldPosition),dFdy(worldPosition)));
        vec3 sun=normalize(vec3(-0.5,0.8,-0.3));
        float lighting=0.58+0.42*abs(dot(n,sun));
        if(MaterialDetail<4.5) {
            // Double-sided leaf transmission; cutout atlas preserves holes between leaves.
            lighting=0.66+0.34*abs(dot(n,sun));
            lighting*=0.9+0.1*noise(worldPosition.xz*1.7);
        }
        color.rgb*=lighting;
    }
    color*=ColorModulator;
    color.rgb=mix(color.rgb,CampusFogColor,smoothstep(650.0,1000.0,viewDistance));
    fragColor=color;
}
