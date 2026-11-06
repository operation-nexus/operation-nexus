// Wires the WS client and banner into the page. Does nothing without `#token=` (prototype dev mode).
import { renderBanner } from "./banner";
import { mountHud } from "../hud/mount";
import { LiveMap } from "../live-map";
import type { Stage } from "../stage";
import { takeToken, WireClient } from "./wire-client";

// [UNVERIFIED] path: the server endpoint ships with NX-170 (b); change here when it lands.
export const WS_PATH = "/ws";

/** `mount` runs only when a token is present, so the no-token prototype keeps `#root` to itself. */
export function startFeed(
  win: Window,
  mount: () => Pick<
    Stage,
    | "world"
    | "banners"
    | "showTheater"
    | "showNodes"
    | "panels"
    | "sitrep"
    | "toast"
    | "units"
    | "fx"
  >,
): WireClient | null {
  const token = takeToken(win.location, win.history);
  if (token === null) return null;
  const doc = win.document;
  const surface = mount();
  const banner = doc.createElement("div");
  banner.className = "nx-banner";
  banner.hidden = true;
  surface.banners.appendChild(banner);
  const hud = mountHud(surface, win, () => client.store);
  const live = new LiveMap(surface.units, surface.fx, () => client.store, {
    now: () => win.performance.now(),
    raf: (cb) => win.requestAnimationFrame(cb),
    caf: (id) => win.cancelAnimationFrame(id),
  });
  const scheme = win.location.protocol === "https:" ? "wss:" : "ws:";
  const client = new WireClient({
    url: `${scheme}//${win.location.host}${WS_PATH}`,
    token,
    makeSocket: (u) => new WebSocket(u) as never,
    random: Math.random,
    uptimeMs: () => win.performance.now(),
    // The hash was cleared, so a reload would lose the token: put it back for the reload only;
    // the next page load clears it again.
    reload: (t) => {
      win.history.replaceState(null, "", `#token=${encodeURIComponent(t)}`);
      win.location.reload();
    },
    onState: (s) => renderBanner(banner, surface.world, s),
    onFrame: (f) => {
      surface.showNodes(client.store.nodes);
      live.onFrame(f);
      hud.frame(f, client.store);
    },
    onWelcome: () => {
      const t = client.store.theater;
      if (t !== null) surface.showTheater(t);
      live.reset();
    },
  });
  client.start();
  live.start();
  return client;
}
