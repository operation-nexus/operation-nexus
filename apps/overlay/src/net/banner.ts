// Connection banners (OVERLAY §0.3). Fixed strings only, never server text or the token (SEC-OV-1).
import "./banner.css";

export type Fatal = "UPDATE_REQUIRED" | "AUTH_FAILED";
export interface ConnState {
  fatal: Fatal | null;
  stale: boolean; // 2 s without data (WP-5)
  hadData: boolean; // a Snapshot has been applied
}

const TEXT: Record<Fatal | "COMMS_RESYNC", string> = {
  UPDATE_REQUIRED: "UPDATE REQUIRED",
  AUTH_FAILED: "AUTH FAILED",
  COMMS_RESYNC: "COMMS RESYNC",
};

/** A fatal state outranks COMMS RESYNC (UPDATE REQUIRED is only ever set once fatal); null = no banner. */
export function bannerText(s: ConnState): string | null {
  if (s.fatal) return TEXT[s.fatal];
  return s.stale ? TEXT.COMMS_RESYNC : null;
}

/** `dim` holds the last rendered frame; it stays, dimmed, under the banner. Sets html[data-nx-state]. */
export function renderBanner(
  banner: HTMLElement,
  dim: HTMLElement,
  s: ConnState,
): void {
  const text = bannerText(s);
  banner.hidden = text === null;
  banner.textContent = text ?? "";
  dim.classList.toggle("nx-dim", text !== null && s.hadData);
  banner.ownerDocument.documentElement.dataset["nxState"] = !s.hadData
    ? "cold"
    : text === null
      ? "live"
      : "degraded";
}
