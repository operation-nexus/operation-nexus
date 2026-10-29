import type { TelemetryState, ThreatTier } from "../types/telemetry";
import { createElement } from "../utils/dom";
import { STRAIT_1_THEATER } from "../theater/strait1";
import { ThreatSitrepPanel } from "./threat-sitrep-panel";
import type { SitrepView } from "./threat-sitrep";

export class HudOverlay {
  private container: HTMLElement | null = null;
  private rootElement: HTMLElement | null = null;

  // Cached DOM elements
  private quorumFillEl: HTMLElement | null = null;
  private staticFillEl: HTMLElement | null = null;
  private quorumTextEl: HTMLElement | null = null;
  private staticTextEl: HTMLElement | null = null;
  private objectiveTextEl: HTMLElement | null = null;
  private countdownEl: HTMLElement | null = null;
  private threatBadgeEl: HTMLElement | null = null;
  private sitrepContainerEl: HTMLElement | null = null;
  private tickerTextEl: HTMLElement | null = null;
  private threatSitreps = new ThreatSitrepPanel(STRAIT_1_THEATER);

  initialize(parentContainer: HTMLElement): void {
    this.container = parentContainer;

    const overlay = createElement("div", "nexus-hud-overlay");
    overlay.style.position = "absolute";
    overlay.style.top = "0";
    overlay.style.left = "0";
    overlay.style.width = "100%";
    overlay.style.height = "100%";
    overlay.style.pointerEvents = "none";
    overlay.style.display = "flex";
    overlay.style.flexDirection = "column";
    overlay.style.justifyContent = "space-between";
    overlay.style.padding = "14px";
    overlay.style.boxSizing = "border-box";
    overlay.style.fontFamily = "monospace";
    overlay.style.zIndex = "50";

    // TOP HUD BAR: Momentum Bar, Objective Countdown, Threat Badge
    const topBar = createElement("div", "hud-top-bar");
    topBar.style.display = "flex";
    topBar.style.justifyContent = "space-between";
    topBar.style.alignItems = "center";
    topBar.style.gap = "16px";
    topBar.style.background = "rgba(9, 18, 33, 0.88)";
    topBar.style.border = "1px solid #1e3a5f";
    topBar.style.borderRadius = "8px";
    topBar.style.padding = "8px 16px";
    topBar.style.backdropFilter = "blur(8px)";

    // Momentum Gauge (OV-1 / OV-12)
    const momentumBox = createElement("div", "hud-momentum-box");
    momentumBox.style.display = "flex";
    momentumBox.style.alignItems = "center";
    momentumBox.style.gap = "10px";
    momentumBox.style.minWidth = "280px";

    const quorumLabel = createElement("span");
    quorumLabel.style.color = "#00e5ff";
    quorumLabel.style.fontWeight = "bold";
    quorumLabel.style.fontSize = "11px";
    quorumLabel.textContent = "QUORUM ";
    const quorumPctSpan = createElement("span");
    quorumPctSpan.id = "hud-quorum-pct";
    quorumPctSpan.textContent = "50%";
    quorumLabel.appendChild(quorumPctSpan);

    const barTrack = createElement("div");
    barTrack.style.flex = "1";
    barTrack.style.height = "10px";
    barTrack.style.background = "#0f172a";
    barTrack.style.border = "1px solid #1e3a5f";
    barTrack.style.borderRadius = "999px";
    barTrack.style.overflow = "hidden";
    barTrack.style.display = "flex";

    const quorumFill = createElement("div");
    quorumFill.id = "hud-quorum-fill";
    quorumFill.style.width = "50%";
    quorumFill.style.height = "100%";
    quorumFill.style.background = "linear-gradient(90deg, #0284c7, #00e5ff)";
    quorumFill.style.transition = "width 0.3s ease";

    const staticFill = createElement("div");
    staticFill.id = "hud-static-fill";
    staticFill.style.width = "50%";
    staticFill.style.height = "100%";
    staticFill.style.background = "linear-gradient(90deg, #ff0055, #be123c)";
    staticFill.style.transition = "width 0.3s ease";

    barTrack.appendChild(quorumFill);
    barTrack.appendChild(staticFill);

    const staticLabel = createElement("span");
    staticLabel.style.color = "#ff0055";
    staticLabel.style.fontWeight = "bold";
    staticLabel.style.fontSize = "11px";
    const staticPctSpan = createElement("span");
    staticPctSpan.id = "hud-static-pct";
    staticPctSpan.textContent = "50%";
    staticLabel.appendChild(staticPctSpan);
    const staticSuffix = createElement("span");
    staticSuffix.textContent = " STATIC";
    staticLabel.appendChild(staticSuffix);

    momentumBox.appendChild(quorumLabel);
    momentumBox.appendChild(barTrack);
    momentumBox.appendChild(staticLabel);

    // Objective Pill Banner
    const objectivePill = createElement("div", "hud-objective-pill");
    objectivePill.style.display = "flex";
    objectivePill.style.alignItems = "center";
    objectivePill.style.gap = "12px";
    objectivePill.style.background = "rgba(15, 23, 42, 0.7)";
    objectivePill.style.border = "1px solid #38bdf8";
    objectivePill.style.borderRadius = "20px";
    objectivePill.style.padding = "4px 14px";

    const objectiveName = createElement("span");
    objectiveName.id = "hud-objective-name";
    objectiveName.style.color = "#f8fafc";
    objectiveName.style.fontSize = "11px";
    objectiveName.style.letterSpacing = "0.8px";
    objectiveName.textContent = "SECURE STRAIT CROSSINGS";

    const countdown = createElement("span");
    countdown.id = "hud-countdown";
    countdown.style.color = "#f59e0b";
    countdown.style.fontWeight = "bold";
    countdown.style.fontSize = "12px";
    countdown.style.background = "rgba(245, 158, 11, 0.15)";
    countdown.style.padding = "2px 8px";
    countdown.style.borderRadius = "12px";
    countdown.textContent = "15:00";

    objectivePill.appendChild(objectiveName);
    objectivePill.appendChild(countdown);

    // Threat Director Condition Badge (OV-19)
    const threatBadge = createElement("div");
    threatBadge.id = "hud-threat-badge";
    threatBadge.style.fontSize = "10px";
    threatBadge.style.fontWeight = "bold";
    threatBadge.style.padding = "4px 10px";
    threatBadge.style.borderRadius = "4px";
    threatBadge.style.border = "1px solid #10b981";
    threatBadge.style.color = "#10b981";
    threatBadge.style.background = "rgba(16, 185, 129, 0.12)";
    threatBadge.textContent = "DEFCON: PATTERN OF LIFE";

    topBar.appendChild(momentumBox);
    topBar.appendChild(objectivePill);
    topBar.appendChild(threatBadge);

    // MIDDLE LAYER: Link-16 Sitrep Feed
    const middleRow = createElement("div");
    middleRow.style.display = "flex";
    middleRow.style.justifyContent = "flex-start";
    middleRow.style.marginTop = "10px";

    const sitrepCard = createElement("div");
    sitrepCard.style.background = "rgba(9, 18, 33, 0.82)";
    sitrepCard.style.border = "1px solid rgba(30, 58, 95, 0.7)";
    sitrepCard.style.borderRadius = "6px";
    sitrepCard.style.padding = "8px 12px";
    sitrepCard.style.width = "320px";
    sitrepCard.style.backdropFilter = "blur(6px)";

    const sitrepTitle = createElement("div");
    sitrepTitle.style.fontSize = "9px";
    sitrepTitle.style.color = "#38bdf8";
    sitrepTitle.style.letterSpacing = "1px";
    sitrepTitle.style.borderBottom = "1px solid rgba(30, 58, 95, 0.5)";
    sitrepTitle.style.paddingBottom = "4px";
    sitrepTitle.style.marginBottom = "6px";
    sitrepTitle.textContent = "LINK-16 TACTICAL SITREP FEED";

    const sitrepLog = createElement("div");
    sitrepLog.id = "hud-sitrep-log";
    sitrepLog.style.display = "flex";
    sitrepLog.style.flexDirection = "column";
    sitrepLog.style.gap = "4px";
    sitrepLog.style.fontSize = "9px";
    sitrepLog.style.minHeight = "80px";

    const initRow = createElement("div");
    initRow.style.color = "#94a3b8";
    initRow.textContent = "[00:00] SITREP INITIALIZED. MONITORING STRAIT-1.";
    sitrepLog.appendChild(initRow);

    sitrepCard.appendChild(sitrepTitle);
    sitrepCard.appendChild(sitrepLog);
    middleRow.appendChild(sitrepCard);

    // BOTTOM BAR: How-to-Play Marquee Ticker
    const bottomBar = createElement("div", "hud-bottom-bar");
    bottomBar.style.background = "rgba(9, 18, 33, 0.92)";
    bottomBar.style.border = "1px solid #1e3a5f";
    bottomBar.style.borderRadius = "6px";
    bottomBar.style.padding = "6px 14px";
    bottomBar.style.display = "flex";
    bottomBar.style.alignItems = "center";
    bottomBar.style.gap = "14px";
    bottomBar.style.backdropFilter = "blur(8px)";

    const howToBadge = createElement("div");
    howToBadge.style.background = "#00e5ff";
    howToBadge.style.color = "#020617";
    howToBadge.style.fontSize = "10px";
    howToBadge.style.fontWeight = "bold";
    howToBadge.style.padding = "2px 8px";
    howToBadge.style.borderRadius = "4px";
    howToBadge.style.whiteSpace = "nowrap";
    howToBadge.textContent = "HOW TO PLAY";

    const tickerWrap = createElement("div");
    tickerWrap.style.flex = "1";
    tickerWrap.style.overflow = "hidden";
    tickerWrap.style.whiteSpace = "nowrap";

    const tickerMarquee = createElement("span");
    tickerMarquee.id = "hud-ticker-marquee";
    tickerMarquee.style.color = "#e2e8f0";
    tickerMarquee.style.fontSize = "10px";
    tickerMarquee.style.letterSpacing = "0.5px";
    tickerMarquee.textContent =
      "TYPE !join strike | recon | logi TO DEPLOY \u2022 PROTECT NORTH & SOUTH HIGHWAY BRIDGES \u2022 SECURE REAR HAVEN CONVOYS";

    tickerWrap.appendChild(tickerMarquee);
    bottomBar.appendChild(howToBadge);
    bottomBar.appendChild(tickerWrap);

    overlay.appendChild(topBar);
    overlay.appendChild(middleRow);
    overlay.appendChild(bottomBar);
    this.threatSitreps.mount(overlay);

    this.container.appendChild(overlay);
    this.rootElement = overlay;

    // Cache element references
    this.quorumFillEl = overlay.querySelector("#hud-quorum-fill");
    this.staticFillEl = overlay.querySelector("#hud-static-fill");
    this.quorumTextEl = overlay.querySelector("#hud-quorum-pct");
    this.staticTextEl = overlay.querySelector("#hud-static-pct");
    this.objectiveTextEl = overlay.querySelector("#hud-objective-name");
    this.countdownEl = overlay.querySelector("#hud-countdown");
    this.threatBadgeEl = overlay.querySelector("#hud-threat-badge");
    this.sitrepContainerEl = overlay.querySelector("#hud-sitrep-log");
    this.tickerTextEl = overlay.querySelector("#hud-ticker-marquee");
  }

