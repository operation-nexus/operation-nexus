import type { Plugin } from "vite";
import { defineConfig } from "vite";

// SEC-OV-2 (OVERLAY §0.4). `'self'` for connect-src: in CSP3 it also matches ws:/wss: on the same host
// and port, which is the WS origin (start.ts builds the URL from location.host).
export const CSP = [
  "default-src 'none'",
  "script-src 'self'",
  "style-src 'self'",
  "font-src 'self'",
  "connect-src 'self'",
  "base-uri 'none'",
  "form-action 'none'",
].join("; ");

// Build only: the dev server injects CSS as <style> tags and an HMR client, which this policy forbids.
const csp: Plugin = {
  name: "nx-csp",
  apply: "build",
  transformIndexHtml: (html) =>
    html.replace(
      "<!--nx-csp-->",
      `<meta http-equiv="Content-Security-Policy" content="${CSP}" />`,
    ),
};

// assetsInlineLimit 0: fonts are files, never data: URLs (font-src 'self' would block them).
export default defineConfig({
  plugins: [csp],
  build: { assetsInlineLimit: 0 },
});
