import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Delta } from "../contracts/wire/delta";
import type { Hud, Snapshot } from "../contracts/wire/snapshot";
import { mountHud } from "../hud/mount";
import { WireStore } from "../net/store";
import type { PublicEvent } from "../contracts/wire/hud";
import src_clock from "../hud/clock.ts?raw";
import src_mount from "../hud/mount.ts?raw";
import src_rotator from "../hud/rotator.ts?raw";
import src_sitrep_stack from "../hud/sitrep-stack.ts?raw";
import src_strings from "../hud/strings.ts?raw";
import src_topbar from "../hud/topbar.ts?raw";
import { HudClock, fmtTicks } from "../hud/clock";
import { cycle, members, Rotator } from "../hud/rotator";
import { SitrepStack } from "../hud/sitrep-stack";
import { TopBar, nodesText, litSegments } from "../hud/topbar";

// NX-178: HUD top bar, timers, rotating panel, OV-26 on the live stream (OVERLAY §0.5-0.6).

class FakeEl {
  children: FakeEl[] = [];
  parentElement: FakeEl | null = null;
  className = "";
  hidden = false;
  attrs: Record<string, string> = {};
  private text = "";
  readonly cl = new Set<string>();
  constructor(readonly tag: string) {}
  get textContent(): string {
    return this.children.length > 0
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
    add: (c: string) => void this.cl.add(c),
    remove: (c: string) => void this.cl.delete(c),
  };
  appendChild(c: FakeEl): FakeEl {
    c.parentElement = this;
    this.children.push(c);
    return c;
  }
  replaceChildren(...c: FakeEl[]): void {
    this.children = [];
    c.forEach((x) => this.appendChild(x));
  }
  remove(): void {
    const p = this.parentElement;
    if (p) p.children = p.children.filter((x) => x !== this);
  }
  setAttribute(k: string, v: string): void {
    this.attrs[k] = v;
  }
  find(cls: string): FakeEl[] {
    const out: FakeEl[] = this.className.split(" ").includes(cls) ? [this] : [];
    for (const c of this.children) out.push(...c.find(cls));
    return out;
  }
}
const doc = {
  createElement: (tag: string) => new FakeEl(tag),
} as unknown as Document;
const root = (): HTMLElement => new FakeEl("div") as unknown as HTMLElement;
const fe = (e: HTMLElement): FakeEl => e as unknown as FakeEl;
const text = (e: HTMLElement, cls: string): string =>
  fe(e).find(cls)[0]?.textContent ?? "<none>";
const win = {
  setInterval: (f: () => void, ms: number) => setInterval(f, ms),
  clearInterval: (id: number) => clearInterval(id),
  setTimeout: (f: () => void, ms: number) => setTimeout(f, ms),
} as unknown as Window;

function hud(over: Record<string, unknown> = {}): Hud {
  return {
    type: "Hud",
    v: "1",
    momentum_pct: 60,
    momentum_breakdown: null,
    objective_mode: "TIMED",
    objective: { node_id: "n1", name: "Hold Haven", deadline_tick: 6000 },
    threat_tier: "ALPHA",
    nodes_held: 3,
    nodes_total: 5,
    campaign_clock: {
      elapsed_ticks: 1000,
      limit_ticks: 36000,
      paused: false,
      pause_reason: null,
    },
    ticker: [],
    panels: { tasking_needed: [], top_commanders: [] },
    active_humans: null,
    operators: null,
    ...over,
  } as unknown as Hud;
}

function bar(h: Hud | null, clock = new HudClock()): HTMLElement {
  const r = root();
  new TopBar(doc, r).render(h, clock);
  return r;
}
function clockFor(h: Hud, tick: number | null = 0): HudClock {
  const c = new HudClock();
  c.rebase(h, tick);
  return c;
}

