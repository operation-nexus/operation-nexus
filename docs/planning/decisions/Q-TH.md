# Decided questions: Q-TH

Owner-decided (✅) rows moved verbatim from `../OPEN-QUESTIONS.md` on 2026-11-01 (W3, Q-DEV-37), grouped by their original section. Open and lead-decided rows stay in OPEN-QUESTIONS.

## Theater #1 sketch (NX-008, 2026-10-19)

| ID | Question | Decision | Priority | Status |
|---|---|---|---|---|
| Q-TH-1 | Layout | Bridged strait running north–south through the middle; three lanes and sectors (NORTH, CENTRE air-only, SOUTH); coalition west with sanctuary, west airbase and two FOBs; two contested bridgeheads on the east bank; Static east with east airbase, two FOBs and HQ; ~400 × 240 km; 12 nodes, 8 of them strategic bases. Supersedes the tracker's "≈15 nodes". | P1 | ✅ 2026-10-19 |
| Q-TH-2 | Forward airbase | A `forward_airbase` theater field names it (`west-airbase` here), the same base the idle floor protects. Owner: losing the sanctuary, or it taking enough damage, would matter more as a loss condition; open as Q-TH-7. | P1 | ✅ 2026-10-19 |
| Q-TH-3 | Ports | None in theater #1 (no navy until P3); the strait is scenery plus two bridges. | P1 | ✅ 2026-10-19 |
| Q-TH-4 | Heightmap | Optional in the first build; theater #1 ships masking regions (northern hills across the strait, southern valley on the east side). Owner: a heightmap will still be needed later. | P1 | ✅ 2026-10-19 |
| Q-TH-5 | Facilities | Mirrored: each main airbase gets a radar and an air-defense site, each FOB an air-defense site; the Static also has a radar at its HQ. Static garrison quotas PROPOSED: airbase 6, FOB 4, HQ 8. No facilities at the contested bridgeheads. | P1 | ✅ 2026-10-19 |
| Q-TH-6 | Names and files | Plain working names (brand pass later); `content/theaters/strait-1.yaml`; sketch `docs/design/theater-1.svg`; tracker row corrected. | P1 | ✅ 2026-10-19 |
| Q-TH-7 | Defeat condition | The sanctuary can be besieged, never captured; it has defense HP; defeat = that HP held at 0 for `campaign.defeat.hold_min` (PROPOSED 30 game min), a visible last stand. The forward-airbase and 25% rule is removed (replaces Q-GD-7's rule). Idle floor: with no humans the sanctuary's HP can't drop below 1 and `forward_airbase` can't be captured. | P1 | ✅ 2026-10-19 |
