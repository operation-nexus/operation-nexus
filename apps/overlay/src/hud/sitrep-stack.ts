// OV-26 on the live stream: PublicEvent ThreatAdaptation -> ThreatSitrepBoard -> cards.
// Styles are CSS classes (no inline styles, §0.4); text goes through textContent (OV-9).
import type { PublicEvent } from "../contracts/wire/hud";
import type { Event } from "../contracts/events/event";
import { h } from "./topbar";
import type { WingmenFeed } from "./wingmen";
import {
  MAX_SHOWN,
  sitrepLines,
  ThreatSitrepBoard,
  type NameLookup,
  type SitrepTier,
} from "./threat-sitrep";

const GLYPH: Record<SitrepTier, string> = {
  LAST_STAND: "diamond",
  ALERT: "triangle",
  WIN: "circle",
  INTEL: "square",
  EASE: "down",
};

export class SitrepStack {
  private board = new ThreatSitrepBoard();
  private sig = "";
  constructor(
    private doc: Document,
    private root: HTMLElement,
    private callsign: (id: number) => string | undefined,
    private names: () => NameLookup,
    private wing: WingmenFeed | null = null,
  ) {}

  /** Events from a Delta; `tick` is the store tick (game time, so a paused world keeps its cards). */
  ingest(events: readonly PublicEvent[], tick: number): void {
    this.board.ingest(events as readonly Event[], this.callsign);
    this.render(tick);
  }

  render(tick: number): void {
    const view = this.board.view(tick);
    // NX-511: wingmen lines are the lowest priority: they fill only the slots the threat cards leave free
    // and never count in "+N more".
    const wing = this.wing?.view(tick) ?? [];
    const room = Math.max(0, MAX_SHOWN - view.shown.length);
    const wings = wing.slice(0, room);
    const hidden = view.hiddenCount; // "+N more" counts threat cards only: a hidden wing line is not a hidden threat
    const sig = `${view.shown.map((e) => `${e.key}#${e.event.event_seq}`).join(",")}|${wings.map((w) => w.key).join(",")}|${hidden}`;
    if (sig === this.sig) return;
    this.sig = sig;
    const d = this.doc;
    const cards = view.shown.map((entry) => {
      const l = sitrepLines(entry, this.names());
      const card = h(d, "div", `nx-card nx-tier-${entry.tier}`);
      h(d, "i", `nx-shape ${GLYPH[entry.tier]}`, card).setAttribute(
        "aria-hidden",
        "true",
      );
      const body = h(d, "div", "nx-card-body", card);
      h(d, "div", "nx-kicker", body, l.kicker);
      h(d, "div", "nx-line", body, l.headline);
      if (l.credit !== null) h(d, "div", "nx-line nx-credit", body, l.credit);
      return card;
    });
    for (const w of wings) {
      const card = h(d, "div", "nx-card nx-tier-WING");
      h(d, "i", "nx-shape circle", card).setAttribute("aria-hidden", "true");
      const body = h(d, "div", "nx-card-body", card);
      h(d, "div", "nx-line", body, w.text);
      cards.push(card);
    }
    if (hidden > 0)
      cards.push(h(d, "div", "nx-more", undefined, `+${hidden} more`));
    this.root.replaceChildren(...cards);
  }
}