describe("top bar fields", () => {
  it("renders every field from a Hud", () => {
    const h = hud({
      ticker: [
        { tick: 1, text: "old", category: "SYSTEM" },
        { tick: 9, text: "newest", category: "CAPTURE" },
      ],
    });
    const r = bar(h, clockFor(h));
    expect(text(r, "nx-signal")).toContain("Signal strength");
    expect(
      fe(r)
        .find("nx-meter")[0]
        ?.children.filter((s) => s.cl.has("on")),
    ).toHaveLength(6);
    expect(text(r, "nx-nodes")).toBe("Nodes held3 of 5");
    expect(text(r, "nx-obj")).toBe("ObjectiveHold Haven08:20");
    expect(text(r, "nx-threat")).toBe("ThreatAlpha");
    expect(text(r, "nx-war")).toBe("War clock58:20");
    expect(text(r, "nx-ticker-item")).toBe("newest");
    expect(text(r, "nx-howto")).toBe(
      "Type !join strike | recon | logi to deploy",
    );
  });

  it("maps all tiers through hud.tier keys; unknown tier shows its id", () => {
    for (const [k, w] of [
      ["PATTERN_OF_LIFE", "Pattern of life"],
      ["ALPHA", "Alpha"],
      ["BRAVO", "Bravo"],
      ["ZULU", "ZULU"],
    ] as const) {
      const r = bar(hud({ threat_tier: k }));
      expect(text(r, "nx-threat")).toBe(`Threat${w}`);
    }
  });

  it("cold start: every field is a dash, nothing defaulted", () => {
    const r = bar(null);
    for (const c of [
      "nx-nodes",
      "nx-obj",
      "nx-threat",
      "nx-war",
      "nx-signal",
    ]) {
      const body = text(r, c).replace(
        /Nodes held|Objective|Threat|War clock|Signal strength/,
        "",
      );
      expect(body.replace(/—/g, "")).toBe("");
      expect(body).toContain("—");
    }
    expect(
      fe(r)
        .find("nx-meter")[0]
        ?.children.some((s) => s.cl.has("on")),
    ).toBe(false);
    expect(text(r, "nx-ticker-item")).toBe("");
  });

  it("null cases: momentum, nodes, deadline, limit, empty ticker", () => {
    const h = hud({
      momentum_pct: null,
      nodes_held: undefined,
      objective: { node_id: "n", name: "X", deadline_tick: null },
      campaign_clock: {
        elapsed_ticks: 5,
        limit_ticks: null,
        paused: false,
        pause_reason: null,
      },
    });
    const r = bar(h, clockFor(h));
    expect(text(r, "nx-signal")).toBe("Signal strength—");
    expect(text(r, "nx-nodes")).toBe("Nodes held—");
    expect(text(r, "nx-obj")).toBe("ObjectiveX—");
    expect(text(r, "nx-war")).toBe("War clock—");
    expect(nodesText(hud({ nodes_total: undefined }))).toBe("—");
    expect(nodesText(hud({ nodes_held: 0, nodes_total: 0 }))).toBe("—"); // campaign layer off
    expect(nodesText(hud({ nodes_held: 0, nodes_total: 4 }))).toBe("0 of 4");
    expect(litSegments(0)).toBe(0);
    expect(litSegments(100)).toBe(10);
    expect(litSegments(null)).toBe(0);
  });

  it("objective_mode OFF hides the objective and its timer; TIMED shows them", () => {
    const off = bar(hud({ objective_mode: "OFF" }));
    expect(fe(off).find("nx-obj")[0]?.hidden).toBe(true);
    expect(fe(bar(hud())).find("nx-obj")[0]?.hidden).toBe(false);
    const none = bar(hud({ objective: null }));
    expect(text(none, "nx-obj")).toBe("Objective——");
  });

  it("renders an XSS-shaped feed string as literal text", () => {
    const bad = '<img src=x onerror="alert(1)"><script>alert(2)</script>';
    const r = bar(
      hud({
        objective: { node_id: "n", name: bad, deadline_tick: null },
        ticker: [{ tick: 1, text: bad, category: "SYSTEM" }],
      }),
    );
    expect(text(r, "nx-name")).toBe(bad);
    expect(text(r, "nx-ticker-item")).toBe(bad);
    expect(fe(r).find("nx-name")[0]?.children).toHaveLength(0); // no parsed nodes
  });
});

