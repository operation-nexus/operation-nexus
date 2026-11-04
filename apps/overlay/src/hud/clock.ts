// Campaign-clock timers (OVERLAY §0.5): objective countdown and war countdown, in game ticks.
// Re-based on every Hud/Snapshot, advanced by the ticks the Delta stream reports, frozen while paused.
import type { Hud } from "../contracts/wire/snapshot";
import { DASH } from "./strings";

export const TICKS_PER_S = 10; // SC-2

const p2 = (n: number): string => String(n).padStart(2, "0");

/** m:ss, or h:mm:ss when `hours`; DASH for null (DI-1). Expired shows 0, not a negative. */
export function fmtTicks(ticks: number | null, hours: boolean): string {
  if (ticks === null) return DASH;
  const s = Math.floor(Math.max(0, ticks) / TICKS_PER_S);
  if (hours && s >= 3600)
    return `${Math.floor(s / 3600)}:${p2(Math.floor((s % 3600) / 60))}:${p2(s % 60)}`;
  return `${p2(Math.floor(s / 60))}:${p2(s % 60)}`;
}

export class HudClock {
  private hud: Hud | null = null;
  private elapsed = 0;
  private last: number | null = null;

  /** `tick` is the store's last applied tick (null before the first Snapshot). */
  rebase(h: Hud, tick: number | null): void {
    this.hud = h;
    this.elapsed = h.campaign_clock.elapsed_ticks;
    this.last = tick;
  }

  advance(tick: number): void {
    if (
      this.hud !== null &&
      this.last !== null &&
      !this.hud.campaign_clock.paused
    )
      this.elapsed += Math.max(0, tick - this.last);
    this.last = Math.max(this.last ?? tick, tick); // never backwards
  }

  objective(): string {
    const d = this.hud?.objective?.deadline_tick ?? null;
    return fmtTicks(d === null ? null : d - this.elapsed, false);
  }

  war(): string {
    const l = this.hud?.campaign_clock.limit_ticks ?? null;
    return fmtTicks(l === null ? null : l - this.elapsed, true);
  }
}
