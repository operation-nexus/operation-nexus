import { getRoot } from "./root";
import { TacticalC2App } from "./app";
import { startFeed } from "./net/start";
import { mountStage } from "./stage";
// Also imported by stage.ts; here too because the no-token prototype path never mounts the stage but needs the page rules.
import "./stage.css";

const root = getRoot(document);
// With `#token=` the live stage runs; without it the prototype mock feed does (dev mode).
if (startFeed(window, () => mountStage(root, window)) === null) {
  void new TacticalC2App(root).start();
}
