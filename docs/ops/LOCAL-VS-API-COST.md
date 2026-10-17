# Local LLM vs Paid API: Cost–Benefit Analysis

Date: 2026-10-17 · Status: Draft for owner decision (Q-AI-3, Q-AI-5, Q-ARCH-4)

> **How to read this.** Prices and hardware specs are **sourced**. Monthly costs are **ESTIMATES** that depend on token assumptions we made up (§3); they are not measurements. Many sources were reachable only through search-engine snippets, marked **(S)**. Re-check those before buying anything. Raw data: [`data/llm-cost-estimates.csv`](data/llm-cost-estimates.csv).

## TL;DR
1. **Game runtime LLM (director advisor, narration, `!order`):** at expected volumes, a cheap hosted API costs about **$5–17/month**. Buying a GPU for this **doesn't pay off** unless chat sends about 1,000 `!order`s/hour.
2. **Your GTX 1080 is the cheapest local option** (about $2–14/month extra electricity, because the PC runs 24/7 for the stream anyway). The costs:
   - It shares 8 GB of VRAM with OBS and the overlay browser.
   - It's stuck on CUDA 12.x builds, because NVIDIA dropped Pascal from CUDA 13.
   - It runs only ~7–8B models, which are much weaker than hosted small models.
   - It's worth a **free experiment** for narration, but not something to depend on.
3. **TTS should stay local** (Piper/Kokoro, $0). Gemini TTS would cost about $66–133/month at 1 line/min and reportedly has request caps.
4. **Local models can't replace Claude Code for development.** 7–8B models score about 23–24% on SWE-bench Verified vs 88%+ for frontier models. Keep the subscription.
5. **Don't buy a Raspberry Pi for LLMs.** It's too slow at medium load and infeasible at high load. A Pi is fine as a watchdog or monitor box.

![Estimated monthly cost by option](img/llm-monthly-cost.svg)

![Cumulative 24-month cost, medium scenario](img/llm-cumulative-24mo.svg)

## 1. Sourced prices (USD per 1M tokens, input / output)
| Model | Price | Notes | Source |
|---|---|---|---|
| Claude Haiku 5.5 | 0.10 / 0.50 | batch 0.05/0.25; cache hit 0.01. The page notes the newer tokenizer produces ~30% more tokens. If that applies, costs are ×1.3. | platform.claude.com/docs/en/about-claude/pricing (fetched) |
| Claude Haiku 4.5 | 1 / 5 | | same |
| Gemini 3.1 Flash-Lite | 0.25 / 1.50 | | ai.google.dev/gemini-api/docs/pricing (S) |
| Gemini 3.5 Flash-Lite | 0.30 / 2.50 | output includes thinking tokens | same (S) |
| Gemini 3.8 Flash | 0.75 / 3.75 → 1.50 / 7.50 after 2026-12-31 | introductory price | same (S) |
| GPT-5.4 nano | 0.20 / 1.25 | | developers.openai.com (S) |
| GPT-5.4 mini | 0.75 / 4.50 | | developers.openai.com (S) |
| Groq Llama 3.1 8B | 0.05 / 0.08 | older snapshot | groq.com/pricing (S) |
| DeepInfra Llama 3.1 8B | 0.02 / 0.03 | **[UNVERIFIED]** (aggregators only) | — |
| Gemini TTS (Flash-Lite TTS) | 6.00 → 12.00 per 1M audio tokens | | ai.google.dev pricing (S) |

**Gemini free tier:** it doesn't fit our volume. The low scenario alone is about 2,880 calls/day, and free-tier daily caps are **[UNVERIFIED]** (forum reports of 500–1,000/day). Free-tier data is "used to improve our products", which conflicts with sending viewer text (THREAT-MODEL).

