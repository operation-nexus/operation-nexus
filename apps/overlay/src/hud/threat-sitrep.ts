import type { Event, ThreatAdaptation } from "../contracts/events/event";
import type { TheaterDefinition } from "../types/theater";

// OVERLAY OV-26 (NX-496): the threat sitrep stack. A pure model: events in, a view out.

export type SitrepCategory = ThreatAdaptation["category"];
export type SitrepTier = "LAST_STAND" | "ALERT" | "WIN" | "INTEL" | "EASE";

interface TierRule {
  rank: number; // lower shows first
  ttlTicks: number; // on-screen life in game ticks (10 Hz, SC-2)
}

// Display-only timing (no game outcome), PROPOSED in OV-26 (Q-UX-13).
export const TIER_RULES: Record<SitrepTier, TierRule> = {
  LAST_STAND: { rank: 0, ttlTicks: 600 },
  ALERT: { rank: 1, ttlTicks: 300 },
  WIN: { rank: 2, ttlTicks: 200 },
  INTEL: { rank: 3, ttlTicks: 150 },
  EASE: { rank: 4, ttlTicks: 150 },
};

// Within a tier, the category order breaks ties before recency.
// Record over the contract enum: tsc fails when a category is added or removed.
const CATEGORY_RULES: Record<
  SitrepCategory,
  { tier: SitrepTier; order: number; slot: string }
> = {
  SANCTUARY_AT_RISK: { tier: "LAST_STAND", order: 0, slot: "SANCTUARY" },
  HOLD_AT_RISK: { tier: "ALERT", order: 1, slot: "HOLD" },
  STAGING_LAUNCHED: { tier: "ALERT", order: 2, slot: "STAGING" },
  STAGING: { tier: "ALERT", order: 3, slot: "STAGING" },
  STRIKE_DOWNED: { tier: "WIN", order: 4, slot: "STRIKE" },
  IADS_REINFORCED: { tier: "INTEL", order: 5, slot: "IADS" },
  CONVOY_ESCORT: { tier: "INTEL", order: 6, slot: "CONVOY" },
  STAGING_DISPERSED: { tier: "EASE", order: 7, slot: "STAGING" },
};

export const MAX_SHOWN = 3;
const MAX_CREDITS_SHOWN = 3;

export interface SitrepEntry {
  key: string;
  event: ThreatAdaptation;
  tier: SitrepTier;
  order: number;
  expiresAtTick: number;
  credit: string | null;
}

export interface SitrepView {
  shown: SitrepEntry[];
  hiddenCount: number;
}

export function tierOf(ev: ThreatAdaptation): SitrepTier {
  // A DOWN (CONVOY_ESCORT, IADS_REINFORCED) is an adaptation fading away.
  return ev.direction === "DOWN" ? "EASE" : CATEGORY_RULES[ev.category].tier;
}

// One card per slot, sector and node: a newer event replaces the older card, so a
// STAGING_LAUNCHED or STAGING_DISPERSED closes the sector's STAGING card and a DOWN
// replaces its UP.
export function slotKey(ev: ThreatAdaptation): string {
  return `${CATEGORY_RULES[ev.category].slot}|${ev.sector_id}|${ev.node_id ?? ""}`;
}

export function creditLine(
  ids: readonly number[],
  callsignOf: (id: number) => string | undefined,
): string | null {
  if (ids.length === 0) return null;
  const names: string[] = [];
  for (const id of ids) {
    const name = callsignOf(id);
    if (name !== undefined) names.push(name);
    if (names.length === MAX_CREDITS_SHOWN) break;
  }
  const rest = ids.length - names.length;
  const parts = names.length > 0 ? [names.join(", ")] : [];
  if (rest > 0) parts.push(`+${rest}`);
  return `Credit: ${parts.join(" ")}`;
}

export function compareEntries(a: SitrepEntry, b: SitrepEntry): number {
  return (
    TIER_RULES[a.tier].rank - TIER_RULES[b.tier].rank ||
    a.order - b.order ||
    b.event.event_seq - a.event.event_seq
  );
}

