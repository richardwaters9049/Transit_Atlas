import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import type { Position } from "./model";
import type { StudyCamera } from "./study-file";
import { pointCloud } from "./point-cloud";
import type { PlotPoint } from "./point-cloud";

const AXIS_COLOURS = ["#81bdff", "#78ddc0", "#c6a0fa"];
const VIEW_DIRECTION = new THREE.Vector3(0.63, 0.44, 1).normalize();

interface Marker {
  element: HTMLSpanElement;
  position: THREE.Vector3;
  compact: boolean;
}

interface Selection {
  query: PlotPoint;
  neighbours: PlotPoint[];
  active: number;
}

interface Study {
  scenarios: PlotPoint[];
  references: PlotPoint[];
  nominal: PlotPoint;
  releaseLink: boolean;
}

export class SignalScene {
  private readonly renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  private readonly scene = new THREE.Scene();
  private readonly camera = new THREE.PerspectiveCamera(41, 1, 0.035, 500);
  private readonly controls: OrbitControls;
  private readonly content = new THREE.Group();
  private readonly selectionLines = new THREE.Group();
  private readonly studyLayers = new THREE.Group();
  private readonly projected = new THREE.Vector3();
  private readonly pixelRatio = Math.min(window.devicePixelRatio, 2);
  private axisLabels: Marker[] = [];
  private pointLabels: Marker[] = [];
  private points: PlotPoint[] = [];
  private cloud?: ReturnType<typeof pointCloud>;
  private selection?: Selection;
  private study?: Study;
  private studyClouds: ReturnType<typeof pointCloud>[] = [];
  private example = false;
  private focused = false;
  private framePending = false;
  private gesturePointers = new Set<number>();
  private clickStart?: [number, number];

  constructor(
    private readonly mount: HTMLElement,
    private readonly axisMount: HTMLElement,
    private readonly markerMount: HTMLElement,
    private readonly onSelect: (id: string) => void,
  ) {
    this.renderer.setPixelRatio(this.pixelRatio);
    this.mount.append(this.renderer.domElement);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.14;
    this.controls.maxDistance = 110;
    this.controls.addEventListener("change", this.requestFrame);
    this.scene.add(this.content, this.studyLayers, this.selectionLines);
    this.frameView();
    new ResizeObserver(() => this.resize()).observe(this.mount);
    this.bindPicking();
  }

  show(points: PlotPoint[], example = false): void {
    this.clear(this.content);
    this.clear(this.selectionLines);
    this.clear(this.studyLayers);
    this.study = undefined;
    this.studyClouds = [];
    this.points = points;
    this.example = example;
    this.focused = false;
    this.selection = undefined;
    this.cloud = pointCloud(points, this.pixelRatio, example ? 14 : 5.2, example ? 1 : 0.74);
    this.content.add(this.cloud);
    const grid = new THREE.GridHelper(example ? 3 : 16, 16, "#46505a", "#343d46");
    grid.material.transparent = true;
    grid.material.opacity = 0.56;
    grid.material.depthWrite = false;
    this.content.add(grid);
    this.addAxes(example ? 1.2 : 4.7);
    this.markerMount.replaceChildren();
    this.pointLabels = example
      ? points.map((point) => {
        const tag = point.id === "Query" ? "scene-tag query-tag" : "scene-tag teaching-tag";
        return this.addMarker(this.markerMount, point.id, point.position, point.colour, tag);
      })
      : [];
    this.frameView();
  }

  highlight(query: PlotPoint, neighbours: PlotPoint[], active: number): void {
    const queryChanged = this.selection?.query.id !== query.id;
    this.selection = { query, neighbours, active };
    this.drawSelection();
    if (this.focused && queryChanged && !this.study) this.frameView();
    this.requestFrame();
  }

  showStudy(scenarios: PlotPoint[], references: PlotPoint[], nominal: PlotPoint, releaseLink = false): void {
    this.clear(this.studyLayers);
    this.study = { scenarios, references, nominal, releaseLink };
    const referenceLayer = pointCloud(references, this.pixelRatio, 10, 0.95);
    const scenarioLayer = pointCloud(scenarios, this.pixelRatio, 12, 0.95);
    scenarioLayer.renderOrder = 1;
    this.studyClouds = [referenceLayer, scenarioLayer];
    this.studyLayers.add(...this.studyClouds);
    if (releaseLink) this.studyLayers.add(this.lines([scenarios[0].position, nominal.position], "#81ddeb", 0.90, true));
    this.focused = true;
    this.drawSelection();
    this.frameView();
  }

  setFocus(focused: boolean): void {
    if (this.focused === focused) return;
    this.focused = focused;
    this.drawSelection();
    this.frameView();
  }