describe("timer math", () => {
  it("formats m:ss and h:mm:ss, expired as zero, null as a dash", () => {
    expect(fmtTicks(null, true)).toBe("—");
    expect(fmtTicks(0, false)).toBe("00:00");
    expect(fmtTicks(-50, false)).toBe("00:00");
    expect(fmtTicks(6000, false)).toBe("10:00");
    expect(fmtTicks(36000, false)).toBe("60:00"); // objective: minutes, no hours
    expect(fmtTicks(36000, true)).toBe("1:00:00");
    expect(fmtTicks(599, false)).toBe("00:59");
  });

  it("advances by Delta ticks, freezes while paused, re-bases on a Hud", () => {
    const c = clockFor(hud(), 100);
    c.advance(150); // +50 ticks = 5 s
    expect(c.objective()).toBe("08:15");
    expect(c.war()).toBe("58:15");
    const p = hud({
      campaign_clock: {
        elapsed_ticks: 2000,
        limit_ticks: 36000,
        paused: true,
        pause_reason: "STAFF",
      },
    });
    c.rebase(p, 150);
    c.advance(400);
    expect(c.objective()).toBe("06:40"); // frozen at elapsed 2000
    expect(c.war()).toBe("56:40");
    c.rebase(hud(), 400); // Hud wins over the locally advanced value
    expect(c.objective()).toBe("08:20");
    c.advance(300); // a lower tick (restart) never runs the clock backwards
    expect(c.objective()).toBe("08:20");
  });
});

describe("rotating panel", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());
  const job = (k: string) => ({
    job_kind: k,
    node_id: null,
    sector_id: "north",
    slots_open: 2,
  });
  const full = () =>
    hud({
      panels: {
        tasking_needed: [job("SCOUT")],
        top_commanders: [
          { role: "STRIKE", rows: [{ callsign: "VIPER-01", value: 7 }] },
          { role: "RECON", rows: [] },
        ],
      },
      operators: { by_role: [{ role: "STRIKE", count: 2 }], by_rank_band: [] },
    });
  const shown = (r: HTMLElement) => text(r, "nx-rotor-title");

  it("cycles NEEDED twice per cycle, others once, in order", () => {
    const m = members(full(), (i) => i);
    expect(cycle(m.needed, m.others).map((x) => x.id)).toEqual([
      "needed",
      "operators",
      "needed",
      "top-STRIKE",
    ]);
  });

  it("rotates every 15 s on real-time timers and skips empty members", () => {
    const r = root();
    const rot = new Rotator(doc, r, win, (i) => i);
    rot.update(full());
    const seen = [shown(r)];
    for (let i = 0; i < 4; i++) {
      vi.advanceTimersByTime(14_999);
      expect(shown(r)).toBe(seen[seen.length - 1]);
      vi.advanceTimersByTime(1);
      seen.push(shown(r));
    }
    expect(seen).toEqual([
      "NEEDED",
      "Operators",
      "NEEDED",
      "Top STRIKE",
      "NEEDED",
    ]);
    expect(text(r, "nx-rotor-row")).toBe("SCOUT north, 2 open");
  });

  it("never pads: no rows at all hides the panel; RECON with no rows is not a member", () => {
    const r = root();
    const rot = new Rotator(doc, r, win, (i) => i);
    rot.update(hud());
    expect(fe(r).find("nx-rotor")[0]?.hidden).toBe(true);
    expect(members(full(), (i) => i).others.map((x) => x.id)).toEqual([
      "operators",
      "top-STRIKE",
    ]);
    rot.update(
      hud({
        panels: { tasking_needed: [], top_commanders: [] },
        operators: null,
      }),
    );
    expect(fe(r).find("nx-rotor")[0]?.hidden).toBe(true);
  });

  it("jumps on when the visible member loses its rows", () => {
    const r = root();
    const rot = new Rotator(doc, r, win, (i) => i);
    rot.update(full());
    expect(shown(r)).toBe("NEEDED");
    rot.update(
      hud({
        operators: { by_role: [{ role: "LOGI", count: 1 }], by_rank_band: [] },
      }),
    );
    expect(shown(r)).toBe("Operators");
  });
});

