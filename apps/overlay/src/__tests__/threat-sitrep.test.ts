import { describe, expect, it } from "vitest";
import type { Event, ThreatAdaptation } from "../contracts/events/event";
import { HudOverlay } from "../hud/hud-overlay";
import { ThreatSitrepBoard, sitrepLines } from "../hud/threat-sitrep";
import type { SitrepView } from "../hud/threat-sitrep";
import { STRAIT_1_THEATER } from "../theater/strait1";
import { SimulationFeedGenerator } from "../simulation/mock-feed";
import { createElement } from "../utils/dom";
import { expectUnderBudget } from "./perf-gate";

// OVERLAY OV-26 (NX-496): the threat sitrep stack.

let seq = 0;
function ev(
  category: ThreatAdaptation["category"],
  over: Partial<ThreatAdaptation> = {},
): ThreatAdaptation {
  seq++;
  return {
    kind: "ThreatAdaptation",
    tick: 100,
    event_seq: seq,
    campaign_id: "0190a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b",
    side: "ENEMY",
    category,
    sector_id: "north",
    direction: "UP",
    node_id: null,
    credit_ids: [],
    ...over,
  };
}

const CALLSIGNS: Record<number, string> = { 101: "VIPER-01", 102: "GHOST-1" };
const callsignOf = (id: number) => CALLSIGNS[id];

function boardWith(...events: Event[]): ThreatSitrepBoard {
  const board = new ThreatSitrepBoard();
  board.ingest(events, callsignOf);
  return board;
}

function linesAt(view: SitrepView): string[] {
  return view.shown.map((e) => {
    const l = sitrepLines(e, STRAIT_1_THEATER);
    return `${l.kicker} | ${l.headline}${l.credit ? ` | ${l.credit}` : ""}`;
  });
}

describe("OV-26 mapping: every category renders its tier and wording", () => {
  const cases: Array<[ThreatAdaptation, string]> = [
    [
      ev("SANCTUARY_AT_RISK", { sector_id: "centre", node_id: "haven" }),
      "LAST STAND · Centre | NULL strikes Haven Sanctuary, the sanctuary is at risk",
    ],
    [
      ev("HOLD_AT_RISK", { node_id: "cross-n" }),
      "ALERT · North | NULL moves on North Crossing, the hold is at risk",
    ],
    [
      ev("STAGING", { sector_id: "south" }),
      "ALERT · South | NULL forces are massing in South",
    ],
    [
      ev("STAGING_LAUNCHED"),
      "ALERT · North | NULL assault launching from North",
    ],
    [ev("STAGING_DISPERSED"), "EASING · North | massing disperses"],
    [
      ev("STRIKE_DOWNED", {
        sector_id: "centre",
        node_id: "west-airbase",
        credit_ids: [101, 102],
      }),
      "WIN · Centre | NULL strike package downed near West Airbase | Credit: VIPER-01, GHOST-1",
    ],
    [
      ev("IADS_REINFORCED"),
      "INTEL · North | NULL reinforces its air defense in North",
    ],
    [
      ev("IADS_REINFORCED", { direction: "DOWN" }),
      "EASING · North | NULL air defense back to normal in North",
    ],
    [
      ev("CONVOY_ESCORT"),
      "INTEL · North | NULL convoys now run with escorts in North",
    ],
    [
      ev("CONVOY_ESCORT", { direction: "DOWN" }),
      "EASING · North | NULL convoy escorts stand down in North",
    ],
  ];
  for (const [event, expected] of cases) {
    it(`${event.category} ${event.direction}`, () => {
      expect(linesAt(boardWith(event).view(100))).toEqual([expected]);
    });
  }

  it("shows an unknown id as-is and a missing node as a dash (DI-1)", () => {
    const view = boardWith(
      ev("HOLD_AT_RISK", { sector_id: "far-east", node_id: null }),
    ).view(100);
    expect(linesAt(view)).toEqual([
      "ALERT · far-east | NULL moves on —, the hold is at risk",
    ]);
  });

  it("credits unresolved units as a count and shows no line without credits", () => {
    const view = boardWith(
      ev("STRIKE_DOWNED", { node_id: "bridge-n", credit_ids: [7, 101, 9] }),
    ).view(100);
    expect(view.shown[0]?.credit).toBe("Credit: VIPER-01 +2");
    const none = boardWith(
      ev("STRIKE_DOWNED", { node_id: "bridge-n", credit_ids: [7] }),
    ).view(100);
    expect(none.shown[0]?.credit).toBe("Credit: +1");
    expect(boardWith(ev("STAGING")).view(100).shown[0]?.credit).toBeNull();
  });

  it("ignores events that are not ThreatAdaptation", () => {
    const tier: Event = {
      kind: "ThreatTierChanged",
      tick: 100,
      event_seq: 99,
      campaign_id: "0190a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b",
      side: "ENEMY",
      from: "ALPHA",
      to: "BRAVO",
      cp_smoothed: 12,
    };
    expect(boardWith(tier).view(100)).toEqual({ shown: [], hiddenCount: 0 });
  });
});

