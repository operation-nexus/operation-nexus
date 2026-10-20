/* Generated from contracts/ by make contracts (NX-021). Do not edit. */

/**
 * Client to server, first frame (CONTRACTS §7, WIRE-PROTOCOL).
 */
export interface Hello {
  type: "Hello";
  /**
   * PROTOCOL_VERSION (contracts/VERSION).
   */
  v: string;
  client_kind: "OVERLAY" | "PIP" | "VERTICAL";
  /**
   * SEC-API-2.
   */
  capability_token: string;
  last_tick: number | null;
}