  update(state: TelemetryState): void {
    if (!this.rootElement) return;

    // 1. Momentum Bar Update
    const quorumPct = Math.max(
      0,
      Math.min(100, Math.round(state.momentum.quorum)),
    );
    const staticPct = 100 - quorumPct;
    if (this.quorumFillEl) this.quorumFillEl.style.width = `${quorumPct}%`;
    if (this.staticFillEl) this.staticFillEl.style.width = `${staticPct}%`;
    if (this.quorumTextEl) this.quorumTextEl.textContent = `${quorumPct}%`;
    if (this.staticTextEl) this.staticTextEl.textContent = `${staticPct}%`;

    // 2. Objective & Countdown
    if (this.objectiveTextEl) {
      this.objectiveTextEl.textContent = state.objectiveName.toUpperCase();
    }
    if (this.countdownEl) {
      const mins = Math.floor(state.countdownSeconds / 60)
        .toString()
        .padStart(2, "0");
      const secs = (state.countdownSeconds % 60).toString().padStart(2, "0");
      this.countdownEl.textContent = `${mins}:${secs}`;
    }

    // 3. Threat Badge Update (OV-19)
    if (this.threatBadgeEl) {
      this.applyThreatBadgeStyle(state.threatTier);
    }

    // 4. Link-16 Sitrep Feed (Last 6 entries)
    if (this.sitrepContainerEl && state.sitrep && state.sitrep.length > 0) {
      const recent = state.sitrep.slice(-6);
      const container = this.sitrepContainerEl;
      for (const child of Array.from(container.children)) {
        container.removeChild(child);
      }
      for (const item of recent) {
        const row = createElement("div");
        row.style.color =
          item.side === "COALITION"
            ? "#00e5ff"
            : item.side === "ENEMY"
              ? "#ff0055"
              : "#94a3b8";
        row.style.overflow = "hidden";
        row.style.textOverflow = "ellipsis";
        row.style.whiteSpace = "nowrap";
        row.textContent = `[${item.id}] ${item.text}`;
        container.appendChild(row);
      }
    }

    // 5. Ticker Update
    if (this.tickerTextEl && state.ticker && state.ticker.length > 0) {
      const tickerJoined = state.ticker
        .map((t) => `${t.category}: ${t.text}`)
        .join(" \u2022 ");
      this.tickerTextEl.textContent = `TYPE !join strike | recon | logi TO PLAY \u2022 ${tickerJoined}`;
    }
  }

