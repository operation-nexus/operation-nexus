---
name: add-config-key
description: Add, rename or retire an Operation Nexus balance key (contracts/config/balance.json) with its registry metadata, default, loader field, spec row, regenerated reference and goldens, in one change. Use whenever a feature needs a new tunable number, switch or rule option, or a key's default, bounds, unit or audience changes.
---

# Add a balance key

Every tunable in the sim is a balance key, and a key exists in seven places that move together
(CONFIG-AND-CONTENT CFG-1, CFG-2, CFG-5; Q-CFG-15..22; NX-390). Read first: CONFIG-AND-CONTENT §3,
§4.4, §5 (hot reload), §6 (the block your key joins); `scripts/gen_config_reference.py` (the
guard); `contracts/README.md`; AGENTS.md rules 0 and 6; `docs/quality/DATA-INTEGRITY.md`.

## 1. Decide the key (before any edit)
- **Name and block:** `<block>.<key>` in the block whose subsystem reads it (`sim`, `slots`, `air`,
  `fow`, `logistics`, `combat`, `capture`, `campaign`, `tasking`, `director`). Snake case, the
  unit in the name when it isn't obvious (`_s`, `_m`, `_ticks`, `_mult`).
- **Value:** where the number comes from. A spec, a Q-row or the owner gives a decided value; a
  value nobody decided is `PROPOSED` and gets a Q-row (`Decided by lead, owner may veto`) or goes to
  the owner (build-loop §3). Never invent a number without marking it (DATA-INTEGRITY).
- **Clock (CFG-9):** a time key names its clock in the schema description (game, world or tick)
  and converts once in the loader, never in the kernel.

## 2. The seven places, in one change
1. **Schema** `contracts/config/balance.json`: the property under its block, listed in that
   block's `required` (CFG-2: no code defaults), with `type`, bounds (`minimum` etc., only bounds
   the spec or harness justifies, §4.4), `description` (meaning, clock, spec or Q-row), and all
   eight annotations:

   | Field | Value |
   |---|---|
   | `x-unit` | the unit (`s (world)`, `m`, `ticks`, `multiplier`, `switch` for a bool, `—` for an enum) |
   | `x-hot-reload` | true only when §5 says the key may change mid-campaign |
   | `x-category` | the block's category (`BLOCK_CATEGORY` in the guard) |
   | `x-audience` | `OPERATOR` for a rule switch an operator picks, `TUNER` for a balance number (default), `DEVELOPER` for an internal |
   | `x-edit-role` | `ADMIN`, or `NONE` for a fixed key |
   | `x-tune` | `{min, max, step, scale}` inside the schema bounds and containing the default, `scale` `LINEAR` or `LOG`; `null` for a bool, enum, structural or fixed key |
   | `x-source` | the spec section or Q-row, as in the §6 Source column |
   | `x-status` | `PROPOSED`, `RULE_DEFAULT` (a decided rule shipped as an option), `VALIDATED` (harness-checked) or `FIXED` |

   Every key needs all eight; `make contracts` fails on a missing one.
2. **Default** `balance/default.yaml`: the value, with the same marker comment as its neighbours
   (`# PROPOSED`, Q-row).
3. **Loader** `services/sim/src/nexus/core/rules.py`: the field on the block's rules dataclass,
   converted to ticks or milli units once; refuse a value that rounds to nothing with a message
   naming the key. The kernel reads only the loader's field.
4. **Spec row** CONFIG-AND-CONTENT §6: key, type, unit, default and marker, source, hot-reload.
   Name the key in the subsystem spec where the rule is described.
5. **Generated** `make contracts`: regenerates the Python and TypeScript types and
   `docs/specs/CONFIG-REFERENCE.md`, and fails on a missing or invalid annotation. Bump
   `contracts/VERSION` MINOR once per PR (contracts/README); never edit generated files.
6. **Tests:** the loader reads it (`tests/runtime/test_config.py` or the subsystem's tests); a rule
   option (a bool or enum that switches behaviour) joins the default, non-default and
   every-option-flipped determinism tests in `tests/core/test_rule_options.py`; the behaviour test
   flips the key through the shipped config, not only a hand-built rules object (a hand-built one
   let a hard-wired loader value pass, NX-373 part 2).
7. **Goldens:** a new key changes `config_hash`. Update `GOLDEN_CONFIG_HASH` in
   `tests/runtime/test_config.py`, rewrite the case inputs with
   `uv run --frozen python -m golden.make_cases` (from `services/sim/tests`) and `expected.json`
   with `NEXUS_UPDATE_GOLDEN=1 uv run --frozen pytest tests/golden`. Then compare every
   `event_count` and `events_hash` with `git show HEAD:<path>`: if only `config_hash` and checkpoint
   hashes moved, say so in the PR body; if an event stream moved, the PR needs the `golden-update`
   label and the reason.

## 3. Rename or retire
A rename is retire-plus-add in the same PR: every place above, plus a grep of the old name across
`services/`, `tools/` (harness profiles and `--set` examples), `docs/` and `balance/` overrides in
golden cases. Removing a key a theater or preset still sets fails the load (CFG-1 rejects unknown
keys), so search `content/` too.

## 4. Done when
`make check` passes, `git status` after `make contracts` shows no new drift, the §6 row and the
schema say the same thing, and the PR body lists the key, its value and where the value came from.
