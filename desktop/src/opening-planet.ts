import * as THREE from "three";

const MAP_WIDTH = 768;
const MAP_HEIGHT = MAP_WIDTH / 2;

function hash(x: number, y: number, z: number): number {
  let bits = Math.imul(x, 374761393) ^ Math.imul(y, 668265263) ^ Math.imul(z, 1274126177);
  bits = Math.imul(bits ^ (bits >>> 13), 1274126177);
  return ((bits ^ (bits >>> 16)) >>> 0) / 4294967296;
}

function noise(x: number, y: number, z: number): number {
  const ix = Math.floor(x);
  const iy = Math.floor(y);
  const iz = Math.floor(z);
  const u = THREE.MathUtils.smoothstep(x - ix, 0, 1);
  const v = THREE.MathUtils.smoothstep(y - iy, 0, 1);
  const w = THREE.MathUtils.smoothstep(z - iz, 0, 1);
  const mix = THREE.MathUtils.lerp;
  const base = mix(
    mix(hash(ix, iy, iz), hash(ix + 1, iy, iz), u),
    mix(hash(ix, iy + 1, iz), hash(ix + 1, iy + 1, iz), u),
    v,
  );
  const top = mix(
    mix(hash(ix, iy, iz + 1), hash(ix + 1, iy, iz + 1), u),
    mix(hash(ix, iy + 1, iz + 1), hash(ix + 1, iy + 1, iz + 1), u),
    v,
  );
  return mix(base, top, w);
}

function makeMap() {
  const canvas = document.createElement("canvas");
  canvas.width = MAP_WIDTH;
  canvas.height = MAP_HEIGHT;
  const context = canvas.getContext("2d")!;
  const pixels = context.createImageData(MAP_WIDTH, MAP_HEIGHT);
  return { canvas, context, pixels };
}

function texture(map: ReturnType<typeof makeMap>, colour = true): THREE.CanvasTexture {
  map.context.putImageData(map.pixels, 0, 0);
  const texture = new THREE.CanvasTexture(map.canvas);
  if (colour) texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function createMaps() {
  const surface = makeMap();
  const elevation = makeMap();
  const cloud = makeMap();
  const smooth = THREE.MathUtils.smoothstep;
  const mix = THREE.MathUtils.lerp;
  const longitudes = Array.from({ length: MAP_WIDTH }, (_, index) => {
    const angle = (index + 0.5) / MAP_WIDTH * Math.PI * 2;
    return [Math.cos(angle), Math.sin(angle)];
  });
  for (let row = 0; row < MAP_HEIGHT; row++) {
    const latitude = (row + 0.5) / MAP_HEIGHT * Math.PI;
    const y = Math.cos(latitude);
    const radius = Math.sin(latitude);
    for (let column = 0; column < MAP_WIDTH; column++) {
      const x = longitudes[column][0] * radius;
      const z = longitudes[column][1] * radius;
      // Sample in 3D so the continents and clouds meet across the texture seam.
      const warp = noise(5 * x + 11, 5 * y - 3, 5 * z + 5) - 0.5;
      const continent = 0.74 * noise(x * 3.2 + warp + 4, y * 3.2 - warp, z * 3.2 + 2) +
        0.19 * noise(9 * x - 7, 9 * y, 9 * z) + 0.07 * noise(31 * x, 31 * y, 31 * z);
      const land = smooth(continent, 0.46, 0.53);
      const ridges = (1 - Math.abs(2 * noise(x * 23 + warp * 2, y * 23, z * 23) - 1)) ** 3;
      const grain = noise(105 * x, 105 * y, 105 * z);
      const frost = smooth(Math.abs(y) + warp * 0.40, 0.78, 0.99);
      const rock = 49 + 77 * ridges + 35 * grain;
      const water = 18 + 28 * smooth(continent, 0.30, 0.50) + 8 * grain;
      const base = mix(mix(water, rock, land), 167 + 31 * grain, frost);
      const index = (row * MAP_WIDTH + column) * 4;
      surface.pixels.data.set([base - 3, base + 6, base + 15 - land * 8, 255], index);

      const relief = 31 + land * (64 + 99 * ridges + 32 * grain) + 18 * frost;
      elevation.pixels.data.set([relief, relief, relief, 255], index);

      const banks = 0.57 * noise(6 * x - 2, 13 * y + warp * 6, 6 * z + 8) +
        0.28 * noise(18 * x + warp * 3, 25 * y, 18 * z) + 0.15 * noise(56 * x, 56 * y, 56 * z);
      const cover = 170 * smooth(banks, 0.51, 0.73);
      cloud.pixels.data.set([207, 220, 233, cover], index);
    }
  }
  return { terrain: texture(surface), bump: texture(elevation, false), clouds: texture(cloud) };
}

export function makePlanet() {
  const maps = createMaps();
  const planet = new THREE.Group();
  planet.rotation.z = -0.22;
  const surface = new THREE.Mesh(
    new THREE.SphereGeometry(1.26, 72, 48),
    new THREE.MeshStandardMaterial({ map: maps.terrain, bumpMap: maps.bump, bumpScale: 0.055, roughness: 0.91 }),
  );
  const clouds = new THREE.Mesh(
    new THREE.SphereGeometry(1.277, 60, 40),
    new THREE.MeshStandardMaterial({ map: maps.clouds, transparent: true, opacity: 0.67, depthWrite: false }),
  );
  clouds.rotation.y = 0.23;
  const atmosphere = new THREE.Mesh(
    new THREE.SphereGeometry(1.29, 60, 40),
    new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      vertexShader: `
        varying vec3 normalAtLimb;
        varying vec3 towardCamera;
        void main() {
          vec4 view = modelViewMatrix * vec4(position, 1.0);
          normalAtLimb = normalize(normalMatrix * normal);
          towardCamera = -view.xyz;
          gl_Position = projectionMatrix * view;
        }
      `,
      fragmentShader: `
        varying vec3 normalAtLimb;
        varying vec3 towardCamera;
        void main() {
          vec3 normal = normalize(normalAtLimb);
          float limb = 1.0 - max(0.0, dot(normal, normalize(towardCamera)));
          float sun = smoothstep(-0.4, 0.9, dot(normal, normalize(vec3(0.76, 0.54, 0.36))));
          float haze = pow(limb, 3.4) * (0.07 + 0.43 * sun);
          gl_FragColor = vec4(mix(vec3(0.35, 0.56, 0.76), vec3(0.67, 0.81, 0.91), sun), haze);
        }
      `,
    }),
  );
  atmosphere.renderOrder = 1;
  planet.add(surface, clouds, atmosphere);
  return {
    object: planet,
    rotate(elapsed: number) {
      surface.rotation.y = 0.42 + 0.24 * elapsed;
      clouds.rotation.y = 0.23 + 0.31 * elapsed;
    },
    disposeTextures() {
      Object.values(maps).forEach((map) => map.dispose());
    },
  };
}
