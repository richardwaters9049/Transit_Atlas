import * as THREE from "three";
import type { Position } from "./model";

export interface PlotPoint {
  id: string;
  position: Position;
  colour: string;
  selectable?: boolean;
}

export function pointCloud(points: PlotPoint[], pixelRatio: number, size: number, intensity: number) {
  const positions = new Float32Array(points.length * 3);
  const colours = new Float32Array(points.length * 3);
  const colour = new THREE.Color();
  points.forEach((point, index) => {
    positions.set(point.position, 3 * index);
    colour.set(point.colour).toArray(colours, 3 * index);
  });
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("tint", new THREE.BufferAttribute(colours, 3));

  const material = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    uniforms: {
      pointSize: { value: size * pixelRatio },
      targetDepth: { value: 1 },
      intensity: { value: intensity },
    },
    vertexShader: `
      attribute vec3 tint;
      uniform float pointSize;
      uniform float targetDepth;
      varying vec3 vTint;
      varying float vDepth;

      void main() {
        vec4 viewPosition = modelViewMatrix * vec4(position, 1.0);
        vDepth = clamp(targetDepth / max(0.01, -viewPosition.z), 0.38, 1.25);
        vTint = tint;
        gl_PointSize = pointSize * vDepth;
        gl_Position = projectionMatrix * viewPosition;
      }
    `,
    fragmentShader: `
      uniform float intensity;
      varying vec3 vTint;
      varying float vDepth;

      void main() {
        float radius = length(gl_PointCoord - vec2(0.5));
        float core = 1.0 - smoothstep(0.17, 0.32, radius);
        float halo = 1.0 - smoothstep(0.22, 0.5, radius);
        float alpha = (0.83 * core + 0.17 * halo) * intensity * min(vDepth, 1.0);
        gl_FragColor = vec4(vTint, alpha);
        #include <colorspace_fragment>
      }
    `,
  });
  return new THREE.Points(geometry, material);
}
