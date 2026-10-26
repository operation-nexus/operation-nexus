import { describe, expect, it } from "vitest";
import { RenderManager } from "../renderers/manager";

function createMockContainer(): HTMLElement {
  const children: HTMLElement[] = [];
  const el = {
    getBoundingClientRect: () => ({
      width: 1280,
      height: 720,
      top: 0,
      left: 0,
      bottom: 720,
      right: 1280,
    }),
    appendChild: (child: HTMLElement) => {
      children.push(child);
      Object.assign(child, { parentElement: el });
      return child;
    },
    removeChild: (child: HTMLElement) => {
      const idx = children.indexOf(child);
      if (idx !== -1) children.splice(idx, 1);
      Object.assign(child, { parentElement: null });
      return child;
    },
    children,
  } as unknown as HTMLElement;
  return el;
}

describe("RenderManager — Dynamic Hot-Swapping & Lifecycle", () => {
  it("registers all four core visual paradigms", () => {
    const manager = new RenderManager();
    const themes = manager.getAvailableThemes();
    const themeIds = themes.map((t) => t.id);

    expect(themeIds).toContain("crt");
    expect(themeIds).toContain("holo3d");
    expect(themeIds).toContain("flir");
    expect(themeIds).toContain("batch");
    expect(themes.length).toBe(4);
  });

  it("attaches to a container and initializes the default theme", async () => {
    const manager = new RenderManager();
    const container = createMockContainer();

    await manager.attach(container, "crt");
    expect(manager.getActiveThemeId()).toBe("crt");
    expect(manager.getActiveEngine()?.name).toBe("2D CRT Vector Phosphor");
  });

  it("hot-swaps cleanly between all 4 paradigms without leaking state", async () => {
    const manager = new RenderManager();
    const container = createMockContainer();
    const themeLog: string[] = [];

    manager.onThemeChange((themeId) => {
      themeLog.push(themeId);
    });

    await manager.attach(container, "crt");
    expect(manager.getActiveThemeId()).toBe("crt");

    // Switch to Option B: 3D Holo Table
    await manager.switchTheme("holo3d");
    expect(manager.getActiveThemeId()).toBe("holo3d");
    expect(manager.getActiveEngine()?.id).toBe("holo3d");

    // Switch to Option C: FLIR MFD
    await manager.switchTheme("flir");
    expect(manager.getActiveThemeId()).toBe("flir");
    expect(manager.getActiveEngine()?.id).toBe("flir");

    // Switch to Option D: High-Density Batch
    await manager.switchTheme("batch");
    expect(manager.getActiveThemeId()).toBe("batch");
    expect(manager.getActiveEngine()?.id).toBe("batch");

    // Switch back to Option A: CRT Vector
    await manager.switchTheme("crt");
    expect(manager.getActiveThemeId()).toBe("crt");

    expect(themeLog).toEqual(["crt", "holo3d", "flir", "batch", "crt"]);

    manager.dispose();
    expect(manager.getActiveEngine()).toBeNull();
  });

  it("throws a descriptive error when requesting an unknown theme", async () => {
    const manager = new RenderManager();
    const container = createMockContainer();
    await manager.attach(container, "crt");

    await expect(manager.switchTheme("non-existent-theme")).rejects.toThrow(
      'Unknown rendering theme: "non-existent-theme"',
    );
  });
});
