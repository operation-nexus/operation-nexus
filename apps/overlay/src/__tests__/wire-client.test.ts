import { decode, encode } from "@msgpack/msgpack";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { startFeed, WS_PATH } from "../net/start";
import { bannerText, renderBanner, type ConnState } from "../net/banner";
import {
  BACKOFF_MIN_MS,
  backoffMs,
  PROTOCOL_V,
  MIN_UPTIME_FOR_RELOAD_MS,
  RELOAD_BACKOFF_MS,
  RELOAD_DELAY_MS,
  RESYNC_ACK_MS,
  STALE_MS,
  takeToken,
  WireClient,
  type SocketLike,
} from "../net/wire-client";

class FakeSocket implements SocketLike {
  binaryType = "";
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: unknown }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;
  sent: Record<string, unknown>[] = [];
  send(d: Uint8Array): void {
    this.sent.push(decode(d) as Record<string, unknown>);
  }
  close(): void {}
  recv(frame: unknown): void {
    const b = encode(frame);
    const ab = b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
    this.onmessage?.({ data: ab });
  }
}

const hud = {
  type: "Hud",
  v: PROTOCOL_V,
  momentum_pct: 50,
  momentum_breakdown: null,
  objective_mode: "OFF",
  objective: null,
  threat_tier: "ALPHA",
  nodes_held: 0,
  nodes_total: 0,
  campaign_clock: {
    elapsed_ticks: 0,
    limit_ticks: null,
    paused: false,
    pause_reason: null,
  },
  time_limit_score: null,
  ticker: [],
  panels: { campaign_status: {}, tasking_needed: [], top_commanders: [] },
  active_humans: null,
  operators: null,
};
const welcome = (): unknown => ({
  type: "Welcome",
  v: PROTOCOL_V,
  theater: { nodes: [], edges: [], terrain_ref: null },
});
const snap = (tick: number, extra: object = {}): unknown => ({
  type: "Snapshot",
  v: PROTOCOL_V,
  tick,
  entities: [{ entity_id: 1, hp_pct: 100 }],
  nodes: [{ node_id: "n1", owner: "NEUTRAL" }],
  blobs: [],
  last_known: [],
  hud,
  ...extra,
});
const delta = (
  tick: number,
  base_tick: number,
  extra: object = {},
): unknown => ({
  type: "Delta",
  v: PROTOCOL_V,
  tick,
  base_tick,
  upserts: [],
  removes: [],
  node_patches: [],
  blobs: null,
  last_known: null,
  events: [],
  ...extra,
});

let socks: FakeSocket[];
let states: ConnState[];
let reload: ReturnType<typeof vi.fn<(t: string) => void>>;
let uptime = 1e9;
function make(
  random = () => 0.5,
  onFrame?: (f: { type: string }) => void,
): { c: WireClient; s: () => FakeSocket } {
  const c = new WireClient({
    url: "ws://x/ws",
    token: "tok",
    makeSocket: () => {
      const s = new FakeSocket();
      socks.push(s);
      return s;
    },
    random,
    uptimeMs: () => uptime,
    reload,
    onState: (st) => states.push(st),
    ...(onFrame ? { onFrame } : {}),
  });
  c.start();
  return { c, s: () => socks[socks.length - 1] as FakeSocket };
}

beforeEach(() => {
  vi.useFakeTimers();
  socks = [];
  states = [];
  uptime = 1e9;
  reload = vi.fn<(t: string) => void>();
});
afterEach(() => vi.useRealTimers());

