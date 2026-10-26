import type {
  IRenderEngine,
  RenderEngineOptions,
  RenderFrameState,
  CameraTarget,
  VisualEffect,
} from "../../types/render";
import type { TheaterDefinition } from "../../types/theater";
import type { VisualUnit } from "../../types/unit";
import { STRAIT_1_THEATER, STRAIT_CHANNEL_BOUNDS } from "../../theater/strait1";
import {
  drawUnitVectorShape,
  FACTION_TOKENS,
} from "../../symbology/dual-encoding";
import { createCanvasElement } from "../../utils/dom";

export class CrtVectorEngine implements IRenderEngine {
  readonly id = "crt";
  readonly name = "2D CRT Vector Phosphor";

  private container: HTMLElement | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private ctx: CanvasRenderingContext2D | null = null;
  private theater: TheaterDefinition = STRAIT_1_THEATER;
  private width = 1280;
  private height = 720;
  private pixelRatio = 1;
  private radarAngleRad = 0;
  private scanlineOffset = 0;
  private effects: VisualEffect[] = [];
  private selectedUnitId: number | null = null;

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
      this.canvas = createCanvasElement(this.container, "crt-vector-canvas");
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
      if (this.ctx) {
        this.ctx.imageSmoothingEnabled = true;
      }
    }
  }

  updateTheaterMap(theater: TheaterDefinition): void {
    this.theater = theater;
  }

  triggerEffect(effect: VisualEffect): void {
    this.effects.push(effect);
    if (this.effects.length > 30) {
      this.effects.shift();
    }
  }

  setCameraTarget(target: CameraTarget): void {
    if (target.unitId !== undefined) {
      this.selectedUnitId = target.unitId;
    }
  }

  renderFrame(state: RenderFrameState): void {
    if (!this.ctx || !this.canvas) return;
    const ctx = this.ctx;

    // Advance oscilloscope radar sweep angle
    this.radarAngleRad = (this.radarAngleRad + 0.035) % (Math.PI * 2);
    this.scanlineOffset = (this.scanlineOffset + 1) % 4;
    this.selectedUnitId = state.selectedUnitId ?? this.selectedUnitId;

    ctx.save();
    ctx.scale(this.pixelRatio, this.pixelRatio);

    // 1. Clear background to dark void
    ctx.fillStyle = FACTION_TOKENS.VOID_BACKGROUND;
    ctx.fillRect(0, 0, this.width, this.height);

    // 2. Render Theater Geometry (Coordinate projection: Sim meters -> Screen pixels)
    this.renderTheaterGrid(ctx);
    this.renderWaterChannel(ctx);
    this.renderSectors(ctx);
    this.renderSupplyCorridors(ctx);
    this.renderNodes(ctx);

    // 3. Render Units with Dual-Encoding (OV-2 / OV-3) and Speed Trails
    this.renderUnits(ctx, state.units);

    // 4. Render Active Ephemeral Effects (Missile arcs, kinetic bursts)
    this.renderEffects(ctx, state.effects);

    // 5. Render Oscilloscope Radar Sweep (CRT Vector aesthetic)
    this.renderRadarSweep(ctx);

    // 6. Render CRT Phosphor Scanline Overlay
    this.renderScanlines(ctx);

    ctx.restore();
  }

  dispose(): void {
    if (this.canvas && this.canvas.parentElement) {
      this.canvas.parentElement.removeChild(this.canvas);
    }
    this.canvas = null;
    this.ctx = null;
    this.container = null;
    this.effects = [];
  }

  // --- Projection Helpers ---
  private projectX(xMeters: number): number {
    return (xMeters / this.theater.boundsM.w) * this.width;
  }

  private projectY(yMeters: number): number {
    return (yMeters / this.theater.boundsM.h) * this.height;
  }

  private renderTheaterGrid(ctx: CanvasRenderingContext2D): void {
    ctx.save();
    ctx.strokeStyle = "rgba(30, 58, 95, 0.28)";
    ctx.lineWidth = 1;

    // Tactical MGRS grid lines every 50km
    for (let x = 50000; x < this.theater.boundsM.w; x += 50000) {
      const sx = this.projectX(x);
      ctx.beginPath();
      ctx.moveTo(sx, 0);
      ctx.lineTo(sx, this.height);
      ctx.stroke();
    }

    for (let y = 50000; y < this.theater.boundsM.h; y += 50000) {
      const sy = this.projectY(y);
      ctx.beginPath();
      ctx.moveTo(0, sy);
      ctx.lineTo(this.width, sy);
      ctx.stroke();
    }
    ctx.restore();
  }

  private renderWaterChannel(ctx: CanvasRenderingContext2D): void {
    const x1 = this.projectX(STRAIT_CHANNEL_BOUNDS.westBankX);
    const x2 = this.projectX(STRAIT_CHANNEL_BOUNDS.eastBankX);
    const channelW = x2 - x1;

    ctx.save();
    // Recessed water trench fill
    ctx.fillStyle = "rgba(4, 18, 36, 0.85)";
    ctx.fillRect(x1, 0, channelW, this.height);

    // Shoreline banks
    ctx.strokeStyle = "rgba(0, 229, 255, 0.35)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(x1, 0);
    ctx.lineTo(x1, this.height);
    ctx.moveTo(x2, 0);
    ctx.lineTo(x2, this.height);
    ctx.stroke();

    // Water channel label
    ctx.fillStyle = "rgba(0, 229, 255, 0.25)";
    ctx.font = "9px monospace";
    ctx.fillText("STRAIT-1 WATER CHANNEL (-3.5M)", x1 + 6, 20);
    ctx.restore();
  }

  private renderSectors(ctx: CanvasRenderingContext2D): void {
    ctx.save();
    ctx.strokeStyle = "rgba(56, 189, 248, 0.15)";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);

    for (const sec of this.theater.sectors) {
      const p0 = sec.polygon[0];
      const p2 = sec.polygon[2];
      if (p0 && p2) {
        const yLine = this.projectY(p2[1]);
        ctx.beginPath();
        ctx.moveTo(0, yLine);
        ctx.lineTo(this.width, yLine);
        ctx.stroke();

        ctx.fillStyle = "rgba(148, 163, 184, 0.4)";
        ctx.font = "10px monospace";
        ctx.fillText(
          `SECTOR: ${sec.name.toUpperCase()}`,
          12,
          this.projectY(p0[1]) + 16,
        );
      }
    }
    ctx.restore();
  }

  private renderSupplyCorridors(ctx: CanvasRenderingContext2D): void {
    ctx.save();
    ctx.lineWidth = 2;

    const nodeMap = new Map(this.theater.nodes.map((n) => [n.id, n]));

    for (const edge of this.theater.edges) {
      const na = nodeMap.get(edge.a);
      const nb = nodeMap.get(edge.b);
      if (!na || !nb) continue;

      const ax = this.projectX(na.pos[0]);
      const ay = this.projectY(na.pos[1]);
      const bx = this.projectX(nb.pos[0]);
      const by = this.projectY(nb.pos[1]);

      if (edge.bridge) {
        // Elevated Highway Bridge (North or South Bridge)
        ctx.strokeStyle = "rgba(245, 158, 11, 0.75)";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(bx, by);
        ctx.stroke();

        // Bridge truss cross markers
        const midX = (ax + bx) / 2;
        const midY = (ay + by) / 2;
        ctx.fillStyle = "#f59e0b";
        ctx.font = "8px monospace";
        ctx.fillText(`[BRIDGE +14M]`, midX - 32, midY - 6);
      } else {
        // Standard Road Corridor
        ctx.strokeStyle = "rgba(30, 58, 95, 0.65)";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(bx, by);
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  private renderNodes(ctx: CanvasRenderingContext2D): void {
    ctx.save();
    for (const node of this.theater.nodes) {
      const nx = this.projectX(node.pos[0]);
      const ny = this.projectY(node.pos[1]);

      const isCoalition = node.startOwner === "COALITION";
      const isEnemy = node.startOwner === "ENEMY";
      const color = isCoalition
        ? FACTION_TOKENS.QUORUM_CYAN
        : isEnemy
          ? FACTION_TOKENS.STATIC_MAGENTA
          : FACTION_TOKENS.NEUTRAL_SLATE;

      ctx.fillStyle = color;
      ctx.strokeStyle = color;
      ctx.shadowColor = color;
      ctx.shadowBlur = 6;

      ctx.beginPath();
      if (node.kind === "AIRBASE" || node.kind === "HQ") {
        ctx.arc(nx, ny, 6, 0, Math.PI * 2);
      } else if (node.kind === "BRIDGE") {
        ctx.rect(nx - 4, ny - 4, 8, 8);
      } else {
        ctx.arc(nx, ny, 4, 0, Math.PI * 2);
      }
      ctx.fill();

      // Node label
      ctx.fillStyle = "#f8fafc";
      ctx.font = "9px monospace";
      ctx.shadowBlur = 0;
      ctx.fillText(node.name.toUpperCase(), nx + 8, ny + 3);
    }
    ctx.restore();
  }

  private renderUnits(
    ctx: CanvasRenderingContext2D,
    unitsData: VisualUnit[] | Map<number, VisualUnit>,
  ): void {
    const units = Array.isArray(unitsData)
      ? unitsData
      : Array.from(unitsData.values());

    for (const unit of units) {
      const ux = this.projectX(unit.x);
      const uy = this.projectY(unit.y);

      // 1. Render Phosphor Speed Trails
      if (unit.trailHistory && unit.trailHistory.length > 0) {
        ctx.save();
        ctx.lineWidth = 1.5;
        for (let i = 0; i < unit.trailHistory.length - 1; i++) {
          const ptA = unit.trailHistory[i];
          const ptB = unit.trailHistory[i + 1];
          if (!ptA || !ptB) continue;
          const ax = this.projectX(ptA.x);
          const ay = this.projectY(ptA.y);
          const bx = this.projectX(ptB.x);
          const by = this.projectY(ptB.y);

          const trailColor =
            unit.side === "COALITION"
              ? `rgba(0, 229, 255, ${ptA.alpha * 0.4})`
              : `rgba(255, 0, 85, ${ptA.alpha * 0.4})`;

          ctx.strokeStyle = trailColor;
          ctx.beginPath();
          ctx.moveTo(ax, ay);
          ctx.lineTo(bx, by);
          ctx.stroke();
        }
        ctx.restore();
      }

      // 2. Render Directional Velocity Vector Leader
      if (unit.speedMps && unit.speedMps > 0) {
        const angleRad = ((unit.headingDeg - 90) * Math.PI) / 180;
        const leaderLen = Math.min(24, Math.max(8, unit.speedMps * 0.1));
        const lx = ux + Math.cos(angleRad) * leaderLen;
        const ly = uy + Math.sin(angleRad) * leaderLen;

        ctx.save();
        ctx.strokeStyle =
          unit.side === "COALITION"
            ? "rgba(0, 229, 255, 0.6)"
            : "rgba(255, 0, 85, 0.6)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(ux, uy);
        ctx.lineTo(lx, ly);
        ctx.stroke();
        ctx.restore();
      }

      // 3. Render Dual-Encoded Shape (OV-2 / OV-3)
      ctx.save();
      ctx.translate(ux, uy);
      ctx.rotate((unit.headingDeg * Math.PI) / 180);
      drawUnitVectorShape(ctx, unit, 8);
      ctx.restore();

      // 4. OV-4 Label Gating: Only render callsigns for selected unit or convoy leader
      const isSelected = unit.id === this.selectedUnitId || unit.isSelected;
      if (isSelected || unit.isConvoyLeader) {
        ctx.save();
        ctx.fillStyle =
          unit.side === "COALITION"
            ? FACTION_TOKENS.QUORUM_CYAN
            : FACTION_TOKENS.STATIC_MAGENTA;
        ctx.font = "bold 9px monospace";
        const label = unit.convoyFollowers
          ? `${unit.callsign} [TRUCK] +${unit.convoyFollowers}`
          : unit.callsign;
        ctx.fillText(label, ux + 10, uy - 4);
        ctx.restore();
      }
    }
  }

  private renderEffects(
    ctx: CanvasRenderingContext2D,
    extraEffects?: VisualEffect[],
  ): void {
    const allEffects = [...this.effects, ...(extraEffects ?? [])];

    for (const fx of allEffects) {
      if (fx.type === "MISSILE_TRAJECTORY") {
        const sx = this.projectX(fx.sourcePos[0]);
        const sy = this.projectY(fx.sourcePos[1]);
        const tx = this.projectX(fx.targetPos[0]);
        const ty = this.projectY(fx.targetPos[1]);
        const currX = sx + (tx - sx) * fx.progress;
        const currY = sy + (ty - sy) * fx.progress;

        ctx.save();
        ctx.strokeStyle = fx.color || "#ff0055";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(sx, sy);
        ctx.lineTo(currX, currY);
        ctx.stroke();

        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(currX, currY, 2.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      } else if (fx.type === "KINETIC_BURST") {
        const bx = this.projectX(fx.pos[0]);
        const by = this.projectY(fx.pos[1]);
        const radius = (fx.radiusMeters / 1000) * (this.width / 400);

        ctx.save();
        ctx.strokeStyle = fx.color || "#00e5ff";
        ctx.lineWidth = 2;
        ctx.globalAlpha = Math.max(0, 1 - fx.progress);
        ctx.beginPath();
        ctx.arc(bx, by, Math.max(4, radius * fx.progress), 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      }
    }
  }

  private renderRadarSweep(ctx: CanvasRenderingContext2D): void {
    const sweepRadius = Math.max(this.width, this.height);
    const centerX = this.width / 2;
    const centerY = this.height / 2;

    ctx.save();
    const grad = ctx.createRadialGradient(
      centerX,
      centerY,
      0,
      centerX,
      centerY,
      sweepRadius,
    );
    grad.addColorStop(0, "rgba(0, 229, 255, 0.08)");
    grad.addColorStop(1, "rgba(0, 229, 255, 0.0)");

    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.arc(
      centerX,
      centerY,
      sweepRadius,
      this.radarAngleRad - 0.25,
      this.radarAngleRad,
    );
    ctx.closePath();
    ctx.fill();

    // Leading sweep beam
    ctx.strokeStyle = "rgba(0, 229, 255, 0.25)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.lineTo(
      centerX + Math.cos(this.radarAngleRad) * sweepRadius,
      centerY + Math.sin(this.radarAngleRad) * sweepRadius,
    );
    ctx.stroke();
    ctx.restore();
  }

  private renderScanlines(ctx: CanvasRenderingContext2D): void {
    ctx.save();
    ctx.fillStyle = "rgba(0, 0, 0, 0.22)";
    for (let y = this.scanlineOffset; y < this.height; y += 4) {
      ctx.fillRect(0, y, this.width, 1.5);
    }

    // Subtle edge vignette
    const vignette = ctx.createRadialGradient(
      this.width / 2,
      this.height / 2,
      this.width * 0.35,
      this.width / 2,
      this.height / 2,
      this.width * 0.75,
    );
    vignette.addColorStop(0, "rgba(0,0,0,0)");
    vignette.addColorStop(1, "rgba(2, 6, 15, 0.65)");
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, this.width, this.height);
    ctx.restore();
  }
}
