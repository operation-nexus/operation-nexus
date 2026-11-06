import { describe, expect, it } from "vitest";
import type { Event, ThreatAdaptation } from "../contracts/events/event";
import type { Delta } from "../contracts/wire/delta";
import type { Hud, Snapshot } from "../contracts/wire/snapshot";
import { HudClock } from "../hud/clock";
import {
  BANNER_MS,
  CARD_TTL_TICKS,
  FinalHours,
  HYSTERESIS_TICKS,
  THRESHOLD_TICKS,
  phaseOf,
  scoreOf,
} from "../hud/final-hours";
import { mountHud } from "../hud/mount";
import { SitrepStack, placeFinalHours } from "../hud/sitrep-stack";
import { ThreatSitrepBoard } from "../hud/threat-sitrep";
import { TopBar } from "../hud/topbar";
import { WireStore } from "../net/store";

// NX-515, OVERLAY §0.11: final-hours phases, push, banner and OV-26 card (FH-T1 to FH-T9).

const [T1, T2, T3] = THRESHOLD_TICKS;
const LIMIT = 800_000;

type Score = { coalition: number; enemy: number } | null;
function hud(
  remaining: number,
  over: {
    paused?: boolean;
    score?: Score;
    nodes_total?: number;
    limit?: number | null;
  } = {},
): Hud {
  const limit = over.limit === undefined ? LIMIT : over.limit;
  return {
    type: "Hud",
    v: "1",
    momentum_pct: 50,
    momentum_breakdown: null,
    objective_mode: "OFF",
    objective: null,
    threat_tier: "ALPHA",
    nodes_held: 3,
    nodes_total: over.nodes_total ?? 8,
    campaign_clock: {
      elapsed_ticks: limit === null ? 0 : limit - remaining,
      limit_ticks: limit,
      paused: over.paused ?? false,
      pause_reason: over.paused ? "STAFF" : null,
    },
    time_limit_score:
      over.score === undefined ? { coalition: 40, enemy: 35 } : over.score,
    ticker: [],
    panels: {
      campaign_status: { nodes_held: {}, result: null },
      tasking_needed: [],
      top_commanders: [],
    },
    active_humans: null,
    operators: null,
  } as unknown as Hud;
}

/** One update at `remaining` ticks, store tick `tick`, wall time `now`. */
function at(
  fh: FinalHours,
  remaining: number,
  o: { paused?: boolean; tick?: number; now?: number; score?: Score } = {},
): void {
  fh.update(hud(remaining, o), remaining, o.tick ?? 1000, o.now ?? 0);
}
const banner = (fh: FinalHours, now = 0): string | null => fh.bannerText(now);

describe("FH-T1: each threshold fires once, at or below its value", () => {
  it("fires at the value, not one tick above, and only once", () => {
    const fh = new FinalHours();
    at(fh, T1 + 100);
    expect(fh.push()).toBeNull();
    at(fh, T1 + 1);
    expect(fh.push()).toBeNull();
    at(fh, T1);
    expect(banner(fh)).toBe("FINAL 6 HOURS");
    expect(fh.push()?.phase).toBe(1);
    at(fh, T1 - 10, { now: BANNER_MS + 1 });
    expect(banner(fh, BANNER_MS + 1)).toBeNull(); // not fired again
    at(fh, T2);
    expect(banner(fh)).toBe("FINAL HOUR");
    at(fh, T3);
    expect(banner(fh)).toBe("FINAL 10 MINUTES");
    expect(fh.push()).toMatchObject({ phase: 3, label: "FINAL MINUTES" });
  });
  it("is 6 h, 1 h, 10 min in 10 Hz ticks, and the banner lasts 5 s of real time", () => {
    expect(THRESHOLD_TICKS).toEqual([216000, 36000, 6000]);
    const fh = new FinalHours();
    at(fh, T1 + 5);
    at(fh, T1, { now: 100 });
    expect(banner(fh, 100 + BANNER_MS - 1)).not.toBeNull();
    expect(banner(fh, 100 + BANNER_MS)).toBeNull();
  });
  it("phaseOf picks the tightest threshold", () => {
    expect([T1 + 1, T1, T2 + 1, T2, T3 + 1, T3, 0, -5].map(phaseOf)).toEqual([
      0, 1, 1, 2, 2, 3, 3, 3,
    ]);
  });
  it("labels the cards 6 h, 1 h and 10 min left", () => {
    const fh = new FinalHours();
    at(fh, T1 + 1);
    at(fh, T1);
    expect(fh.cardAt(1000)?.kicker).toBe("FINAL HOURS · 6 h left");
    at(fh, T2);
    expect(fh.cardAt(1000)?.kicker).toBe("FINAL HOURS · 1 h left");
    at(fh, T3);
    expect(fh.cardAt(1000)?.kicker).toBe("FINAL HOURS · 10 min left");
  });
});

