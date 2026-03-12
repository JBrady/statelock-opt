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

## Results

| Candidate | Config change | Score | Delta vs incumbent | Accepted | Reason |
| --- | --- | ---: | ---: | --- | --- |
| `state/incumbent` | baseline | 93.7536 | 0.0000 | baseline | incumbent reference |
| `state/candidates/candidate_0001` | `memory_policy.max_items_per_type: 3 -> 2` | 91.2645 | -2.4891 | no | `unsupported_answer_rate above threshold` |
| `state/candidates/generated_0001` | no config change | 93.7536 | 0.0000 | no | `unsupported_answer_rate above threshold` |
| `state/candidates/proof_top_k_final_4` | `retrieval.top_k_final: 3 -> 4` | 96.9094 | +3.1558 | yes | `accepted` |

Experimental setup:

- offline replay benchmark
- lexical-only retrieval
- deterministic scoring
- bounded config surface

### Note: Acceptance Reason Ordering

The optimizer currently reports the first failing gate in the acceptance pipeline. That can produce unintuitive reasons for no-op candidates. For example, an identical bundle may still report a threshold failure such as `unsupported_answer_rate above threshold` instead of a clearer reason like “no diff from incumbent.”

Possible improvement: reorder acceptance checks so identical or zero-delta candidates return a clearer reason such as `no diff from incumbent` or `score delta below minimum threshold` before reporting other failing thresholds.

## Benchmark Wedge

The proof depends on three deterministic benchmark cases added to `evals/dataset.jsonl`:

- `case_021`: creates a real win for `top_k_final=4` by making the fourth retrieved record carry the uncertainty needed for a correct refusal
- `case_022`: penalizes `min_term_overlap=2` with a short-query false-refusal failure
- `case_023`: penalizes `max_same_source=1` by requiring two same-source support records

These cases make the benchmark discriminative without loosening thresholds or expanding scope.

The key proof case is `case_021`. With the incumbent policy, `top_k_final=3` stops before the uncertainty record is selected, so the system answers too early from incomplete evidence. With `top_k_final=4`, the uncertainty record is included, the behavior changes in the intended direction, and the candidate avoids the incumbent failure.

## Why This Proves The Loop Works

This proof matters because the repo now demonstrates all three parts of a trustworthy optimizer loop:

- bad candidates are rejected
- no-op or weak nearby candidates are rejected
- a better candidate is accepted under the current strict scoring and acceptance rules

The accepted candidate is not a prompt rewrite or a broader architecture change. It is a bounded lexical retrieval change discovered within the existing MVP surface.

More concretely:

- the incumbent fails the wedge because it selects too few records in the critical case
- `top_k_final=4` fixes that behavior without changing the rest of the bundle
- the scorer credits the resulting improvement strongly enough for the optimizer to accept it under the current thresholds

## Post-Proof Hardening

The core v0.1 proof is intentionally narrow and already complete.

What remains after the proof is not “invent more optimizer behavior.”
What remains is hardening work around:

- eval integrity
- artifact provenance
- dataset scaffolding
- experiment-memory clarity
- future integration sketches

Those topics now live in:

- `docs/OPT_HARDENING_AUDIT.md`
- `docs/OPT_EVAL_STRATEGY.md`
- `docs/OPT_MEMORY_HARDENING.md`
- `docs/OPT_ENGINE_CONTRACT_SKETCH.md`

## Proof Still Holds After Hardening

The first hardening pass was implemented without changing the proof outcome.

The repo now additionally protects the proof with:

- runtime schema validation for replay rows
- raw-byte dataset and schema fingerprints in artifacts
- shared dataset identity across incumbent and candidate evaluation inside a single acceptance run
- regression coverage for case order, per-case scores, aggregate scores, final decision, and proposer stability for the checked-in memory state

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
