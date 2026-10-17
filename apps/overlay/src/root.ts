// Overlay entry point (OVERLAY spec). Renders nothing until the WS client exists (NX-175).
export function getRoot(doc: Document): HTMLElement {
  const root = doc.getElementById("root");
  if (root === null) {
    throw new Error("Overlay root element #root is missing");
  }
  return root;
}
