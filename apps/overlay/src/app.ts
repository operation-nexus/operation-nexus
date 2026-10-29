import { RenderManager } from "./renderers/manager";
import { HudOverlay } from "./hud/hud-overlay";
import { SimulationFeedGenerator } from "./simulation/mock-feed";
import { HoloTableEngine } from "./renderers/holo3d/holo-engine";
import { FlirMfdEngine } from "./renderers/flir/flir-engine";
import { ThreatSitrepBoard } from "./hud/threat-sitrep";
import type { RenderFrameState } from "./types/render";

export class TacticalC2App {
  private root: HTMLElement;
  private renderManager = new RenderManager();
  private hud = new HudOverlay();
  private feedGenerator = new SimulationFeedGenerator();
  private sitrepBoard = new ThreatSitrepBoard();

  private viewportContainer: HTMLElement | null = null;
  private controlDeckEl: HTMLElement | null = null;
  private animFrameId: number | null = null;
  private isHighDensityMode = false;

  constructor(root: HTMLElement) {
    this.root = root;
  }

  async start(): Promise<void> {
    this.buildLayout();

    if (!this.viewportContainer) {
      throw new Error("Viewport container failed to build");
    }

    // Attach RenderManager and Telemetry HUD
    const urlParams =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search)
        : null;
    const requested = urlParams?.get("theme") ?? "crt";
    const known = this.renderManager.getAvailableThemes().map((t) => t.id);
    const initialTheme = known.includes(requested) ? requested : "crt";

    await this.renderManager.attach(this.viewportContainer, initialTheme);
    this.highlightActiveThemeButton(initialTheme);
    this.updateSecondaryControls(initialTheme);
    this.hud.initialize(this.viewportContainer);

