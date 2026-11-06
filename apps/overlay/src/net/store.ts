// State store: Welcome, Snapshot, Delta, Hud (WIRE-PROTOCOL WP-3, WP-7, §6; OVERLAY §0.3).
import type { Delta } from "../contracts/wire/delta";
import type {
  BlobView,
  EntityView,
  Hud,
  LastKnownView,
  NodeView,
  Snapshot,
} from "../contracts/wire/snapshot";
import type { Welcome } from "../contracts/wire/welcome";

export type DeltaResult = "applied" | "ignored" | "gap";

export class WireStore {
  /** Last applied tick; null until a Snapshot (cold start) and after a resync drop. */
  tick: number | null = null;
  theater: Welcome["theater"] | null = null;
  /** Welcome.tick_rate_hz: converts ticks to ms for interpolation (OVERLAY §0.10); null until a Welcome. */
  tickRateHz: number | null = null;
  entities = new Map<number, EntityView>();
  nodes = new Map<string, NodeView>();
  blobs: BlobView[] = [];
  lastKnown: LastKnownView[] = [];
  hud: Hud | null = null;

  /** A fresh Welcome: unsynced, so a lower tick (server restart) is accepted (WP §6); the data stays until the Snapshot. */
  applyWelcome(w: Welcome): void {
    this.resync();
    this.theater = w.theater;
    this.tickRateHz = w.tick_rate_hz;
  }

  applySnapshot(s: Snapshot): void {
    this.entities = new Map(s.entities.map((e) => [e.entity_id, e]));
    this.nodes = new Map(s.nodes.map((n) => [n.node_id, n]));
    this.blobs = s.blobs;
    this.lastKnown = s.last_known;
    this.hud = s.hud ?? this.hud;
    this.tick = s.tick;
  }

  applyHud(h: Hud): void {
    this.hud = h;
  }

  /** "gap": base_tick is not the last applied tick; unsynced until a Snapshot. */
  applyDelta(d: Delta): DeltaResult {
    if (this.tick === null || d.tick <= this.tick) return "ignored";
    if (d.base_tick !== this.tick) {
      this.resync();
      return "gap";
    }
    for (const id of d.removes) this.entities.delete(id);
    for (const p of d.upserts) {
      this.entities.set(p.entity_id, {
        ...this.entities.get(p.entity_id),
        ...p,
      } as EntityView);
    }
    for (const p of d.node_patches) {
      const prev = this.nodes.get(p.node_id);
      if (prev) this.nodes.set(p.node_id, { ...prev, ...p } as NodeView);
    }
    if (d.blobs !== null) this.blobs = d.blobs;
    if (d.last_known !== null) this.lastKnown = d.last_known;
    this.tick = d.tick;
    return "applied";
  }

  /** Control{RESYNC}, a gap or a Welcome: stop applying Deltas and wait for the Snapshot.
   *  The last data stays, so the dimmed last frame is not cleared (OVERLAY §0.3). */
  resync(): void {
    this.tick = null;
  }
}
