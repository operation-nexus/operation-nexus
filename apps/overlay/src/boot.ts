// Page start-up: the live stage with `#token=`; without it nothing renders, except in a dev build (OVERLAY §0).
import { getRoot } from "./root";
import { startFeed } from "./net/start";
import { mountStage } from "./stage";

/**
 * Without a token a production page stays empty: no stage, no socket, and never mock data (Rule 0, DI-1).
 * `prototype` starts the dev-only mock feed; main.ts passes it only under `import.meta.env.DEV`.
 */
export async function boot(
  win: Window,
  prototype: ((root: HTMLElement) => Promise<void>) | null,
): Promise<void> {
  const root = getRoot(win.document);
  if (startFeed(win, () => mountStage(root, win)) !== null) return;
  await prototype?.(root);
}
