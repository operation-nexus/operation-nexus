// Units, fog blobs and last-known marks (OVERLAY §0.10, NX-177; OV-2): drawn every frame on the units canvas.
// Shapes, sizes, alphas and the fog look are PROPOSED until the brand guide (NX-274). No labels, no flight
// symbols in this slice (OV-4 narrowed); the only text is a last-known mark's age.
import type {
  BlobView,
  EntityView,
  LastKnownView,
} from "./contracts/wire/snapshot";
import type { Pose } from "./interp";
import { COL, FONT } from "./nodes";
import type { MapFrame } from "./stage-math";

type Kind = EntityView["unit_kind"];
type Pt = [number, number];
type Side = EntityView["side"];

const pts = (n: number[]): Pt[] =>
  Array.from({ length: n.length / 2 }, (_, i) => [
    n[2 * i] ?? 0,
    n[2 * i + 1] ?? 0,
  ]);
const ARROW = pts([0, -1.2, 0.8, 0.9, 0, 0.45, -0.8, 0.9]);
const DIAMOND = pts([0, -1.1, 0.8, 0, 0, 1.1, -0.8, 0]);
const BOX = pts([
  -0.5, -1, 0.5, -1, 0.8, -0.7, 0.8, 0.7, 0.5, 1, -0.5, 1, -0.8, 0.7, -0.8,
  -0.7,
]);
const HEX = pts([0, -1, 0.87, -0.5, 0.87, 0.5, 0, 1, -0.87, 0.5, -0.87, -0.5]);
const SHIELD = pts([0, -1.1, 0.9, -0.3, 0.6, 0.9, -0.6, 0.9, -0.9, -0.3]);
const OCT = pts([
  -0.4, -1, 0.4, -1, 1, -0.4, 1, 0.4, 0.4, 1, -0.4, 1, -1, 0.4, -1, -0.4,
]);
const TRI = pts([0, -1.1, 1, 0.8, -1, 0.8]);

/** Silhouette and radius in stage px, by unit_kind (the Quorum arrowhead / diamond / chamfered box language of
 *  prototype style 3; the enemy gets the same silhouette, jagged). */
export const SHAPE: Record<Kind, { pts: Pt[]; r: number }> = {
  STRIKE_FIGHTER: { pts: ARROW, r: 15 },
  ENEMY_FIGHTER: { pts: ARROW, r: 15 },
  ENEMY_STRIKE_FIGHTER: { pts: ARROW, r: 15 },
  RECON_UAV: { pts: DIAMOND, r: 13 },
  ENEMY_RECON_UAV: { pts: DIAMOND, r: 13 },
  LOGI_TRUCK: { pts: BOX, r: 14 },
  ENEMY_CONVOY: { pts: BOX, r: 15 },
  GARRISON_INFANTRY: { pts: HEX, r: 12 },
  ENEMY_ARMOR: { pts: SHIELD, r: 15 },
  RADAR_SITE: { pts: OCT, r: 16 },
  AIR_DEFENSE_SITE: { pts: TRI, r: 16 },
};

/** Enemy outline: every vertex pushed out, a notch pulled in between each pair (spiky jets, sawtooth trucks). */
const jag = (p: Pt[]): Pt[] =>
  p.flatMap((a, i) => {
    const b = p[(i + 1) % p.length] ?? a;
    return [
      [a[0] * 1.15, a[1] * 1.15],
      [(a[0] + b[0]) * 0.3, (a[1] + b[1]) * 0.3],
    ];
  });
const OUTLINE = (k: Kind, s: Side): Pt[] =>
  s === "ENEMY" ? JAGGED[k] : SHAPE[k].pts;
const JAGGED = Object.fromEntries(
  Object.entries(SHAPE).map(([k, v]) => [k, jag(v.pts)]),
) as Record<Kind, Pt[]>;

