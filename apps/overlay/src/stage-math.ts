// Stage geometry (OVERLAY §0.7): a fixed 1920x1080 stage, CSS-scaled and centered in the browser source.
export const STAGE_W = 1920;
export const STAGE_H = 1080;
export const DPR_CAP = 2; // PROPOSED
export const SAFE_FRAC = 0.05; // PROPOSED, each edge

export interface Fit {
  scale: number;
  x: number;
  y: number;
}

/** Largest uniform scale that fits the viewport, centered (letterboxed, never cropped). */
export function fitStage(vw: number, vh: number): Fit {
  const scale = Math.min(vw / STAGE_W, vh / STAGE_H);
  return {
    scale,
    x: (vw - STAGE_W * scale) / 2,
    y: (vh - STAGE_H * scale) / 2,
  };
}

/** Canvas backing store = on-screen CSS size x DPR, DPR capped (an invalid DPR counts as 1). */
export function backingSize(
  scale: number,
  dpr: number,
): { w: number; h: number } {
  const d = Number.isFinite(dpr) && dpr > 0 ? Math.min(dpr, DPR_CAP) : 1;
  return {
    w: Math.max(1, Math.round(STAGE_W * scale * d)),
    h: Math.max(1, Math.round(STAGE_H * scale * d)),
  };
}

/** Stage-pixel rectangle inside the safe area. */
export function safeRect(): { x: number; y: number; w: number; h: number } {
  const x = STAGE_W * SAFE_FRAC;
  const y = STAGE_H * SAFE_FRAC;
  return { x, y, w: STAGE_W - 2 * x, h: STAGE_H - 2 * y };
}

/** Stage-pixel rectangle the map is framed in: inside the safe area, under the top bar (116 px in the
 *  prototype's HUD region) and above the ticker (OVERLAY §1, §0.10). PROPOSED until NX-274. */
export const MAP_RECT = { x: 96, y: 120, w: 1728, h: 880 };

export interface MapFrame {
  /** Stage px per metre. */
  k: number;
  at: (p: { x_m: number; y_m: number }) => [number, number];
}

/** The one projector for every map layer (OVERLAY §0.10, Q-UX-18/19): `bounds_m` fits the map rectangle,
 *  contain (never crop), anchored top-left; +y is north, so the screen y flips. */
export function mapFrame(
  bounds: { w: number; h: number },
  r: { x: number; y: number; w: number; h: number } = MAP_RECT,
): MapFrame {
  const k = Math.min(r.w / bounds.w, r.h / bounds.h);
  return {
    k,
    at: (p) => [r.x + p.x_m * k, r.y + (bounds.h - p.y_m) * k],
  };
}
