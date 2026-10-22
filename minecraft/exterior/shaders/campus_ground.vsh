#version 150
in vec3 Position;
in vec2 UV0;
uniform mat4 ModelViewMat;
uniform mat4 ProjMat;
uniform vec3 TileAnchor;
out vec2 texCoord0;
out vec3 worldPosition;
out float viewDistance;
void main() {
    vec4 eye = ModelViewMat * vec4(Position, 1.0);
    gl_Position = ProjMat * eye;
    viewDistance = length(eye.xyz);
    texCoord0 = UV0;
    worldPosition = Position + TileAnchor;
}
