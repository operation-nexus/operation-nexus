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
import { createCanvasElement } from "../../utils/dom";

export type FlirPolarity = "WHITE_HOT" | "BLACK_HOT";

export class FlirMfdEngine implements IRenderEngine {
  readonly id = "flir";
  readonly name = "FLIR / MFD Cockpit Sensor";

  private container: HTMLElement | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private ctx: CanvasRenderingContext2D | null = null;
  private theater: TheaterDefinition = STRAIT_1_THEATER;
  private width = 1280;
  private height = 720;
  private pixelRatio = 1;

  private polarity: FlirPolarity = "WHITE_HOT";
  private currentHeadingDeg = 90;
  private pitchDeg = 0;
  private trackedUnitId: number | null = null;
  private noiseSeed = 0;

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
      this.canvas = createCanvasElement(this.container, "flir-mfd-canvas");
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
    // FLIR noise glitch or sensor flash
    this.noiseSeed = (this.noiseSeed + 13) % 100;
  }

  setCameraTarget(target: CameraTarget): void {
    if (target.unitId !== undefined) {
      this.trackedUnitId = target.unitId;
    }
  }

  setPolarity(polarity: FlirPolarity): void {
    this.polarity = polarity;
  }

  getPolarity(): FlirPolarity {
    return this.polarity;
  }

  renderFrame(state: RenderFrameState): void {
    if (!this.ctx || !this.canvas) return;
    const ctx = this.ctx;

    this.noiseSeed = (this.noiseSeed + 1) % 1000;
    const units = Array.isArray(state.units)
      ? state.units
      : Array.from(state.units.values());

    // Auto-select tracked target if none set
    if (this.trackedUnitId === null && units.length > 0) {
      const enemy = units.find((u) => u.side === "ENEMY");
      this.trackedUnitId = enemy ? enemy.id : (units[0]?.id ?? null);
    }

    const trackedUnit = units.find((u) => u.id === this.trackedUnitId);
    if (trackedUnit) {
      this.currentHeadingDeg = trackedUnit.headingDeg;
    }

    ctx.save();
    ctx.scale(this.pixelRatio, this.pixelRatio);

    // 1. Monochromatic Background
    const isWhiteHot = this.polarity === "WHITE_HOT";
    ctx.fillStyle = isWhiteHot ? "#0a1017" : "#020408";
    ctx.fillRect(0, 0, this.width, this.height);

    // 2. Analog Sensor Thermal Grain / Noise
    this.renderSensorNoise(ctx);

    // 3. Central Tactical FLIR Reticle / Crosshairs
    this.renderCrosshairs(ctx);

    // 4. Collimated Pitch Ladder (+20° to -20°)
    this.renderPitchLadder(ctx);

    // 5. Tactical Compass Heading Ribbon at top
    this.renderCompassRibbon(ctx);

    // 6. Ownship Link-16 Telemetry Data Readout
    this.renderLink16Telemetry(ctx, trackedUnit, state);

    // 7. Tactical Target Acquisition Brackets
    this.renderTargetBrackets(ctx, units);

    // 8. Picture-in-Picture (PiP) Thermal Infrared Scope
    this.renderThermalPiP(ctx, trackedUnit);

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

  private renderSensorNoise(ctx: CanvasRenderingContext2D): void {
    ctx.save();
    ctx.fillStyle = "rgba(0, 229, 255, 0.03)";
    for (let i = 0; i < 40; i++) {
      const rx = (this.noiseSeed * (i + 1) * 37) % this.width;
      const ry = (this.noiseSeed * (i + 1) * 59) % this.height;
      ctx.fillRect(rx, ry, 2, 2);
    }
    ctx.restore();
  }

  private renderCrosshairs(ctx: CanvasRenderingContext2D): void {
    const cx = this.width / 2;
    const cy = this.height / 2;

    ctx.save();
    ctx.strokeStyle = "rgba(0, 229, 255, 0.75)";
    ctx.lineWidth = 1.5;

    // Center crosshair gap
    const gap = 16;
    const len = 36;

    ctx.beginPath();
    // Left
    ctx.moveTo(cx - gap - len, cy);
    ctx.lineTo(cx - gap, cy);
    // Right
    ctx.moveTo(cx + gap, cy);
    ctx.lineTo(cx + gap + len, cy);
    // Top
    ctx.moveTo(cx, cy - gap - len);
    ctx.lineTo(cx, cy - gap);
    // Bottom
    ctx.moveTo(cx, cy + gap);
    ctx.lineTo(cx, cy + gap + len);
    ctx.stroke();

    // Flight Path Marker circle
    ctx.beginPath();
    ctx.arc(cx, cy, 5, 0, Math.PI * 2);
    ctx.stroke();

    // Mode stamp
    ctx.fillStyle = "#00e5ff";
    ctx.font = "bold 10px monospace";
    ctx.fillText(`FLIR / MFD: [${this.polarity}]`, cx - 60, cy + gap + 30);
    ctx.restore();
  }

  private renderPitchLadder(ctx: CanvasRenderingContext2D): void {
    const cx = this.width / 2;
    const cy = this.height / 2;

    ctx.save();
    ctx.strokeStyle = "rgba(0, 229, 255, 0.6)";
    ctx.fillStyle = "rgba(0, 229, 255, 0.8)";
    ctx.font = "9px monospace";
    ctx.lineWidth = 1.5;

    const rungs = [-20, -10, 0, 10, 20];
    const rungWidth = 70;
    const spacingY = 32;

    for (const deg of rungs) {
      const yOffset = cy - (deg - this.pitchDeg) * (spacingY / 10);
      if (yOffset < 80 || yOffset > this.height - 80) continue;

      if (deg === 0) {
        // Horizon line (waterline)
        ctx.beginPath();
        ctx.moveTo(cx - rungWidth - 20, yOffset);
        ctx.lineTo(cx - 20, yOffset);
        ctx.moveTo(cx + 20, yOffset);
        ctx.lineTo(cx + rungWidth + 20, yOffset);
        ctx.stroke();
        ctx.fillText("00", cx - rungWidth - 36, yOffset + 3);
        ctx.fillText("00", cx + rungWidth + 24, yOffset + 3);
      } else {
        // Angled pitch rung
        const isPositive = deg > 0;
        const tickDrop = isPositive ? 6 : -6;

        ctx.beginPath();
        // Left rung
        ctx.moveTo(cx - rungWidth, yOffset + tickDrop);
        ctx.lineTo(cx - rungWidth, yOffset);
        ctx.lineTo(cx - 20, yOffset);
        // Right rung
        ctx.moveTo(cx + 20, yOffset);
        ctx.lineTo(cx + rungWidth, yOffset);
        ctx.lineTo(cx + rungWidth, yOffset + tickDrop);
        ctx.stroke();

        const label = Math.abs(deg).toString().padStart(2, "0");
        ctx.fillText(label, cx - rungWidth - 18, yOffset + 3);
        ctx.fillText(label, cx + rungWidth + 4, yOffset + 3);
      }
    }
    ctx.restore();
  }

  private renderCompassRibbon(ctx: CanvasRenderingContext2D): void {
    const ribbonY = 32;
    const cx = this.width / 2;
    const ribbonWidth = Math.min(500, this.width - 40);

    ctx.save();
    ctx.strokeStyle = "rgba(0, 229, 255, 0.5)";
    ctx.lineWidth = 1;
    ctx.strokeRect(cx - ribbonWidth / 2, ribbonY - 14, ribbonWidth, 24);

    ctx.beginPath();
    // Center pointer caret
    ctx.moveTo(cx, ribbonY + 14);
    ctx.lineTo(cx - 5, ribbonY + 20);
    ctx.lineTo(cx + 5, ribbonY + 20);
    ctx.closePath();
    ctx.fillStyle = "#00e5ff";
    ctx.fill();

    // Tick marks every 10 degrees
    ctx.font = "9px monospace";
    ctx.fillStyle = "#00e5ff";
    ctx.textAlign = "center";

    const currentH = this.currentHeadingDeg;
    for (let offset = -40; offset <= 40; offset += 5) {
      const heading = (Math.round(currentH) + offset + 360) % 360;
      const x = cx + offset * 5;

      if (x < cx - ribbonWidth / 2 + 10 || x > cx + ribbonWidth / 2 - 10)
        continue;

      if (heading % 10 === 0) {
        ctx.beginPath();
        ctx.moveTo(x, ribbonY - 14);
        ctx.lineTo(x, ribbonY - 4);
        ctx.stroke();

        let label = heading.toString().padStart(3, "0");
        if (heading === 0) label = "N";
        else if (heading === 90) label = "E";
        else if (heading === 180) label = "S";
        else if (heading === 270) label = "W";

        ctx.fillText(label, x, ribbonY + 8);
      } else {
        ctx.beginPath();
        ctx.moveTo(x, ribbonY - 14);
        ctx.lineTo(x, ribbonY - 8);
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  private renderLink16Telemetry(
    ctx: CanvasRenderingContext2D,
    trackedUnit: VisualUnit | undefined,
    state: RenderFrameState,
  ): void {
    const leftX = 28;
    const topY = 100;

    ctx.save();
    ctx.fillStyle = "#00e5ff";
    ctx.font = "11px monospace";

    ctx.fillText("LINK-16 TACTICAL MFD", leftX, topY);
    ctx.strokeStyle = "rgba(0, 229, 255, 0.4)";
    ctx.beginPath();
    ctx.moveTo(leftX, topY + 4);
    ctx.lineTo(leftX + 160, topY + 4);
    ctx.stroke();

    ctx.font = "10px monospace";
    ctx.fillStyle = "#94a3b8";
    const alt = trackedUnit ? (trackedUnit.z ?? 45) * 100 : 4500;
    const spd = trackedUnit ? (trackedUnit.speedMps ?? 240) : 240;
    const mach = (spd / 340).toFixed(2);

    ctx.fillText(`ALT: ${Math.round(alt)} FT`, leftX, topY + 22);
    ctx.fillText(`IAS: ${Math.round(spd * 1.94)} KTS`, leftX, topY + 36);
    ctx.fillText(`MACH: ${mach}`, leftX, topY + 50);
    ctx.fillText(
      `HDG: ${Math.round(this.currentHeadingDeg)}°`,
      leftX,
      topY + 64,
    );
    ctx.fillText(`POLARITY: ${this.polarity}`, leftX, topY + 78);
    ctx.fillText(`THREAT: ${state.telemetry.threatTier}`, leftX, topY + 92);
    ctx.fillText(
      `Q-MOMENTUM: ${Math.round(state.telemetry.momentum.quorum)}%`,
      leftX,
      topY + 106,
    );
    ctx.restore();
  }

  private renderTargetBrackets(
    ctx: CanvasRenderingContext2D,
    units: VisualUnit[],
  ): void {
    ctx.save();
    for (const unit of units) {
      if (unit.id !== this.trackedUnitId && unit.side !== "ENEMY") continue;

      const screenX = (unit.x / this.theater.boundsM.w) * this.width;
      const screenY = (unit.y / this.theater.boundsM.h) * this.height;

      const isTarget = unit.id === this.trackedUnitId;
      const bracketSize = isTarget ? 22 : 14;
      const color = isTarget ? "#ff0055" : "rgba(255, 0, 85, 0.55)";

      ctx.strokeStyle = color;
      ctx.lineWidth = isTarget ? 2 : 1;

      // Draw 4 corner brackets
      const b = bracketSize;
      const corner = 5;

      // Top-Left
      ctx.beginPath();
      ctx.moveTo(screenX - b, screenY - b + corner);
      ctx.lineTo(screenX - b, screenY - b);
      ctx.lineTo(screenX - b + corner, screenY - b);
      // Top-Right
      ctx.moveTo(screenX + b - corner, screenY - b);
      ctx.lineTo(screenX + b, screenY - b);
      ctx.lineTo(screenX + b, screenY - b + corner);
      // Bottom-Left
      ctx.moveTo(screenX - b, screenY + b - corner);
      ctx.lineTo(screenX - b, screenY + b);
      ctx.lineTo(screenX - b + corner, screenY + b);
      // Bottom-Right
      ctx.moveTo(screenX + b - corner, screenY + b);
      ctx.lineTo(screenX + b, screenY + b);
      ctx.lineTo(screenX + b, screenY + b - corner);
      ctx.stroke();

      if (isTarget) {
        ctx.fillStyle = "#ff0055";
        ctx.font = "9px monospace";
        ctx.fillText(
          `[TRK-LOCK: ${unit.callsign}]`,
          screenX - b,
          screenY + b + 12,
        );
        const distNm = Math.round(
          Math.hypot(unit.x - 200000, unit.y - 120000) / 1852,
        );
        ctx.fillText(`RNG: ${distNm} NM`, screenX - b, screenY + b + 22);
      }
    }
    ctx.restore();
  }

  private renderThermalPiP(
    ctx: CanvasRenderingContext2D,
    trackedUnit: VisualUnit | undefined,
  ): void {
    const pipW = 240;
    const pipH = 150;
    const pipX = this.width - pipW - 24;
    const pipY = 80;

    ctx.save();
    // Outer border
    ctx.strokeStyle = "rgba(0, 229, 255, 0.6)";
    ctx.lineWidth = 1.5;
    ctx.strokeRect(pipX, pipY, pipW, pipH);

    // Thermal scope viewport
    ctx.fillStyle = this.polarity === "WHITE_HOT" ? "#0f172a" : "#000000";
    ctx.fillRect(pipX, pipY, pipW, pipH);

    // Raster lines in PiP
    ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
    for (let y = pipY; y < pipY + pipH; y += 3) {
      ctx.fillRect(pipX, y, pipW, 1.5);
    }

    const pipCenterX = pipX + pipW / 2;
    const pipCenterY = pipY + pipH / 2;

    // Heat core bloom (Radial Gaussian IR diffusion)
    const isWhiteHot = this.polarity === "WHITE_HOT";
    const coreGrad = ctx.createRadialGradient(
      pipCenterX,
      pipCenterY,
      2,
      pipCenterX,
      pipCenterY,
      32,
    );
    if (isWhiteHot) {
      coreGrad.addColorStop(0, "rgba(255, 255, 255, 0.95)");
      coreGrad.addColorStop(0.3, "rgba(255, 200, 100, 0.6)");
      coreGrad.addColorStop(0.7, "rgba(255, 50, 50, 0.25)");
      coreGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
    } else {
      coreGrad.addColorStop(0, "rgba(0, 0, 0, 0.95)");
      coreGrad.addColorStop(0.4, "rgba(50, 50, 50, 0.5)");
      coreGrad.addColorStop(1, "rgba(255, 255, 255, 0)");
    }
    ctx.fillStyle = coreGrad;
    ctx.beginPath();
    ctx.arc(pipCenterX, pipCenterY, 32, 0, Math.PI * 2);
    ctx.fill();

    // PiP Reticle crosshairs
    ctx.strokeStyle = isWhiteHot ? "#00e5ff" : "#ff0055";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pipCenterX - 18, pipCenterY);
    ctx.lineTo(pipCenterX + 18, pipCenterY);
    ctx.moveTo(pipCenterX, pipCenterY - 18);
    ctx.lineTo(pipCenterX, pipCenterY + 18);
    ctx.stroke();

    // PiP Banner Stamp
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 9px monospace";
    ctx.fillText("THERMAL IR PiP [10x FLIR]", pipX + 8, pipY + 14);
    const targetLabel = trackedUnit ? trackedUnit.callsign : "SEARCHING...";
    ctx.fillStyle = "#ff0055";
    ctx.fillText(`TARGET: ${targetLabel}`, pipX + 8, pipY + pipH - 8);

    ctx.restore();
  }
}
