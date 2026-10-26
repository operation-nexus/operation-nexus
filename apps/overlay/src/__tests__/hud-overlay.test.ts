import { describe, expect, it } from "vitest";
import { HudOverlay } from "../hud/hud-overlay";
import type { TelemetryState } from "../types/telemetry";
import { createElement } from "../utils/dom";

function createMockContainer(): HTMLElement {
  return createElement("div");
}

describe("Real-Time Telemetry HUD Overlay", () => {
  it("initializes and mounts HUD elements", () => {
    const hud = new HudOverlay();
    const container = createMockContainer();

    hud.initialize(container);

    const overlayEl = container.querySelector(".nexus-hud-overlay");
    expect(overlayEl).not.toBeNull();

    expect(container.querySelector("#hud-quorum-fill")).not.toBeNull();
    expect(container.querySelector("#hud-static-fill")).not.toBeNull();
    expect(container.querySelector("#hud-objective-name")).not.toBeNull();
    expect(container.querySelector("#hud-countdown")).not.toBeNull();
    expect(container.querySelector("#hud-threat-badge")).not.toBeNull();
    expect(container.querySelector("#hud-sitrep-log")).not.toBeNull();
    expect(container.querySelector("#hud-ticker-marquee")).not.toBeNull();
  });

  it("updates momentum gauge, countdown, threat badge, and sitrep entries", () => {
    const hud = new HudOverlay();
    const container = createMockContainer();
    hud.initialize(container);

    const state: TelemetryState = {
      momentum: { quorum: 65, static: 35 },
      countdownSeconds: 842, // 14:02
      objectiveName: "CAPTURE NORTH BRIDGEHEAD",
      threatTier: "BRAVO",
      sitrep: [
        {
          id: "S1",
          timestamp: 1000,
          text: "NORTH BRIDGE DAMAGED",
          severity: "alert",
          side: "NEUTRAL",
        },
        {
          id: "S2",
          timestamp: 2000,
          text: "VIPER-01 DESTROYED STATIC CONVOY",
          severity: "info",
          side: "COALITION",
        },
      ],
      ticker: [
        {
          id: "T1",
          category: "RECRUITMENT",
          text: "TYPE !join strike TO PLAY",
        },
      ],
    };

    hud.update(state);

    const quorumPct = container.querySelector("#hud-quorum-pct");
    expect(quorumPct?.textContent).toBe("65%");

    const staticPct = container.querySelector("#hud-static-pct");
    expect(staticPct?.textContent).toBe("35%");

    const countdown = container.querySelector("#hud-countdown");
    expect(countdown?.textContent).toBe("14:02");

    const objective = container.querySelector("#hud-objective-name");
    expect(objective?.textContent).toBe("CAPTURE NORTH BRIDGEHEAD");

    const threatBadge = container.querySelector("#hud-threat-badge");
    expect(threatBadge?.textContent).toContain("CONDITION BRAVO");

    const sitrep = container.querySelector("#hud-sitrep-log");
    expect(sitrep?.textContent).toContain("VIPER-01 DESTROYED STATIC CONVOY");

    // Test transition to PATTERN_OF_LIFE and ALPHA
    hud.update({
      ...state,
      threatTier: "PATTERN_OF_LIFE",
    });
    expect(threatBadge?.textContent).toContain("PATTERN OF LIFE");

    hud.update({
      ...state,
      threatTier: "ALPHA",
    });
    expect(threatBadge?.textContent).toContain("CONDITION ALPHA");

    hud.dispose();
  });
});
