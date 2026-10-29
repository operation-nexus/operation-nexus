import type { RenderFrameState, VisualEffect } from "../types/render";
import type { VisualUnit } from "../types/unit";
import type { TelemetryState } from "../types/telemetry";
import type { ThreatAdaptation } from "../contracts/events/event";

// Mock ThreatAdaptation script for the OV-26 stack: one every SITREP_EVERY ticks, in a
// loop over every category (node and sector ids are Strait-1's).
const SITREP_EVERY = 90;
type Cat = ThreatAdaptation["category"];
// [category, sector, direction, node, credited unit ids]
const SITREP_SCRIPT: Array<
  [Cat, string, "UP" | "DOWN", string | null, number[]]
> = [
  ["STAGING", "north", "UP", null, []],
  ["IADS_REINFORCED", "south", "UP", null, []],
  ["STAGING_LAUNCHED", "north", "UP", null, []],
  ["HOLD_AT_RISK", "north", "UP", "cross-n", []],
  ["STRIKE_DOWNED", "centre", "UP", "west-airbase", [101, 102]],
  ["SANCTUARY_AT_RISK", "centre", "UP", "haven", []],
  ["CONVOY_ESCORT", "centre", "UP", null, []],
  ["STAGING", "south", "UP", null, []],
  ["STAGING_DISPERSED", "south", "UP", null, []],
  ["IADS_REINFORCED", "south", "DOWN", null, []],
];

export class SimulationFeedGenerator {
  private tick = 0;
  private simTimeMs = 0;
  private highDensityCount = 0;
  private countdown = 900; // 15:00
  private quorumPct = 52;
  private eventSeq = 0;

  generateFrameState(highDensityMode = false): RenderFrameState {
    this.tick++;
    this.simTimeMs += 100; // 10 Hz sim stepping
    if (this.tick % 10 === 0 && this.countdown > 0) {
      this.countdown--;
    }

    // Tug-of-war momentum oscillation
    this.quorumPct = 50 + Math.sin(this.tick * 0.05) * 8;

    const units = highDensityMode
      ? this.generate500PlusSwarm()
      : this.generateStandardTacticalUnits();

    const threatTier =
      this.tick % 300 < 100
        ? "PATTERN_OF_LIFE"
        : this.tick % 300 < 200
          ? "ALPHA"
          : "BRAVO";

    const telemetry: TelemetryState = {
      momentum: {
        quorum: this.quorumPct,
        static: 100 - this.quorumPct,
      },
      countdownSeconds: this.countdown,
      objectiveName: "SECURE STRAIT CROSSINGS",
      threatTier,
      sitrep: [
        {
          id: "SIT-01",
          timestamp: Date.now() - 5000,
          text: "VIPER-01 INGRESSING NORTH BRIDGE SECTOR",
          severity: "info",
          side: "COALITION",
        },
        {
          id: "SIT-02",
          timestamp: Date.now() - 4000,
          text: "MULE-04 SUPPLY CONVOY REACHED FOB-S-W",
          severity: "info",
          side: "COALITION",
        },
        {
          id: "SIT-03",
          timestamp: Date.now() - 3000,
          text: "STATIC ARMOR SIGHTED VICINITY CROSS-N",
          severity: "warn",
          side: "ENEMY",
        },
        {
          id: "SIT-04",
          timestamp: Date.now() - 2000,
          text: "RADAR LOCK DETECTED: ENEMY AIR DEFENSE ACTIVE",
          severity: "alert",
          side: "ENEMY",
        },
        {
          id: "SIT-05",
          timestamp: Date.now() - 1000,
          text: "NORTH BRIDGE INTEGRITY AT 94%",
          severity: "warn",
          side: "NEUTRAL",
        },
      ],
      ticker: [
        {
          id: "TK-1",
          category: "RECRUITMENT",
          text: "TYPE !join strike | recon | logi TO PLAY",
        },
        {
          id: "TK-2",
          category: "INTEL",
          text: "NORTH HIGHWAY BRIDGE STRUCTURALLY SOUND",
        },
        {
          id: "TK-3",
          category: "LOGISTICS",
          text: "HAVEN SANCTUARY MAINTAINING FULL AMMO RESUPPLY",
        },
      ],
      unitCount: units.length,
    };

    // Ballistic missile arc effect
    const missileProgress = (this.tick % 60) / 60;
    const effects: VisualEffect[] = [
      {
        type: "MISSILE_TRAJECTORY",
        id: "MSL-01",
        sourcePos: [90000, 120000, 2], // West Airbase
        targetPos: [290000, 40000, 2], // FOB NE
        progress: missileProgress,
        peakAltitudeMeters: 8000,
        color: "#ff0055",
      },
    ];

    if (missileProgress > 0.9) {
      effects.push({
        type: "KINETIC_BURST",
        id: "BST-01",
        pos: [290000, 40000, 2],
        radiusMeters: 5000,
        progress: (missileProgress - 0.9) * 10,
        color: "#00e5ff",
      });
    }

    return {
      tick: this.tick,
      simTime: this.simTimeMs,
      units,
      telemetry,
      effects,
      events: this.threatAdaptations(),
      selectedUnitId: 101, // Track VIPER-01 by default
      cameraPreset: "WIDE",
    };
  }

