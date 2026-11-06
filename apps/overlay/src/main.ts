import { boot } from "./boot";
// Also imported by stage.ts; here too because the dev-only prototype path never mounts the stage but needs the page rules.
import "./stage.css";

// Vite replaces `import.meta.env.DEV` with a literal, so a production build drops the ternary's dev arm and the
// dynamic import with it: the mock feed is not in the bundle and a token-less production page stays empty.
void boot(
  window,
  import.meta.env.DEV
    ? async (root) => {
        const { TacticalC2App } = await import("./app");
        await new TacticalC2App(root).start();
      }
    : null,
);
