// Insert after the analytic glazing colour is computed, before final lighting.
if(glass>.5&&PlanarStrength>0.0&&abs(dot(PlanarPlane,vec4(worldPosition,1.0)))<.03&&abs(dot(n,PlanarPlane.xyz))>.999){
    vec4 projected=PlanarMatrix*vec4(worldPosition,1.0);
    vec2 uv=projected.xy/projected.w*.5+.5;
    if(projected.w>0.0&&all(greaterThanEqual(uv,vec2(0)))&&all(lessThanEqual(uv,vec2(1)))){
        vec3 scene=texture(PlanarTexture,uv).rgb;
        planarRadiance=scene*vec3(.90,.96,1.0);
        planarWeight=(.65+.30*fresnel)*PlanarStrength;
    }
}
