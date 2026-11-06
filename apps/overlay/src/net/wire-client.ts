// WS client for the WIRE-PROTOCOL feed (NX-175 a). Binary msgpack frames; the token is never logged or stored.
import { decode, encode } from "@msgpack/msgpack";
import protocolVersion from "../../../../contracts/VERSION?raw";
import type { Ack } from "../contracts/wire/ack";
import type { Delta } from "../contracts/wire/delta";
import type { Hello } from "../contracts/wire/hello";
import type { Hud, Snapshot } from "../contracts/wire/snapshot";
import type { Welcome } from "../contracts/wire/welcome";
import type { ConnState, Fatal } from "./banner";
import { WireStore } from "./store";

export const PROTOCOL_V = protocolVersion.trim();
export const BACKOFF_MIN_MS = 500; // WP-5
export const BACKOFF_MAX_MS = 10_000;
export const STALE_MS = 2_000;
export const RELOAD_DELAY_MS = 5_000; // PROPOSED: lets the banner show
export const MIN_UPTIME_FOR_RELOAD_MS = 30_000; // PROPOSED: a younger page waits RELOAD_BACKOFF_MS
export const RELOAD_BACKOFF_MS = 60_000; // PROPOSED
export const RESYNC_ACK_MS = 1_000; // re-send the resync Ack at most this often
const CLOSE_AUTH_FAILED = 4002;
const CLOSE_VERSION_MISMATCH = 4003;

export interface SocketLike {
  binaryType: string;
  onopen: (() => void) | null;
  onmessage: ((e: { data: unknown }) => void) | null;
  onclose: ((e: { code: number }) => void) | null;
  onerror: (() => void) | null;
  send(data: Uint8Array): void;
  close(): void;
}
export interface ClientDeps {
  url: string;
  token: string;
  makeSocket: (url: string) => SocketLike;
  random: () => number;
  /** Ms since the page loaded. In-memory reload guard: no storage may hold a counter across loads. */
  uptimeMs: () => number;
  /** Reloads the page; the hash was cleared, so the caller puts the token back in memory only (start.ts). */
  reload: (token: string) => void;
  onState: (s: ConnState) => void;
  /** After a Welcome is applied: the theater is in the store (terrain redraw, OVERLAY §0.2). */
  onWelcome?: () => void;
  /** After a Snapshot or Hud is applied, or a Delta that applied: the HUD reads the store (NX-178). */
  onFrame?: (f: Snapshot | Hud | Delta) => void;
}

/** Reads `#token=…` once and clears the fragment. Returns null when absent. */
export function takeToken(loc: Location, hist: History): string | null {
  // Not URLSearchParams: form-decoding turns a literal "+" (base64 tokens) into a space.
  const m = /(?:^|&)token=([^&]*)/.exec(loc.hash.slice(1));
  let token: string | null;
  try {
    token = m?.[1] === undefined ? null : decodeURIComponent(m[1]);
  } catch {
    token = null; // malformed escape: treated as absent
  }
  hist.replaceState(null, "", loc.pathname + loc.search);
  return token === null || token === "" ? null : token;
}

/** Jittered exponential backoff in [0.5 s, min(10 s, 0.5 s * 2^attempt)] (WP-5). */
export function backoffMs(attempt: number, random: () => number): number {
  const cap = Math.min(BACKOFF_MAX_MS, BACKOFF_MIN_MS * 2 ** attempt);
  return BACKOFF_MIN_MS + random() * (cap - BACKOFF_MIN_MS);
}

type Frame = { type: string } & Record<string, unknown>;
const isObj = (x: unknown): x is Record<string, unknown> =>
  typeof x === "object" && x !== null && !Array.isArray(x);
const isInt = Number.isInteger;
/** An array whose every element passes `ok`. */
const all = (x: unknown, ok: (e: unknown) => boolean): boolean =>
  Array.isArray(x) && x.every(ok);
const hasInt = (k: string) => (e: unknown) => isObj(e) && isInt(e[k]);
const hasStr = (k: string) => (e: unknown) =>
  isObj(e) && typeof e[k] === "string";
const nullOr = (x: unknown, ok: (x: unknown) => boolean): boolean =>
  x === null || ok(x);

