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
void main() {
    vec4 color=texture(Sampler0,texCoord0);
    if(abs(MaterialDetail-13.0)<.1){
        // Average fine timber boards over a slightly wider pixel footprint.
        // MapTile must also lift Minecraft's initial level-zero sampling clamp.
        vec2 size=vec2(textureSize(Sampler0,0));
        float footprint=max(length(dFdx(texCoord0)*size),length(dFdy(texCoord0)*size));
        color=textureLod(Sampler0,texCoord0,max(0.0,log2(max(footprint,1.0))+1.5));
    }
    if(color.a<(MaterialDetail>3.5&&MaterialDetail<4.5?0.45:0.1))discard;
    // The aerial image supplies surveyed colour and markings. Only close-range
    // material grain is reconstructed; it does not invent additional geometry.
    float proximity=1.0-smoothstep(10.0,28.0,viewDistance);
    if(MaterialDetail>0.5&&MaterialDetail<1.5&&viewDistance<110.0) {
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
        vec3 mapped=texture(Sampler5,clamp(surfaceUv,0.0,1.0)).rgb;
        if(any(lessThan(surfaceUv,vec2(0)))||any(greaterThan(surfaceUv,vec2(1))))mapped=vec3(0);
        float mappedTotal=mapped.r+mapped.g+mapped.b;
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
        vec3 asphaltColor=aerial;
        if(mapped.b>.001){
            // Four-metre scanned aggregate detail. Keep broad aerial shade,
            // with bounded highlights so washed-out pixels do not erase grain.
            vec3 asphalt=groundTexture(Sampler7,worldPosition*.25,weights);
            asphaltColor=asphalt*clamp(aerialLum/.55,.4,1.2);
        }
        vec3 material=(mapped.r*lawnColor+mapped.g*pavingColor+mapped.b*asphaltColor)/max(mappedTotal,.0001);
        color.rgb=mix(color.rgb,material,mappedAmount*materialRange);
        grass=mix(grass,mapped.r/max(mappedTotal,.0001),mappedAmount);
        if(proximity>0.0){
            vec3 cn=groundNormalDetail(Sampler2,materialPosition,weights),gn=groundNormalDetail(Sampler4,materialPosition,weights);
            vec3 detail=mix(cn,gn,grass);
            if(mapped.b>.001){
                vec3 asphaltNormal=groundNormalDetail(Sampler8,worldPosition*.25,weights);
                detail=mix(detail,asphaltNormal,clamp(mapped.b,0.0,1.0));
            }
            detail-=geometric*dot(detail,geometric);
            vec3 n=normalize(geometric+detail*.35);
            vec3 sun=normalize(vec3(-.5,.8,-.3));
            color.rgb*=mix(1.0,(.55+.45*max(dot(n,sun),0.0))/.91,proximity);
        }
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
        color.rgb*=.65+.35*max(dot(n,normalize(vec3(-.5,.8,-.3))),0.0);
    }
    if(abs(MaterialDetail-9.0)<.1) {
        vec3 roofN=normalize(cross(dFdx(worldPosition),dFdy(worldPosition)));
        if(dot(roofN,CameraPosition-worldPosition)<0.0)roofN=-roofN;
        if(roofN.y<-.05)color.rgb=vec3(.25,.27,.28);
    }
    if((MaterialDetail>1.5&&MaterialDetail<3.5)||(MaterialDetail>5.5&&MaterialDetail<8.5)||abs(MaterialDetail-11.0)<.1||abs(MaterialDetail-13.0)<.1) {
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
