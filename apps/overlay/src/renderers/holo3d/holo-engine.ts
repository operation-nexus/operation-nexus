import * as THREE from "three";
import type {
  IRenderEngine,
  RenderEngineOptions,
  RenderFrameState,
  CameraTarget,
  VisualEffect,
} from "../../types/render";
import type { TheaterDefinition } from "../../types/theater";
import type { VisualUnit } from "../../types/unit";
import { isAirUnit } from "../../symbology/dual-encoding";
import { STRAIT_1_THEATER } from "../../theater/strait1";
import {
  ELEVATION_CHANNEL_WATER,
  ELEVATION_TERRAIN_BASE,
  ELEVATION_BRIDGE_DECK_MIN,
  ELEVATION_BRIDGE_DECK_MAX,
  getBallisticMissileAltitude,
} from "../../theater/elevation";
import { createCanvasElement } from "../../utils/dom";

export interface CameraPresetConfig {
  position: THREE.Vector3;
  target: THREE.Vector3;
  fov: number;
}

export const CAMERA_PRESETS: Record<
  "WIDE" | "COMBAT_45" | "TOP_DOWN",
  CameraPresetConfig
> = {
  WIDE: {
    position: new THREE.Vector3(0, 460, 540),
    target: new THREE.Vector3(0, 0, 0),
    fov: 42,
  },
  COMBAT_45: {
    position: new THREE.Vector3(-180, 190, 160),
    target: new THREE.Vector3(0, 0, 0),
    fov: 45,
  },
  TOP_DOWN: {
    position: new THREE.Vector3(0, 780, 10),
    target: new THREE.Vector3(0, 0, 0),
    fov: 35,
  },
};

export class HoloTableEngine implements IRenderEngine {
  readonly id = "holo3d";
  readonly name = "3D Holographic War Room Table";

  private container: HTMLElement | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private renderer: THREE.WebGLRenderer | null = null;
  private scene: THREE.Scene | null = null;
  private camera: THREE.PerspectiveCamera | null = null;
  private theater: TheaterDefinition = STRAIT_1_THEATER;

  private currentPreset: "WIDE" | "COMBAT_45" | "TOP_DOWN" = "WIDE";
  private targetCameraPos = new THREE.Vector3(0, 460, 540);
  private targetCameraLookAt = new THREE.Vector3(0, 0, 0);

  // Scene object groups
  private terrainGroup: THREE.Group | null = null;
  private bridgeGroup: THREE.Group | null = null;
  private unitsGroup: THREE.Group | null = null;
  private effectsGroup: THREE.Group | null = null;
  private gridHelper: THREE.GridHelper | null = null;

  private unitMeshes = new Map<number, THREE.Object3D>();
  private activeEffects: VisualEffect[] = [];
  private isHeadless = false;

  async initialize(
    container: HTMLElement,
    options?: RenderEngineOptions,
  ): Promise<void> {
    this.container = container;
    const rect = container.getBoundingClientRect();
    const width = rect.width || 1280;
    const height = rect.height || 720;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x050b14);
    this.scene.fog = new THREE.FogExp2(0x050b14, 0.0008);

    this.camera = new THREE.PerspectiveCamera(42, width / height, 1, 5000);
    this.camera.position.copy(CAMERA_PRESETS.WIDE.position);
    this.camera.lookAt(CAMERA_PRESETS.WIDE.target);

    // Ambient and tactical holographic directional lights
    const ambientLight = new THREE.AmbientLight(0x1e3a5f, 1.2);
    this.scene.add(ambientLight);

    const sunLight = new THREE.DirectionalLight(0x00e5ff, 1.5);
    sunLight.position.set(100, 300, 150);
    this.scene.add(sunLight);

    const magentaFill = new THREE.DirectionalLight(0xff0055, 0.9);
    magentaFill.position.set(-150, 200, -100);
    this.scene.add(magentaFill);

    // Group hierarchies
    this.terrainGroup = new THREE.Group();
    this.bridgeGroup = new THREE.Group();
    this.unitsGroup = new THREE.Group();
    this.effectsGroup = new THREE.Group();

    this.scene.add(this.terrainGroup);
    this.scene.add(this.bridgeGroup);
    this.scene.add(this.unitsGroup);
    this.scene.add(this.effectsGroup);

    // Base holographic war room grid table
    this.gridHelper = new THREE.GridHelper(800, 40, 0x00e5ff, 0x1e3a5f);
    this.gridHelper.position.y = -1;
    this.scene.add(this.gridHelper);

