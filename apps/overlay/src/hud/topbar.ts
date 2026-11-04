// Always-on top bar (OVERLAY §0.5, OV-12) and the ticker strip. Every value goes through
// textContent (WP-6, OV-9); a null or missing field shows DASH, never a number (DI-1).
import type { Hud } from "../contracts/wire/snapshot";
import type { HudClock } from "./clock";
import { DASH, t, tierText } from "./strings";

export const SEGMENTS = 10;

export function h(
  doc: Document,
  tag: string,
  cls: string,
  parent?: HTMLElement,
  text?: string,
): HTMLElement {
  const e = doc.createElement(tag);
  e.className = cls;
  if (text !== undefined) e.textContent = text;
  parent?.appendChild(e);
  return e;
}

export const setText = (e: HTMLElement, s: string): void => {
  if (e.textContent !== s) e.textContent = s;
};

const isNum = (n: unknown): n is number =>
  typeof n === "number" && Number.isFinite(n);

/** "N of M", or DASH when either is missing or there is nothing to hold (M = 0, campaign layer off). */
export function nodesText(hud: Hud | null): string {
  const n = hud?.nodes_held;
  const m = hud?.nodes_total;
  return isNum(n) && isNum(m) && m > 0 ? `${n} of ${m}` : DASH;
}

export function litSegments(pct: number | null | undefined): number {
  return isNum(pct)
    ? Math.max(0, Math.min(SEGMENTS, Math.round(pct / (100 / SEGMENTS))))
    : 0;
}

export class TopBar {
  private segs: HTMLElement[] = [];
  private v: Record<
    "pct" | "nodes" | "obj" | "timer" | "tier" | "war",
    HTMLElement
  >;
  private bar: HTMLElement;
  private objCell: HTMLElement;
  private glyph: HTMLElement;
  private tick: HTMLElement;

  constructor(doc: Document, parent: HTMLElement) {
    const bar = (this.bar = h(doc, "div", "nx-topbar", parent));
    const cell = (cls: string, label: Parameters<typeof t>[0]): HTMLElement => {
      const c = h(doc, "div", `nx-cell ${cls}`, bar);
      h(doc, "div", "nx-label", c, t(label));
      return c;
    };
    const sig = cell("nx-signal", "hud.signal");
    const row = h(doc, "div", "nx-row", sig);
    const meter = h(doc, "div", "nx-meter", row);
    meter.setAttribute("aria-hidden", "true");
    for (let i = 0; i < SEGMENTS; i++) this.segs.push(h(doc, "i", "", meter));
    const pct = h(doc, "span", "nx-val", row, DASH);
    const nodes = h(doc, "div", "nx-val", cell("nx-nodes", "hud.nodes"), DASH);
    this.objCell = cell("nx-obj", "hud.objective");
    const orow = h(doc, "div", "nx-row", this.objCell);
    const obj = h(doc, "span", "nx-val nx-name", orow, DASH);
    const timer = h(doc, "span", "nx-val", orow, DASH);
    const trow = h(doc, "div", "nx-row", cell("nx-threat", "hud.threat"));
    this.glyph = h(doc, "i", "nx-glyph", trow);
    this.glyph.setAttribute("aria-hidden", "true");
    const tier = h(doc, "span", "nx-val", trow, DASH);
    const war = h(doc, "div", "nx-val", cell("nx-war", "hud.war"), DASH);
    this.v = { pct, nodes, obj, timer, tier, war };

    const strip = h(doc, "div", "nx-ticker", parent);
    h(doc, "span", "nx-howto", strip, t("hud.howto"));
    this.tick = h(doc, "span", "nx-ticker-item", strip);
  }

  render(hud: Hud | null, clock: HudClock): void {
    const lit = litSegments(hud?.momentum_pct);
    this.segs.forEach((s, i) => s.classList.toggle("on", i < lit));
    const pct = hud?.momentum_pct;
    setText(this.v.pct, isNum(pct) ? `${Math.round(pct)}%` : DASH);
    setText(this.v.nodes, nodesText(hud));
    // OFF hides the objective and its timer; before the first Hud the mode is unknown, so the field shows DASH.
    const off = hud?.objective_mode === "OFF";
    this.objCell.hidden = off;
    this.bar.classList.toggle("no-obj", off); // the grid drops the column
    setText(this.v.obj, hud?.objective?.name ?? DASH);
    setText(this.v.timer, clock.objective());
    const tier = hud?.threat_tier;
    setText(this.v.tier, tier ? tierText(tier) : DASH);
    this.glyph.setAttribute("data-tier", tier ?? "");
    setText(this.v.war, clock.war());
    // Newest item by tick; the contract does not fix the array order.
    const items = hud?.ticker ?? [];
    const last = items.reduce<(typeof items)[number] | null>(
      (a, x) => (a === null || x.tick >= a.tick ? x : a),
      null,
    );
    setText(this.tick, last?.text ?? "");
  }
}
