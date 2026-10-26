/**
 * Physical Elevation Budget constants for Hiveplex / Operation Nexus.
 * Designed to eliminate Z-fighting and enforce spatial realism across 2D/3D renderers.
 * (See docs/specs/TERRAIN-AND-BIOMES.md and references/elevation-budget-and-zfighting.md).
 */

export const ELEVATION_CHANNEL_BED = -10.0; // Trench floor meters
export const ELEVATION_CHANNEL_WATER = -3.5; // Recessed water surface meters (eliminates shoreline Z-fighting)
export const ELEVATION_SHORELINE_BEVEL = 0.0; // Shoreline bank contact line
export const ELEVATION_TERRAIN_BASE = 2.0; // Lowland plains base elevation
export const ELEVATION_HILLS_NORTH = 32.0; // Northern mountain ridges
export const ELEVATION_ROAD_OFFSET = 0.22; // Road mesh polygonOffset height
export const ELEVATION_BRIDGE_DECK_MIN = 2.0; // Bridge abutment height at bank
export const ELEVATION_BRIDGE_DECK_MAX = 14.0; // Mid-span apex clearance over recessed water
export const ELEVATION_VEHICLE_SURFACE = 0.35; // Ground vehicle ride height above road
export const ELEVATION_AIR_CRUISE = 45.0; // Default aerial unit altitude

/**
 * Calculates vertical height along an elevated bridge span.
 * Rises from abutment (+2.0m) to apex (+14.0m) at mid-span using a smooth parabolic camber.
 *
 * @param progress 0.0 at West bank, 0.5 at mid-channel, 1.0 at East bank.
 */
export function getBridgeDeckElevation(progress: number): number {
  const clamped = Math.max(0, Math.min(1, progress));
  const spanHeight = ELEVATION_BRIDGE_DECK_MAX - ELEVATION_BRIDGE_DECK_MIN;
  // Parabolic camber: 4 * p * (1 - p) peaks at 1.0 when p = 0.5
  const camber = 4 * clamped * (1 - clamped);
  return ELEVATION_BRIDGE_DECK_MIN + spanHeight * camber;
}

/**
 * Calculates the 3D parabolic missile trajectory altitude at a given progress.
 * Formula: y = y0 + deltaY * progress + sin(progress * PI) * peakAltitude
 */
export function getBallisticMissileAltitude(
  startAltitude: number,
  targetAltitude: number,
  progress: number,
  peakAltitude: number,
): number {
  const p = Math.max(0, Math.min(1, progress));
  const baseline = startAltitude + (targetAltitude - startAltitude) * p;
  const arc = Math.sin(p * Math.PI) * peakAltitude;
  return baseline + arc;
}