describe("token", () => {
  it("is read from the hash and cleared with replaceState", () => {
    const replaceState = vi.fn();
    const loc = { hash: "#token=abc%20d", pathname: "/o", search: "?a=1" };
    expect(
      takeToken(loc as Location, { replaceState } as unknown as History),
    ).toBe("abc d");
    expect(replaceState).toHaveBeenCalledWith(null, "", "/o?a=1");
  });
  it("keeps a literal + and treats a malformed escape as absent", () => {
    const h = { replaceState: vi.fn() } as unknown as History;
    const at = (hash: string) =>
      takeToken({ hash, pathname: "/", search: "" } as Location, h);
    expect(at("#x=1&token=a+b/c==")).toBe("a+b/c==");
    expect(at("#token=a%2Bb")).toBe("a+b");
    expect(at("#token=%E0%A4%A")).toBeNull();
    expect(at("#xtoken=abc")).toBeNull();
  });
  it("is null when absent", () => {
    const h = { replaceState: vi.fn() } as unknown as History;
    expect(
      takeToken({ hash: "", pathname: "/", search: "" } as Location, h),
    ).toBeNull();
  });
});

describe("handshake and store", () => {
  it("sends Hello on open", () => {
    const { s } = make();
    s().onopen?.();
    expect(s().sent[0]).toEqual({
      type: "Hello",
      v: PROTOCOL_V,
      client_kind: "OVERLAY",
      capability_token: "tok",
      last_tick: null,
    });
  });

  it("applies Snapshot then Deltas and acks", () => {
    const { c, s } = make();
    s().recv(welcome());
    s().recv(snap(10));
    s().recv(
      delta(11, 10, {
        upserts: [
          { entity_id: 1, hp_pct: 50 },
          { entity_id: 2, hp_pct: 9 },
        ],
        node_patches: [{ node_id: "n1", owner: "ENEMY" }],
        blobs: [{ blob_id: 1 }],
      }),
    );
    s().recv(delta(12, 11, { removes: [2] }));
    expect(c.store.tick).toBe(12);
    expect(c.store.entities.get(1)).toMatchObject({ hp_pct: 50 });
    expect(c.store.entities.has(2)).toBe(false);
    expect(c.store.nodes.get("n1")).toMatchObject({ owner: "ENEMY" });
    expect(c.store.blobs).toHaveLength(1); // null on the next delta = unchanged
    expect(s().sent.map((a) => a["applied_tick"])).toEqual([11, 12]);
  });

  it("drops frames before Welcome and unknown or malformed frames", () => {
    const { c, s } = make();
    s().recv(snap(5));
    expect(c.store.tick).toBeNull();
    s().recv(welcome());
    s().recv({ type: "Bogus", v: "0.1" });
    s().recv({ type: "Delta", tick: "x" });
    s().recv(snap(5));
    expect(c.store.tick).toBe(5);
  });

  it("asks for a resync on a gap", () => {
    const { c, s } = make();
    s().recv(welcome());
    s().recv(snap(10));
    s().recv(delta(13, 12));
    expect(s().sent).toEqual([
      { type: "Ack", v: PROTOCOL_V, applied_tick: 10 },
    ]);
    expect(c.store.tick).toBeNull();
    expect(c.store.entities.size).toBe(1); // the last data stays until the Snapshot
  });

  it("accepts a lower tick after a fresh Welcome", () => {
    const { c, s } = make();
    s().recv(welcome());
    s().recv(snap(500));
    s().recv(welcome());
    s().recv(snap(3));
    s().recv(delta(4, 3));
    expect(c.store.tick).toBe(4);
  });

  it("Control RESYNC keeps the last data and waits for a Snapshot", () => {
    const { c, s } = make();
    s().recv(welcome());
    s().recv(snap(10));
    s().recv({ type: "Control", v: PROTOCOL_V, action: "RESYNC" });
    expect(c.store.entities.size).toBe(1);
    s().recv(delta(11, 10));
    expect(c.store.tick).toBeNull();
    s().recv(snap(11));
    expect(c.store.tick).toBe(11);
  });

  it("Control RELOAD shows UPDATE REQUIRED and reloads after a delay", () => {
    const { s } = make();
    s().recv(welcome());
    s().recv({ type: "Control", v: PROTOCOL_V, action: "RELOAD" });
    expect(states.at(-1)?.fatal).toBe("UPDATE_REQUIRED");
    expect(reload).not.toHaveBeenCalled();
    vi.advanceTimersByTime(RELOAD_DELAY_MS);
    expect(reload).toHaveBeenCalledWith("tok");
  });
});