describe("FH-T2: nothing fires while paused", () => {
  it("fires on the first running update after", () => {
    const fh = new FinalHours();
    at(fh, T1 + 100);
    at(fh, T2 - 5, { paused: true });
    expect(fh.push()).toBeNull();
    expect(fh.cardAt(1000)).toBeNull();
    expect(banner(fh)).toBeNull();
    at(fh, T2 - 5);
    expect(banner(fh)).toBe("FINAL HOUR");
    expect(fh.push()?.phase).toBe(2);
  });
  it("hides a live banner when a pause starts (a pause banner wins)", () => {
    const fh = new FinalHours();
    at(fh, T2 + 1);
    at(fh, T2);
    at(fh, T2 - 1, { paused: true });
    expect(banner(fh)).toBeNull();
    expect(fh.push()?.phase).toBe(2); // the push stays
  });
  it("card life counts store ticks, so a paused world keeps its card", () => {
    const fh = new FinalHours();
    at(fh, T2 + 1);
    at(fh, T2, { tick: 5000 });
    expect(fh.cardAt(5000 + CARD_TTL_TICKS - 1)).not.toBeNull();
    expect(fh.cardAt(5000 + CARD_TTL_TICKS)).toBeNull();
  });
  it("FH-1 and FH-2 cards live 60 s, the FH-3 card stays", () => {
    expect(CARD_TTL_TICKS).toBe(600);
    const fh = new FinalHours();
    at(fh, T3 + 1);
    at(fh, T3, { tick: 100 });
    expect(fh.cardAt(100 + 10 ** 7)).not.toBeNull();
  });
});

describe("FH-T3: hysteresis", () => {
  it("a re-base lifting remaining back over a threshold by under 30 s does not re-fire", () => {
    const fh = new FinalHours();
    at(fh, T2 + 1);
    at(fh, T2 - 1);
    at(fh, T2 + HYSTERESIS_TICKS, { now: 10_000 }); // up, but not over by more than 30 s
    expect(fh.push()?.phase).toBe(2);
    at(fh, T2 - 2, { now: 10_001 });
    expect(banner(fh, 10_001)).toBeNull();
  });
  it("a lift over 30 s re-arms it", () => {
    const fh = new FinalHours();
    at(fh, T2 + 1);
    at(fh, T2 - 1);
    at(fh, T2 + HYSTERESIS_TICKS + 1);
    expect(fh.push()?.phase).toBe(1);
    at(fh, T2, { now: 20_000 });
    expect(banner(fh, 20_000)).toBe("FINAL HOUR");
  });
});

describe("FH-T4: an extension drops the phase and re-arms", () => {
  it("clears the push and the card, and plays the climax again at the new end", () => {
    const fh = new FinalHours();
    at(fh, T3 + 1);
    at(fh, T3);
    expect(fh.push()?.phase).toBe(3);
    at(fh, T1 + 10_000); // limit_ticks raised: back above 6 h
    expect(fh.push()).toBeNull();
    expect(fh.cardAt(1000)).toBeNull();
    at(fh, T1, { now: 50_000 });
    expect(banner(fh, 50_000)).toBe("FINAL 6 HOURS");
  });
  it("an extension into the middle band drops to the phase it is in", () => {
    const fh = new FinalHours();
    at(fh, T3 + 1);
    at(fh, T3);
    at(fh, T2 - 1_000); // above FH-3 plus hysteresis, still under 1 h
    expect(fh.push()?.phase).toBe(2); // FH-3 re-armed; FH-2 stays fired, so no second banner
    expect(fh.cardAt(1000)).toBeNull(); // the FH-3 card went with its phase
  });
});

describe("FH-T5: load or reconnect inside a phase", () => {
  it("shows the push and a fresh card, no banner", () => {
    const fh = new FinalHours();
    at(fh, T2 - 50, { tick: 7000, now: 1 });
    expect(fh.push()?.phase).toBe(2);
    expect(banner(fh, 1)).toBeNull();
    expect(fh.cardAt(7000)?.phase).toBe(2);
    expect(fh.cardAt(7000 + CARD_TTL_TICKS - 1)).not.toBeNull(); // a fresh life from the load tick
  });
  it("restores even when paused", () => {
    const fh = new FinalHours();
    at(fh, T3 - 5, { paused: true });
    expect(fh.push()?.phase).toBe(3);
    expect(fh.cardAt(1000)?.phase).toBe(3);
  });
  it("does nothing before the first Snapshot tick", () => {
    const fh = new FinalHours();
    fh.update(hud(T3), T3, null, 0);
    expect(fh.push()).toBeNull();
  });
});