    this.setupWindowResize();
    this.startRenderLoop();
  }

  private buildLayout(): void {
    this.root.replaceChildren();
    this.root.style.width = "100vw";
    this.root.style.height = "100vh";
    this.root.style.margin = "0";
    this.root.style.padding = "0";
    this.root.style.overflow = "hidden";
    this.root.style.display = "flex";
    this.root.style.flexDirection = "column";
    this.root.style.backgroundColor = "#020617";
    this.root.style.color = "#f8fafc";
    this.root.style.fontFamily = "monospace";

    // 1. Interactive Control Deck Header
    const controlDeck = document.createElement("header");
    controlDeck.className = "nexus-control-deck";
    controlDeck.style.display = "flex";
    controlDeck.style.alignItems = "center";
    controlDeck.style.justifyContent = "space-between";
    controlDeck.style.padding = "8px 16px";
    controlDeck.style.background = "#090d16";
    controlDeck.style.borderBottom = "1px solid #1e293b";
    controlDeck.style.zIndex = "100";

    const brandGroup = document.createElement("div");
    brandGroup.style.display = "flex";
    brandGroup.style.alignItems = "center";
    brandGroup.style.gap = "10px";

    const brandTitle = document.createElement("span");
    brandTitle.style.fontWeight = "700";
    brandTitle.style.color = "#00e5ff";
    brandTitle.style.letterSpacing = "1px";
    brandTitle.style.fontSize = "13px";
    brandTitle.textContent = "HIVEPLEX / OPERATION NEXUS";

    const brandBadge = document.createElement("span");
    brandBadge.style.background = "rgba(0, 229, 255, 0.15)";
    brandBadge.style.border = "1px solid #00e5ff";
    brandBadge.style.color = "#00e5ff";
    brandBadge.style.fontSize = "9px";
    brandBadge.style.padding = "2px 6px";
    brandBadge.style.borderRadius = "4px";
    brandBadge.textContent = "C2 LIVE OVERLAY";

    brandGroup.appendChild(brandTitle);
    brandGroup.appendChild(brandBadge);

    // Segmented Paradigm Switcher (Emil Kowalski Smooth Tabs)
    const switcher = document.createElement("div");
    switcher.className = "paradigm-switcher";
    switcher.style.display = "flex";
    switcher.style.gap = "4px";
    switcher.style.background = "#0d131f";
    switcher.style.padding = "3px";
    switcher.style.borderRadius = "6px";
    switcher.style.border = "1px solid #1e293b";

    const themes: Array<{ id: string; label: string; active: boolean }> = [
      { id: "crt", label: "OPT A: 2D CRT VECTOR", active: true },
      { id: "holo3d", label: "OPT B: 3D HOLO TABLE", active: false },
      { id: "flir", label: "OPT C: FLIR MFD", active: false },
      { id: "batch", label: "OPT D: BATCH (500+)", active: false },
    ];

    for (const theme of themes) {
      const btn = document.createElement("button");
      btn.setAttribute("data-theme", theme.id);
      btn.className = "deck-btn";
      btn.style.background = theme.active ? "#00e5ff" : "transparent";
      btn.style.color = theme.active ? "#020617" : "#94a3b8";
      btn.style.border = "none";
      btn.style.padding = "4px 10px";
      btn.style.fontSize = "10px";
      btn.style.borderRadius = "4px";
      btn.style.cursor = "pointer";
      btn.style.fontFamily = "monospace";
      btn.style.fontWeight = theme.active ? "bold" : "normal";
      btn.textContent = theme.label;
      switcher.appendChild(btn);
    }

    // Secondary Controls: 3D Camera / FLIR polarity / Swarm toggle
    const secondary = document.createElement("div");
    secondary.id = "deck-secondary-controls";
    secondary.style.display = "flex";
    secondary.style.alignItems = "center";
    secondary.style.gap = "6px";

    const secBtns: Array<{ id: string; label: string; hidden: boolean }> = [
      { id: "btn-camera-wide", label: "WIDE CAM", hidden: true },
      { id: "btn-camera-combat", label: "COMBAT 45\u00b0", hidden: true },
      { id: "btn-camera-top", label: "TOP-DOWN", hidden: true },
      { id: "btn-toggle-flir-polarity", label: "FLIR POLARITY", hidden: true },
      { id: "btn-toggle-500-swarm", label: "500+ SWARM: OFF", hidden: false },
    ];

    for (const cfg of secBtns) {
      const btn = document.createElement("button");
      btn.id = cfg.id;
      if (cfg.hidden) btn.style.display = "none";
      btn.style.background = "#1e293b";
      btn.style.color = "#f8fafc";
      btn.style.border = "1px solid #334155";
      btn.style.padding = "3px 8px";
      btn.style.fontSize = "9px";
      btn.style.borderRadius = "4px";
      btn.style.cursor = "pointer";
      btn.textContent = cfg.label;
      secondary.appendChild(btn);
    }

    controlDeck.appendChild(brandGroup);
    controlDeck.appendChild(switcher);
    controlDeck.appendChild(secondary);

    this.root.appendChild(controlDeck);
    this.controlDeckEl = controlDeck;

    // 2. Stage Viewport Container (decidedly houses the active canvas and HUD overlay)
    const stageContainer = document.createElement("div");
    stageContainer.className = "nexus-stage-viewport";
    stageContainer.style.flex = "1";
    stageContainer.style.position = "relative";
    stageContainer.style.width = "100%";
    stageContainer.style.height = "100%";
    stageContainer.style.overflow = "hidden";
    stageContainer.style.backgroundColor = "#050b14";

    this.root.appendChild(stageContainer);
    this.viewportContainer = stageContainer;

    this.wireControlEvents();
  }

  private wireControlEvents(): void {
    if (!this.controlDeckEl) return;

    // Wire paradigm switcher buttons
    const buttons =
      this.controlDeckEl.querySelectorAll<HTMLButtonElement>("[data-theme]");
    buttons.forEach((btn) => {
      btn.addEventListener("click", async () => {
        const themeId = btn.getAttribute("data-theme");
        if (!themeId) return;

        this.highlightActiveThemeButton(themeId);
        await this.renderManager.switchTheme(themeId);
        this.updateSecondaryControls(themeId);
      });
    });

    // Wire secondary 3D Camera presets
    const btnWide =
      this.controlDeckEl.querySelector<HTMLButtonElement>("#btn-camera-wide");
    const btnCombat =
      this.controlDeckEl.querySelector<HTMLButtonElement>("#btn-camera-combat");
    const btnTop =
      this.controlDeckEl.querySelector<HTMLButtonElement>("#btn-camera-top");

    btnWide?.addEventListener("click", () => {
      const active = this.renderManager.getActiveEngine();
      if (active instanceof HoloTableEngine) active.setCameraPreset("WIDE");
    });
    btnCombat?.addEventListener("click", () => {
      const active = this.renderManager.getActiveEngine();
      if (active instanceof HoloTableEngine)
        active.setCameraPreset("COMBAT_45");
    });
    btnTop?.addEventListener("click", () => {
      const active = this.renderManager.getActiveEngine();
      if (active instanceof HoloTableEngine) active.setCameraPreset("TOP_DOWN");
    });

    // Wire FLIR polarity button
    const btnPolarity = this.controlDeckEl.querySelector<HTMLButtonElement>(
      "#btn-toggle-flir-polarity",
    );
    btnPolarity?.addEventListener("click", () => {
      const active = this.renderManager.getActiveEngine();
      if (active instanceof FlirMfdEngine) {
        const next =
          active.getPolarity() === "WHITE_HOT" ? "BLACK_HOT" : "WHITE_HOT";
        active.setPolarity(next);
        btnPolarity.textContent = `POLARITY: ${next}`;
      }
    });

    // Wire 500+ unit swarm toggle
    const btnSwarm = this.controlDeckEl.querySelector<HTMLButtonElement>(
      "#btn-toggle-500-swarm",
    );
    btnSwarm?.addEventListener("click", () => {
      this.isHighDensityMode = !this.isHighDensityMode;
      btnSwarm.textContent = `500+ SWARM: ${this.isHighDensityMode ? "ON" : "OFF"}`;
      btnSwarm.style.borderColor = this.isHighDensityMode
        ? "#00e5ff"
        : "#334155";
      btnSwarm.style.color = this.isHighDensityMode ? "#00e5ff" : "#f8fafc";
    });
  }

  private highlightActiveThemeButton(themeId: string): void {
    if (!this.controlDeckEl) return;
    const buttons =
      this.controlDeckEl.querySelectorAll<HTMLButtonElement>("[data-theme]");
    buttons.forEach((b) => {
      const isActive = b.getAttribute("data-theme") === themeId;
      b.style.background = isActive ? "#00e5ff" : "transparent";
      b.style.color = isActive ? "#020617" : "#94a3b8";
      b.style.fontWeight = isActive ? "bold" : "normal";
    });
  }

  private updateSecondaryControls(themeId: string): void {
    if (!this.controlDeckEl) return;
    const btnWide =
      this.controlDeckEl.querySelector<HTMLButtonElement>("#btn-camera-wide");
    const btnCombat =
      this.controlDeckEl.querySelector<HTMLButtonElement>("#btn-camera-combat");
    const btnTop =
      this.controlDeckEl.querySelector<HTMLButtonElement>("#btn-camera-top");
    const btnPolarity = this.controlDeckEl.querySelector<HTMLButtonElement>(
      "#btn-toggle-flir-polarity",
    );

    const is3D = themeId === "holo3d";
    const isFlir = themeId === "flir";

    if (btnWide) btnWide.style.display = is3D ? "inline-block" : "none";
    if (btnCombat) btnCombat.style.display = is3D ? "inline-block" : "none";
    if (btnTop) btnTop.style.display = is3D ? "inline-block" : "none";
    if (btnPolarity)
      btnPolarity.style.display = isFlir ? "inline-block" : "none";
  }

  private setupWindowResize(): void {
    if (typeof window === "undefined") return;
    window.addEventListener("resize", () => {
      if (this.viewportContainer) {
        const rect = this.viewportContainer.getBoundingClientRect();
        this.renderManager.resize(
          rect.width,
          rect.height,
          window.devicePixelRatio || 1,
        );
      }
    });
  }

  private startRenderLoop(): void {
    const loop = () => {
      const frameState = this.feedGenerator.generateFrameState(
        this.isHighDensityMode,
      );

      // Render decoupled stage frame
      this.renderManager.renderFrame(frameState);

      // Update decoupled HUD
      this.hud.update(frameState.telemetry);
      this.updateThreatSitreps(frameState);

      if (typeof requestAnimationFrame !== "undefined") {
        this.animFrameId = requestAnimationFrame(loop);
      }
    };

    if (typeof requestAnimationFrame !== "undefined") {
      this.animFrameId = requestAnimationFrame(loop);
    } else {
      // In non-browser / headless test environment, execute one frame
      loop();
    }
  }

  // OV-26: events feed the sitrep board; credits name units in this frame.
  private updateThreatSitreps(frame: RenderFrameState): void {
    const units = frame.units;
    this.sitrepBoard.ingest(frame.events ?? [], (id) =>
      units instanceof Map
        ? units.get(id)?.callsign
        : units.find((u) => u.id === id)?.callsign,
    );
    this.hud.updateThreatSitreps(this.sitrepBoard.view(frame.tick));
  }

  getRenderManager(): RenderManager {
    return this.renderManager;
  }

  getHud(): HudOverlay {
    return this.hud;
  }

  dispose(): void {
    if (
      this.animFrameId !== null &&
      typeof cancelAnimationFrame !== "undefined"
    ) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
    this.hud.dispose();
    this.renderManager.dispose();
    this.root.replaceChildren();
  }
}
