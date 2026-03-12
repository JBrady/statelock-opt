# StateLock Local Context Optimizer

An offline optimizer that discovers better memory retrieval policies by replaying conversations and scoring results deterministically.

`statelock-opt` is a local, eval-driven optimizer for StateLock-style memory systems. It does not train models. It tests bounded retrieval, context-assembly, and prompt-fragment policies offline, scores them deterministically, and decides whether to accept or reject a candidate configuration.

The problem it solves is simple: memory systems often fail because the retrieval or context policy is wrong, not because the underlying model needs retraining. This repo exists to prove that those policy decisions can be improved through offline replay.

The system is intentionally narrow:
- offline replay only
- lexical retrieval only
- deterministic-first scoring only
- bounded config mutation
- bounded prompt-fragment mutation only
- strict accept/reject loop
- distilled experiment memory

## Status

statelock-opt v0.1 establishes a minimal proof that the optimizer can:

• evaluate candidate retrieval/context policies offline  
• reject weak candidates under strict scoring  
• accept a genuinely better candidate  

That core proof is complete.
Current work focuses on post-proof hardening: eval integrity, reproducibility, documentation alignment, and safer extension points.

The reproducible experiment demonstrating this behavior is documented in:

docs/OPT_PROOF.md

## Proof Result (v0.1)

Incumbent score: 93.7536  
Winning candidate: retrieval.top_k_final: 3 → 4  
Candidate score: 96.9094  
Delta: +3.1558  
Decision: accepted

See docs/OPT_PROOF.md for the full reproducible experiment.

## Why This Exists

StateLock-style memory systems often fail because of policy choices, not because the model needs retraining. Common failure modes are:
- retrieving the wrong memories
- citing records that were not actually used
- answering when evidence is missing
- refusing when evidence is present
- polluting the context window with distractors
- wasting latency and tokens on oversized context

This repo turns that into a measurable optimization problem with a fixed harness and a bounded edit surface.

## Quick Start

```bash
uv sync
uv run python -m statelock_opt.run --candidate state/candidates/candidate_0001
```

That command:
1. loads the candidate config bundle
2. replays the fixed eval dataset
3. compares it with the incumbent config
4. accepts or rejects the candidate
5. writes run history and distilled experiment memory updates

To generate a new candidate from the incumbent plus priors:

```bash
uv run python -m statelock_opt.proposer --output state/candidates/generated_0001
```

## v0.1 Proof Artifact

The repo includes a stable proof candidate at `state/candidates/proof_top_k_final_4`.

The optimizer tests candidate retrieval and context policies offline against a fixed benchmark. On the current proof benchmark:

- incumbent score: `93.7536`
- discovered winning change: `retrieval.top_k_final: 3 -> 4`
- candidate score: `96.9094`
- delta: `+3.1558`
- decision: `accepted`

The reproducible demo flow is documented in [docs/OPT_PROOF.md](docs/OPT_PROOF.md).

Supporting hardening references:

- [docs/OPT_architecture.md](docs/OPT_architecture.md)
- [docs/OPT_repo_snapshot.md](docs/OPT_repo_snapshot.md)
- [docs/OPT_HARDENING_AUDIT.md](docs/OPT_HARDENING_AUDIT.md)
- [docs/OPT_EVAL_STRATEGY.md](docs/OPT_EVAL_STRATEGY.md)
- [docs/OPT_MEMORY_HARDENING.md](docs/OPT_MEMORY_HARDENING.md)
- [docs/OPT_EXPERIMENT_REGISTRY.md](docs/OPT_EXPERIMENT_REGISTRY.md)
- [docs/OPT_HYPOTHESES.md](docs/OPT_HYPOTHESES.md)
- [docs/OPT_ENGINE_CONTRACT_SKETCH.md](docs/OPT_ENGINE_CONTRACT_SKETCH.md)

## Post-Proof Hardening Now Present

The repo now includes the first hardening pass around the proof artifact:

- replay rows are validated against `evals/schema.json` before evaluation
- dataset and schema fingerprints are derived from raw file bytes only
- one shared dataset identity is reused across incumbent and candidate evaluation inside a single acceptance run
- `summary.json` and `run.json` now carry additive, non-semantic provenance metadata such as `artifact_format_version`, dataset identity, and bundle identity
- regression checks preserve proof invariants for case count, case order, per-case scores, aggregate scores, and final accept/reject outcome
- proposer behavior is still expected to remain unchanged for the same checked-in memory state
- a lightweight append-only registry now records structured run summaries under `artifacts/registry/experiments.jsonl`
- a regenerated hypothesis snapshot now records exact-signature beliefs under `artifacts/analysis/hypotheses.jsonl`

The hardening regression suite lives in `tests/test_hardening_regressions.py`.
The experiment-registry coverage lives in `tests/test_experiment_registry.py`.
The hypothesis-layer coverage lives in `tests/test_hypotheses.py`.

Recommended verification after behavior changes:

```bash
uv run python -m compileall src
uv run python -m unittest discover -s tests -v
```

## Reproduce the Proof

Evaluate incumbent:

```bash
uv run python - <<'PY'
from pathlib import Path
from statelock_opt.replay import evaluate_bundle

result = evaluate_bundle(
    Path("state/incumbent"),
    "proof_incumbent",
    Path("artifacts/reports/proof_incumbent"),
)
print(round(result["aggregate"]["total_score"], 4))
PY
```

Evaluate winning candidate:

```bash
uv run python - <<'PY'
from pathlib import Path
from statelock_opt.replay import evaluate_bundle

result = evaluate_bundle(
    Path("state/candidates/proof_top_k_final_4"),
    "proof_candidate",
    Path("artifacts/reports/proof_candidate"),
)
print(round(result["aggregate"]["total_score"], 4))
PY
```

Run optimizer acceptance check:

```bash
tmpdir=$(mktemp -d)
cp -R state/incumbent "$tmpdir/incumbent"
uv run python -m statelock_opt.run \
  --incumbent "$tmpdir/incumbent" \
  --candidate state/candidates/proof_top_k_final_4
rm -rf "$tmpdir"
```

## Core Repo Shape

```text
configs/                 bounded editable config surface
prompts/                 fixed base prompt plus bounded fragment inventory
evals/                   local replay dataset and schema
state/incumbent/         current accepted config
state/candidates/        candidate config bundles to evaluate
memory/                  raw run history plus distilled findings
src/statelock_opt/       replay, scoring, proposing, acceptance, distillation
artifacts/               per-run outputs and reports
program.md               agent instructions for the optimizer loop
```

The `artifacts/` tree now also includes:

- `artifacts/registry/experiments.jsonl`: an append-only index of completed runs
- `artifacts/analysis/hypotheses.jsonl`: a regenerated exact-signature belief snapshot derived from the registry

## Design Principles

- Boring over fancy.
- Deterministic-first over semantic judging.
- Config mutation over arbitrary code mutation.
- Distilled experiment memory over raw logs alone.
- Strict anti-cheese scoring so the system cannot "win" by refusing too often.

## Notes

- v1 supports lexical retrieval only. Hybrid and semantic retrieval are later-phase additions.
- Prompt behavior is bounded by fragment selection. The optimizer cannot rewrite the full system prompt.
- The local model adapter is fixed. The optimizer is improving policy, not model weights.