describe("OV-26 ordering", () => {
  it("puts SANCTUARY_AT_RISK on top whatever the arrival order, then by tier", () => {
    const board = boardWith(
      ev("CONVOY_ESCORT", { sector_id: "south" }),
      ev("STRIKE_DOWNED", { node_id: "bridge-n" }),
      ev("STAGING", { sector_id: "south" }),
      ev("SANCTUARY_AT_RISK", { sector_id: "centre", node_id: "haven" }),
    );
    const view = board.view(100);
    expect(view.shown.map((e) => e.event.category)).toEqual([
      "SANCTUARY_AT_RISK",
      "STAGING",
      "STRIKE_DOWNED",
    ]);
    expect(view.hiddenCount).toBe(1);
  });

  it("ranks an active adaptation above one that is easing", () => {
    const board = boardWith(
      ev("CONVOY_ESCORT", { sector_id: "south" }),
      ev("IADS_REINFORCED", { direction: "DOWN" }),
    );
    expect(board.view(100).shown.map((e) => e.tier)).toEqual(["INTEL", "EASE"]);
  });

  it("orders alerts hold, launch, massing, then newest first", () => {
    const board = boardWith(
      ev("STAGING", { sector_id: "south" }),
      ev("STAGING", { sector_id: "centre" }),
      ev("HOLD_AT_RISK", { node_id: "cross-n" }),
    );
    expect(board.view(100).shown.map((e) => e.event.sector_id)).toEqual([
      "north",
      "centre",
      "south",
    ]);
  });
});

describe("OV-26 expiry (game ticks)", () => {
  it("keeps a card for its tier's life and drops it at the end", () => {
    const board = boardWith(
      ev("SANCTUARY_AT_RISK", { tick: 1000, node_id: "haven" }), // 60 s
      ev("STAGING", { tick: 1000 }), // 30 s
      ev("CONVOY_ESCORT", { tick: 1000 }), // 15 s
    );
    expect(board.view(1149).shown).toHaveLength(3);
    expect(board.view(1150).shown).toHaveLength(2);
    expect(board.view(1299).shown).toHaveLength(2);
    expect(board.view(1300).shown.map((e) => e.event.category)).toEqual([
      "SANCTUARY_AT_RISK",
    ]);
    expect(board.view(1599).shown).toHaveLength(1);
    expect(board.view(1600)).toEqual({ shown: [], hiddenCount: 0 });
  });

  it("a hidden card still expires on its own clock", () => {
    const board = boardWith(
      ev("CONVOY_ESCORT", { tick: 0, sector_id: "south" }),
      ev("SANCTUARY_AT_RISK", { tick: 0, node_id: "haven" }),
      ev("HOLD_AT_RISK", { tick: 0, node_id: "cross-n" }),
      ev("STAGING", { tick: 0, sector_id: "centre" }),
    );
    expect(board.view(0).hiddenCount).toBe(1);
    expect(board.view(150).hiddenCount).toBe(0);
  });
});