  reset(): void {
    this.controls.enableDamping = false;
    this.controls.update();
    this.controls.reset();
    this.controls.enableDamping = true;
    this.requestFrame();
  }

  captureView(): StudyCamera {
    return {
      position: this.camera.position.toArray(),
      target: this.controls.target.toArray(),
      focused: this.focused,
    };
  }

  restoreView(view: StudyCamera): void {
    this.controls.enableDamping = false;
    this.controls.update();
    this.controls.target.fromArray(view.target);
    this.camera.position.fromArray(view.position);
    this.controls.update();
    this.controls.enableDamping = true;
    this.requestFrame();
  }

  private frameView(): void {
    const selection = this.selection;
    const points = this.study
      ? [this.study.nominal, ...this.study.scenarios, ...this.study.references]
      : selection ? [selection.query, ...selection.neighbours] : [];
    const bounds = this.focused && points.length
      ? new THREE.Box3().setFromPoints(points.map((point) => new THREE.Vector3(...point.position)))
      : undefined;
    const sphere = bounds?.getBoundingSphere(new THREE.Sphere());
    const vertical = THREE.MathUtils.degToRad(this.camera.fov / 2);
    const horizontal = Math.atan(Math.tan(vertical) * this.camera.aspect);
    const distance = sphere
      ? Math.max(sphere.radius, 0.2) / Math.sin(Math.min(vertical, horizontal)) * 1.5
      : this.example ? 3.7 : 14.5;

    this.controls.enableDamping = false;
    this.controls.update();
    this.controls.target.copy(sphere?.center ?? new THREE.Vector3());
    this.controls.minDistance = this.focused ? 0.18 : 0.65;
    this.camera.position.copy(this.controls.target).addScaledVector(VIEW_DIRECTION, distance);
    this.controls.update();
    this.controls.saveState();
    this.controls.enableDamping = true;
    this.requestFrame();
  }

  private drawSelection(): void {
    this.clear(this.selectionLines);
    this.markerMount.replaceChildren();
    this.pointLabels = [];
    if (!this.selection) return;
    const { query, neighbours, active } = this.selection;
    const selected = neighbours[active];

    if (this.focused) {
      const branches = neighbours.filter((_, index) => index !== active)
        .flatMap((point) => [query.position, point.position]);
      this.selectionLines.add(this.lines(branches, selected.colour, 0.27, true));
    }
    this.selectionLines.add(this.lines([query.position, selected.position], selected.colour, 0.86, true));

    this.pointLabels.push(
      this.addMarker(this.markerMount, query.id, query.position, query.colour, "scene-tag query-tag"),
      this.addMarker(this.markerMount, `${active + 1} · ${selected.id}`, selected.position, selected.colour, "scene-tag active-tag"),
      ...neighbours.flatMap((point, index) => index === active
        ? []
        : [this.addMarker(this.markerMount, String(index + 1), point.position, point.colour, "rank-marker", true)]),
    );
    const study = this.study;
    if (study && (study.releaseLink || query.id !== study.nominal.id)) {
      const other = query.id === study.nominal.id ? study.scenarios[0] : study.nominal;
      const caption = study.releaseLink ? other.id + " position" : "Catalogue position";
      this.pointLabels.push(this.addMarker(
        this.markerMount, caption, other.position, other.colour, "scene-tag nominal-tag",
      ));
    }
  }

