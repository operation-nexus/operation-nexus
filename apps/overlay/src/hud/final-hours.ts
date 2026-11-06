// Final hours (OVERLAY §0.11, NX-515): phases, countdown push, threshold banner and the OV-26 card.
// A pure model: Hud and Delta events in, view state out. The score is only ever `Hud.time_limit_score`
// (the overlay computes none); every threshold and life below is a constant until a config key exists.
import type { Hud } from "../contracts/wire/snapshot";
import { TICKS_PER_S } from "./clock";
import { DASH } from "./strings";
import { nodesText } from "./topbar";

export type Phase = 0 | 1 | 2 | 3;
type Live = 1 | 2 | 3;
/** Owner, 2026-11-06 (Q-UX-29): T-6 h, T-1 h, T-10 min, in game ticks (SC-2). */
export const THRESHOLD_TICKS = [
  6 * 3600 * TICKS_PER_S,
  3600 * TICKS_PER_S,
  10 * 60 * TICKS_PER_S,
] as const;
/** PROPOSED: a re-base that lifts remaining back over a threshold by less than 30 s does not re-arm it. */
export const HYSTERESIS_TICKS = 30 * TICKS_PER_S;
/** PROPOSED: the FH-1 and FH-2 card's life in game ticks (60 s); FH-3's card stays to the end. */
export const CARD_TTL_TICKS = 60 * TICKS_PER_S;
/** PROPOSED: the threshold banner's life in real milliseconds. */
export const BANNER_MS = 5000;

const BANNER = ["FINAL 6 HOURS", "FINAL HOUR", "FINAL 10 MINUTES"] as const;
const LEFT = ["6 h left", "1 h left", "10 min left"] as const;

export type Lead = "COALITION" | "NULL" | "LEVEL" | "NONE";
export interface Score {
  lead: Lead;
  text: string;
}
export interface Push {
  phase: Live;
  label: string;
  score: Score;
}
export interface FinalHoursCard {
  phase: Live;
  kicker: string;
  lines: [string, string];
}

/** The leader and margin from the server's score; DASH for a null field (DI-1). */
export function scoreOf(hud: Hud | null): Score {
  const s = hud?.time_limit_score;
  if (!s) return { lead: "NONE", text: DASH };
  if (s.coalition > s.enemy)
    return { lead: "COALITION", text: `COALITION +${s.coalition - s.enemy}` };
  if (s.enemy > s.coalition)
    return { lead: "NULL", text: `NULL +${s.enemy - s.coalition}` };
  return { lead: "LEVEL", text: "LEVEL" };
}

function cardLines(hud: Hud | null): [string, string] {
  const s = hud?.time_limit_score;
  const one = !s
    ? `Points: ${DASH}`
    : s.coalition > s.enemy
      ? `Coalition leads on points, ${s.coalition} to ${s.enemy}`
      : s.enemy > s.coalition
        ? `NULL leads on points, ${s.enemy} to ${s.coalition}`
        : `Points level at ${s.coalition}`;
  return [one, `Coalition holds ${nodesText(hud)} strategic nodes`];
}

/** The phase a remaining time is in: the tightest threshold at or below it. */
export function phaseOf(remaining: number): Phase {
  return remaining <= THRESHOLD_TICKS[2]
    ? 3
    : remaining <= THRESHOLD_TICKS[1]
      ? 2
      : remaining <= THRESHOLD_TICKS[0]
        ? 1
        : 0;
}

export class FinalHours {
  private level: Phase = 0; // the highest threshold fired this campaign
  private seen = false; // the first update of a campaign restores, with no banner
  private campaignId: string | null = null;
  private ended = false;
  private hud: Hud | null = null;
  private card: { phase: Live; expiresAt: number | null } | null = null;
  private banner: { phase: Live; until: number } | null = null;

  private clear(): void {
    this.level = 0;
    this.seen = false;
    this.card = null;
    this.banner = null;
  }

  /** Delta events: a `CampaignEnded` clears everything; a new `campaign_id` re-arms every threshold. */
  ingest(events: readonly { kind: string; campaign_id?: string }[]): void {
    for (const ev of events) {
      const id = ev.campaign_id;
      if (id !== undefined && id !== this.campaignId) {
        if (this.campaignId !== null) {
          this.clear();
          this.ended = false;
        }
        this.campaignId = id;
      }
      if (ev.kind === "CampaignEnded") {
        this.clear();
        this.ended = true;
      }
    }
  }

  /** `remaining` is the war countdown in ticks (null: no limit); `tick` the store tick (null before a Snapshot). */
  update(
    hud: Hud | null,
    remaining: number | null,
    tick: number | null,
    nowMs: number,
  ): void {
    this.hud = hud;
    if (
      this.ended ||
      hud?.panels?.campaign_status?.result ||
      remaining === null ||
      tick === null
    ) {
      this.clear();
      return;
    }
    // An extension (or a new campaign) lifts remaining: the phase drops and its threshold re-arms.
    while (
      this.level > 0 &&
      remaining > THRESHOLD_TICKS[this.level - 1]! + HYSTERESIS_TICKS
    )
      this.level = (this.level - 1) as Phase;
    if (this.card && this.card.phase > this.level) this.card = null;
    if (this.banner && this.banner.phase > this.level) this.banner = null;
    const p = phaseOf(remaining);
    const restore = !this.seen;
    this.seen = true;
    const paused = hud?.campaign_clock.paused ?? false;
    if (p > this.level && (restore || !paused)) {
      this.level = p;
      this.card = {
        phase: p as Live,
        expiresAt: p === 3 ? null : tick + CARD_TTL_TICKS,
      };
      if (!restore)
        this.banner = { phase: p as Live, until: nowMs + BANNER_MS };
    }
  }

  /** The countdown push for the top bar; null outside the final hours. */
  push(): Push | null {
    if (this.level === 0) return null;
    return {
      phase: this.level,
      label: this.level === 3 ? "FINAL MINUTES" : "FINAL HOURS",
      score: scoreOf(this.hud),
    };
  }

  /** The centre-of-map banner text while it is live; never while paused (a pause banner wins). */
  bannerText(nowMs: number): string | null {
    const b = this.banner;
    if (!b || nowMs >= b.until || this.hud?.campaign_clock.paused) return null;
    return BANNER[b.phase - 1] ?? null;
  }

  /** The OV-26 card at this store tick, or null (expired, cleared or none). */
  cardAt(tick: number): FinalHoursCard | null {
    const c = this.card;
    if (!c || (c.expiresAt !== null && tick >= c.expiresAt)) return null;
    return {
      phase: c.phase,
      kicker: `FINAL HOURS · ${LEFT[c.phase - 1]}`,
      lines: cardLines(this.hud),
    };
  }
}