describe("OV-26 on the live stream", () => {
  const ta = (over: Record<string, unknown>) =>
    ({
      kind: "ThreatAdaptation",
      tick: 100,
      event_seq: 1,
      campaign_id: "c1",
      side: "ENEMY",
      category: "HOLD_AT_RISK",
      sector_id: "north",
      direction: "UP",
      node_id: "n1",
      credit_ids: [],
      ...over,
    }) as unknown as PublicEvent;
  const mk = () => {
    const r = root();
    const s = new SitrepStack(
      doc,
      r,
      (id) => (id === 7 ? "VIPER-01" : undefined),
      () => ({ sectors: [], nodes: [{ id: "n1", name: "Haven" }] }),
    );
    return { r, s };
  };

  it("maps a Delta's ThreatAdaptation to a card with names from the Welcome nodes", () => {
    const { r, s } = mk();
    s.ingest(
      [
        ta({}),
        ta({
          category: "STRIKE_DOWNED",
          event_seq: 2,
          sector_id: "south",
          credit_ids: [7, 8],
        }),
        { kind: "JobDone" } as unknown as PublicEvent,
      ],
      100,
    );
    const lines = fe(r).children.map((c) => c.textContent);
    expect(lines[0]).toBe(
      "ALERT · northNULL moves on Haven, the hold is at risk",
    );
    expect(lines[1]).toContain(
      "WIN · southNULL strike package downed near Haven",
    );
    expect(lines[1]).toContain("Credit: VIPER-01 +1");
    expect(fe(r).children).toHaveLength(2); // non-sitrep events raise no card
  });

  it("expires on game ticks and replays change nothing", () => {
    const { r, s } = mk();
    s.ingest([ta({})], 100);
    s.ingest([ta({ event_seq: 1 })], 101);
    expect(fe(r).children).toHaveLength(1);
    s.render(400); // 100 + 300 ticks
    expect(fe(r).children).toHaveLength(0);
  });
});

describe("source hygiene", () => {
  it("HUD modules never write HTML or inline styles", () => {
    const all = {
      clock: src_clock,
      mount: src_mount,
      rotator: src_rotator,
      "sitrep-stack": src_sitrep_stack,
      strings: src_strings,
      topbar: src_topbar,
    };
    for (const [f, src] of Object.entries(all)) {
      expect(src, f).not.toMatch(
        /innerHTML|outerHTML|insertAdjacentHTML|\.style\b|setAttribute\(\s*["']style/,
      );
    }
  });
});

describe("review fixes", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());
  const job = {
    job_kind: "SCOUT",
    node_id: null,
    sector_id: "north",
    slots_open: 1,
  };
  const oneOther = () =>
    hud({
      panels: { tasking_needed: [job], top_commanders: [] },
      operators: { by_role: [{ role: "LOGI", count: 1 }], by_rank_band: [] },
    });

  it("with one other member NEEDED alternates 1:1, never twice in a row", () => {
    const m = members(oneOther(), (i) => i);
    expect(cycle(m.needed, m.others).map((x) => x.id)).toEqual([
      "needed",
      "operators",
    ]);
    const r = root();
    const rot = new Rotator(doc, r, win, (i) => i);
    rot.update(oneOther());
    const seen = [text(r, "nx-rotor-title")];
    for (let i = 0; i < 5; i++) {
      vi.advanceTimersByTime(15_000);
      seen.push(text(r, "nx-rotor-title"));
    }
    expect(seen).toEqual([
      "NEEDED",
      "Operators",
      "NEEDED",
      "Operators",
      "NEEDED",
      "Operators",
    ]);
  });

  it("the first member after an empty panel gets a full dwell", () => {
    const r = root();
    const rot = new Rotator(doc, r, win, (i) => i);
    vi.advanceTimersByTime(10_000);
    rot.update(oneOther());
    expect(text(r, "nx-rotor-title")).toBe("NEEDED");
    vi.advanceTimersByTime(14_999);
    expect(text(r, "nx-rotor-title")).toBe("NEEDED");
    vi.advanceTimersByTime(1);
    expect(text(r, "nx-rotor-title")).toBe("Operators");
  });

  it("the clock never moves backwards", () => {
    const c = clockFor(hud(), 100);
    c.advance(200);
    c.advance(150); // out-of-order tick
    c.advance(250); // only +50 from 200
    expect(c.objective()).toBe("08:05"); // +100 +0 +50
  });

  it("rounds a float momentum for display", () => {
    expect(text(bar(hud({ momentum_pct: 61.6 })), "nx-signal")).toBe(
      "Signal strength62%",
    );
  });

  it("OFF drops the objective column from the grid", () => {
    expect(
      fe(bar(hud({ objective_mode: "OFF" })))
        .find("nx-topbar")[0]
        ?.cl.has("no-obj"),
    ).toBe(true);
    expect(fe(bar(hud())).find("nx-topbar")[0]?.cl.has("no-obj")).toBe(false);
  });

  const bad = '<img src=x onerror="alert(1)">';
  it("renders a hostile callsign in the rotator as literal text", () => {
    const r = root();
    const rot = new Rotator(doc, r, win, (i) => i);
    rot.update(
      hud({
        panels: {
          tasking_needed: [],
          top_commanders: [
            { role: "STRIKE", rows: [{ callsign: bad, value: 3 }] },
          ],
        },
      }),
    );
    const row = fe(r).find("nx-rotor-row")[0];
    expect(row?.textContent).toBe(`${bad}: 3`);
    expect(row?.children).toHaveLength(0);
  });

  it("renders a hostile callsign on a sitrep card as literal text", () => {
    const r = root();
    const s = new SitrepStack(
      doc,
      r,
      () => bad,
      () => ({ sectors: [], nodes: [] }),
    );
    s.ingest(
      [
        {
          kind: "ThreatAdaptation",
          tick: 1,
          event_seq: 1,
          campaign_id: "c",
          side: "ENEMY",
          category: "STRIKE_DOWNED",
          sector_id: "north",
          direction: "UP",
          node_id: null,
          credit_ids: [5],
        } as unknown as PublicEvent,
      ],
      1,
    );
    const credit = fe(r).find("nx-credit")[0];
    expect(credit?.textContent).toBe(`Credit: ${bad}`);
    expect(credit?.children).toHaveLength(0);
  });
});