/** Fill opacity by damage_state; the outline is always drawn, DISABLED is dashed, so it never rests on colour. */
export const FILL: Record<EntityView["damage_state"], number> = {
  HEALTHY: 1,
  DAMAGED: 0.6,
  MISSION_KILL: 0.3,
  DISABLED: 0,
};
export const GARRISON_ALPHA = 0.55;
export const LAST_KNOWN_ALPHA = 0.45;
export const BLOB_R = { S: 28, M: 44, L: 64 } as const;

const ok = (p: { x_m: number; y_m: number } | undefined): boolean =>
  Number.isFinite(p?.x_m) && Number.isFinite(p?.y_m);

function shape(
  ctx: CanvasRenderingContext2D,
  kind: Kind,
  side: Side,
  [x, y]: Pt,
  heading: number | null,
  state: EntityView["damage_state"] | null,
  alpha: number,
): void {
  const sh = SHAPE[kind];
  if (sh === undefined) return;
  ctx.save();
  ctx.translate(x, y);
  if (heading !== null) ctx.rotate((heading * Math.PI) / 180); // 0 = north (up), clockwise
  ctx.beginPath();
  OUTLINE(kind, side).forEach(([px, py], i) =>
    i === 0
      ? ctx.moveTo(px * sh.r, py * sh.r)
      : ctx.lineTo(px * sh.r, py * sh.r),
  );
  ctx.closePath();
  ctx.globalAlpha = alpha;
  if (state !== null) {
    ctx.fillStyle = COL.ink;
    ctx.fill();
    ctx.globalAlpha = alpha * FILL[state];
    ctx.fillStyle = COL[side];
    ctx.fill();
    ctx.globalAlpha = alpha;
  }
  ctx.strokeStyle = COL[side];
  ctx.lineWidth = 2.5;
  ctx.lineJoin = "miter";
  ctx.setLineDash(state === null || state === "DISABLED" ? [5, 4] : []);
  ctx.stroke();
  ctx.restore();
}

export interface Scene {
  entities: ReadonlyMap<number, EntityView>;
  blobs: readonly BlobView[];
  lastKnown: readonly LastKnownView[];
  pose: (id: number) => Pose | undefined;
  /** Seconds since a last-known entry was seen (server ticks over the tick rate). */
  ageSec: (seenTick: number) => number;
}

export const ageText = (s: number): string =>
  s < 60 ? `${Math.floor(s)}s` : `${Math.floor(s / 60)}m`;

/** Fog first (under), then last-known, then the live units. */
export function drawWorld(
  ctx: CanvasRenderingContext2D,
  f: MapFrame,
  s: Scene,
): void {
  for (const b of s.blobs) {
    const r = BLOB_R[b?.size];
    if (r === undefined || !ok(b.cell_center)) continue;
    const [x, y] = f.at(b.cell_center);
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, COL.ENEMY + "66");
    g.addColorStop(1, COL.ENEMY + "00");
    ctx.fillStyle = g;
    ctx.fillRect(x - r, y - r, 2 * r, 2 * r);
  }
  ctx.font = FONT;
  ctx.textAlign = "center";
  for (const k of s.lastKnown) {
    if (!ok(k.pos) || SHAPE[k.unit_kind] === undefined) continue;
    const p = f.at(k.pos);
    shape(ctx, k.unit_kind, "ENEMY", p, k.heading_deg, null, LAST_KNOWN_ALPHA);
    ctx.globalAlpha = LAST_KNOWN_ALPHA;
    ctx.fillStyle = COL.ENEMY;
    ctx.fillText(
      ageText(s.ageSec(k.seen_tick)),
      p[0],
      p[1] + SHAPE[k.unit_kind].r + 20,
    );
    ctx.globalAlpha = 1;
  }
  for (const e of s.entities.values()) {
    const p = s.pose(e.entity_id);
    if (p === undefined) continue;
    shape(
      ctx,
      e.unit_kind,
      e.side,
      f.at(p),
      e.domain === "STATIC" ? null : p.heading_deg,
      e.damage_state,
      e.owner_kind === "AI_GARRISON" ? GARRISON_ALPHA : 1,
    );
  }
}
