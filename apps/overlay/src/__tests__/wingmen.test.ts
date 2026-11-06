import { describe, expect, it } from "vitest";
import type { PublicEvent } from "../contracts/wire/hud";
import type { EntityView } from "../contracts/wire/snapshot";
import type { FinalHoursCard } from "../hud/final-hours";
import { SitrepStack } from "../hud/sitrep-stack";
import { MAX_SHOWN } from "../hud/threat-sitrep";
import { WING_TTL_TICKS, WingmenFeed } from "../hud/wingmen";
import { mapFrame } from "../stage-math";
import { drawWorld, type Scene } from "../units";

// NX-511: AI wingmen feed line and tether (GAMEPLAY §1b item 246, Q-GP-51).
type Op = [string, unknown[]];
const ent = (id: number, over: Partial<EntityView> = {}): EntityView => ({
  entity_id: id,
  unit_kind: "STRIKE_FIGHTER",
  side: "COALITION",
  domain: "AIR",
  owner_kind: "COMMANDER",
  callsign: null,
  pos: { x_m: 100000 + id * 1000, y_m: 100000 },
  heading_deg: 0,
  speed_mps: 0,
  hp_pct: 100,
  damage_state: "HEALTHY",
  painted: false,
  spotted: null,
  package_id: null,
  follow_entity_id: null,
  follower_count: 0,
  cosmetic: { halo: null, trail: null },
  badges: [],
  probation: false,
  auto: false,
  ...over,
});
const wingman = (id: number, lead: number, over: Partial<EntityView> = {}) =>
  ent(id, { owner_kind: "AI_GARRISON", follow_entity_id: lead, ...over });
const map = (l: EntityView[]) => new Map(l.map((e) => [e.entity_id, e]));

/** Count the tether strokes: a lone moveTo + lineTo pair followed by a stroke (a glyph has many vertices). */
function tethers(list: EntityView[]): number {
  const ops: Op[] = [];
  const ctx = new Proxy(
    {},
    {
      get:
        (_t, n: string) =>
        (...a: unknown[]) =>
          void ops.push([n, a]),
      set: () => true,
    },
  ) as unknown as CanvasRenderingContext2D;
  const entities = map(list);
  const s: Scene = {
    entities,
    blobs: [],
    lastKnown: [],
    pose: (id) => {
      const e = entities.get(id);
      return e && { ...e.pos, heading_deg: 0 };
    },
    ageSec: () => 0,
  };
  drawWorld(ctx, mapFrame({ w: 400000, h: 240000 }), s);
  return ops.filter(
    (o, i) =>
      o[0] === "moveTo" &&
      ops[i + 1]?.[0] === "lineTo" &&
      ops[i + 2]?.[0] === "stroke",
  ).length;
}

describe("wingman tether", () => {
  it("one line per AI follower with a live lead", () => {
    expect(tethers([ent(1), wingman(2, 1), wingman(3, 1)])).toBe(2);
  });
  it("none for a viewer follower, a missing lead, or a non-follower", () => {
    expect(tethers([ent(1), ent(2, { follow_entity_id: 1 })])).toBe(0);
    expect(tethers([wingman(2, 99)])).toBe(0);
    expect(tethers([ent(1), wingman(2, 1, { follow_entity_id: null })])).toBe(
      0,
    );
  });
  it("none when the followed unit is itself an AI unit", () => {
    expect(tethers([wingman(1, 9), wingman(2, 1)])).toBe(0);
  });
  it("none when a pose is not finite", () => {
    const bad = { x_m: NaN, y_m: 0 };
    expect(tethers([ent(1, { pos: bad }), wingman(2, 1)])).toBe(0);
    expect(tethers([ent(1), wingman(2, 1, { pos: bad })])).toBe(0);
  });
  it("none for an enemy follower", () => {
    expect(tethers([ent(1), wingman(2, 1, { side: "ENEMY" })])).toBe(0);
  });
});

const spawn = (id: number, seq: number, over: Record<string, unknown> = {}) =>
  ({
    kind: "UnitSpawned",
    tick: 50,
    event_seq: seq,
    campaign_id: "c1",
    entity_id: id,
    side: "COALITION",
    owner_kind: "AI_GARRISON",
    ...over,
  }) as unknown as PublicEvent;

describe("wingmen feed line", () => {
  const world = (cs: string | null = "VIPER-27") =>
    map([ent(1, { callsign: cs }), wingman(2, 1), wingman(3, 1)]);
  const text = (f: WingmenFeed, t = 50) => f.view(t).map((l) => l.text);

  it("singular for one, plural for two, one line per lead", () => {
    const f = new WingmenFeed();
    f.ingest([spawn(2, 1)], world());
    expect(text(f)).toEqual(["VIPER-27 leads 1 [AI] wingman"]);
    const g = new WingmenFeed();
    g.ingest([spawn(2, 1), spawn(3, 2)], world());
    expect(text(g)).toEqual(["VIPER-27 leads 2 [AI] wingmen"]);
  });
  it("a missing callsign shows the dash", () => {
    const f = new WingmenFeed();
    f.ingest([spawn(2, 1)], world(null));
    expect(text(f)).toEqual(["— leads 1 [AI] wingman"]);
  });
  it("a replayed Delta adds nothing; a new campaign restarts", () => {
    const f = new WingmenFeed();
    f.ingest([spawn(2, 5), spawn(3, 6)], world());
    f.ingest([spawn(2, 5), spawn(3, 6)], world());
    expect(text(f)).toEqual(["VIPER-27 leads 2 [AI] wingmen"]);
    expect(text(f, 500)).toEqual([]); // expired
    f.ingest([spawn(2, 5), spawn(3, 6)], world());
    expect(text(f, 60)).toEqual([]); // a replay does not bring it back
    f.ingest([spawn(2, 1, { campaign_id: "c2" })], world());
    expect(text(f)).toEqual(["VIPER-27 leads 1 [AI] wingman"]);
  });
  it("ignores a wingman that follows an AI unit", () => {
    const f = new WingmenFeed();
    f.ingest([spawn(3, 1)], map([wingman(2, 9), wingman(3, 2)]));
    expect(text(f)).toEqual([]);
  });
  it("ignores viewer spawns, enemy spawns, and followers of no live lead", () => {
    const f = new WingmenFeed();
    f.ingest(
      [
        spawn(2, 1, { owner_kind: "COMMANDER" }),
        spawn(2, 2, { side: "ENEMY" }),
        spawn(9, 3),
      ],
      world(),
    );
    expect(text(f)).toEqual([]);
  });
  it("expires after the TTL in game ticks", () => {
    const f = new WingmenFeed();
    f.ingest([spawn(2, 1)], world());
    expect(text(f, 50 + WING_TTL_TICKS - 1)).toHaveLength(1);
    expect(text(f, 50 + WING_TTL_TICKS)).toHaveLength(0);
  });
});

