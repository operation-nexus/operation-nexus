import { describe, expect, expectTypeOf, it } from "vitest";
import type {
  NodeCaptured,
  ThreatTierChanged,
  UnitDamageStateChanged,
  UnitSpawned,
} from "../contracts/events/event";
import { isAirUnit } from "../symbology/dual-encoding";
import enumsRaw from "../../../../contracts/common/enums.json?raw";
import { EDGE_LAYERS, NODE_KINDS } from "../types/theater";
import type { Side } from "../types/theater";
import type { ThreatTier } from "../types/telemetry";
import type { DamageState, UnitKind, UnitSide } from "../types/unit";

// Drift guard (NX-423, AGENTS.md rule 6): overlay enums are the generated ones.
describe("overlay enums equal the generated contract types", () => {
  it("aliases the generated field types", () => {
    expectTypeOf<UnitKind>().toEqualTypeOf<UnitSpawned["unit_kind"]>();
    expectTypeOf<UnitSide>().toEqualTypeOf<UnitSpawned["side"]>();
    expectTypeOf<DamageState>().toEqualTypeOf<UnitDamageStateChanged["to"]>();
    expectTypeOf<DamageState>().toEqualTypeOf<UnitDamageStateChanged["from"]>();
    expectTypeOf<ThreatTier>().toEqualTypeOf<ThreatTierChanged["to"]>();
    expectTypeOf<Side>().toEqualTypeOf<NodeCaptured["to"]>();
  });

  it("classifies every UnitKind (air or not)", () => {
    // Record<UnitKind, ...> fails tsc when a contract kind is added or removed.
    const all: Record<UnitKind, true> = {
      STRIKE_FIGHTER: true,
      RECON_UAV: true,
      LOGI_TRUCK: true,
      GARRISON_INFANTRY: true,
      ENEMY_FIGHTER: true,
      ENEMY_STRIKE_FIGHTER: true,
      ENEMY_RECON_UAV: true,
      ENEMY_ARMOR: true,
      ENEMY_CONVOY: true,
      RADAR_SITE: true,
      AIR_DEFENSE_SITE: true,
    };
    const air = (Object.keys(all) as UnitKind[]).filter(isAirUnit);
    expect(air).toEqual([
      "STRIKE_FIGHTER",
      "RECON_UAV",
      "ENEMY_FIGHTER",
      "ENEMY_STRIKE_FIGHTER",
      "ENEMY_RECON_UAV",
    ]);
  });
});

describe("overlay theater enums equal contracts/common/enums.json", () => {
  const defs = JSON.parse(enumsRaw).$defs as Record<string, { enum: string[] }>;

  it("NodeKind", () => {
    expect([...NODE_KINDS].sort()).toEqual(
      [...(defs["NodeKind"]?.enum ?? [])].sort(),
    );
  });

  it("EdgeLayer", () => {
    expect([...EDGE_LAYERS].sort()).toEqual(
      [...(defs["EdgeLayer"]?.enum ?? [])].sort(),
    );
  });
});