describe("reconnect", () => {
  it("bounds and jitters the backoff", () => {
    expect(backoffMs(0, () => 0.99)).toBe(500);
    expect(backoffMs(3, () => 0)).toBe(500);
    expect(backoffMs(3, () => 1)).toBe(4000);
    expect(backoffMs(30, () => 1)).toBe(10_000);
    expect(backoffMs(30, () => 0.5)).toBe(5250);
  });

  it("retries with growing delay on an ordinary close and resets on Welcome", () => {
    const { s } = make(() => 1);
    s().onclose?.({ code: 1001 });
    vi.advanceTimersByTime(499);
    expect(socks).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(socks).toHaveLength(2);
    s().onclose?.({ code: 1006 });
    vi.advanceTimersByTime(999);
    expect(socks).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(socks).toHaveLength(3);
    s().recv(welcome());
    s().onclose?.({ code: 1006 });
    vi.advanceTimersByTime(500);
    expect(socks).toHaveLength(4);
  });

  it("retries after a socket error, once", () => {
    const { s } = make(() => 0);
    s().onerror?.();
    vi.advanceTimersByTime(500);
    expect(socks).toHaveLength(2);
  });

  it.each([
    [4002, "AUTH FAILED"],
    [4003, "UPDATE REQUIRED"],
  ])("does not retry on close %i", (code, text) => {
    const { s } = make();
    s().onclose?.({ code });
    vi.advanceTimersByTime(60_000);
    expect(socks).toHaveLength(1);
    expect(bannerText(states.at(-1) as ConnState)).toBe(text);
  });
});

describe("banners", () => {
  it("shows COMMS RESYNC after 2 s without data and clears on data", () => {
    const { s } = make();
    vi.advanceTimersByTime(STALE_MS);
    expect(states.at(-1)?.stale).toBe(true);
    s().recv(welcome());
    expect(states.at(-1)?.stale).toBe(true); // a Welcome is not data
    s().recv(snap(1));
    expect(states.at(-1)?.stale).toBe(false);
  });

  it("UPDATE REQUIRED outranks COMMS RESYNC", () => {
    const base = { hadData: true };
    expect(bannerText({ ...base, fatal: null, stale: true })).toBe(
      "COMMS RESYNC",
    );
    expect(bannerText({ ...base, fatal: "UPDATE_REQUIRED", stale: true })).toBe(
      "UPDATE REQUIRED",
    );
    expect(bannerText({ ...base, fatal: null, stale: false })).toBeNull();
  });

  it("dims the last frame under a banner; cold start is not dimmed", () => {
    const toggles: boolean[] = [];
    const dim = {
      classList: { toggle: (_: string, on: boolean) => toggles.push(on) },
    };
    const dataset: Record<string, string> = {};
    const banner = {
      hidden: true,
      textContent: "",
      ownerDocument: { documentElement: { dataset } },
    };
    const r = (s: ConnState): void =>
      renderBanner(banner as never, dim as never, s);
    r({ fatal: null, stale: true, hadData: false });
    expect([toggles.at(-1), dataset["nxState"]]).toEqual([false, "cold"]);
    r({ fatal: null, stale: true, hadData: true });
    expect([toggles.at(-1), dataset["nxState"]]).toEqual([true, "degraded"]);
    r({ fatal: null, stale: false, hadData: true });
    expect([toggles.at(-1), dataset["nxState"]]).toEqual([false, "live"]);
  });

  it("renders text only: hostile server text never reaches the banner, and innerHTML is never used", () => {
    const hostile = "<img src=x onerror=alert(1)>";
    let html = 0;
    const banner = {
      hidden: true,
      textContent: "",
      ownerDocument: { documentElement: { dataset: {} } },
      set innerHTML(_: string) {
        html++;
      },
    };
    const dim = { classList: { toggle: () => undefined } };
    const { c, s } = make();
    s().recv({
      ...(welcome() as object),
      theater: { nodes: [{ name: hostile }], edges: [] },
    });
    s().recv({ type: "Control", v: hostile, action: hostile });
    s().recv({ type: hostile, v: PROTOCOL_V });
    for (const st of states) renderBanner(banner as never, dim as never, st);
    vi.advanceTimersByTime(STALE_MS);
    for (const st of states) renderBanner(banner as never, dim as never, st);
    expect(banner.textContent).toBe("COMMS RESYNC");
    expect(banner.textContent).not.toContain("<");
    expect(html).toBe(0);
    expect(c.store.theater?.nodes[0]).toMatchObject({ name: hostile }); // data, rendered as text by NX-178
  });
});

