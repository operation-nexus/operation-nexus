import { describe, expect, it } from "vitest";
import type { PublicEvent } from "../contracts/wire/hud";
import type { EntityView } from "../contracts/wire/snapshot";
import { SitrepStack } from "../hud/sitrep-stack";
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
      feed,
    );
    feed.ingest([spawn(2, 1)], map([ent(1, { callsign: bad }), wingman(2, 1)]));
    stack.render(50);
    expect(root.all()).toContain(`${bad} leads 1 [AI] wingman`);
    expect(root.children[0]?.className).toContain("nx-tier-WING");
  });
});