    // Attempt WebGLRenderer creation with graceful headless fallback
    try {
      if (options?.canvas) {
        this.canvas = options.canvas;
      } else {
        this.canvas = createCanvasElement(this.container, "holo-table-canvas");
      }

      this.renderer = new THREE.WebGLRenderer({
        canvas: this.canvas,
        antialias: options?.antialias ?? true,
        logarithmicDepthBuffer: options?.logarithmicDepthBuffer ?? true,
      });
      this.renderer.setSize(width, height);
      this.renderer.setPixelRatio(options?.pixelRatio ?? 1);
    } catch {
      // Headless / Node testing environment without WebGL
      this.isHeadless = true;
    }

    this.buildTheaterMesh();
  }

  resize(width: number, height: number, pixelRatio = 1): void {
    if (this.camera) {
      this.camera.aspect = Math.max(1, width) / Math.max(1, height);
      this.camera.updateProjectionMatrix();
    }
    if (this.renderer && !this.isHeadless) {
      this.renderer.setSize(width, height);
      this.renderer.setPixelRatio(pixelRatio);
    }
  }

  updateTheaterMap(theater: TheaterDefinition): void {
    this.theater = theater;
    this.buildTheaterMesh();
  }

  setCameraPreset(preset: "WIDE" | "COMBAT_45" | "TOP_DOWN"): void {
    this.currentPreset = preset;
    const config = CAMERA_PRESETS[preset];
    this.targetCameraPos.copy(config.position);
    this.targetCameraLookAt.copy(config.target);
    if (this.camera) {
      this.camera.fov = config.fov;
      this.camera.updateProjectionMatrix();
    }
  }

  setCameraTarget(target: CameraTarget): void {
    if (target.mode === "OVERVIEW") {
      this.setCameraPreset("WIDE");
    } else if (target.mode === "COMBAT") {
      this.setCameraPreset("COMBAT_45");
    } else if (target.mode === "TOP_DOWN") {
      this.setCameraPreset("TOP_DOWN");
    } else if (target.position) {
      this.targetCameraPos.set(
        target.position[0],
        target.position[1],
        target.position[2],
      );
      if (target.lookAt) {
        this.targetCameraLookAt.set(
          target.lookAt[0],
          target.lookAt[1],
          target.lookAt[2],
        );
      }
    }
  }

  triggerEffect(effect: VisualEffect): void {
    this.activeEffects.push(effect);
    if (this.activeEffects.length > 20) {
      this.activeEffects.shift();
    }
  }

  renderFrame(state: RenderFrameState): void {
    if (state.cameraPreset && state.cameraPreset !== this.currentPreset) {
      this.setCameraPreset(state.cameraPreset);
    }

    // Smooth camera damping towards target (Emil Kowalski spring glide)
    if (this.camera) {
      this.camera.position.lerp(this.targetCameraPos, 0.08);
      this.camera.lookAt(this.targetCameraLookAt);
    }

    // Update units in 3D
    this.update3DUnits(state.units);

    // Update 3D ballistic missile arcs & kinetic bursts
    this.update3DEffects(state.effects);

    if (this.renderer && this.scene && this.camera && !this.isHeadless) {
      this.renderer.render(this.scene, this.camera);
    }
  }

  private disposeObject(obj: THREE.Object3D): void {
    obj.traverse((node) => {
      const n = node as THREE.Mesh | THREE.Line;
      n.geometry?.dispose();
      const mat = n.material as THREE.Material | THREE.Material[] | undefined;
      if (Array.isArray(mat)) {
        mat.forEach((m) => m.dispose());
      } else {
        mat?.dispose();
      }
    });
  }

  dispose(): void {
    if (this.scene) {
      this.disposeObject(this.scene);
    }
    if (this.renderer) {
      this.renderer.dispose();
      this.renderer = null;
    }
    if (this.canvas && this.canvas.parentElement) {
      this.canvas.parentElement.removeChild(this.canvas);
    }
    this.canvas = null;
    this.scene = null;
    this.camera = null;
    this.container = null;
    this.unitMeshes.clear();
    this.activeEffects = [];
  }

  // --- Theater 3D Geometry Builder ---
  private buildTheaterMesh(): void {
    if (!this.terrainGroup || !this.bridgeGroup) return;

    // Clear previous geometries
    while (this.terrainGroup.children.length > 0) {
      const child = this.terrainGroup.children[0];
      if (child) {
        this.terrainGroup.remove(child);
        this.disposeObject(child);
      }
    }
    while (this.bridgeGroup.children.length > 0) {
      const child = this.bridgeGroup.children[0];
      if (child) {
        this.bridgeGroup.remove(child);
        this.disposeObject(child);
      }
    }

    // Theater coordinate mapping: 400km x 240km -> 400 x 240 world units
    // West Landmass: -200 to -15
    const westLandGeo = new THREE.PlaneGeometry(185, 240, 16, 16);
    westLandGeo.rotateX(-Math.PI / 2);
    const westLandMat = new THREE.MeshStandardMaterial({
      color: 0x0a192f,
      roughness: 0.8,
      metalness: 0.2,
      wireframe: false,
    });
    const westLand = new THREE.Mesh(westLandGeo, westLandMat);
    westLand.position.set(-107.5, ELEVATION_TERRAIN_BASE, 0);
    this.terrainGroup.add(westLand);

    // East Landmass: +15 to +200
    const eastLandGeo = new THREE.PlaneGeometry(185, 240, 16, 16);
    eastLandGeo.rotateX(-Math.PI / 2);
    const eastLandMat = new THREE.MeshStandardMaterial({
      color: 0x14101e,
      roughness: 0.8,
      metalness: 0.2,
      wireframe: false,
    });
    const eastLand = new THREE.Mesh(eastLandGeo, eastLandMat);
    eastLand.position.set(107.5, ELEVATION_TERRAIN_BASE, 0);
    this.terrainGroup.add(eastLand);

    // Recessed Strait-1 Water Channel: -15 to +15 at Y = -3.5m (eliminates Z-fighting)
    const waterGeo = new THREE.PlaneGeometry(30, 240);
    waterGeo.rotateX(-Math.PI / 2);
    const waterMat = new THREE.MeshStandardMaterial({
      color: 0x0284c7,
      roughness: 0.2,
      metalness: 0.8,
      transparent: true,
      opacity: 0.85,
    });
    const waterMesh = new THREE.Mesh(waterGeo, waterMat);
    waterMesh.position.set(0, ELEVATION_CHANNEL_WATER, 0);
    this.terrainGroup.add(waterMesh);

    // Northern Mountains Elevation (Y = +15m..+35m)
    const northMountainGeo = new THREE.ConeGeometry(25, 32, 6);
    const mountainMat = new THREE.MeshStandardMaterial({
      color: 0x1e3a5f,
      wireframe: true,
    });
    const mountainNorth = new THREE.Mesh(northMountainGeo, mountainMat);
    mountainNorth.position.set(30, 16, -90);
    this.terrainGroup.add(mountainNorth);

    // Elevated Highway Bridges (North Bridge: Y = 60km -> Z = -60; South Bridge: Y = 180km -> Z = +60)
    this.buildHighwayBridge(-60);
    this.buildHighwayBridge(60);

    // Road Networks with polygonOffset to prevent coplanar flickering
    this.buildRoadRibbons();
  }

  private buildHighwayBridge(zPos: number): void {
    if (!this.bridgeGroup) return;

    // Bridge deck spanning 30m over water (-15 to +15), rising from +2m to +14m
    const deckLength = 34;
    const deckGeo = new THREE.BoxGeometry(deckLength, 1.2, 5);
    const deckMat = new THREE.MeshStandardMaterial({
      color: 0xf59e0b,
      metalness: 0.6,
      roughness: 0.4,
    });
    const deck = new THREE.Mesh(deckGeo, deckMat);
    deck.position.set(
      0,
      (ELEVATION_BRIDGE_DECK_MAX + ELEVATION_BRIDGE_DECK_MIN) / 2,
      zPos,
    );
    this.bridgeGroup.add(deck);

    // Support pylons rooted in recessed water bed (-10m up to bridge deck)
    const pylonGeo = new THREE.CylinderGeometry(0.8, 1.2, 18, 8);
    const pylonMat = new THREE.MeshStandardMaterial({ color: 0x475569 });

    const pylonWest = new THREE.Mesh(pylonGeo, pylonMat);
    pylonWest.position.set(-10, 0, zPos);
    this.bridgeGroup.add(pylonWest);

    const pylonEast = new THREE.Mesh(pylonGeo, pylonMat);
    pylonEast.position.set(10, 0, zPos);
    this.bridgeGroup.add(pylonEast);
  }

  private buildRoadRibbons(): void {
    if (!this.terrainGroup) return;

    const roadMat = new THREE.MeshBasicMaterial({
      color: 0x334155,
      polygonOffset: true,
      polygonOffsetFactor: -1,
      polygonOffsetUnits: -2,
    });

    const m2w = (x: number, y: number) => ({
      x: (x / this.theater.boundsM.w) * 400 - 200,
      z: (y / this.theater.boundsM.h) * 240 - 120,
    });

    const nodeMap = new Map(this.theater.nodes.map((n) => [n.id, n]));

    for (const edge of this.theater.edges) {
      const na = nodeMap.get(edge.a);
      const nb = nodeMap.get(edge.b);
      if (!na || !nb) continue;

      const pA = m2w(na.pos[0], na.pos[1]);
      const pB = m2w(nb.pos[0], nb.pos[1]);

      const dx = pB.x - pA.x;
      const dz = pB.z - pA.z;
      const length = Math.sqrt(dx * dx + dz * dz);
      const angle = Math.atan2(dz, dx);

      const roadGeo = new THREE.PlaneGeometry(length, 2.5);
      roadGeo.rotateX(-Math.PI / 2);
      const roadMesh = new THREE.Mesh(roadGeo, roadMat);
      roadMesh.position.set(
        (pA.x + pB.x) / 2,
        ELEVATION_TERRAIN_BASE + 0.1,
        (pA.z + pB.z) / 2,
      );
      roadMesh.rotation.y = -angle;
      this.terrainGroup.add(roadMesh);
    }
  }

  private update3DUnits(
    unitsData: VisualUnit[] | Map<number, VisualUnit>,
  ): void {
    if (!this.unitsGroup) return;
    const units = Array.isArray(unitsData)
      ? unitsData
      : Array.from(unitsData.values());

    const activeIds = new Set<number>();

    for (const unit of units) {
      activeIds.add(unit.id);
      let mesh = this.unitMeshes.get(unit.id);

      const wx = (unit.x / this.theater.boundsM.w) * 400 - 200;
      const wz = (unit.y / this.theater.boundsM.h) * 240 - 120;
      const isAir = isAirUnit(unit.kind);
      const wy = isAir ? 40 : ELEVATION_TERRAIN_BASE + 1.2;

      if (!mesh) {
        mesh = this.create3DUnitMesh(unit);
        this.unitsGroup.add(mesh);
        this.unitMeshes.set(unit.id, mesh);
      }

      mesh.position.set(wx, wy, wz);
      mesh.rotation.y = (-unit.headingDeg * Math.PI) / 180;
    }

    // Cleanup despawned unit meshes
    for (const [id, mesh] of this.unitMeshes.entries()) {
      if (!activeIds.has(id)) {
        this.unitsGroup.remove(mesh);
        this.disposeObject(mesh);
        this.unitMeshes.delete(id);
      }
    }
  }

  private create3DUnitMesh(unit: VisualUnit): THREE.Object3D {
    const group = new THREE.Group();
    const isCoalition = unit.side === "COALITION";
    const color = isCoalition ? 0x00e5ff : 0xff0055;

    if (isCoalition) {
      // Quorum Chevron / Delta Wing (OV-2 / OV-3)
      const geo = new THREE.ConeGeometry(2.5, 5, 3);
      geo.rotateX(Math.PI / 2);
      const mat = new THREE.MeshStandardMaterial({
        color,
        emissive: color,
        emissiveIntensity: 0.6,
      });
      const cone = new THREE.Mesh(geo, mat);
      group.add(cone);
    } else {
      // Static Jagged Sawtooth Shard (OV-2 / OV-3)
      const geo = new THREE.DodecahedronGeometry(2.6, 0);
      const mat = new THREE.MeshStandardMaterial({
        color,
        emissive: color,
        emissiveIntensity: 0.8,
        wireframe: true,
      });
      const shard = new THREE.Mesh(geo, mat);
      shard.scale.set(0.7, 1.8, 1);
      group.add(shard);
    }

    // Altitude drop-line for aircraft
    const isAir = isAirUnit(unit.kind);
    if (isAir) {
      const lineGeo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(0, 0, 0),
        new THREE.Vector3(0, -38, 0),
      ]);
      const lineMat = new THREE.LineBasicMaterial({
        color: isCoalition ? 0x00e5ff : 0xff0055,
        transparent: true,
        opacity: 0.35,
      });
      const dropLine = new THREE.Line(lineGeo, lineMat);
      group.add(dropLine);

      // Ground shadow ring
      const ringGeo = new THREE.RingGeometry(1.2, 1.8, 16);
      ringGeo.rotateX(-Math.PI / 2);
      const ringMat = new THREE.MeshBasicMaterial({
        color: isCoalition ? 0x00e5ff : 0xff0055,
        transparent: true,
        opacity: 0.4,
      });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.position.y = -38;
      group.add(ring);
    }

    return group;
  }

  private update3DEffects(extraEffects?: VisualEffect[]): void {
    if (!this.effectsGroup) return;
    const all = [...this.activeEffects, ...(extraEffects ?? [])];

    // Clear previous frame dynamic effects
    while (this.effectsGroup.children.length > 0) {
      const child = this.effectsGroup.children[0];
      if (child) {
        this.effectsGroup.remove(child);
        this.disposeObject(child);
      }
    }

    for (const fx of all) {
      if (fx.type === "MISSILE_TRAJECTORY") {
        // Parabolic Ballistic Missile Arc: y = y0 + deltaY * p + sin(p * PI) * hPeak
        const p = fx.progress;
        const sx = (fx.sourcePos[0] / this.theater.boundsM.w) * 400 - 200;
        const sz = (fx.sourcePos[1] / this.theater.boundsM.h) * 240 - 120;
        const tx = (fx.targetPos[0] / this.theater.boundsM.w) * 400 - 200;
        const tz = (fx.targetPos[1] / this.theater.boundsM.h) * 240 - 120;

        const currentX = sx + (tx - sx) * p;
        const currentZ = sz + (tz - sz) * p;
        const currentY = getBallisticMissileAltitude(
          ELEVATION_TERRAIN_BASE + 2,
          ELEVATION_TERRAIN_BASE + 2,
          p,
          45, // peak altitude in 3D world units
        );

        // Projectile missile head
        const missileGeo = new THREE.SphereGeometry(1.2, 8, 8);
        const missileMat = new THREE.MeshBasicMaterial({ color: 0xff0055 });
        const missile = new THREE.Mesh(missileGeo, missileMat);
        missile.position.set(currentX, currentY, currentZ);
        this.effectsGroup.add(missile);

        // 3D Parabolic trajectory curve points
        const points: THREE.Vector3[] = [];
        for (let step = 0; step <= p; step += 0.05) {
          const stepX = sx + (tx - sx) * step;
          const stepZ = sz + (tz - sz) * step;
          const stepY = getBallisticMissileAltitude(
            ELEVATION_TERRAIN_BASE + 2,
            ELEVATION_TERRAIN_BASE + 2,
            step,
            45,
          );
          points.push(new THREE.Vector3(stepX, stepY, stepZ));
        }

        if (points.length > 1) {
          const curveGeo = new THREE.BufferGeometry().setFromPoints(points);
          const curveMat = new THREE.LineBasicMaterial({
            color: 0xff0055,
            transparent: true,
            opacity: 0.7,
          });
          const line = new THREE.Line(curveGeo, curveMat);
          this.effectsGroup.add(line);
        }
      } else if (fx.type === "KINETIC_BURST") {
        const bx = (fx.pos[0] / this.theater.boundsM.w) * 400 - 200;
        const bz = (fx.pos[1] / this.theater.boundsM.h) * 240 - 120;
        const burstRadius = Math.max(2, 12 * fx.progress);

        const sphereGeo = new THREE.SphereGeometry(burstRadius, 12, 12);
        const sphereMat = new THREE.MeshBasicMaterial({
          color: 0x00e5ff,
          wireframe: true,
          transparent: true,
          opacity: Math.max(0, 1 - fx.progress),
        });
        const burst = new THREE.Mesh(sphereGeo, sphereMat);
        burst.position.set(bx, ELEVATION_TERRAIN_BASE + 4, bz);
        this.effectsGroup.add(burst);
      }
    }
  }

  // --- Inspection getters for test assertions ---
  getScene(): THREE.Scene | null {
    return this.scene;
  }

  getCamera(): THREE.PerspectiveCamera | null {
    return this.camera;
  }

  getPreset(): "WIDE" | "COMBAT_45" | "TOP_DOWN" {
    return this.currentPreset;
  }
}
