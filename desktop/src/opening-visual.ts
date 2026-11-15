import * as THREE from "three";
import { makePlanet } from "./opening-planet";

function starfield() {
  let state = 34587;
  const random = () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 2 ** 32;
  };
  const points = new Float32Array(660 * 3);
  const colours = new Float32Array(points.length);
  const colour = new THREE.Color();
  for (let i = 0; i < points.length; i += 3) {
    points.set([(random() - 0.5) * 40, (random() - 0.5) * 25, -2 - random() * 20], i);
    const brightness = 0.18 + random() * 0.78;
    colour.setRGB(brightness * 0.91, brightness * 0.96, brightness);
    colour.toArray(colours, i);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(points, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colours, 3));
  return new THREE.Points(geometry, new THREE.PointsMaterial({
    size: 0.04, vertexColors: true, transparent: true, opacity: 0.68, depthWrite: false,
  }));
}

function orbitTrail(radius: number) {
  const segments = 44;
  const points = [];
  const colours = [];
  for (let index = 0; index <= segments; index++) {
    const fraction = index / segments;
    const angle = -fraction * 0.76;
    points.push(radius * Math.cos(angle), radius * Math.sin(angle), 0);
    const glow = (1 - fraction) ** 2;
    colours.push(glow * 0.58, glow * 0.81, glow);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(points, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colours, 3));
  return new THREE.Line(geometry, new THREE.LineBasicMaterial({
    vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
  }));
}

export function launchOrbit(container: HTMLElement): () => void {
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "low-power" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  container.append(renderer.domElement);

  const sky = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(41, 1, 0.05, 80);
  camera.position.set(0, 0.25, 7);
  const stars = starfield();
  sky.add(stars, new THREE.HemisphereLight("#c9d7e1", "#335166", 0.80));
  const daylight = new THREE.DirectionalLight("#fff1df", 3.8);
  daylight.position.set(4.5, 3.2, 4);
  const rim = new THREE.DirectionalLight("#d0eaff", 2.3);
  rim.position.set(4, 0.5, -3);
  sky.add(daylight, rim);

  const system = new THREE.Group();
  sky.add(system);
  const planet = makePlanet();
  system.add(planet.object);

  const orbit = new THREE.Group();
  orbit.rotation.set(1.04, 0.44, -0.31);
  system.add(orbit);
  const orbitRadius = 1.77;
  orbit.add(new THREE.Mesh(
    new THREE.TorusGeometry(orbitRadius, 0.006, 6, 128),
    new THREE.MeshBasicMaterial({ color: "#d3dfeb", transparent: true, opacity: 0.63 }),
  ));
  const satellite = new THREE.Mesh(
    new THREE.SphereGeometry(0.034, 10, 8),
    new THREE.MeshBasicMaterial({ color: "#f3f8ff" }),
  );
  const flyby = new THREE.Group();
  satellite.position.x = orbitRadius;
  flyby.add(satellite, orbitTrail(orbitRadius));
  orbit.add(flyby);

  function resize() {
    const width = container.clientWidth;
    const height = container.clientHeight;
    if (!width || !height) return;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
  }

  const observer = new ResizeObserver(resize);
  observer.observe(container);
  resize();
  const baseline = performance.now();
  renderer.setAnimationLoop(() => {
    const elapsed = (performance.now() - baseline) / 1000;
    const approach = THREE.MathUtils.smoothstep(elapsed, 0, 1.8);
    const pass = THREE.MathUtils.smoothstep(elapsed, 1.15, 5.4);
    system.position.set(Math.min(2.35, camera.aspect * 1.22) + 0.45 * (1 - approach) - 0.1 * pass,
      0.15 - 0.13 * pass, 0);
    system.rotation.y = -0.35 + 0.60 * pass;
    system.scale.setScalar(0.61 + 0.40 * approach + 0.10 * pass);
    planet.rotate(elapsed);
    stars.rotation.z = elapsed * 0.023;
    flyby.rotation.z = 0.38 + elapsed * 1.16;
    renderer.render(sky, camera);
  });

  return () => {
    observer.disconnect();
    renderer.setAnimationLoop(null);
    sky.traverse((object) => {
      if (object instanceof THREE.Mesh || object instanceof THREE.Points || object instanceof THREE.Line) {
        object.geometry.dispose();
        object.material.dispose();
      }
    });
    planet.disposeTextures();
    renderer.dispose();
    renderer.domElement.remove();
  };
}