/** The Hud fields the HUD dereferences (contracts/wire/hud.json); a frame missing one is dropped, not rendered. */
function validHud(x: unknown): boolean {
  if (!isObj(x)) return false;
  const c = x["campaign_clock"];
  const p = x["panels"];
  const o = x["operators"];
  return (
    nullOr(x["momentum_pct"], isInt) &&
    isInt(x["nodes_held"]) &&
    isInt(x["nodes_total"]) &&
    typeof x["threat_tier"] === "string" &&
    typeof x["objective_mode"] === "string" &&
    nullOr(
      x["objective"],
      (v) =>
        isObj(v) &&
        typeof v["name"] === "string" &&
        nullOr(v["deadline_tick"], isInt),
    ) &&
    isObj(c) &&
    isInt(c["elapsed_ticks"]) &&
    nullOr(c["limit_ticks"], isInt) &&
    typeof c["paused"] === "boolean" &&
    nullOr(
      x["time_limit_score"],
      (v) => isObj(v) && isInt(v["coalition"]) && isInt(v["enemy"]),
    ) &&
    all(x["ticker"], (e) => hasInt("tick")(e) && hasStr("text")(e)) &&
    isObj(p) &&
    all(p["tasking_needed"], isObj) &&
    all(p["top_commanders"], (r) => isObj(r) && all(r["rows"], isObj)) &&
    nullOr(
      o,
      (v) =>
        isObj(v) &&
        all(v["by_role"], isObj) &&
        nullOr(v["by_rank_band"], (b) => all(b, isObj)),
    )
  );
}

/** Checks type, required fields and every element before anything is applied (WP-2, WP-13). */
function valid(f: Frame): boolean {
  switch (f.type) {
    case "Welcome":
      return isObj(f["theater"]);
    case "Snapshot":
      return (
        isInt(f["tick"]) &&
        all(f["entities"], hasInt("entity_id")) &&
        all(f["nodes"], hasStr("node_id")) &&
        all(f["blobs"], isObj) &&
        all(f["last_known"], isObj) &&
        nullOr(f["hud"], validHud)
      );
    case "Delta":
      return (
        isInt(f["tick"]) &&
        isInt(f["base_tick"]) &&
        all(f["upserts"], hasInt("entity_id")) &&
        all(f["removes"], isInt) &&
        all(f["node_patches"], hasStr("node_id")) &&
        nullOr(f["blobs"], (x) => all(x, isObj)) &&
        nullOr(f["last_known"], (x) => all(x, isObj))
      );
    case "Hud":
      return validHud(f);
    case "Control":
      return f["action"] === "RELOAD" || f["action"] === "RESYNC";
    default:
      return false;
  }
}

export class WireClient {
  readonly store = new WireStore();
  private state: ConnState = { fatal: null, stale: false, hadData: false };
  private sock: SocketLike | null = null;
  private attempt = 0;
  private welcomed = false;
  private lastApplied: number | null = null;
  private lastResyncAck = -Infinity;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private staleTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(private readonly d: ClientDeps) {}

  start(): void {
    this.armStale(); // once: a reconnect attempt is not data, so it must not re-arm the timer
    this.connect();
  }

  private connect(): void {
    this.retryTimer = null;
    this.welcomed = false;
    let s: SocketLike;
    try {
      s = this.d.makeSocket(this.d.url);
    } catch {
      this.scheduleRetry();
      return;
    }
    s.binaryType = "arraybuffer";
    this.sock = s;
    s.onopen = () => {
      const hello: Hello = {
        type: "Hello",
        v: PROTOCOL_V,
        client_kind: "OVERLAY",
        capability_token: this.d.token,
        last_tick: null,
      };
      s.send(encode(hello));
    };
    s.onmessage = (e) => this.onMessage(e.data);
    s.onclose = (e) => {
      this.detach();
      if (e.code === CLOSE_VERSION_MISMATCH) this.setFatal("UPDATE_REQUIRED");
      else if (e.code === CLOSE_AUTH_FAILED) this.setFatal("AUTH_FAILED");
      else this.scheduleRetry();
    };
    s.onerror = () => {
      this.detach();
      s.close();
      this.scheduleRetry();
    };
  }