describe("OV-26 dedupe", () => {
  it("a repeat in the same sector and node refreshes one card", () => {
    const board = boardWith(
      ev("SANCTUARY_AT_RISK", { tick: 0, node_id: "haven" }),
      ev("SANCTUARY_AT_RISK", { tick: 500, node_id: "haven" }),
    );
    const view = board.view(700);
    expect(view.shown).toHaveLength(1);
    expect(view.shown[0]?.event.tick).toBe(500);
  });

  it("a stale or replayed event never replaces a newer card", () => {
    const newer = ev("HOLD_AT_RISK", { tick: 300, node_id: "cross-n" });
    const older = { ...newer, event_seq: newer.event_seq - 1, tick: 10 };
    const board = boardWith(newer, older);
    expect(board.view(300).shown.map((e) => e.event.tick)).toEqual([300]);
  });

  it("a payoff closes the massing card of its sector only", () => {
    const board = boardWith(
      ev("STAGING", { sector_id: "north" }),
      ev("STAGING", { sector_id: "south" }),
      ev("STAGING_LAUNCHED", { sector_id: "north" }),
      ev("STAGING_DISPERSED", { sector_id: "south" }),
    );
    expect(
      board
        .view(100)
        .shown.map((e) => `${e.event.category}@${e.event.sector_id}`),
    ).toEqual(["STAGING_LAUNCHED@north", "STAGING_DISPERSED@south"]);
  });

  it("a DOWN replaces the UP of its category and sector", () => {
    const board = boardWith(
      ev("IADS_REINFORCED"),
      ev("IADS_REINFORCED", { direction: "DOWN" }),
    );
    expect(board.view(100).shown.map((e) => e.tier)).toEqual(["EASE"]);
  });

  it("a new campaign clears the old campaign's cards", () => {
    const board = boardWith(
      ev("SANCTUARY_AT_RISK", {
        event_seq: 500,
        tick: 900000,
        node_id: "haven",
        campaign_id: "c1",
      }),
      ev("SANCTUARY_AT_RISK", {
        event_seq: 3,
        tick: 20,
        node_id: "haven",
        campaign_id: "c2",
      }),
    );
    const view = board.view(25);
    expect(view.shown.map((e) => e.event.campaign_id)).toEqual(["c2"]);
    expect(view.hiddenCount).toBe(0);
  });

  it("different nodes keep separate cards", () => {
    const board = boardWith(
      ev("HOLD_AT_RISK", { node_id: "cross-n" }),
      ev("HOLD_AT_RISK", { node_id: "fob-n-w" }),
    );
    expect(board.view(100).shown).toHaveLength(2);
  });
});