describe("FH-T6: the end and a new campaign", () => {
  const ended = (
    result: string,
    id = "c1",
  ): { kind: string; campaign_id: string; result: string } => ({
    kind: "CampaignEnded",
    campaign_id: id,
    result,
  });
  it.each(["VICTORY", "DEFEAT", "TIME_LIMIT", "ABORTED"])(
    "CampaignEnded %s clears everything",
    (r) => {
      const fh = new FinalHours();
      at(fh, T2 + 1);
      at(fh, T2);
      fh.ingest([ended(r)]);
      at(fh, T2 - 100); // the frozen world keeps sending Huds
      expect(fh.push()).toBeNull();
      expect(fh.cardAt(1000)).toBeNull();
      expect(banner(fh)).toBeNull();
    },
  );
  it("a Hud that already carries a result shows nothing (reconnect after the end)", () => {
    const fh = new FinalHours();
    const h = hud(T3 - 5);
    (h.panels.campaign_status as { result: string }).result = "TIME_LIMIT";
    fh.update(h, T3 - 5, 1000, 0);
    expect(fh.push()).toBeNull();
  });
  it("a new campaign_id resets every fired threshold", () => {
    const fh = new FinalHours();
    fh.ingest([{ kind: "UnitSpawned", campaign_id: "c1" }]);
    at(fh, T1 + 1);
    at(fh, T1);
    expect(fh.push()?.phase).toBe(1);
    fh.ingest([{ kind: "UnitSpawned", campaign_id: "c2" }]);
    expect(fh.push()).toBeNull();
    at(fh, T1 - 5, { now: 9_000 }); // the new campaign's first update restores
    expect(fh.push()?.phase).toBe(1);
    expect(banner(fh, 9_000)).toBeNull();
  });
  it("a new campaign_id lifts the ended latch", () => {
    const fh = new FinalHours();
    fh.ingest([ended("TIME_LIMIT", "c1")]);
    fh.ingest([{ kind: "UnitSpawned", campaign_id: "c2" }]);
    at(fh, T1 + 1);
    at(fh, T1);
    expect(fh.push()?.phase).toBe(1);
  });
});

describe("FH-T7: stack order", () => {
  const ta = (category: ThreatAdaptation["category"], n: number): Event =>
    ({
      kind: "ThreatAdaptation",
      tick: 100,
      event_seq: n,
      campaign_id: "c",
      side: "ENEMY",
      category,
      sector_id: "north",
      direction: "UP",
      node_id: null,
      credit_ids: [],
    }) as unknown as Event;
  const card = {
    phase: 2 as const,
    kicker: "k",
    lines: ["a", "b"] as [string, string],
  };
  const order = (events: Event[], c: typeof card | null): string[] => {
    const b = new ThreatSitrepBoard();
    b.ingest(events, () => undefined);
    return placeFinalHours(b.view(100), c).shown.map((i) =>
      i.kind === "final" ? "FINAL_HOURS" : i.entry.tier,
    );
  };
  it("puts FINAL HOURS under LAST STAND and over ALERT, WIN, INTEL and EASING", () => {
    const all = [
      ta("STRIKE_DOWNED", 1),
      ta("HOLD_AT_RISK", 2),
      ta("SANCTUARY_AT_RISK", 3),
    ];
    expect(order(all, card)).toEqual(["LAST_STAND", "FINAL_HOURS", "ALERT"]);
    expect(order([ta("HOLD_AT_RISK", 2)], card)).toEqual([
      "FINAL_HOURS",
      "ALERT",
    ]);
    expect(order([ta("SANCTUARY_AT_RISK", 3)], card)).toEqual([
      "LAST_STAND",
      "FINAL_HOURS",
    ]);
    expect(order([], card)).toEqual(["FINAL_HOURS"]);
    expect(
      order([ta("STRIKE_DOWNED", 1), ta("IADS_REINFORCED", 4)], card),
    ).toEqual(["FINAL_HOURS", "WIN", "INTEL"]);
  });
  it("counts the card in the +N more overflow", () => {
    const evs = [
      ta("SANCTUARY_AT_RISK", 1),
      ta("HOLD_AT_RISK", 2),
      ta("STAGING", 3),
    ];
    const b = new ThreatSitrepBoard();
    b.ingest(evs, () => undefined);
    const v = placeFinalHours(b.view(100), card);
    expect(v.shown).toHaveLength(3);
    expect(v.hiddenCount).toBe(1);
    expect(v.shown.map((i) => i.kind)).toEqual(["event", "final", "event"]);
  });
  it("without a card the board view is unchanged", () => {
    expect(order([ta("HOLD_AT_RISK", 2)], null)).toEqual(["ALERT"]);
  });
});

