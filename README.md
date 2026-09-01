# Crab-1 — a 1.7B OSINT agent you can actually test

Crab-1 is a Qwen3-1.7B fine-tuned (QLoRA SFT) to build a factual profile of a
French company from its name alone — official website, administrative
department, sector — using three tools: the official French company registry,
web search, and page extraction. It runs locally on a consumer GPU, costs
nothing per profile, and finishes in ~4 tool-calling turns (~9 s/profile on an
RTX 3060 Ti).

This repo contains **everything you need to verify the published claims
yourself**: the evaluation harness, the 30-company ground-truth set, and the
scoring function. The model weights are on Hugging Face (GGUF F16, Apache-2.0,
same license as the Qwen3 base).

What it deliberately does NOT contain: the training-data factory (teacher
generation, trajectory filtering, dataset build). That's the subject of an
upcoming series — recipe, mistakes and all.

## Published numbers — with dates, because they matter

| Model (same harness, n=30, 8-turn cap) | 2026-07-22 | 2026-08-30 |
|---|---|---|
| **Crab-1 (this model)** | **76.7 %** | **66.7 %** |
| Claude Haiku 4.5 | — | 66.7 % |
| Claude Opus 4.5 | — | 56.7 % |
| Claude Sonnet 4.5 | — | 53.3 % |
| Qwen3-1.7B untrained | 56.7 % | 70.0 % |
| Llama 3.1 8B, plain prompting | 0 % | — |

Pass rate = reward ≥ 0.7 (TLD-strict website match + department-level
location, dynamic denominator — see `harness/reward.py`).

**⚠️ This benchmark is perishable.** The tools hit the live web. The same
weights scored 76.7 % in July and 66.7 % in late August — nothing changed but
the search results. The untrained baseline moved even more (56.7 % → 70.0 %).
Two consequences:

1. Only compare models measured **the same day**. That's why every column
   above is dated, and why the Claude numbers were measured the same morning
   as the Crab-1 re-run.
2. Your numbers will differ from ours. Expect the ballpark, not the digit.

What stays stable across dates: Crab-1 **always submits** a profile within
the turn budget (100 % submit rate vs 60–80 % for the frontier models, which
tend to keep verifying past the 8-turn cap), and it's 2–4× faster end-to-end.
Fine-tuning didn't buy intelligence — it bought protocol discipline: stop on
time, fill the exact schema. For a fleet of cheap local crawlers, that's the
property that matters.

## Quickstart

Requirements: Python 3.10+, [Ollama](https://ollama.com), a GPU with ~5 GB
VRAM (or patience on CPU).

```bash
pip install -r requirements.txt

# 1. Get the weights (GGUF F16) from Hugging Face, then:
ollama create crab1-v7 -f Modelfile

# 2. One profile, interactively:
python quickstart.py "Doctolib"

# 3. The full 30-company eval (~5 min, live web):
python eval/run_eval.py --model crab1-v7 --out results/crab1_v7.json

# 4. Fair comparison — run the untrained base the same day:
ollama pull qwen3:1.7b
python eval/run_eval.py --model qwen3:1.7b --out results/baseline.json
```

`OLLAMA_BASE_URL` overrides the default `http://localhost:11434`.

## How the eval works

- The model gets a fixed system prompt (`harness/agent_config.py`) and four
  native tool schemas (`harness/crab_harness.py`).
- Max 8 turns. Tools are executed for real (`harness/tools.py`): DuckDuckGo
  search, trafilatura extraction, recherche-entreprises.api.gouv.fr registry.
- On `submit_answer`, the profile is scored (`harness/reward.py`): website at
  registrable-domain level (wrong TLD = half credit), location at department
  level (`harness/fr_geo.py` maps names/codes, incl. Corsica and DOM),
  sector when ground truth exists. Fields without ground truth are excluded
  from the mean instead of being free points.

## Honest limitations

- Trained and evaluated on **French** companies only; the registry tool is
  France-specific.
- The eval set is 30 companies — big enough to rank models, too small for
  decimal-point bragging.
- Name collisions in the registry (brand name ≠ legal name) are the main
  remaining failure mode.
- The model is a specialist. Ask it anything outside "profile this French
  company with these tools" and the base 1.7B is what you get.

## License

Weights: Apache-2.0 (derivative of Qwen3-1.7B). Code in this repo: MIT.

Write-up with the full story: https://yegorgaidar.org/blog/crab1-slm-osint/
