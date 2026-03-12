# OPT Experiment Registry

## Purpose

The experiment registry is a lightweight, append-only lab notebook index for completed optimizer runs.

It does not replace canonical run artifacts.
It summarizes them so the repo can accumulate structured experiment evidence over time.

The registry is intentionally:

- file-based
- additive
- deterministic
- human-inspectable
- non-semantic

In v1 it is not read by scoring, acceptance, proposer logic, or memory refresh.

## Location

The registry lives at:

- `artifacts/registry/experiments.jsonl`

Each line is one completed acceptance run.

## Record Shape

Each registry record includes:

- `registry_format_version`
- `run_id`
- `run_timestamp_utc`
- `artifact_format_version`
- `artifact_paths`
- `candidate_path`
- `dataset_identity`
- `incumbent_bundle_identity`
- `candidate_bundle_identity`
- `changed_fields`
- `change_signature`
- `aggregate`
- `incumbent_aggregate`
- `metric_deltas`
- `decision`
- `case_types`
- `case_delta_summary`
- `case_family_summary`
- `proof_role_summary`
- `promoted_lessons`
- `registry_warnings`

The registry stays lightweight by pointing back to `run.json`, `summary.json`, and `cases.json` rather than copying their full payloads.

## Write Lifecycle

Registry generation happens after:

1. the acceptance decision is computed
2. `run.json` is written
3. `memory/runs.jsonl` is appended
4. `refresh_memory()` completes

That ordering matters because lesson-promotion attribution depends on the pre-refresh and post-refresh `memory/lessons.jsonl` state.

Registry generation is downstream of decision logic.
If registry generation fails, the run remains valid and `run.json` remains the canonical per-run artifact.

## Relationship to Existing Artifacts

The registry does not supersede any existing file in v1.

Current roles:

- `artifacts/runs/<run_id>/run.json`: canonical per-run summary
- `artifacts/runs/<run_id>/*/summary.json`: canonical per-eval aggregate artifact
- `artifacts/runs/<run_id>/*/cases.json`: canonical detailed per-case artifact
- `memory/runs.jsonl`: canonical distillation feed for experiment memory
- `artifacts/registry/experiments.jsonl`: additive audit/index layer

## Lesson Attribution

`promoted_lessons` are derived from the difference between pre-refresh and post-refresh `memory/lessons.jsonl`.

Attribution uses a stable lesson identity based on:

- `lesson_type`
- `promotion_rule`
- `pattern`
- `scope`

It does not rely on `lesson_id`, because lesson ids are regeneration-local.

If lesson attribution is unavailable in v1:

- `promoted_lessons` is emitted as `[]`
- `registry_warnings` includes `lesson_attribution_unavailable`

That fallback is non-semantic and does not invalidate the run.

## Timestamp Guardrail

`run_id` is the canonical identifier.

`run_timestamp_utc` is intentionally optional in v1.
It should only be populated if run-id parsing is already a stable and unambiguous repo contract.

Because the repo contains historical run ids with more than one shape, v1 keeps `run_timestamp_utc` as `null`.

## Backfill

There is no automatic backfill in v1.

The registry begins with runs completed after implementation.
This keeps the first version low-risk and avoids heuristic reconstruction of older lesson promotions.

## Relation to Hypotheses

The hypothesis layer is a downstream analysis view derived from the registry:

- `artifacts/analysis/hypotheses.jsonl`

Current separation of responsibilities:

- the registry is the canonical append-only experiment-history source
- the hypothesis file is a regenerated belief snapshot

To preserve that boundary, the hypothesis layer stores full evidence counts but only small bounded run-reference lists.
It must not become a second run ledger.
