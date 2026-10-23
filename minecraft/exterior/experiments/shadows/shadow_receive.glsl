uniform sampler2D Sampler11;
uniform mat4 CampusShadowMatrix;
uniform float CampusShadowStrength;
float campusShadow(vec3 p) {
    if(CampusShadowStrength<=0.0)return 0.0;
    vec3 n=normalize(cross(dFdx(p),dFdy(p)));
    if(dot(n,CameraPosition-p)<0.0)n=-n;
    vec4 projected=CampusShadowMatrix*vec4(p+n*.01,1.0);
    vec3 at=projected.xyz/projected.w*.5+.5;
    if(any(lessThan(at,vec3(0)))||any(greaterThan(at,vec3(1))))return 0.0;
    vec3 dx=dFdx(at),dy=dFdy(at);
    float determinant=dx.x*dy.y-dx.y*dy.x;
    vec2 plane=abs(determinant)>1e-12?vec2(dx.z*dy.y-dy.z*dx.y,dx.x*dy.z-dy.x*dx.z)/determinant:vec2(0);
    float shade=0.0;
    for(int y=-1;y<=1;y++)for(int x=-1;x<=1;x++){
        vec2 sampleUv=(floor(at.xy*4096.0)+vec2(x,y)+.5)/4096.0;
        float nearest=textureLod(Sampler11,sampleUv,0.0).r;
        float compare=at.z+dot(plane,sampleUv-at.xy)-.00003;
        shade+=compare>nearest?1.0:0.0;
    }
    float edge=1.0-smoothstep(.80,.98,max(abs(at.x*2.0-1.0),abs(at.y*2.0-1.0)));
    return shade/9.0*edge;
}

