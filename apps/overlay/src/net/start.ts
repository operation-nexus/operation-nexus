// Wires the WS client and banner into the page. Does nothing without `#token=` (prototype dev mode).
import { renderBanner } from "./banner";
import { takeToken, WireClient } from "./wire-client";

// [UNVERIFIED] path: the server endpoint ships with NX-170 (b); change here when it lands.
export const WS_PATH = "/ws";

export function startFeed(win: Window, dim: HTMLElement): WireClient | null {
  const token = takeToken(win.location, win.history);
  if (token === null) return null;
  const doc = win.document;
  const banner = doc.createElement("div");
  banner.className = "nx-banner";
  banner.hidden = true;
  doc.body.appendChild(banner);
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
    onState: (s) => renderBanner(banner, dim, s),
  });
  client.start();
  return client;
}