  private detach(): void {
    if (this.sock) {
      this.sock.onopen = this.sock.onmessage = null;
      this.sock.onclose = this.sock.onerror = null;
    }
    this.sock = null;
  }

  private scheduleRetry(): void {
    if (this.state.fatal || this.retryTimer !== null) return;
    this.retryTimer = setTimeout(
      () => this.connect(),
      backoffMs(this.attempt++, this.d.random),
    );
  }

  private setFatal(f: Fatal): void {
    if (this.state.fatal === "UPDATE_REQUIRED") return; // it outranks AUTH FAILED
    if (f === "UPDATE_REQUIRED") {
      // A 4003 soon after load means the last reload did not help: wait longer, bounding a stale-CDN loop.
      const wait =
        this.d.uptimeMs() >= MIN_UPTIME_FOR_RELOAD_MS
          ? RELOAD_DELAY_MS
          : RELOAD_BACKOFF_MS;
      setTimeout(() => this.d.reload(this.d.token), wait);
    }
    if (this.retryTimer !== null) clearTimeout(this.retryTimer);
    if (this.staleTimer !== null) clearTimeout(this.staleTimer);
    this.retryTimer = this.staleTimer = null;
    this.push({ ...this.state, fatal: f });
  }

  /** Data is a Snapshot or an applied Delta; 2 s without one shows COMMS RESYNC (WP-5). */
  private armStale(): void {
    if (this.state.stale) this.push({ ...this.state, stale: false });
    if (this.staleTimer !== null) clearTimeout(this.staleTimer);
    this.staleTimer = setTimeout(
      () => this.push({ ...this.state, stale: true }),
      STALE_MS,
    );
  }

  private push(s: ConnState): void {
    this.state = s;
    this.d.onState(s);
  }

  private onMessage(data: unknown): void {
    if (this.state.fatal || !(data instanceof ArrayBuffer)) return;
    let f: unknown;
    try {
      f = decode(new Uint8Array(data));
    } catch {
      return;
    }
    if (!isObj(f) || typeof (f as Frame).type !== "string") return;
    const frame = f as Frame;
    if (!valid(frame) || (frame.type !== "Welcome" && !this.welcomed)) return;
    try {
      this.dispatch(frame);
    } catch {
      // treated like a malformed frame: dropped
    }
  }

  private dispatch(frame: Frame): void {
    switch (frame.type) {
      case "Welcome":
        this.welcomed = true;
        this.attempt = 0;
        this.store.applyWelcome(frame as unknown as Welcome);
        this.d.onWelcome?.();
        break;
      case "Snapshot":
        this.store.applySnapshot(frame as unknown as Snapshot);
        this.lastApplied = this.store.tick;
        this.armStale();
        if (!this.state.hadData) this.push({ ...this.state, hadData: true });
        this.d.onFrame?.(frame as unknown as Snapshot);
        break;
      case "Hud":
        this.store.applyHud(frame as unknown as Hud);
        this.d.onFrame?.(frame as unknown as Hud);
        break;
      case "Delta":
        this.onDelta(frame as unknown as Delta);
        break;
      case "Control":
        if (frame["action"] === "RELOAD") this.setFatal("UPDATE_REQUIRED");
        else this.store.resync(); // the Snapshot follows (WP-3)
        break;
    }
  }

  private onDelta(d: Delta): void {
    const r = this.store.applyDelta(d);
    if (r === "applied") {
      this.lastApplied = d.tick;
      this.armStale();
      this.ack(d.tick);
      this.d.onFrame?.(d);
    } else if (this.store.tick === null) {
      // Unsynced (gap, RESYNC or a lost Snapshot): an Ack asks for a Snapshot (WP-3), at most 1/s.
      const now = Date.now();
      if (r === "gap" || now - this.lastResyncAck >= RESYNC_ACK_MS) {
        this.lastResyncAck = now;
        this.ack(this.lastApplied ?? 0);
      }
    }
  }

  private ack(applied_tick: number): void {
    const ack: Ack = { type: "Ack", v: PROTOCOL_V, applied_tick };
    this.sock?.send(encode(ack));
  }
}