describe("FH-T8: no limit and no strategic nodes", () => {
  it("limit_ticks null: no push, no card, no banner", () => {
    const fh = new FinalHours();
    fh.update(hud(0, { limit: null }), null, 1000, 0);
    expect(fh.push()).toBeNull();
    expect(fh.cardAt(1000)).toBeNull();
    expect(banner(fh)).toBeNull();
  });
  it("a clock with no limit clears a phase it was in", () => {
    const fh = new FinalHours();
    at(fh, T3 - 1);
    fh.update(hud(0, { limit: null }), null, 1000, 0);
    expect(fh.push()).toBeNull();
  });
  it("HudClock.warRemaining is null without a limit or a Hud", () => {
    const c = new HudClock();
    expect(c.warRemaining()).toBeNull();
    c.rebase(hud(0, { limit: null }), 0);
    expect(c.warRemaining()).toBeNull();
    c.rebase(hud(T3), 0);
    expect(c.warRemaining()).toBe(T3);
  });
  it("nodes_total 0 shows the dash in the card's node line", () => {
    const fh = new FinalHours();
    fh.update(hud(T3, { nodes_total: 0 }), T3, 1000, 0);
    expect(fh.cardAt(1000)?.lines[1]).toBe("Coalition holds — strategic nodes");
  });
});

describe("FH-T9: leader and margin on the chip and the card", () => {
  const cases: [Score, string, string, string][] = [
    [
      { coalition: 40, enemy: 35 },
      "COALITION +5",
      "COALITION",
      "Coalition leads on points, 40 to 35",
    ],
    [
      { coalition: 30, enemy: 41 },
      "NULL +11",
      "NULL",
      "NULL leads on points, 41 to 30",
    ],
    [{ coalition: 38, enemy: 38 }, "LEVEL", "LEVEL", "Points level at 38"],
    [null, "—", "NONE", "Points: —"],
  ];
  it.each(cases)("%j", (score, chip, lead, line) => {
    const fh = new FinalHours();
    at(fh, T1 + 1, { score });
    at(fh, T1, { score });
    expect(fh.push()?.score).toEqual({ lead, text: chip });
    expect(scoreOf(hud(T1, { score }))).toEqual({ lead, text: chip });
    expect(fh.cardAt(1000)?.lines).toEqual([
      line,
      "Coalition holds 3 of 8 strategic nodes",
    ]);
  });
  it("follows the live score on the next Hud", () => {
    const fh = new FinalHours();
    at(fh, T1 + 1);
    at(fh, T1);
    at(fh, T1 - 10, { score: { coalition: 1, enemy: 9 } });
    expect(fh.push()?.score.text).toBe("NULL +8");
  });
});

// A minimal DOM, enough for TopBar, SitrepStack and mountHud.
class El {
  children: El[] = [];
  className = "";
  hidden = false;
  attrs: Record<string, string> = {};
  cl = new Set<string>();
  private text = "";
  get textContent(): string {
    return this.children.length
      ? this.children.map((c) => c.textContent).join("")
      : this.text;
  }
  set textContent(v: string) {
    this.children = [];
    this.text = v;
  }
  classList = {
    toggle: (c: string, f: boolean) =>
      void (f ? this.cl.add(c) : this.cl.delete(c)),
  };
  appendChild(c: El): El {
    this.children.push(c);
    return c;
  }
  replaceChildren(...c: El[]): void {
    this.children = c;
  }
  setAttribute(k: string, v: string): void {
    this.attrs[k] = v;
  }
  find(cls: string): El[] {
    const own: El[] = this.className.split(" ").includes(cls) ? [this] : [];
    return own.concat(...this.children.map((c) => c.find(cls)));
  }
}
const doc = { createElement: () => new El() } as unknown as Document;
const win = {
  setInterval: () => 0,
  clearInterval: () => undefined,
  setTimeout: () => 0,
} as unknown as Window;
const first = (r: El, cls: string): El => {
  const e = r.find(cls)[0];
  if (!e) throw new Error(cls);
  return e;
};

