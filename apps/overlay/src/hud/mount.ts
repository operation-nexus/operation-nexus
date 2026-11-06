// Wires the HUD pieces into the stage containers (OVERLAY §0.6) and feeds them from the wire frames.
import "./hud.css";
import type { Delta } from "../contracts/wire/delta";
import type { Hud, Snapshot } from "../contracts/wire/snapshot";
import type { WireStore } from "../net/store";
import type { Stage } from "../stage";
import { HudClock } from "./clock";
import { FinalHours } from "./final-hours";
import { Rotator } from "./rotator";
import { SitrepStack } from "./sitrep-stack";
import { TopBar, h, setText } from "./topbar";
import { WingmenFeed } from "./wingmen";

export interface HudView {
  frame: (f: Snapshot | Hud | Delta, store: WireStore) => void;
}

export function mountHud(
  stage: Pick<Stage, "panels" | "sitrep" | "toast">,
  win: Window,
  store: () => WireStore,
): HudView {
  const doc = win.document;
  const clock = new HudClock();
  const bar = new TopBar(doc, stage.panels);
  const names = () => ({
    sectors: [],
    nodes: (store().theater?.nodes ?? []).map((n) => ({
      id: n.node_id,
      name: n.name,
    })),
  });
  const place = (id: string): string =>
    names().nodes.find((n) => n.id === id)?.name ?? id;
  const rotor = new Rotator(doc, stage.panels, win, place);
  const fh = new FinalHours();
  const banner = h(doc, "div", "nx-fh-banner", stage.toast);
  banner.hidden = true;
  const wing = new WingmenFeed();
  const stack = new SitrepStack(
    doc,
    stage.sitrep,
    (id) => store().entities.get(id)?.callsign ?? undefined,
    names,
    (tick) => fh.cardAt(tick),
    wing,
  );
  bar.render(null, clock, fh); // cold start: every field "—" (§0.3, DI-1)
  return {
    frame: (f, s) => {
      if (f.type === "Delta") {
        clock.advance(f.tick);
        fh.ingest(f.events);
        fh.update(s.hud, clock.warRemaining(), s.tick, Date.now());
        wing.ingest(f.events, s.entities);
        stack.ingest(f.events, f.tick);
      } else {
        // Rebase only from a frame that carries a Hud; a Snapshot without one keeps the old clock basis.
        const hud = f.type === "Snapshot" ? f.hud : f;
        if (hud) clock.rebase(hud, s.tick);
        else if (f.type === "Snapshot") clock.advance(f.tick);
        rotor.update(s.hud);
        fh.update(s.hud, clock.warRemaining(), s.tick, Date.now());
        if (s.tick !== null) stack.render(s.tick);
      }
      bar.render(s.hud, clock, fh);
      const text = fh.bannerText(Date.now());
      banner.hidden = text === null;
      setText(banner, text ?? "");
    },
  };
}
