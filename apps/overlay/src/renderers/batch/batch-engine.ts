import type {
  IRenderEngine,
  RenderEngineOptions,
  RenderFrameState,
  CameraTarget,
  VisualEffect,
} from "../../types/render";
import type { TheaterDefinition } from "../../types/theater";
import type { VisualUnit } from "../../types/unit";
import { STRAIT_1_THEATER } from "../../theater/strait1";
import { FACTION_TOKENS } from "../../symbology/dual-encoding";
import { createCanvasElement } from "../../utils/dom";

export interface BatchPerformanceStats {
  unitCount: number;
  frameTimeMs: number;
  estimatedFps: number;
  batchPasses: number;
}

export class BatchSpriteEngine implements IRenderEngine {
  readonly id = "batch";
  readonly name = "High-Density Batch Spriting";

  private container: HTMLElement | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private ctx: CanvasRenderingContext2D | null = null;
  private theater: TheaterDefinition = STRAIT_1_THEATER;
  private width = 1280;
  private height = 720;
  private pixelRatio = 1;

  private lastStats: BatchPerformanceStats = {
    unitCount: 0,
    frameTimeMs: 0,
    estimatedFps: 60,
    batchPasses: 0,
  };

  async initialize(
    container: HTMLElement,
    options?: RenderEngineOptions,
  ): Promise<void> {
    this.container = container;
    this.pixelRatio =
      options?.pixelRatio ??
      (typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1);

    if (options?.canvas) {
      this.canvas = options.canvas;
    } else {
      this.canvas = createCanvasElement(this.container, "batch-sprite-canvas");
    }

    const rect = container.getBoundingClientRect();
    this.resize(rect.width || 1280, rect.height || 720, this.pixelRatio);
  }

  resize(width: number, height: number, pixelRatio = 1): void {
    this.width = Math.max(width, 100);
    this.height = Math.max(height, 100);
    this.pixelRatio = pixelRatio;

    if (this.canvas) {
      this.canvas.width = Math.floor(this.width * this.pixelRatio);
      this.canvas.height = Math.floor(this.height * this.pixelRatio);
      this.ctx = this.canvas.getContext("2d");
    }
  }

  updateTheaterMap(theater: TheaterDefinition): void {
    this.theater = theater;
  }

  triggerEffect(effect: VisualEffect): void {
    void effect;
  }

  setCameraTarget(target: CameraTarget): void {
    void target;
  }

  getPerformanceStats(): BatchPerformanceStats {
    return this.lastStats;
  }

  renderFrame(state: RenderFrameState): void {
    if (!this.ctx || !this.canvas) return;
    const ctx = this.ctx;
    const startTime =
      typeof performance !== "undefined" ? performance.now() : Date.now();

    const units = Array.isArray(state.units)
      ? state.units
      : Array.from(state.units.values());

    ctx.save();
    ctx.scale(this.pixelRatio, this.pixelRatio);

    // 1. Clear background
    ctx.fillStyle = "#030712";
    ctx.fillRect(0, 0, this.width, this.height);

    // 2. Simple backdrop grid
    this.renderFastGrid(ctx);

    // 3. Batched High-Density Unit Rendering (Groups: Quorum Chevrons vs Static Sawtooths)
    let batchPasses = 0;
    const quorumUnits: VisualUnit[] = [];
    const staticUnits: VisualUnit[] = [];

    for (const unit of units) {
      if (unit.side === "COALITION") {
        quorumUnits.push(unit);
      } else {
        staticUnits.push(unit);
      }
    }

    // Batch Pass 1: Quorum Velocity Leaders
    ctx.strokeStyle = "rgba(0, 229, 255, 0.4)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (const u of quorumUnits) {
      const sx = (u.x / this.theater.boundsM.w) * this.width;
      const sy = (u.y / this.theater.boundsM.h) * this.height;
      const rad = ((u.headingDeg - 90) * Math.PI) / 180;
      ctx.moveTo(sx, sy);
      ctx.lineTo(sx + Math.cos(rad) * 10, sy + Math.sin(rad) * 10);
    }
    ctx.stroke();
    batchPasses++;

    // Batch Pass 2: Quorum Chevrons (OV-2 / OV-3)
    ctx.fillStyle = FACTION_TOKENS.QUORUM_CYAN;
    ctx.beginPath();
    for (const u of quorumUnits) {
      const sx = (u.x / this.theater.boundsM.w) * this.width;
      const sy = (u.y / this.theater.boundsM.h) * this.height;
      const rad = (u.headingDeg * Math.PI) / 180;
      const cos = Math.cos(rad);
      const sin = Math.sin(rad);

      // Delta Wing local coords: (0, -6), (5, 6), (0, 3), (-5, 6)
      const p1x = sx + (0 * cos - -6 * sin);
      const p1y = sy + (0 * sin + -6 * cos);
      const p2x = sx + (5 * cos - 6 * sin);
      const p2y = sy + (5 * sin + 6 * cos);
      const p3x = sx + (0 * cos - 3 * sin);
      const p3y = sy + (0 * sin + 3 * cos);
      const p4x = sx + (-5 * cos - 6 * sin);
      const p4y = sy + (-5 * sin + 6 * cos);

      ctx.moveTo(p1x, p1y);
      ctx.lineTo(p2x, p2y);
      ctx.lineTo(p3x, p3y);
      ctx.lineTo(p4x, p4y);
      ctx.closePath();
    }
    ctx.fill();
    batchPasses++;

