import { getRoot } from "./root";
import { TacticalC2App } from "./app";

const root = getRoot(document);
const app = new TacticalC2App(root);
void app.start();