describe("malformed Hud frames (WP-13)", () => {
  const bad: [string, unknown][] = [
    ["no campaign_clock", { ...hud, campaign_clock: undefined }],
    [
      "elapsed_ticks string",
      { ...hud, campaign_clock: { ...hud.campaign_clock, elapsed_ticks: "1" } },
    ],
    ["ticker [null]", { ...hud, ticker: [null] }],
    [
      "panels.top_commanders rows null",
      {
        ...hud,
        panels: {
          ...hud.panels,
          top_commanders: [{ role: "STRIKE", rows: null }],
        },
      },
    ],
    [
      "operators.by_role missing",
      { ...hud, operators: { by_rank_band: null } },
    ],
    [
      "time_limit_score missing",
      (({ time_limit_score: _omit, ...rest }) => rest)(hud),
    ],
    [
      "time_limit_score fractional",
      { ...hud, time_limit_score: { coalition: 1.5, enemy: 0 } },
    ],
    [
      "objective deadline 1.5",
      { ...hud, objective: { node_id: "n1", name: "x", deadline_tick: 1.5 } },
    ],
  ];
  it.each(bad)(
    "drops a Hud with %s and keeps the last good one",
    (_n, frame) => {
      const { c, s } = make();
      s().recv(welcome());
      s().recv(snap(10));
      const before = c.store.hud;
      expect(() => s().recv(frame)).not.toThrow();
      expect(c.store.hud).toBe(before);
    },
  );
  it("applies a well-formed Hud", () => {
    const { c, s } = make();
    s().recv(welcome());
    s().recv(snap(10));
    s().recv({ ...hud, momentum_pct: 70 });
    expect(c.store.hud?.momentum_pct).toBe(70);
  });
});

describe("hostile elements (WP-13)", () => {
  const cases: [string, unknown][] = [
    ["Snapshot entities [null]", snap(20, { entities: [null] })],
    ["Snapshot nodes [null]", snap(20, { nodes: [null] })],
    ["Snapshot entity_id string", snap(20, { entities: [{ entity_id: "1" }] })],
    ["Snapshot hud number", snap(20, { hud: 5 })],
    [
      "Snapshot hud without campaign_clock",
      snap(20, { hud: { ...hud, campaign_clock: null } }),
    ],
    [
      "Snapshot hud without panels",
      snap(20, { hud: { ...hud, panels: undefined } }),
    ],
    ["Snapshot NaN tick", snap(NaN)],
    ["Delta upserts [null]", delta(11, 10, { upserts: [null] })],
    ["Delta node_patches [null]", delta(11, 10, { node_patches: [null] })],
    ["Delta upsert id 1.5", delta(11, 10, { upserts: [{ entity_id: 1.5 }] })],
    ["Delta node id number", delta(11, 10, { node_patches: [{ node_id: 7 }] })],
    ["Delta removes string", delta(11, 10, { removes: ["x"] })],
    ["Delta NaN tick", delta(NaN, 10)],
  ];
  it.each(cases)("drops %s without throwing or mutating", (_n, frame) => {
    const { c, s } = make();
    s().recv(welcome());
    s().recv(snap(10));
    const before = JSON.stringify([...c.store.entities, ...c.store.nodes]);
    expect(() => s().recv(frame)).not.toThrow();
    expect(c.store.tick).toBe(10);
    expect(JSON.stringify([...c.store.entities, ...c.store.nodes])).toBe(
      before,
    );
    expect(s().sent).toEqual([]);
  });

  it("a half-bad Delta applies nothing (removes are not done)", () => {
    const { c, s } = make();
    s().recv(welcome());
    s().recv(snap(10));
    s().recv(delta(11, 10, { removes: [1], upserts: [null] }));
    expect(c.store.entities.has(1)).toBe(true);
    expect(c.store.tick).toBe(10);
  });

  it("drops a text frame", () => {
    const { c, s } = make();
    s().onmessage?.({ data: JSON.stringify(welcome()) });
    s().recv(snap(1));
    expect(c.store.tick).toBeNull();
  });
});