describe("OV-26 event to HUD", () => {
  function mountHud(): { hud: HudOverlay; root: HTMLElement } {
    const root = createElement("div");
    const hud = new HudOverlay();
    hud.initialize(root);
    return { hud, root };
  }

  it("renders the stack, most urgent first, with a hidden count", () => {
    const { hud, root } = mountHud();
    const board = boardWith(
      ev("CONVOY_ESCORT", { sector_id: "south" }),
      ev("HOLD_AT_RISK", { node_id: "cross-n" }),
      ev("STAGING", { sector_id: "centre" }),
      ev("SANCTUARY_AT_RISK", { sector_id: "centre", node_id: "haven" }),
    );
    hud.updateThreatSitreps(board.view(100));

    const cards = root.querySelectorAll(".sitrep-card");
    expect(cards).toHaveLength(3);
    expect(cards[0]?.className).toContain("sitrep-LAST_STAND");
    expect(cards[0]?.textContent).toContain(
      "NULL strikes Haven Sanctuary, the sanctuary is at risk",
    );
    expect(cards[1]?.textContent).toContain("NULL moves on North Crossing");
    expect(root.querySelector(".sitrep-more")?.textContent).toBe("+1 more");
    hud.dispose();
  });

  it("keeps the DOM when nothing changed and clears when all expired", () => {
    const { hud, root } = mountHud();
    const board = boardWith(ev("STAGING", { tick: 0 }));
    hud.updateThreatSitreps(board.view(0));
    const first = root.querySelector(".sitrep-card");
    hud.updateThreatSitreps(board.view(10));
    expect(root.querySelector(".sitrep-card")).toBe(first);
    hud.updateThreatSitreps(board.view(300));
    expect(root.querySelectorAll(".sitrep-card")).toHaveLength(0);
    expect(root.querySelector(".sitrep-more")).toBeNull();
    hud.dispose();
  });

  it("updates the hidden count when only hidden cards expire", () => {
    const { hud, root } = mountHud();
    const board = boardWith(
      ev("SANCTUARY_AT_RISK", { tick: 0, node_id: "haven" }),
      ev("HOLD_AT_RISK", { tick: 0, node_id: "cross-n" }),
      ev("STAGING", { tick: 0, sector_id: "centre" }),
      ev("CONVOY_ESCORT", { tick: 0, sector_id: "south" }),
      ev("IADS_REINFORCED", { tick: 100, sector_id: "south" }),
    );
    hud.updateThreatSitreps(board.view(0));
    expect(root.querySelector(".sitrep-more")?.textContent).toBe("+2 more");
    hud.updateThreatSitreps(board.view(150)); // convoy card (hidden) expired
    expect(root.querySelector(".sitrep-more")?.textContent).toBe("+1 more");
    hud.updateThreatSitreps(board.view(250)); // air defense card expired too
    expect(root.querySelector(".sitrep-more")).toBeNull();
    expect(root.querySelectorAll(".sitrep-card")).toHaveLength(3);
    hud.dispose();
  });

  it("redraws a card when a new campaign restarts the same slot and seq", () => {
    const { hud, root } = mountHud();
    const board = new ThreatSitrepBoard();
    const first = ev("STRIKE_DOWNED", {
      node_id: "bridge-n",
      credit_ids: [101],
    });
    board.ingest([{ ...first, event_seq: 1, campaign_id: "c1" }], callsignOf);
    hud.updateThreatSitreps(board.view(100));
    expect(root.querySelector(".sitrep-credit")?.textContent).toBe(
      "Credit: VIPER-01",
    );
    const next = ev("STRIKE_DOWNED", {
      node_id: "bridge-n",
      credit_ids: [102],
    });
    board.ingest([{ ...next, event_seq: 1, campaign_id: "c2" }], callsignOf);
    hud.updateThreatSitreps(board.view(100));
    expect(root.querySelector(".sitrep-credit")?.textContent).toBe(
      "Credit: GHOST-1",
    );
    hud.dispose();
  });

  it("redraws a card when its slot gets a newer event", () => {
    const { hud, root } = mountHud();
    const board = new ThreatSitrepBoard();
    board.ingest(
      [ev("STRIKE_DOWNED", { node_id: "bridge-n", credit_ids: [101] })],
      callsignOf,
    );
    hud.updateThreatSitreps(board.view(100));
    expect(root.querySelector(".sitrep-credit")?.textContent).toBe(
      "Credit: VIPER-01",
    );
    board.ingest(
      [ev("STRIKE_DOWNED", { node_id: "bridge-n", credit_ids: [102] })],
      callsignOf,
    );
    hud.updateThreatSitreps(board.view(100));
    expect(root.querySelector(".sitrep-credit")?.textContent).toBe(
      "Credit: GHOST-1",
    );
    hud.dispose();
  });

  it("puts sitrep text on screen as text, never markup (OV-9)", () => {
    const { hud, root } = mountHud();
    const board = boardWith(
      ev("STAGING", { sector_id: "<img src=x onerror=alert(1)>" }),
    );
    hud.updateThreatSitreps(board.view(100));
    const headline = root.querySelector(".sitrep-headline");
    expect(headline?.textContent).toBe(
      "NULL forces are massing in <img src=x onerror=alert(1)>",
    );
    hud.dispose();
  });

  it("the feed's frame events reach the board", () => {
    const feed = new SimulationFeedGenerator();
    const board = new ThreatSitrepBoard();
    let frame = feed.generateFrameState();
    for (let i = 1; i < 90; i++) {
      expect(frame.events).toEqual([]);
      frame = feed.generateFrameState();
    }
    board.ingest(frame.events ?? [], callsignOf);
    expect(linesAt(board.view(frame.tick))).toEqual([
      "ALERT · North | NULL forces are massing in North",
    ]);
  });

  it("stays inside the frame budget over a long run (perf-gated)", () => {
    const { hud } = mountHud();
    const board = new ThreatSitrepBoard();
    const categories: ThreatAdaptation["category"][] = [
      "STAGING",
      "HOLD_AT_RISK",
      "SANCTUARY_AT_RISK",
      "STRIKE_DOWNED",
    ];
    const frames = 5000;
    const t0 = performance.now();
    for (let tick = 0; tick < frames; tick++) {
      const events =
        tick % 20 === 0
          ? [
              ev(categories[(tick / 20) % 4] ?? "STAGING", {
                tick,
                node_id: "haven",
              }),
            ]
          : [];
      board.ingest(events, callsignOf);
      hud.updateThreatSitreps(board.view(tick));
    }
    const meanMs = (performance.now() - t0) / frames;
    expectUnderBudget(meanMs, 0.5);
    hud.dispose();
  });
});