describe("the bar, the stack and the banner render the model", () => {
  const live = (remaining: number, o: Parameters<typeof hud>[1] = {}) => {
    const fh = new FinalHours();
    at(fh, remaining + 20);
    fh.update(hud(remaining, o), remaining, 1000, 0);
    const c = new HudClock();
    c.rebase(hud(remaining, o), 1000);
    return { fh, c };
  };
  it("FH-1 to FH-3 add a label, a chip and a data-fh phase to the war cell", () => {
    for (const [r, phase, label] of [
      [T1, "1", "FINAL HOURS"],
      [T2, "2", "FINAL HOURS"],
      [T3, "3", "FINAL MINUTES"],
    ] as const) {
      const { fh, c } = live(r);
      const root = new El();
      new TopBar(doc, root as unknown as HTMLElement).render(hud(r), c, fh);
      expect(first(root, "nx-war").attrs["data-fh"]).toBe(phase);
      expect(first(root, "nx-fh").hidden).toBe(false);
      expect(first(root, "nx-fh-label").textContent).toBe(label);
      expect(first(root, "nx-fh-text").textContent).toBe("COALITION +5");
      expect(first(root, "nx-fh-glyph").attrs["data-lead"]).toBe("COALITION");
      expect(first(root, "nx-topbar").cl.has("fh")).toBe(true);
    }
  });
  it("the label and chip sit on the countdown's row, so the bar keeps its height (§0.11)", () => {
    const { fh, c } = live(T2);
    const root = new El();
    new TopBar(doc, root as unknown as HTMLElement).render(hud(T2), c, fh);
    const cell = first(root, "nx-war");
    // the cell is only the label and one row: a third block child would stack under the countdown
    expect(cell.children.map((e) => e.className.split(" ").pop())).toEqual([
      "nx-label",
      "nx-war-row",
    ]);
    const row = first(cell, "nx-war-row");
    expect(row.children.map((e) => e.className)).toEqual(["nx-val", "nx-fh"]);
  });
  it("outside the final hours the bar is unchanged", () => {
    const { fh, c } = live(T1 + 100_000);
    const root = new El();
    new TopBar(doc, root as unknown as HTMLElement).render(
      hud(T1 + 100_000),
      c,
      fh,
    );
    expect(first(root, "nx-fh").hidden).toBe(true);
    expect(first(root, "nx-fh-label").textContent).toBe("");
    expect(first(root, "nx-topbar").cl.has("fh")).toBe(false);
  });
  it("the stack shows the FINAL HOURS card with its kicker and two lines", () => {
    const { fh } = live(T2);
    const root = new El();
    const st = new SitrepStack(
      doc,
      root as unknown as HTMLElement,
      () => undefined,
      () => ({ sectors: [], nodes: [] }),
      (t) => fh.cardAt(t),
    );
    st.render(1000);
    const card = first(root, "nx-tier-FINAL_HOURS");
    expect(first(card, "nx-kicker").textContent).toBe("FINAL HOURS · 1 h left");
    expect(card.find("nx-line").map((l) => l.textContent)).toEqual([
      "Coalition leads on points, 40 to 35",
      "Coalition holds 3 of 8 strategic nodes",
    ]);
    expect(first(card, "nx-shape").className).toContain("hourglass");
    st.render(1000 + CARD_TTL_TICKS); // life over
    expect(root.find("nx-card")).toHaveLength(0);
  });
  it("mountHud: a threshold crossing shows the banner in the toast layer, then it ends", () => {
    const panels = new El();
    const toast = new El();
    const store = new WireStore();
    const view = mountHud(
      { panels, sitrep: new El(), toast } as never,
      { ...win, document: doc } as Window,
      () => store,
    );
    const snap = (h: Hud, tick: number): Snapshot =>
      ({
        type: "Snapshot",
        v: "1",
        tick,
        hud: h,
        entities: [],
        nodes: [],
        blobs: [],
        last_known: [],
      }) as unknown as Snapshot;
    const s1 = snap(hud(T1 + 5), 1000);
    store.applySnapshot(s1);
    view.frame(s1, store);
    expect(first(toast, "nx-fh-banner").hidden).toBe(true);
    const d = {
      type: "Delta",
      v: "1",
      tick: 1010,
      base_tick: 1000,
      upserts: [],
      removes: [],
      node_patches: [],
      blobs: null,
      last_known: null,
      events: [],
    } as unknown as Delta;
    store.applyDelta(d);
    view.frame(d, store);
    const b = first(toast, "nx-fh-banner");
    expect(b.hidden).toBe(false);
    expect(b.textContent).toBe("FINAL 6 HOURS");
    expect(first(panels, "nx-war").attrs["data-fh"]).toBe("1");
  });
});