export class ThreatSitrepBoard {
  private entries = new Map<string, SitrepEntry>();
  private campaignId: string | null = null;

  ingest(
    events: readonly Event[],
    callsignOf: (id: number) => string | undefined,
  ): void {
    for (const ev of events) {
      if (ev.kind !== "ThreatAdaptation") continue;
      // A new campaign restarts seq and tick: the old campaign's cards go.
      if (ev.campaign_id !== this.campaignId) {
        this.entries.clear();
        this.campaignId = ev.campaign_id;
      }
      const key = slotKey(ev);
      const prior = this.entries.get(key);
      // A replayed or stale event (reconnect, out of order) never replaces a newer card.
      if (prior && prior.event.event_seq >= ev.event_seq) continue;
      const tier = tierOf(ev);
      this.entries.set(key, {
        key,
        event: ev,
        tier,
        order: CATEGORY_RULES[ev.category].order,
        expiresAtTick: ev.tick + TIER_RULES[tier].ttlTicks,
        credit: creditLine(ev.credit_ids, callsignOf),
      });
    }
  }

  // Game ticks, not wall time: a paused world (OV-21) keeps its sitreps.
  view(tick: number): SitrepView {
    for (const [key, entry] of this.entries) {
      if (tick >= entry.expiresAtTick) this.entries.delete(key);
    }
    const live = [...this.entries.values()].sort(compareEntries);
    return {
      shown: live.slice(0, MAX_SHOWN),
      hiddenCount: Math.max(0, live.length - MAX_SHOWN),
    };
  }
}

// On-screen words (OV-26 table). Quoted owner wordings come from the contract.
const TEXT: Record<
  SitrepCategory,
  { UP: (n: string, s: string) => string; DOWN?: (s: string) => string }
> = {
  SANCTUARY_AT_RISK: {
    UP: (n) => `NULL strikes ${n}, the sanctuary is at risk`,
  },
  HOLD_AT_RISK: { UP: (n) => `NULL moves on ${n}, the hold is at risk` },
  STAGING_LAUNCHED: { UP: (_n, s) => `NULL assault launching from ${s}` },
  STAGING: { UP: (_n, s) => `NULL forces are massing in ${s}` },
  STRIKE_DOWNED: { UP: (n) => `NULL strike package downed near ${n}` },
  IADS_REINFORCED: {
    UP: (_n, s) => `NULL reinforces its air defense in ${s}`,
    DOWN: (s) => `NULL air defense back to normal in ${s}`,
  },
  CONVOY_ESCORT: {
    UP: (_n, s) => `NULL convoys now run with escorts in ${s}`,
    DOWN: (s) => `NULL convoy escorts stand down in ${s}`,
  },
  STAGING_DISPERSED: { UP: () => "massing disperses" }, // Q-TD-47 verbatim
};

const TIER_LABEL: Record<SitrepTier, string> = {
  LAST_STAND: "LAST STAND",
  ALERT: "ALERT",
  WIN: "WIN",
  INTEL: "INTEL",
  EASE: "EASING",
};

export interface SitrepLines {
  kicker: string;
  headline: string;
  credit: string | null;
}

// Names come from the theater; an id the theater does not know shows as-is (ids are
// public, FOW-10), and a missing node shows as the DI-1 dash.
export function sitrepLines(
  entry: SitrepEntry,
  theater: TheaterDefinition,
): SitrepLines {
  const ev = entry.event;
  const sector =
    theater.sectors.find((s) => s.id === ev.sector_id)?.name ?? ev.sector_id;
  const node =
    ev.node_id === null || ev.node_id === undefined
      ? "—"
      : (theater.nodes.find((n) => n.id === ev.node_id)?.name ?? ev.node_id);
  const text = TEXT[ev.category];
  const headline =
    ev.direction === "DOWN" && text.DOWN
      ? text.DOWN(sector)
      : text.UP(node, sector);
  return {
    kicker: `${TIER_LABEL[entry.tier]} · ${sector}`,
    headline,
    credit: entry.credit,
  };
}