  // OV-26 threat sitrep stack (NX-496).
  updateThreatSitreps(view: SitrepView): void {
    this.threatSitreps.render(view);
  }

  private applyThreatBadgeStyle(tier: ThreatTier): void {
    if (!this.threatBadgeEl) return;

    if (tier === "BRAVO") {
      this.threatBadgeEl.textContent = "THREAT: CONDITION BRAVO (ALERT)";
      this.threatBadgeEl.style.borderColor = "#ff0055";
      this.threatBadgeEl.style.color = "#ff0055";
      this.threatBadgeEl.style.backgroundColor = "rgba(255, 0, 85, 0.2)";
      this.threatBadgeEl.style.boxShadow = "0 0 10px rgba(255, 0, 85, 0.6)";
    } else if (tier === "ALPHA") {
      this.threatBadgeEl.textContent = "THREAT: CONDITION ALPHA (CAUTION)";
      this.threatBadgeEl.style.borderColor = "#f59e0b";
      this.threatBadgeEl.style.color = "#f59e0b";
      this.threatBadgeEl.style.backgroundColor = "rgba(245, 158, 11, 0.15)";
      this.threatBadgeEl.style.boxShadow = "none";
    } else {
      this.threatBadgeEl.textContent = "THREAT: PATTERN OF LIFE (NOMINAL)";
      this.threatBadgeEl.style.borderColor = "#10b981";
      this.threatBadgeEl.style.color = "#10b981";
      this.threatBadgeEl.style.backgroundColor = "rgba(16, 185, 129, 0.12)";
      this.threatBadgeEl.style.boxShadow = "none";
    }
  }

  dispose(): void {
    this.threatSitreps.dispose();
    if (this.rootElement && this.rootElement.parentElement) {
      this.rootElement.parentElement.removeChild(this.rootElement);
    }
    this.rootElement = null;
    this.container = null;
  }
}
