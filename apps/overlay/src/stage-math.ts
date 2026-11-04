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