describe("mountHud with a fake stage and the real store", () => {
  const snapshot = (tick: number, h: Hud | null): Snapshot =>
    ({
      type: "Snapshot",
      v: "1",
      tick,
      entities: [],
      nodes: [],
      blobs: [],
      last_known: [],
      hud: h,
    }) as unknown as Snapshot;
  const deltaAt = (tick: number, base: number): Delta =>
    ({
      type: "Delta",
      v: "1",
      tick,
      base_tick: base,
      upserts: [],
      removes: [],
      node_patches: [],
      blobs: null,
      last_known: null,
      events: [],
    }) as unknown as Delta;
  function setup() {
    const panels = root();
    const sitrep = root();
    const store = new WireStore();
    const w = { ...win, document: doc } as unknown as Window;
    const view = mountHud({ panels, sitrep }, w, () => store);
    return { panels, store, view };
  }
  const bar = (r: HTMLElement): string =>
    `${text(r, "nx-nodes")}|${text(r, "nx-obj")}|${text(r, "nx-war")}`;

  it("starts cold, then follows Snapshot, Delta and Hud", () => {
    const { panels, store, view } = setup();
    expect(bar(panels)).toBe("Nodes held—|Objective——|War clock—");
    const snap = snapshot(1000, hud());
    store.applySnapshot(snap);
    view.frame(snap, store);
    expect(bar(panels)).toBe(
      "Nodes held3 of 5|ObjectiveHold Haven08:20|War clock58:20",
    );
    const d = deltaAt(1100, 1000);
    store.applyDelta(d);
    view.frame(d, store);
    expect(text(panels, "nx-obj")).toBe("ObjectiveHold Haven08:10");
    const h2 = hud({
      nodes_held: 4,
      campaign_clock: {
        elapsed_ticks: 1200,
        limit_ticks: 36000,
        paused: false,
        pause_reason: null,
      },
    });
    store.applyHud(h2);
    view.frame(h2, store);
    expect(bar(panels)).toBe(
      "Nodes held4 of 5|ObjectiveHold Haven08:00|War clock58:00",
    );
  });

  it("a Hud before any Snapshot still renders", () => {
    const { panels, store, view } = setup();
    const h = hud();
    store.applyHud(h);
    view.frame(h, store);
    expect(bar(panels)).toBe(
      "Nodes held3 of 5|ObjectiveHold Haven08:20|War clock58:20",
    );
  });

  it("a Snapshot without a Hud keeps the clock and does not rebase the stale Hud", () => {
    const { panels, store, view } = setup();
    const s1 = snapshot(1000, hud());
    store.applySnapshot(s1);
    view.frame(s1, store);
    const s2 = snapshot(1050, null); // store keeps the old Hud
    store.applySnapshot(s2);
    view.frame(s2, store);
    expect(text(panels, "nx-obj")).toBe("ObjectiveHold Haven08:15"); // +50 ticks, not reset to 08:20
  });
});
