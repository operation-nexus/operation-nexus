/* Generated from contracts/ by make contracts (NX-021). Do not edit. */

/**
 * Client to server, after applying a Delta (CONTRACTS section 7).
 */
export interface Ack {
  type: "Ack";
  /**
   * PROTOCOL_VERSION (contracts/VERSION).
   */
  v: string;
  /**
   * 10 Hz game time (SC-2).
   */
  applied_tick: number;
}