describe("sync and staleness", () => {
  it("keeps the last data after a second Welcome, ignores Deltas, then the Snapshot replaces it", () => {
    const { c, s } = make();
    s().recv(welcome());
    s().recv(snap(10));
    s().recv(welcome());
    expect(c.store.tick).toBeNull();
    expect(c.store.entities.get(1)).toMatchObject({ hp_pct: 100 });
    s().recv(delta(11, 10, { upserts: [{ entity_id: 9 }] }));
    expect(c.store.entities.has(9)).toBe(false);
    s().recv(snap(2, { entities: [{ entity_id: 5 }] }));
    expect([...c.store.entities.keys()]).toEqual([5]);
  });

  it("ignores an equal-tick Delta and keeps unchanged fields", () => {
    const { c, s } = make();
    s().recv(welcome());
    s().recv(snap(10));
    s().recv(delta(10, 9, { upserts: [{ entity_id: 1, hp_pct: 1 }] }));
    expect(c.store.entities.get(1)).toMatchObject({ hp_pct: 100 });
    s().recv(delta(11, 10, { upserts: [{ entity_id: 1, speed_mps: 7 }] }));
    expect(c.store.entities.get(1)).toMatchObject({
      hp_pct: 100,
      speed_mps: 7,
    });
  });

  it("last_known null leaves it unchanged, an array replaces it", () => {
    const { c, s } = make();
    s().recv(welcome());
    s().recv(snap(10, { last_known: [{ entity_id: 3 }] }));
    s().recv(delta(11, 10));
    expect(c.store.lastKnown).toHaveLength(1);
    s().recv(delta(12, 11, { last_known: [] }));
    expect(c.store.lastKnown).toHaveLength(0);
  });

  it("shows COMMS RESYNC while reconnect attempts keep failing faster than 2 s", () => {
    const { c, s } = make(() => 0);
    c.start();
    for (let i = 0; i < 6; i++) {
      s().onclose?.({ code: 1006 });
      vi.advanceTimersByTime(BACKOFF_MIN_MS);
    }
    expect(states.at(-1)?.stale).toBe(true);
  });

  it("re-arms the stale timer on an applied Delta, not on Hud or an ignored Delta", () => {
    const { s } = make();
    s().recv(welcome());
    s().recv(snap(10));
    vi.advanceTimersByTime(STALE_MS - 1);
    s().recv(delta(11, 10));
    vi.advanceTimersByTime(STALE_MS - 1);
    expect(states.at(-1)?.stale).toBe(false);
    vi.advanceTimersByTime(1);
    expect(states.at(-1)?.stale).toBe(true);
    s().recv(hud);
    expect(states.at(-1)?.stale).toBe(true);
  });

  it("a stalled resync stays COMMS RESYNC and re-sends the Ack at most once per second", () => {
    const { s } = make();
    s().recv(welcome());
    s().recv(snap(10));
    s().recv({ type: "Control", v: PROTOCOL_V, action: "RESYNC" });
    let t = 11;
    const feed = (): void => s().recv(delta(t, t++ - 1));
    feed();
    expect(s().sent).toHaveLength(1);
    vi.advanceTimersByTime(RESYNC_ACK_MS - 1);
    feed();
    expect(s().sent).toHaveLength(1);
    vi.advanceTimersByTime(1);
    feed();
    expect(s().sent).toHaveLength(2);
    expect(s().sent[1]).toEqual({
      type: "Ack",
      v: PROTOCOL_V,
      applied_tick: 10,
    });
    vi.advanceTimersByTime(STALE_MS);
    expect(states.at(-1)?.stale).toBe(true);
  });
});

