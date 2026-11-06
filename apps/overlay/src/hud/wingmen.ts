// NX-511 (GAMEPLAY §1b item 246, Q-GP-51): "VIPER-27 leads 2 [AI] wingmen". A pure model: the Delta's UnitSpawned
// events plus the store's views in, one low-priority line per lead out. No new wire field: a wingman is a spawned
// COALITION AI_GARRISON view whose follow_entity_id names a live COMMANDER lead.
import type { PublicEvent } from "../contracts/wire/hud";
import type { EntityView } from "../contracts/wire/snapshot";
import { DASH } from "./strings";

/** On-screen life in game ticks (10 Hz): 10 s. Display-only, PROPOSED (OV-26 timing, Q-UX-13). */
export const WING_TTL_TICKS = 100;

export interface WingLine {
  key: string;
  expiresAtTick: number;
  text: string;
  seq: number;
}

export class WingmenFeed {
  private lines = new Map<number, WingLine>();
  private campaignId: string | null = null;
  private lastSeq = -1;

  ingest(
    events: readonly PublicEvent[],
    entities: ReadonlyMap<number, EntityView>,
  ): void {
    const per = new Map<number, { n: number; tick: number; seq: number }>();
    for (const ev of events) {
      if (ev.kind !== "UnitSpawned") continue;
      if (ev.campaign_id !== this.campaignId) {
        this.lines.clear(); // a new campaign restarts seq and tick
        this.campaignId = ev.campaign_id;
        this.lastSeq = -1;
      }
      if (ev.event_seq <= this.lastSeq) continue; // replayed or stale (reconnect)
      this.lastSeq = ev.event_seq;
      if (ev.side !== "COALITION" || ev.owner_kind !== "AI_GARRISON") continue;
      const lead = entities.get(
        entities.get(ev.entity_id)?.follow_entity_id ?? -1,
      );
      if (lead === undefined || lead.owner_kind !== "COMMANDER") continue;
      const n = (per.get(lead.entity_id)?.n ?? 0) + 1;
      per.set(lead.entity_id, { n, tick: ev.tick, seq: ev.event_seq });
    }
    for (const [id, c] of per) {
      const name = entities.get(id)?.callsign ?? DASH;
      this.lines.set(id, {
        key: `wing|${id}|${c.seq}`,
        expiresAtTick: c.tick + WING_TTL_TICKS,
        text: `${name} leads ${c.n} [AI] ${c.n === 1 ? "wingman" : "wingmen"}`,
        seq: c.seq,
      });
    }
  }

  /** Live lines, newest first. Game ticks, so a paused world keeps them. */
  view(tick: number): WingLine[] {
    for (const [id, l] of this.lines)
      if (tick >= l.expiresAtTick) this.lines.delete(id);
    return [...this.lines.values()].sort((a, b) => b.seq - a.seq);
  }
}