## 2. Sourced local inference facts
**CUDA support**
- **Pascal (GTX 10-series):** CUDA 13 removed support (docs.nvidia.com CUDA features archive (S)), and PyTorch 2.15 dropped it too (dev-discuss.pytorch.org (S)). llama.cpp and Ollama reportedly still ship CUDA-12 builds that include Pascal (sm_61). That comes from a third-party post and is **[UNVERIFIED]**.

**Measured generation speed** (llama.cpp, Llama-2-7B Q4_0, [github.com/ggml-org/llama.cpp/discussions/15013](https://github.com/ggml-org/llama.cpp/discussions/15013), fetched)
| GPU | Prompt processing (tok/s) | Generation (tok/s) |
|---|---|---|
| GTX 1080 Ti | 1084 | 62.5 |
| RTX 3060 12GB | 2408 | 76.9 |
| RTX 3090 | 5560 | 161.9 |
| RTX 4060 Ti | 3803 | 64.0 |

- **GTX 1080:** not listed. **ESTIMATE**, scaled by memory bandwidth (320/484 GB/s): about **41 tok/s** generation and **717 tok/s** prompt processing. Run `llama-bench` on your card to get a real number.
- **Raspberry Pi 5** (Ollama Q4_K_M): about 11 tok/s for a 1B model and 4.7 tok/s for a 3B model (S).

**Structured output**
- **Tooling support:** llama.cpp (JSON-Schema → GBNF grammar, with documented limits) and Ollama (`format` = JSON schema) can force syntactically valid JSON. Sources: llama.cpp grammars README (fetched); docs.ollama.com (S).
- **Limit:** this does **not** make the answers correct, so ADR-0007's validation and fallback still apply.

**Hardware prices** (asking prices, not sold prices)
| Item | Price | Source / notes |
|---|---|---|
| Used RTX 3060 12GB | ~$309 | resaleprices.com, 2026-10-03 (S) |
| Used RTX 3090 | ~$1,199 | bestvaluegpu.com, Oct 2026 (S) |
| Raspberry Pi 5 8GB | $175 list | Raspberry Pi product brief, Apr 2026 (S). Excludes PSU, cooling and storage |
| RTX 4060 Ti 16GB | **[UNVERIFIED]** | conflicting figures |

**Power** (TechPowerUp and other reviews (S))
| Item | Idle | Load | Notes |
|---|---|---|---|
| GTX 1080 | — | 180 W rated board | |
| RTX 3060 | ~12 W | ~170–190 W gaming | |
| RTX 3090 | ~36 W | ~365 W gaming | |
| Raspberry Pi 5 | ~3 W | ~8.8 W | |

**Electricity:** US average residential price was **18.31¢/kWh** in July 2026 (eia.gov (S)). Your local rate may differ.
Formula: `$/month = average_watts × 720 / 1000 × $/kWh`

## 3. Assumptions (made up, not sourced; change them and re-run)
**Tokens per call**
| Call type | Input tokens | Output tokens |
|---|---|---|
| Advisor | 1,500 | 80 |
| Narration | 400 | 60 |
| `!order` | 500 | 60 |

**Scenarios**
| Scenario | Advisor | Narration | `!order` |
|---|---|---|---|
| Low | 1/min | 1/min | — |
| Medium | 1/min | 1/min | 100/hour |
| High | 1/min | 1/min | 1,000/hour |

**Cost rules**
- Months are 720 h, running 24/7.
- API cost is at standard prices. Batch pricing doesn't fit 5–10 s deadlines. Prompt caching of system prompts would lower every API number.
- Local cost = electricity + card price ÷ 24 months. That covers the card only; a host PC isn't included.
- GTX 1080 "PC already on" counts only the marginal ~150 W while busy. That 150 W is our assumption.

## 4. Results (ESTIMATES): monthly USD
| Option | Low | Medium | High |
|---|---|---|---|
| GTX 1080 you own (PC already on) | 1.99 | 3.17 | 13.80 (70% busy, deadline risk) |
| Groq Llama 3.1 8B (API) | 4.59 | 6.73 | 26.04 |
| Raspberry Pi 5 | 7.87 | 7.99 (40% busy) | infeasible |
| Claude Haiku 5.5 (API) | 11.23 | 16.99 | 68.83 |
| Used RTX 3060 12GB | 15.36 | 15.93 | 21.08 |
| GPT-5.4 nano (API) | 23.98 | 36.58 | 149.98 |
| Gemini 3.1 Flash-Lite (API) | 29.59 | 45.07 | 184.39 |
| Used RTX 3090 | 55.58 | 56.13 | 61.13 |

**Break-even of a used RTX 3060 ($309) vs each API**, in months:

| vs | Low | Medium | High |
|---|---|---|---|
| Claude Haiku 5.5 | 35 | 22 | 5.1 |
| GPT-5.4 nano | 14 | 9.2 | 2.2 |
| Gemini 3.1 Flash-Lite | 11 | 7.4 | 1.8 |
| Groq Llama 8B | 147 | 84 | 17 |

**Quality isn't equal.** A local 7–8B model is weaker than Haiku or Gemini Flash-class models for the director advisor. For narration (one short line from a template), the gap matters less.

## 5. Coding agents (Claude Code) — not replaceable locally
| Model class | SWE-bench Verified | Source |
|---|---|---|
| 7–8B open models | ~23–24% | arXiv 2506.07636, 2604.11716 (S) |
| 24B open model (Devstral Small 2) | 68.0% | mistral.ai (S); needs 24 GB-class hardware (ESTIMATE) |
| Frontier models | 88–95% | benchlm.ai (S). Harnesses differ, and contamination has been reported. |

Claude plans: Pro $20/month, Max 5x $100, Max 20x $200, all including Claude Code (claude.com/pricing (S)). A used RTX 3090 (~$1,199) costs about a year of Max 5x and still delivers a much weaker agent. **Recommendation: keep using Claude Code with a subscription. Don't buy hardware to replace it.**

## 6. Recommendations
| # | Recommendation | Cost |
|---|---|---|
| R1 | **Phase 4 runtime LLM:** start with a hosted small model behind our `LlmClient` interface. Claude Haiku 5.5 is the quality default (~$11–17/month estimated). Groq Llama 8B is the budget option. Set a hard budget cap (Q-AI-5). | ~$5–17/month |
| R2 | **Free experiment:** run llama.cpp (CUDA-12 build) on the GTX 1080 for **narration only**, measuring VRAM headroom with OBS live, tokens/s, and output quality. If it holds up, narration becomes ~free. The advisor stays on the API. | $0 |
| R3 | **TTS stays local** (Piper or Kokoro) on CPU. | $0 |
| R4 | **Don't buy GPUs or Pis for LLMs now.** Revisit if measured `!order` volume approaches the high scenario. Then a used RTX 3060 12GB in the Linux server breaks even in ~2–5 months against Haiku, nano or Gemini Flash-Lite, but ~17 months against Groq Llama 8B (§4). The server's PSU, PCIe slot and RAM need checking first. | — |
| R5 | **Cheap buys that do help:** a plug-in power meter (gives real wattage instead of estimates) and a small UPS for the stream PC. These are suggestions only; prices weren't researched. | — |
| R6 | **Use the Linux server** for the watchdog, monitoring, staging and backups (HARDWARE.md role split). If its RAM is very low, a RAM upgrade is the most valuable cheap purchase. Exact needs depend on its specs (NX-007). | TBD |

## 7. Gaps to close before deciding (owner)
- [ ] Run `llama-bench` on the GTX 1080 with OBS running. Record VRAM free.
- [ ] Measure wall power for idle, streaming, and streaming plus LLM.
- [ ] Your electricity rate ($/kWh).
- [ ] Real token counts once the prompts exist (provider token counters).
- [ ] Sold (not asking) prices if you decide to buy.
