# OPT Hardening Audit

Date: 2026-03-12

This document captures the repository state immediately before the post-proof hardening changes were implemented.

Its purpose is to preserve a concrete baseline so later hardening work can be checked for hidden behavior changes.

## Baseline Proof State

The core v0.1 proof was already satisfied before hardening:

- bad candidate rejected
- no-op candidate rejected
- genuine improvement accepted

Proof artifact:

- incumbent: `state/incumbent`
- winning candidate: `state/candidates/proof_top_k_final_4`
- winning change: `retrieval.top_k_final: 3 -> 4`

Baseline scores:

- incumbent aggregate score: `93.753623`
- proof candidate aggregate score: `96.909420`
- accepted delta: `+3.155797`

Acceptance baseline against a temporary incumbent copy:

- accepted: `true`
- reason: `accepted`
- false refusal rate: `0.000`
- unsupported answer rate: `0.043`

## Pre-Hardening Runtime Assumptions

These were true before the hardening implementation:

- runtime loaded `evals/dataset.jsonl` directly without enforcing `evals/schema.json`
- run artifacts had no dataset fingerprint metadata
- run artifacts had no paired incumbent/candidate bundle identity metadata beyond the candidate `fingerprint`
- `summary.json` contained only aggregate metrics
- `run.json` contained decision and metric fields, but not artifact format versioning
- proposer consumed only `memory/priors.yaml`, `memory/bad_regions.yaml`, and `memory/known_slow.yaml`
- checked-in `memory/lessons.jsonl` was empty

## Pre-Hardening Baseline Invariants

Hardening work must preserve the following for both the incumbent bundle and the proof candidate relative to this baseline:

- case count
- case order
- per-case scores
- aggregate scores
- final accept/reject decision

### Ordered Case IDs

`case_001` through `case_023` in ascending order.

### Incumbent Per-Case Total Scores

| Case | Score |
| --- | ---: |
| `case_001` | 97.500000 |
| `case_002` | 97.500000 |
| `case_003` | 98.250000 |
| `case_004` | 97.833333 |
| `case_005` | 100.000000 |
| `case_006` | 100.000000 |
| `case_007` | 97.666667 |
| `case_008` | 98.333333 |
| `case_009` | 97.500000 |
| `case_010` | 100.000000 |
| `case_011` | 97.500000 |
| `case_012` | 97.666667 |
| `case_013` | 100.000000 |
| `case_014` | 98.333333 |
| `case_015` | 97.666667 |
| `case_016` | 97.500000 |
| `case_017` | 97.500000 |
| `case_018` | 97.833333 |
| `case_019` | 69.583333 |
| `case_020` | 97.666667 |
| `case_021` | 24.666667 |
| `case_022` | 97.500000 |
| `case_023` | 98.333333 |

Aggregate incumbent score:

- `93.753623`

### Proof Candidate Per-Case Total Scores

| Case | Score |
| --- | ---: |
| `case_001` | 97.500000 |
| `case_002` | 97.500000 |
| `case_003` | 98.250000 |
| `case_004` | 97.833333 |
| `case_005` | 100.000000 |
| `case_006` | 100.000000 |
| `case_007` | 97.666667 |
| `case_008` | 98.333333 |
| `case_009` | 97.500000 |
| `case_010` | 100.000000 |
| `case_011` | 97.500000 |
| `case_012` | 97.666667 |
| `case_013` | 100.000000 |
| `case_014` | 98.333333 |
| `case_015` | 97.666667 |
| `case_016` | 97.500000 |
| `case_017` | 97.500000 |
| `case_018` | 97.833333 |
| `case_019` | 68.875000 |
| `case_020` | 97.375000 |
| `case_021` | 98.250000 |
| `case_022` | 97.500000 |
| `case_023` | 98.333333 |

Aggregate proof-candidate score:

- `96.909420`

## Candidate-Selection Baseline

With the checked-in memory state on March 12, 2026, proposer output remained deterministic and selected the proof-family bundle:

- generated candidate fingerprint: `2a5996df536ff1c4bf5aa0117f923169e4c9b26be3707fd59228c322ec90f3ae`
- generated change family: `retrieval.top_k_final: 3 -> 4`

This baseline matters because experiment-memory hardening must not change proposer behavior for the same checked-in memory state.

## Current Documentation Mismatch Before Hardening

Before hardening, the docs had a mild mismatch:

- `docs/OPT_PROOF.md` and `README.md` already treated the v0.1 proof as achieved
- `docs/OPT_SHIP_PLAN.md` still described lesson distillation as part of what counted as shipped success

The hardening pass should resolve that mismatch by keeping the proof narrow and moving lesson-strengthening into the post-proof track.

## Current Memory State Before Hardening

Checked-in memory state before hardening:

- `memory/runs.jsonl`: 2 runs
- `memory/lessons.jsonl`: empty
- `memory/priors.yaml`: empty
- `memory/bad_regions.yaml`: empty
- `memory/known_slow.yaml`: empty
- `memory/tradeoffs.yaml`: empty
- `memory/failures.yaml`: 2 failure records

This means the repo had early failure memory, but no promoted lessons and no strong learned priors in the checked-in state.

## Guardrails for the Hardening Pass

The hardening work must preserve:

- scoring behavior
- candidate selection behavior
- proof numbers
- accept/reject outcome for the proof candidate

The eval-integrity changes must be semantically read-only:

- do not reorder rows
- do not inject defaults
- do not coerce values
- do not normalize or reserialize for hashing
- do not deduplicate cases automatically
- if the dataset is invalid, fail hard
- if the dataset is valid, preserve exact row order and loaded values
