// The one rotating panel (OVERLAY §0.6, OV-14): NEEDED, operators, Top Commanders per role.
// A member with no real rows is skipped, never padded (DI-4). NEEDED shows at double frequency.
import type { Hud } from "../contracts/wire/snapshot";
import { h } from "./topbar";
import { DASH, t } from "./strings";

/** hud.rotation_s (PROPOSED 15 s, real time, OV-14). */
export const ROTATION_S = 15;

export interface Member {
  id: string;
  title: string;
  rows: string[];
}

/** `place` turns a node id into its theater name; an unknown id shows as the id. */
export function members(
  hud: Hud | null,
  place: (id: string) => string,
): { needed: Member | null; others: Member[] } {
  const none = { needed: null, others: [] };
  if (hud === null) return none;
  const jobs = hud.panels?.tasking_needed ?? [];
  const needed: Member | null =
    jobs.length === 0
      ? null
      : {
          id: "needed",
          title: t("hud.needed"),
          rows: jobs.map((j) => {
            const where = j.node_id ? place(j.node_id) : (j.sector_id ?? DASH);
            return `${j.job_kind} ${where}, ${j.slots_open} open`;
          }),
        };
  const others: Member[] = [];
  const by = hud.operators;
  const bands = by?.by_rank_band ?? [];
  if (by && (by.by_role.length > 0 || bands.length > 0))
    others.push({
      id: "operators",
      title: t("hud.operators"),
      rows: [
        ...by.by_role.map((r) => `${r.role}: ${r.count}`),
        ...bands.map((r) => `${r.band}: ${r.count}`),
      ],
    });
  for (const c of hud.panels?.top_commanders ?? [])
    if (c.rows.length > 0)
      others.push({
        id: `top-${c.role}`,
        title: `${t("hud.top")} ${c.role}`,
        rows: c.rows.map((r) => `${r.callsign}: ${r.value}`),
      });
  return { needed, others };
}

/** One rotation cycle: NEEDED twice, every other member once, NEEDED spread apart (1:1 with a single other member). */
export function cycle(needed: Member | null, others: Member[]): Member[] {
  if (needed === null) return others;
  if (others.length === 0) return [needed];
  // One other member: a 2:1 cycle would show NEEDED twice in a row (30 s) on wrap, so it alternates 1:1.
  if (others.length === 1) return [needed, ...others];
  const mid = Math.ceil(others.length / 2);
  return [needed, ...others.slice(0, mid), needed, ...others.slice(mid)];
}

export class Rotator {
  private n = 0;
  private cur: string | null = null;
  private hud: Hud | null = null;
  private body: HTMLElement;
  private title: HTMLElement;
  private timer: number;

  constructor(
    private doc: Document,
    parent: HTMLElement,
    private win: Pick<Window, "setInterval" | "clearInterval">,
    private place: (id: string) => string,
    private dwellS = ROTATION_S,
  ) {
    const root = h(doc, "div", "nx-rotor", parent);
    this.title = h(doc, "div", "nx-rotor-title", root);
    this.body = h(doc, "div", "nx-rotor-rows", root);
    root.hidden = true;
    this.timer = this.arm();
  }

  private arm(): number {
    return this.win.setInterval(() => this.step(), this.dwellS * 1000);
  }

  /** New Hud: refresh the visible member in place; jump on if it just lost its rows. */
  update(hud: Hud | null): void {
    this.hud = hud;
    const m = members(hud, this.place);
    const live = [m.needed, ...m.others].find((x) => x?.id === this.cur);
    if (live) this.show(live);
    else {
      // The panel was empty and now has members: the first one gets a full dwell.
      if (this.cur === null) {
        this.win.clearInterval(this.timer);
        this.timer = this.arm();
      }
      this.step();
    }
  }

  step(): void {
    const m = members(this.hud, this.place);
    const seq = cycle(m.needed, m.others);
    const next = seq.length === 0 ? null : (seq[this.n++ % seq.length] ?? null);
    this.cur = next?.id ?? null;
    this.show(next);
  }

  private show(m: Member | null | undefined): void {
    const root = this.title.parentElement;
    if (root) root.hidden = !m;
    if (!m) return;
    this.title.textContent = m.title;
    this.body.replaceChildren(
      ...m.rows.map((r) => h(this.doc, "div", "nx-rotor-row", undefined, r)),
    );
  }
}
