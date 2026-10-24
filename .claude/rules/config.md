---
paths:
  - "contracts/config/**"
  - "balance/**"
  - "services/sim/src/nexus/core/rules.py"
---
A balance key lives in seven places that change together (schema with all eight `x-` annotations, `balance/default.yaml`, the loader, CONFIG-AND-CONTENT §6, `make contracts`, tests, goldens): follow the `add-config-key` skill. `scripts/gen_config_reference.py` fails `make contracts` on a missing annotation.
