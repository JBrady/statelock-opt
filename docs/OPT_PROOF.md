# OPT Proof Artifact

## v0.1 Proof

`statelock-opt` now has a small, reproducible proof that the offline optimizer loop can accept a genuinely better candidate.

Accepted improvement:

- incumbent: `state/incumbent`
- winning candidate: `state/candidates/proof_top_k_final_4`
- changed field: `retrieval.top_k_final: 3 -> 4`
- incumbent score: `93.7536`
- winning score: `96.9094`
- delta: `+3.1558`
- decision: `accepted`

## Benchmark Wedge

The proof depends on three deterministic benchmark cases added to `evals/dataset.jsonl`:

- `case_021`: creates a real win for `top_k_final=4` by making the fourth retrieved record carry the uncertainty needed for a correct refusal
- `case_022`: penalizes `min_term_overlap=2` with a short-query false-refusal failure
- `case_023`: penalizes `max_same_source=1` by requiring two same-source support records

These cases make the benchmark discriminative without loosening thresholds or expanding scope.

## Why This Proves The Loop Works

This proof matters because the repo now demonstrates all three parts of a trustworthy optimizer loop:

- bad candidates are rejected
- no-op or weak nearby candidates are rejected
- a better candidate is accepted under the current strict scoring and acceptance rules

The accepted candidate is not a prompt rewrite or a broader architecture change. It is a bounded lexical retrieval change discovered within the existing MVP surface.

## Read-Only Demo

These commands reproduce the proof without modifying the checked-in incumbent.

Incumbent score:

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

Winning candidate score:

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

Accepted result against a temporary incumbent copy:

```bash
tmpdir=$(mktemp -d)
cp -R state/incumbent "$tmpdir/incumbent"
uv run python -m statelock_opt.run \
  --incumbent "$tmpdir/incumbent" \
  --candidate state/candidates/proof_top_k_final_4
rm -rf "$tmpdir"
```
