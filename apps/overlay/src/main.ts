import { getRoot } from "./root";
import { TacticalC2App } from "./app";
import { startFeed } from "./net/start";

const root = getRoot(document);
const app = new TacticalC2App(root);
void app.start();
startFeed(window, root);
