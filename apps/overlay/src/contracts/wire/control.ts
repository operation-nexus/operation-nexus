/* Generated from contracts/ by make contracts (NX-021). Do not edit. */

/**
 * Server to client (WIRE-PROTOCOL section 3). BANNER and KILL_SWITCH join with NX-253.
 */
export interface Control {
  type: "Control";
  /**
   * PROTOCOL_VERSION (contracts/VERSION).
   */
  v: string;
  action: "RELOAD" | "RESYNC";
}