class El {
  children: El[] = [];
  className = "";
  text = "";
  set textContent(v: string) {
    this.text = v;
  }
  appendChild(c: El): El {
    this.children.push(c);
    return c;
  }
  replaceChildren(...c: El[]): void {
    this.children = c;
  }
  setAttribute(): void {}
  all(): string[] {
    return [this.text, ...this.children.flatMap((c) => c.all())];
  }
}

describe("wingmen on the sitrep stack", () => {
  it("renders a hostile callsign as literal text", () => {
    const bad = "<img src=x onerror=alert(1)>";
    const doc = { createElement: () => new El() } as unknown as Document;
    const root = new El();
    const feed = new WingmenFeed();
    const stack = new SitrepStack(
      doc,
      root as unknown as HTMLElement,
      () => undefined,
      () => ({ sectors: [], nodes: [] }),
      () => null,
      feed,
    );
    feed.ingest([spawn(2, 1)], map([ent(1, { callsign: bad }), wingman(2, 1)]));
    stack.render(50);
    expect(root.all()).toContain(`${bad} leads 1 [AI] wingman`);
    expect(root.children[0]?.className).toContain("nx-tier-WING");
  });
});

describe("wing lines and the OV-26 cap", () => {
  const threat = (n: number) =>
    ({
      kind: "ThreatAdaptation",
      tick: 1,
      event_seq: n,
      campaign_id: "c1",
      category: "SANCTUARY_AT_RISK",
      direction: "UP",
      sector_id: `s${n}`,
      node_id: null,
      credit_ids: [],
    }) as unknown as PublicEvent;
  function stack(threats: number, wings: number) {
    const doc = { createElement: () => new El() } as unknown as Document;
    const root = new El();
    const feed = new WingmenFeed();
    const st = new SitrepStack(
      doc,
      root as unknown as HTMLElement,
      () => undefined,
      () => ({ sectors: [], nodes: [] }),
      () => null,
      feed,
    );
    const list = [ent(1, { callsign: "A" }), ent(5, { callsign: "B" })];
    const ev: PublicEvent[] = [];
    for (let i = 0; i < wings; i++) {
      list.push(wingman(10 + i, i === 0 ? 1 : 5));
      ev.push(spawn(10 + i, 100 + i));
    }
    feed.ingest(ev, map(list));
    st.ingest(
      Array.from({ length: threats }, (_, i) => threat(i + 1)),
      5,
    );
    const kids = root.children;
    return {
      wing: kids.filter((k) => k.className.includes("nx-tier-WING")).length,
      more: kids.filter((k) => k.className === "nx-more").map((k) => k.text),
    };
  }
  it("3 threat cards leave no room: no wing card, no +N more for it", () => {
    expect(stack(3, 1)).toEqual({ wing: 0, more: [] });
  });
  it("2 threat cards + 2 wing lines: one wing card, the hidden one is not counted", () => {
    expect(stack(2, 2)).toEqual({ wing: 1, more: [] });
  });
  it("threat overflow still shows +N more", () => {
    expect(stack(5, 1)).toEqual({ wing: 0, more: ["+2 more"] });
  });
});

describe("wing lines with the FINAL HOURS card (NX-511 + NX-515)", () => {
  it("the FINAL HOURS card takes a slot first; wing lines fill only what is left", () => {
    const doc = { createElement: () => new El() } as unknown as Document;
    const root = new El();
    const feed = new WingmenFeed();
    const card = {
      phase: 1,
      kicker: "FINAL HOURS · 6 h left",
      lines: ["a", "b"],
    } as const;
    const st = new SitrepStack(
      doc,
      root as unknown as HTMLElement,
      () => undefined,
      () => ({ sectors: [], nodes: [] }),
      () => card as unknown as FinalHoursCard,
      feed,
    );
    const leads = [1, 3, 5].map((id) => ent(id, { callsign: `L${id}` }));
    feed.ingest(
      [spawn(2, 10), spawn(4, 11), spawn(6, 12)],
      map([...leads, wingman(2, 1), wingman(4, 3), wingman(6, 5)]),
    );
    st.render(50);
    const tiers = root.children.map((k) => k.className);
    expect(tiers.filter((c) => c.includes("nx-tier-FINAL_HOURS"))).toHaveLength(
      1,
    );
    expect(tiers.filter((c) => c.includes("nx-tier-WING"))).toHaveLength(
      MAX_SHOWN - 1,
    );
    expect(tiers.some((c) => c.includes("nx-more"))).toBe(false);
  });
});
