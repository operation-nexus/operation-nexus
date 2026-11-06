// OV-26 on the live stream: PublicEvent ThreatAdaptation -> ThreatSitrepBoard -> cards.
// Styles are CSS classes (no inline styles, §0.4); text goes through textContent (OV-9).
import type { PublicEvent } from "../contracts/wire/hud";
import type { Event } from "../contracts/events/event";
import type { FinalHoursCard } from "./final-hours";
import { h } from "./topbar";
import {
  sitrepLines,
  ThreatSitrepBoard,
  MAX_SHOWN,
  type NameLookup,
  type SitrepEntry,
  type SitrepTier,
  type SitrepView,
} from "./threat-sitrep";

const GLYPH: Record<SitrepTier, string> = {
  LAST_STAND: "diamond",
  ALERT: "triangle",
  WIN: "circle",
  INTEL: "square",
  EASE: "down",
};

export type StackItem =
  | { kind: "event"; entry: SitrepEntry }
  | { kind: "final"; card: FinalHoursCard };

/** The OV-26 priority with the FINAL HOURS card: LAST STAND, FINAL HOURS, ALERT, WIN, INTEL, EASING (§0.11). */
export function placeFinalHours(
  view: SitrepView,
  card: FinalHoursCard | null,
): { shown: StackItem[]; hiddenCount: number } {
  const items: StackItem[] = view.shown.map((entry) => ({
    kind: "event",
    entry,
  }));
  if (card) {
    const at = items.findIndex(
      (i) => i.kind === "event" && i.entry.tier !== "LAST_STAND",
    );
    items.splice(at < 0 ? items.length : at, 0, { kind: "final", card });
  }
  return {
    shown: items.slice(0, MAX_SHOWN),
    hiddenCount: view.hiddenCount + Math.max(0, items.length - MAX_SHOWN),
  };
}

export class SitrepStack {
  private board = new ThreatSitrepBoard();
  private sig = "";
  constructor(
    private doc: Document,
    private root: HTMLElement,
    private callsign: (id: number) => string | undefined,
    private names: () => NameLookup,
    private finalHours: (tick: number) => FinalHoursCard | null = () => null,
  ) {}

  /** Events from a Delta; `tick` is the store tick (game time, so a paused world keeps its cards). */
  ingest(events: readonly PublicEvent[], tick: number): void {
    this.board.ingest(events as readonly Event[], this.callsign);
    this.render(tick);
  }

  render(tick: number): void {
    const view = placeFinalHours(this.board.view(tick), this.finalHours(tick));
    const sig = `${view.shown.map((i) => (i.kind === "final" ? `FH${i.card.phase}:${i.card.kicker}:${i.card.lines.join("|")}` : `${i.entry.key}#${i.entry.event.event_seq}`)).join(",")}|${view.hiddenCount}`;
    if (sig === this.sig) return;
    this.sig = sig;
    const d = this.doc;
    const cards = view.shown.map((item) => {
      if (item.kind === "final") {
        const card = h(d, "div", "nx-card nx-tier-FINAL_HOURS");
        h(d, "i", "nx-shape hourglass", card).setAttribute(
          "aria-hidden",
          "true",
        );
        const body = h(d, "div", "nx-card-body", card);
        h(d, "div", "nx-kicker", body, item.card.kicker);
        for (const line of item.card.lines) h(d, "div", "nx-line", body, line);
        return card;
      }
      const entry = item.entry;
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
    if (view.hiddenCount > 0)
      cards.push(
        h(d, "div", "nx-more", undefined, `+${view.hiddenCount} more`),
      );
    this.root.replaceChildren(...cards);
  }
}
