// Local key -> English map (OVERLAY OV-19). No localization system exists yet; keys keep the
// `hud.tier.<tier>` shape so a real one can replace this file. Fixed strings only, never feed text.
const EN = {
  "hud.signal": "Signal strength",
  "hud.nodes": "Nodes held",
  "hud.objective": "Objective",
  "hud.threat": "Threat",
  "hud.war": "War clock",
  "hud.tier.PATTERN_OF_LIFE": "Pattern of life", // a calm state, not an alert (OV-19)
  "hud.tier.ALPHA": "Alpha",
  "hud.tier.BRAVO": "Bravo",
  "hud.howto": "Type !join strike | recon | logi to deploy",
  "hud.needed": "NEEDED",
  "hud.operators": "Operators",
  "hud.top": "Top",
} as const;

export type StringKey = keyof typeof EN;
export const t = (key: StringKey): string => EN[key];
/** A tier this build has no key for shows its raw id, never a guess (DI-1). */
export const tierText = (tier: string): string =>
  (EN as Record<string, string>)[`hud.tier.${tier}`] ?? tier;
export const DASH = "—";