describe("fatal and failure paths", () => {
  it("UPDATE_REQUIRED beats AUTH_FAILED", () => {
    const { s } = make();
    const first = s();
    first.onclose?.({ code: 4003 });
    expect(states.at(-1)?.fatal).toBe("UPDATE_REQUIRED");
    first.onclose?.({ code: 4002 });
    expect(states.at(-1)?.fatal).toBe("UPDATE_REQUIRED");
  });

  it("reloads exactly at RELOAD_DELAY_MS", () => {
    const { s } = make();
    s().onclose?.({ code: 4003 });
    vi.advanceTimersByTime(RELOAD_DELAY_MS - 1);
    expect(reload).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("a page that loaded moments ago reloads after RELOAD_BACKOFF_MS, not sooner (loop bound)", () => {
    uptime = MIN_UPTIME_FOR_RELOAD_MS - 1;
    const { s } = make();
    s().onclose?.({ code: 4003 });
    vi.advanceTimersByTime(RELOAD_BACKOFF_MS - 1);
    expect(reload).not.toHaveBeenCalled();
    expect(states.at(-1)?.fatal).toBe("UPDATE_REQUIRED");
    vi.advanceTimersByTime(1);
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("retries when the WebSocket constructor throws", () => {
    let n = 0;
    const c = new WireClient({
      url: "ws://x",
      token: "t",
      makeSocket: () => {
        if (n++ === 0) throw new Error("bad url");
        return new FakeSocket();
      },
      random: () => 0,
      uptimeMs: () => 0,
      reload,
      onState: () => undefined,
    });
    expect(() => c.start()).not.toThrow();
    vi.advanceTimersByTime(500);
    expect(n).toBe(2);
  });
});

const fakeSurface = () =>
  ({
    world: { classList: { toggle: () => undefined } },
    banners: { appendChild: () => undefined },
    panels: { appendChild: () => undefined },
    sitrep: { replaceChildren: () => undefined },
    toast: { appendChild: () => undefined },
    showTheater: () => undefined,
    showNodes: () => undefined,
    units: { getContext: () => null },
    fx: { getContext: () => null },
  }) as unknown as ReturnType<Parameters<typeof startFeed>[1]>;

describe("token clearing and startFeed", () => {
  it("clears the token from the URL", () => {
    const calls: string[] = [];
    const hist = {
      replaceState: (_a: unknown, _b: string, u: string) => calls.push(u),
    };
    takeToken(
      { hash: "#token=s3cret", pathname: "/p", search: "" } as Location,
      hist as unknown as History,
    );
    expect(calls).toEqual(["/p"]);
    expect(calls.join()).not.toContain("s3cret");
  });

  function fakeWin(
    protocol: string,
    hash: string,
  ): { win: Window; log: string[] } {
    const log: string[] = [];
    const win = {
      location: {
        protocol,
        host: "h:1",
        hash,
        pathname: "/",
        search: "",
        reload: () => log.push("reload"),
      },
      history: {
        replaceState: (_a: unknown, _b: string, u: string) =>
          log.push(`rs:${u}`),
      },
      performance: { now: () => 1e9 },
      requestAnimationFrame: () => 1,
      cancelAnimationFrame: () => undefined,
      setInterval: (f: () => void, ms: number) => setInterval(f, ms),
      clearInterval: (id: number) => clearInterval(id),
      setTimeout: (f: () => void, ms: number) => setTimeout(f, ms),
      document: {
        createElement: () => ({
          ownerDocument: { documentElement: { dataset: {} } },
          appendChild: () => undefined,
          setAttribute: () => undefined,
          classList: { toggle: () => undefined },
        }),
        body: { appendChild: () => undefined },
      },
    };
    return { win: win as unknown as Window, log };
  }

  it("does nothing without a token", () => {
    expect(startFeed(fakeWin("http:", "").win, fakeSurface)).toBeNull();
  });

  it.each([
    ["http:", "ws:"],
    ["https:", "wss:"],
  ])("connects over the matching scheme (%s)", (protocol, scheme) => {
    const urls: string[] = [];
    vi.stubGlobal("WebSocket", function (u: string) {
      urls.push(u);
      return new FakeSocket();
    });
    startFeed(fakeWin(protocol, "#token=t").win, fakeSurface);
    vi.unstubAllGlobals();
    expect(urls).toEqual([`${scheme}//h:1${WS_PATH}`]);
  });

  it("hands the Welcome theater to showTheater", () => {
    const made: FakeSocket[] = [];
    vi.stubGlobal("WebSocket", function () {
      const f = new FakeSocket();
      made.push(f);
      return f;
    });
    const seen: unknown[] = [];
    const surface = {
      ...fakeSurface(),
      showTheater: (t: unknown) => seen.push(t),
    };
    startFeed(fakeWin("http:", "#token=t").win, () => surface as never);
    vi.unstubAllGlobals();
    const theater = {
      nodes: [
        { node_id: "n1", name: "N1", kind: "FOB", pos: { x_m: 1, y_m: 2 } },
      ],
      edges: [],
      terrain_ref: null,
    };
    made[0]?.recv({ type: "Welcome", v: PROTOCOL_V, theater });
    expect(seen).toEqual([theater]);
  });

  it("hands the store's nodes to showNodes after a Snapshot and after a Delta (NX-176)", () => {
    const made: FakeSocket[] = [];
    vi.stubGlobal("WebSocket", function () {
      const f = new FakeSocket();
      made.push(f);
      return f;
    });
    const owners: (string | undefined)[] = [];
    const surface = {
      ...fakeSurface(),
      showNodes: (n: ReadonlyMap<string, { owner: string }>) =>
        owners.push(n.get("n1")?.owner),
    };
    startFeed(fakeWin("http:", "#token=t").win, () => surface as never);
    vi.unstubAllGlobals();
    made[0]?.recv(welcome());
    made[0]?.recv(snap(1));
    made[0]?.recv(
      delta(2, 1, { node_patches: [{ node_id: "n1", owner: "ENEMY" }] }),
    );
    expect(owners).toEqual(["NEUTRAL", "ENEMY"]);
  });

  it("restores #token before reloading", () => {
    const made: FakeSocket[] = [];
    vi.stubGlobal("WebSocket", function () {
      const f = new FakeSocket();
      made.push(f);
      return f;
    });
    const { win, log } = fakeWin("http:", "#token=a b");
    const client = startFeed(win, fakeSurface);
    vi.unstubAllGlobals();
    expect(client).not.toBeNull();
    made[0]?.onclose?.({ code: 4003 });
    vi.advanceTimersByTime(RELOAD_DELAY_MS);
    expect(log).toEqual(["rs:/", "rs:#token=a%20b", "reload"]);
  });
});

describe("onFrame (NX-178)", () => {
  function frames(): { seen: string[]; recv: (f: unknown) => void } {
    const seen: string[] = [];
    const { s } = make(undefined, (f) => seen.push(f.type));
    s().onopen?.();
    s().recv(welcome());
    return { seen, recv: (f) => s().recv(f) };
  }

  it("fires once for each applied Snapshot, Hud and Delta", () => {
    const { seen, recv } = frames();
    recv(snap(10));
    recv(hud);
    recv(delta(11, 10));
    expect(seen).toEqual(["Snapshot", "Hud", "Delta"]);
  });

  it("fires nothing for a stale Delta, a gap Delta, or a Delta while unsynced", () => {
    const { seen, recv } = frames();
    recv(snap(10));
    seen.length = 0;
    recv(delta(10, 9)); // stale: tick not above the last applied
    recv(delta(12, 11)); // gap: base_tick is not the last applied tick
    recv(delta(13, 12)); // unsynced now: ignored until a Snapshot
    expect(seen).toEqual([]);
    recv(snap(20));
    expect(seen).toEqual(["Snapshot"]);
  });
});