    // Batch Pass 3: Static Velocity Leaders
    ctx.strokeStyle = "rgba(255, 0, 85, 0.4)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (const u of staticUnits) {
      const sx = (u.x / this.theater.boundsM.w) * this.width;
      const sy = (u.y / this.theater.boundsM.h) * this.height;
      const rad = ((u.headingDeg - 90) * Math.PI) / 180;
      ctx.moveTo(sx, sy);
      ctx.lineTo(sx + Math.cos(rad) * 10, sy + Math.sin(rad) * 10);
    }
    ctx.stroke();
    batchPasses++;

    // Batch Pass 4: Static Sawtooth Shards (OV-2 / OV-3)
    ctx.fillStyle = FACTION_TOKENS.STATIC_MAGENTA;
    ctx.beginPath();
    for (const u of staticUnits) {
      const sx = (u.x / this.theater.boundsM.w) * this.width;
      const sy = (u.y / this.theater.boundsM.h) * this.height;
      const rad = (u.headingDeg * Math.PI) / 180;
      const cos = Math.cos(rad);
      const sin = Math.sin(rad);

      // Jagged Sawtooth Shard points
      const p1x = sx + (0 * cos - -7 * sin);
      const p1y = sy + (0 * sin + -7 * cos);
      const p2x = sx + (4 * cos - 1 * sin);
      const p2y = sy + (4 * sin + 1 * cos);
      const p3x = sx + (6 * cos - 7 * sin);
      const p3y = sy + (6 * sin + 7 * cos);
      const p4x = sx + (0 * cos - 3 * sin);
      const p4y = sy + (0 * sin + 3 * cos);
      const p5x = sx + (-6 * cos - 7 * sin);
      const p5y = sy + (-6 * sin + 7 * cos);
      const p6x = sx + (-4 * cos - 1 * sin);
      const p6y = sy + (-4 * sin + 1 * cos);

      ctx.moveTo(p1x, p1y);
      ctx.lineTo(p2x, p2y);
      ctx.lineTo(p3x, p3y);
      ctx.lineTo(p4x, p4y);
      ctx.lineTo(p5x, p5y);
      ctx.lineTo(p6x, p6y);
      ctx.closePath();
    }
    ctx.fill();
    batchPasses++;

    // 4. OV-4 Label Density Budgeting: Suppress swarm text, draw ONLY key commander or selected badge
    this.renderKeyBadges(ctx, units);

    // 5. Benchmark Telemetry HUD Overlay
    const endTime =
      typeof performance !== "undefined" ? performance.now() : Date.now();
    const frameTimeMs = Math.max(0.1, endTime - startTime);

    this.lastStats = {
      unitCount: units.length,
      frameTimeMs: Number(frameTimeMs.toFixed(2)),
      estimatedFps: Math.min(60, Math.round(1000 / Math.max(1, frameTimeMs))),
      batchPasses,
    };

    this.renderStatsPill(ctx, this.lastStats);

    ctx.restore();
  }

  dispose(): void {
    if (this.canvas && this.canvas.parentElement) {
      this.canvas.parentElement.removeChild(this.canvas);
    }
    this.canvas = null;
    this.ctx = null;
    this.container = null;
  }

  private renderFastGrid(ctx: CanvasRenderingContext2D): void {
    ctx.save();
    ctx.strokeStyle = "rgba(30, 58, 95, 0.2)";
    ctx.lineWidth = 1;
    ctx.beginPath();

    for (let x = 0; x < this.width; x += 80) {
      ctx.moveTo(x, 0);
      ctx.lineTo(x, this.height);
    }
    for (let y = 0; y < this.height; y += 80) {
      ctx.moveTo(0, y);
      ctx.lineTo(this.width, y);
    }
    ctx.stroke();
    ctx.restore();
  }

  private renderKeyBadges(
    ctx: CanvasRenderingContext2D,
    units: VisualUnit[],
  ): void {
    ctx.save();
    ctx.font = "bold 9px monospace";

    for (const u of units) {
      if (u.isSelected || u.isConvoyLeader) {
        const sx = (u.x / this.theater.boundsM.w) * this.width;
        const sy = (u.y / this.theater.boundsM.h) * this.height;
        ctx.fillStyle = u.side === "COALITION" ? "#00e5ff" : "#ff0055";
        const badge = u.convoyFollowers
          ? `[TRUCK] +${u.convoyFollowers}`
          : u.callsign;
        ctx.fillText(badge, sx + 8, sy - 4);
      }
    }
    ctx.restore();
  }

  private renderStatsPill(
    ctx: CanvasRenderingContext2D,
    stats: BatchPerformanceStats,
  ): void {
    ctx.save();
    const pillW = 260;
    const pillH = 68;
    const px = this.width - pillW - 20;
    const py = 20;

    ctx.fillStyle = "rgba(9, 18, 33, 0.9)";
    ctx.strokeStyle = "#1e3a5f";
    ctx.lineWidth = 1;
    ctx.fillRect(px, py, pillW, pillH);
    ctx.strokeRect(px, py, pillW, pillH);

    ctx.font = "bold 10px monospace";
    ctx.fillStyle = "#00e5ff";
    ctx.fillText("HIGH-DENSITY BATCH SPRITING", px + 10, py + 16);

    ctx.font = "9px monospace";
    ctx.fillStyle = "#94a3b8";
    ctx.fillText(
      `ACTIVE UNITS: ${stats.unitCount} (TARGET: 500+)`,
      px + 10,
      py + 32,
    );
    ctx.fillText(
      `FRAME RENDER TIME: ${stats.frameTimeMs} ms (<8ms budget)`,
      px + 10,
      py + 46,
    );

    const fpsColor = stats.estimatedFps >= 55 ? "#10b981" : "#f59e0b";
    ctx.fillStyle = fpsColor;
    ctx.fillText(
      `FRAME RATE: ~${stats.estimatedFps} FPS | BATCHES: ${stats.batchPasses}`,
      px + 10,
      py + 60,
    );
    ctx.restore();
  }
}
