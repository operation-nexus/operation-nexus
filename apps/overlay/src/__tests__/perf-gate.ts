import { expect } from "vitest";

// NX-491: a correctness run never asserts wall-clock time (code-quality §9, NX-421).
// The budgets are enforced only when NEXUS_PERF=1 or on GitHub Actions, which sets
// GITHUB_ACTIONS=true on every runner (ci.yml does not set it by hand). Mirrors the Python
// `perf` marker: `make check` skips it, CI runs it.
const env =
  (globalThis as { process?: { env?: Record<string, string | undefined> } })
    .process?.env ?? {};
export const PERF_ENFORCED =
  env.NEXUS_PERF === "1" || env.GITHUB_ACTIONS === "true";

export function expectUnderBudget(actualMs: number, budgetMs: number): void {
  if (PERF_ENFORCED) expect(actualMs).toBeLessThan(budgetMs);
}

export function expectFpsAtLeast(actualFps: number, minFps: number): void {
  if (PERF_ENFORCED) expect(actualFps).toBeGreaterThanOrEqual(minFps);
}
