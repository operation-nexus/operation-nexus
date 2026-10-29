import type { TheaterDefinition } from "../types/theater";
import { createElement } from "../utils/dom";
import { sitrepLines } from "./threat-sitrep";
import type { SitrepTier, SitrepView } from "./threat-sitrep";

// OVERLAY OV-26 (NX-496): the threat sitrep stack, top right under the always-on bar.

const INK = "#020617";
const PANEL = "rgba(9, 18, 33, 0.92)";
const TEXT = "#f8fafc";
const MUTED = "#94a3b8";

// Tone and shape per tier: the shape and the kicker word carry the tier, colour only
// repeats it (OV-3).
const TIER_STYLE: Record<SitrepTier, { tone: string; shape: string }> = {
  LAST_STAND: {
    tone: "#ff0055",
    shape: "polygon(50% 0, 100% 50%, 50% 100%, 0 50%)",
  },
  ALERT: { tone: "#f59e0b", shape: "polygon(50% 0, 100% 100%, 0 100%)" },
  WIN: { tone: "#a3e635", shape: "circle(50%)" },
  INTEL: { tone: "#cbd5e1", shape: "inset(0)" },
  EASE: { tone: MUTED, shape: "polygon(0 0, 100% 0, 50% 100%)" },
};

const NOTCH = 18;
const CARD_CLIP = `polygon(0 0, calc(100% - ${NOTCH}px) 0, 100% ${NOTCH}px, 100% 100%, ${NOTCH}px 100%, 0 calc(100% - ${NOTCH}px))`;

export class ThreatSitrepPanel {
  private root: HTMLElement | null = null;
  private lastSignature = "";

  constructor(private readonly theater: TheaterDefinition) {}

  mount(parent: HTMLElement): void {
    const root = createElement("div", "hud-threat-sitreps");
    root.id = "hud-threat-sitreps";
    root.style.position = "absolute";
    root.style.top = "84px";
    root.style.right = "14px";
    root.style.width = "30%"; // §1a right sidebar share; lines wrap
    root.style.display = "flex";
    root.style.flexDirection = "column";
    root.style.alignItems = "stretch";
    root.style.gap = "10px";
    parent.appendChild(root);
    this.root = root;
  }

  // Rebuilds the DOM only when what is shown changes (frame budget, OV-10).
  render(view: SitrepView): void {
    if (!this.root) return;
    const signature = `${view.shown.map((e) => `${e.key}#${e.event.event_seq}`).join(",")}|${view.hiddenCount}`;
    if (signature === this.lastSignature) return;
    this.lastSignature = signature;

    const cards = view.shown.map((entry) => {
      const lines = sitrepLines(entry, this.theater);
      return this.card(entry.tier, lines.kicker, lines.headline, lines.credit);
    });
    if (view.hiddenCount > 0) {
      const more = createElement("div", "sitrep-more");
      more.style.color = MUTED;
      more.style.fontSize = "28px";
      more.style.alignSelf = "flex-end";
      more.style.background = PANEL;
      more.style.lineHeight = "1.1";
      more.style.padding = "0 8px";
      more.textContent = `+${view.hiddenCount} more`;
      cards.push(more);
    }
    this.root.replaceChildren(...cards);
  }

  private card(
    tier: SitrepTier,
    kicker: string,
    headline: string,
    credit: string | null,
  ): HTMLElement {
    const { tone, shape } = TIER_STYLE[tier];
    const urgent = tier === "LAST_STAND";
    const fg = urgent ? INK : TEXT;

    const card = createElement("div", `sitrep-card sitrep-${tier}`);
    card.style.display = "flex";
    card.style.gap = "16px";
    card.style.alignItems = "flex-start";
    card.style.padding = "12px 22px 14px 16px";
    card.style.background = urgent ? tone : PANEL;
    card.style.borderLeft = `10px solid ${urgent ? INK : tone}`;
    card.style.clipPath = CARD_CLIP;

    const glyph = createElement("div", "sitrep-glyph");
    glyph.style.flex = "0 0 26px";
    glyph.style.height = "26px";
    glyph.style.marginTop = "6px";
    glyph.style.background = urgent ? INK : tone;
    glyph.style.clipPath = shape;

    const body = createElement("div");
    body.style.display = "flex";
    body.style.flexDirection = "column";
    body.style.gap = "4px";
    body.style.minWidth = "0";

    body.appendChild(line("sitrep-kicker", kicker, urgent ? INK : tone, true));
    body.appendChild(line("sitrep-headline", headline, fg, false));
    if (credit !== null) {
      body.appendChild(
        line("sitrep-credit", credit, urgent ? INK : MUTED, false),
      );
    }

    card.appendChild(glyph);
    card.appendChild(body);
    return card;
  }

  dispose(): void {
    if (this.root?.parentElement)
      this.root.parentElement.removeChild(this.root);
    this.root = null;
    this.lastSignature = "";
  }
}

function line(
  className: string,
  text: string,
  color: string,
  kicker: boolean,
): HTMLElement {
  const el = createElement("div", className);
  el.style.color = color;
  el.style.fontSize = "28px"; // OV-1 floor at 1080p
  el.style.lineHeight = "1.2";
  if (kicker) {
    el.style.fontWeight = "bold";
    el.style.letterSpacing = "3px";
  }
  el.textContent = text; // never innerHTML (OV-9)
  return el;
}