  private addAxes(length: number): void {
    const directions = [new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, 1)];
    this.axisMount.replaceChildren();
    this.axisLabels = directions.map((direction, index) => {
      const end = direction.clone().multiplyScalar(length).toArray();
      const negative = direction.clone().multiplyScalar(-length).toArray();
      const name = this.example ? `Coord ${index + 1}` : `PC${index + 1}`;
      const colour = AXIS_COLOURS[index];
      const tickOffset = directions[(index + 1) % 3].clone().multiplyScalar(length * 0.014);
      const ticks: Position[] = [];
      for (const fraction of [-0.75, -0.5, -0.25, 0.25, 0.5, 0.75, 1]) {
        const centre = direction.clone().multiplyScalar(length * fraction);
        ticks.push(centre.clone().sub(tickOffset).toArray(), centre.add(tickOffset).toArray());
      }
      this.content.add(this.lines([negative, [0, 0, 0]], colour, 0.32));
      this.content.add(this.lines([[0, 0, 0], end, ...ticks], colour, 0.66));
      return this.addMarker(this.axisMount, name, end, colour, "axis-marker");
    });
  }

  private lines(points: Position[], colour: string, opacity: number, overlay = false) {
    const geometry = new THREE.BufferGeometry().setFromPoints(points.map((point) => new THREE.Vector3(...point)));
    const material = new THREE.LineBasicMaterial({
      color: colour, depthTest: !overlay, depthWrite: false, transparent: true, opacity,
    });
    const line = new THREE.LineSegments(geometry, material);
    line.renderOrder = overlay ? 2 : 0;
    return line;
  }

  private addMarker(
    container: HTMLElement, text: string, position: Position, colour: string, className: string, compact = false,
  ): Marker {
    const element = document.createElement("span");
    element.className = className;
    if (element.classList.contains("scene-tag")) {
      const caption = document.createElement("span");
      caption.className = "marker-caption";
      caption.textContent = text;
      element.append(caption);
    } else {
      element.textContent = text;
    }
    element.style.setProperty("--marker", colour);
    element.hidden = true;
    container.append(element);
    return { element, position: new THREE.Vector3(...position), compact };
  }

  private bindPicking(): void {
    const canvas = this.renderer.domElement;
    canvas.addEventListener("pointerdown", (event) => {
      this.gesturePointers.add(event.pointerId);
      this.clickStart = this.gesturePointers.size === 1 && event.button === 0
        ? [event.clientX, event.clientY] : undefined;
    });
    canvas.addEventListener("pointercancel", (event) => {
      this.gesturePointers.delete(event.pointerId);
      this.clickStart = undefined;
    });
    canvas.addEventListener("pointerup", (event) => {
      this.gesturePointers.delete(event.pointerId);
      const start = this.clickStart;
      this.clickStart = undefined;
      if (!start || Math.hypot(event.clientX - start[0], event.clientY - start[1]) > 5) return;
      const box = canvas.getBoundingClientRect();
      const hit = this.pick(event.clientX - box.left, event.clientY - box.top, box);
      if (hit) this.onSelect(hit);
    });
  }

  private pick(x: number, y: number, box: DOMRect): string | undefined {
    let hit: string | undefined;
    let best = 10 ** 2;
    for (const point of this.study?.scenarios ?? this.points) {
      if (!point.selectable) continue;
      this.projected.set(...point.position).project(this.camera);
      if (Math.abs(this.projected.z) > 1) continue;
      const delta = ((this.projected.x + 1) * box.width / 2 - x) ** 2
        + ((1 - this.projected.y) * box.height / 2 - y) ** 2;
      if (delta < best) {
        hit = point.id;
        best = delta;
      }
    }
    return hit;
  }

  private clear(group: THREE.Group): void {
    for (const child of group.children) {
      if (child instanceof THREE.Line || child instanceof THREE.Points) {
        child.geometry.dispose();
        const materials = Array.isArray(child.material) ? child.material : [child.material];
        materials.forEach((material) => material.dispose());
      }
    }
    group.clear();
  }

  private resize(): void {
    const width = this.mount.clientWidth;
    const height = this.mount.clientHeight;
    if (!width || !height) return;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
    this.requestFrame();
  }

  private requestFrame = (): void => {
    if (this.framePending) return;
    this.framePending = true;
    requestAnimationFrame(() => {
      this.framePending = false;
      this.controls.update();
      const depth = this.controls.getDistance();
      if (this.cloud) {
        this.cloud.material.uniforms.targetDepth.value = depth;
        this.cloud.material.uniforms.intensity.value = this.example ? 1 : this.study ? 0.16 : this.focused ? 0.40 : 0.74;
      }
      for (const layer of this.studyClouds) layer.material.uniforms.targetDepth.value = depth;
      this.renderer.render(this.scene, this.camera);
      this.positionMarkers(this.axisLabels);
      this.positionMarkers(this.pointLabels);
    });
  };

  private positionMarkers(markers: Marker[]): void {
    const width = this.mount.clientWidth;
    const height = this.mount.clientHeight;
    const occupied: [number, number][] = [];
    for (const { element, position, compact } of markers) {
      this.projected.copy(position).project(this.camera);
      const x = (this.projected.x + 1) * width / 2;
      const y = (1 - this.projected.y) * height / 2;
      const outside = Math.abs(this.projected.z) > 1 || x < 11 || x > width - 11 || y < 13 || y > height - 13;
      const crowded = compact && occupied.some(([px, py]) => Math.hypot(px - x, py - y) < 17);
      element.hidden = outside || crowded;
      if (element.hidden) continue;
      occupied.push([x, y]);
      element.style.left = `${x}px`;
      element.style.top = `${y}px`;
      element.classList.toggle("towards-right", x < 120);
      element.classList.toggle("towards-left", x > width - 120);
    }
  }
}
