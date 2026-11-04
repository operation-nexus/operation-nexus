// The 1920x1080 stage and its layers (OVERLAY §0.2, §0.6, §0.7). Back to front: map canvases
// (terrain, units, FX), DOM panels, OV-26 stack, toasts, banners. NX-177 fills units/FX, NX-178 the DOM containers.
import "./stage.css";
import { backingSize, fitStage } from "./stage-math";
import { TerrainLayer, type Theater } from "./terrain";

export const HEARTBEAT_CELLS = 4;

export interface Stage {
  stage: HTMLElement;
  /** Everything but banners and heartbeat: this is what dims under a banner (§0.3). */
  world: HTMLElement;
  banners: HTMLElement;
  panels: HTMLElement;
  sitrep: HTMLElement;
  toasts: HTMLElement;
  units: HTMLCanvasElement;
  fx: HTMLCanvasElement;
  terrain: TerrainLayer;
  showTheater: (t: Theater) => void;
  layout: () => void;
  dispose: () => void;
}

function el<K extends keyof HTMLElementTagNameMap>(
  doc: Document,
  tag: K,
  cls: string,
  parent: HTMLElement,
): HTMLElementTagNameMap[K] {
  const e = doc.createElement(tag);
  e.className = cls;
  parent.appendChild(e);
  return e;
}

/** OV-8: a binary counter, one step per second, on the main thread, so a stall freezes it. */
function startHeartbeat(win: Window, cells: HTMLElement[]): () => void {
  let n = 0;
  const id = win.setInterval(() => {
    n = (n + 1) % (1 << cells.length);
    cells.forEach((c, i) => c.classList.toggle("on", ((n >> i) & 1) === 1));
    cells[0]?.parentElement?.setAttribute("data-beat", String(n));
  }, 1000);
  return () => win.clearInterval(id);
}

export function mountStage(root: HTMLElement, win: Window): Stage {
  const doc = win.document;
  root.replaceChildren();
  const stage = el(doc, "div", "nx-stage", root);
  const world = el(doc, "div", "nx-world", stage);
  const map = el(doc, "div", "nx-map", world);
  const terrainCanvas = el(doc, "canvas", "nx-terrain", map);
  const units = el(doc, "canvas", "nx-units", map);
  const fx = el(doc, "canvas", "nx-fx", map);
  const safe = el(doc, "div", "nx-safe", world);
  const panels = el(doc, "div", "nx-panels", safe);
  const sitrep = el(doc, "div", "nx-sitrep", safe);
  const toasts = el(doc, "div", "nx-toasts", safe);
  const banners = el(doc, "div", "nx-banners", stage);
  const beat = el(doc, "div", "nx-heartbeat", stage);
  beat.setAttribute("aria-hidden", "true");
  const cells = Array.from({ length: HEARTBEAT_CELLS }, () =>
    el(doc, "i", "", beat),
  );
  const terrain = new TerrainLayer(terrainCanvas);

  const layout = (): void => {
    const fit = fitStage(win.innerWidth, win.innerHeight);
    stage.style.transform = `translate(${fit.x}px, ${fit.y}px) scale(${fit.scale})`;
    const b = backingSize(fit.scale, win.devicePixelRatio);
    for (const c of [terrainCanvas, units, fx]) {
      if (c.width !== b.w || c.height !== b.h) {
        c.width = b.w;
        c.height = b.h;
      }
    }
    terrain.onResize();
  };
  layout();
  win.addEventListener("resize", layout);
  const stopBeat = startHeartbeat(win, cells);

  return {
    stage,
    world,
    banners,
    panels,
    sitrep,
    toasts,
    units,
    fx,
    terrain,
    showTheater: (t) => void terrain.setTheater(t),
    layout,
    dispose: () => {
      win.removeEventListener("resize", layout);
      stopBeat();
    },
  };
}
