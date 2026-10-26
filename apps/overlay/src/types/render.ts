import type { TheaterDefinition } from "./theater";
import type { VisualUnit, VisualEdge } from "./unit";
import type { TelemetryState } from "./telemetry";
import type { VisualEffect } from "./effects";
export type { VisualEffect };

/**
 * Common configuration options provided to render engines during initialization.
 */
export interface RenderEngineOptions {
  canvas?: HTMLCanvasElement | undefined;
  pixelRatio?: number | undefined;
  antialias?: boolean | undefined;
  logarithmicDepthBuffer?: boolean | undefined;
  themeId?: string | undefined;
}

/**
 * Camera target definition for director presets and tactical focus.
 */
export interface CameraTarget {
  mode: "OVERVIEW" | "COMBAT" | "TOP_DOWN" | "UNIT" | "COCKPIT";
  unitId?: number | undefined;
  position?: [number, number, number] | undefined;
  lookAt?: [number, number, number] | undefined;
  fov?: number | undefined;
  transitionDurationMs?: number | undefined;
}

/**
 * Engine-agnostic frame state emitted downstream from simulation/interpolation.
 */
export interface RenderFrameState {
  tick: number;
  simTime: number;
  units: VisualUnit[] | Map<number, VisualUnit>;
  edges?: VisualEdge[] | undefined;
  telemetry: TelemetryState;
  effects?: VisualEffect[] | undefined;
  selectedUnitId?: number | null | undefined;
  cameraPreset?: "WIDE" | "COMBAT_45" | "TOP_DOWN" | undefined;
}

/**
 * Universal interface implemented by all visual paradigms (Options A, B, C, D).
 * Strictly decoupled from simulation state and backend protocols.
 */
export interface IRenderEngine {
  readonly id: string;
  readonly name: string;

  /** Initialize canvas context, shaders, buffers, and DOM containers */
  initialize(
    container: HTMLElement,
    options?: RenderEngineOptions,
  ): Promise<void>;

  /** Handle viewport resizing and high-DPI scaling */
  resize(width: number, height: number, pixelRatio?: number): void;

  /** Update terrain mesh, infrastructure, roads, and bridges */
  updateTheaterMap(theater: TheaterDefinition): void;

  /** Render a single frame from the decoupled simulation state */
  renderFrame(state: RenderFrameState): void;

  /** Trigger ephemeral visual effects (missile bursts, radar sweeps, scanline glitches) */
  triggerEffect(effect: VisualEffect): void;

  /** Direct camera to target preset or tracked unit */
  setCameraTarget(target: CameraTarget): void;

  /** Dispose WebGL/Canvas contexts, geometries, textures, and timers */
  dispose(): void;
}