  private threatAdaptations(): ThreatAdaptation[] {
    if (this.tick % SITREP_EVERY !== 0) return [];
    const step = this.tick / SITREP_EVERY - 1; // first event at tick SITREP_EVERY
    const script = SITREP_SCRIPT[step % SITREP_SCRIPT.length];
    if (!script) return [];
    this.eventSeq++;
    return [
      {
        kind: "ThreatAdaptation",
        tick: this.tick,
        event_seq: this.eventSeq,
        campaign_id: "00000000-0000-7000-8000-000000000000",
        side: "ENEMY",
        category: script[0],
        sector_id: script[1],
        direction: script[2],
        node_id: script[3],
        credit_ids: script[4],
      },
    ];
  }

  private generateStandardTacticalUnits(): VisualUnit[] {
    const t = this.tick * 0.04;

    // Viper-01: Quorum Strike Fighter
    const viperX = 140000 + Math.cos(t) * 45000;
    const viperY = 60000 + Math.sin(t) * 20000;

    // Ghost-1: Quorum Recon UAV
    const ghostX = 200000 + Math.cos(t * 0.7) * 25000;
    const ghostY = 120000 + Math.sin(t * 0.7) * 35000;

    // Mule-04: Quorum Logistics Convoy
    const muleProgress = (this.tick % 200) / 200;
    const muleX = 90000 + muleProgress * (200000 - 90000);
    const muleY = 120000 + muleProgress * (180000 - 120000);

    // Static Strike Null-1
    const staticJetX = 280000 - Math.cos(t) * 35000;
    const staticJetY = 70000 - Math.sin(t) * 15000;

    // Static Heavy Armor Null-9
    const staticArmorX = 240000 - ((this.tick % 150) / 150) * 30000;
    const staticArmorY = 60000;

    return [
      {
        id: 101,
        callsign: "VIPER-01",
        side: "COALITION",
        kind: "STRIKE_FIGHTER",
        x: viperX,
        y: viperY,
        z: 45,
        headingDeg:
          ((Math.atan2(Math.cos(t) * 20000, -Math.sin(t) * 45000) * 180) /
            Math.PI +
            360) %
          360,
        speedMps: 280,
        hpPct: 100,
        damageState: "HEALTHY",
        isSelected: true,
        trailHistory: [
          { x: viperX - 2000, y: viperY - 1000, alpha: 0.8 },
          { x: viperX - 4000, y: viperY - 2000, alpha: 0.5 },
          { x: viperX - 6000, y: viperY - 3000, alpha: 0.2 },
        ],
      },
      {
        id: 102,
        callsign: "GHOST-1",
        side: "COALITION",
        kind: "RECON_UAV",
        x: ghostX,
        y: ghostY,
        z: 60,
        headingDeg: 120,
        speedMps: 140,
        hpPct: 100,
        damageState: "HEALTHY",
        trailHistory: [
          { x: ghostX - 1000, y: ghostY - 1000, alpha: 0.6 },
          { x: ghostX - 2000, y: ghostY - 2000, alpha: 0.3 },
        ],
      },
      {
        id: 103,
        callsign: "MULE-04",
        side: "COALITION",
        kind: "LOGI_TRUCK",
        x: muleX,
        y: muleY,
        z: 0,
        headingDeg: 145,
        speedMps: 28,
        hpPct: 95,
        damageState: "HEALTHY",
        isConvoyLeader: true,
        convoyFollowers: 3,
      },
      {
        id: 201,
        callsign: "NULL-SWARM-A",
        side: "ENEMY",
        kind: "ENEMY_STRIKE_FIGHTER",
        x: staticJetX,
        y: staticJetY,
        z: 50,
        headingDeg: 260,
        speedMps: 310,
        hpPct: 100,
        damageState: "HEALTHY",
        trailHistory: [
          { x: staticJetX + 2000, y: staticJetY, alpha: 0.7 },
          { x: staticJetX + 4000, y: staticJetY, alpha: 0.3 },
        ],
      },
      {
        id: 202,
        callsign: "NULL-IRON-9",
        side: "ENEMY",
        kind: "ENEMY_ARMOR",
        x: staticArmorX,
        y: staticArmorY,
        z: 0,
        headingDeg: 270,
        speedMps: 18,
        hpPct: 80,
        damageState: "DAMAGED",
      },
    ];
  }

  generate500PlusSwarm(): VisualUnit[] {
    const units: VisualUnit[] = [];
    const count = 520;
    this.highDensityCount = count;

    for (let i = 0; i < count; i++) {
      const isCoalition = i % 2 === 0;
      const baseLane = (i % 3) * 80000;
      const progress = ((this.tick * 0.5 + i * 17) % 1000) / 1000;

      const x = isCoalition
        ? 20000 + progress * 200000
        : 380000 - progress * 200000;
      const y = baseLane + 20000 + ((i * 499) % 40000);

      units.push({
        id: i + 1000,
        callsign: isCoalition ? `Q-${i}` : `S-${i}`,
        side: isCoalition ? "COALITION" : "ENEMY",
        kind: isCoalition ? "STRIKE_FIGHTER" : "ENEMY_ARMOR",
        x,
        y,
        headingDeg: isCoalition ? 90 : 270,
        speedMps: isCoalition ? 200 : 80,
        hpPct: 100,
        damageState: "HEALTHY",
        isSelected: i === 0,
      });
    }

    return units;
  }

  getHighDensityCount(): number {
    return this.highDensityCount;
  }
}
