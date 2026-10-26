import type {
  IRenderEngine,
  RenderEngineOptions,
  RenderFrameState,
  CameraTarget,
  VisualEffect,
} from "../types/render";
import type { TheaterDefinition } from "../types/theater";
import { STRAIT_1_THEATER } from "../theater/strait1";
import { CrtVectorEngine } from "./crt2d/crt-engine";
import { HoloTableEngine } from "./holo3d/holo-engine";
import { FlirMfdEngine } from "./flir/flir-engine";
import { BatchSpriteEngine } from "./batch/batch-engine";

export type EngineFactory = () => IRenderEngine;

export interface ThemeInfo {
  id: string;
  name: string;
  description: string;
}

export class RenderManager {
  private activeEngine: IRenderEngine | null = null;
  private engines = new Map<
    string,
    { factory: EngineFactory; info: ThemeInfo }
  >();
  private container: HTMLElement | null = null;
  private currentTheater: TheaterDefinition = STRAIT_1_THEATER;
  private currentWidth = 1280;
  private currentHeight = 720;
  private pixelRatio = 1;
  private currentOptions?: RenderEngineOptions | undefined;
  private themeChangeListeners: Array<(themeId: string) => void> = [];

  constructor() {
    // Register the 4 Authoritative Visual Paradigms
    this.register("crt", () => new CrtVectorEngine(), {
      id: "crt",
      name: "Option A: 2D CRT Vector Phosphor",
      description:
        "Living Glass, glowing vector contours, speed trails, and radar sweep",
    });

    this.register("holo3d", () => new HoloTableEngine(), {
      id: "holo3d",
      name: "Option B: 3D Holographic Tabletop",
      description:
        "Three.js terrain elevation mesh, recessed channel (-3.5m), and parabolic arcs",
    });

    this.register("flir", () => new FlirMfdEngine(), {
      id: "flir",
      name: "Option C: FLIR / MFD Cockpit Sensor",
      description:
        "High-contrast thermal targeting, pitch ladder, and White-Hot PiP",
    });

    this.register("batch", () => new BatchSpriteEngine(), {
      id: "batch",
      name: "Option D: High-Density Batch Spriting",
      description: "Optimized 2D batch spriting rendering 500+ units at 60fps",
    });
  }

  register(themeId: string, factory: EngineFactory, info: ThemeInfo): void {
    this.engines.set(themeId, { factory, info });
  }

  getAvailableThemes(): ThemeInfo[] {
    return Array.from(this.engines.values()).map((entry) => entry.info);
  }

  getActiveEngine(): IRenderEngine | null {
    return this.activeEngine;
  }

  getActiveThemeId(): string | null {
    return this.activeEngine ? this.activeEngine.id : null;
  }

  onThemeChange(listener: (themeId: string) => void): () => void {
    this.themeChangeListeners.push(listener);
    return () => {
      this.themeChangeListeners = this.themeChangeListeners.filter(
        (l) => l !== listener,
      );
    };
  }

  async attach(
    container: HTMLElement,
    initialThemeId = "crt",
    options?: RenderEngineOptions,
  ): Promise<void> {
    this.container = container;
    this.currentOptions = options;
    const rect = container.getBoundingClientRect();
    this.currentWidth = rect.width || 1280;
    this.currentHeight = rect.height || 720;
    this.pixelRatio =
      options?.pixelRatio ??
      (typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1);

    await this.switchTheme(initialThemeId);
  }

  async switchTheme(themeId: string): Promise<void> {
    if (!this.container) {
      throw new Error(
        "RenderManager must be attached to a container DOM element before switching themes",
      );
    }

    const entry = this.engines.get(themeId);
    if (!entry) {
      throw new Error(
        `Unknown rendering theme: "${themeId}". Available: ${Array.from(this.engines.keys()).join(", ")}`,
      );
    }

    // Clean up current active engine without memory leaks
    if (this.activeEngine) {
      this.activeEngine.dispose();
      this.activeEngine = null;
    }

    // Instantiate and initialize new engine
    this.activeEngine = entry.factory();
    await this.activeEngine.initialize(this.container, this.currentOptions);
    this.activeEngine.resize(
      this.currentWidth,
      this.currentHeight,
      this.pixelRatio,
    );
    this.activeEngine.updateTheaterMap(this.currentTheater);

    for (const listener of this.themeChangeListeners) {
      listener(themeId);
    }
  }

  resize(width: number, height: number, pixelRatio = 1): void {
    this.currentWidth = width;
    this.currentHeight = height;
    this.pixelRatio = pixelRatio;
    if (this.activeEngine) {
      this.activeEngine.resize(width, height, pixelRatio);
    }
  }

  updateTheaterMap(theater: TheaterDefinition): void {
    this.currentTheater = theater;
    if (this.activeEngine) {
      this.activeEngine.updateTheaterMap(theater);
    }
  }

  renderFrame(state: RenderFrameState): void {
    if (this.activeEngine) {
      this.activeEngine.renderFrame(state);
    }
  }

  triggerEffect(effect: VisualEffect): void {
    if (this.activeEngine) {
      this.activeEngine.triggerEffect(effect);
    }
  }

  setCameraTarget(target: CameraTarget): void {
    if (this.activeEngine) {
      this.activeEngine.setCameraTarget(target);
    }
  }

  dispose(): void {
    if (this.activeEngine) {
      this.activeEngine.dispose();
      this.activeEngine = null;
    }
    this.container = null;
    this.themeChangeListeners = [];
  }
}
