# OPT Hypotheses

## Purpose

The hypothesis layer is a lightweight, generated belief snapshot derived from the experiment registry.

It is not a source of truth for run history.
It is not a proposer input.
It is not part of scoring, acceptance, or memory refresh.

In v1, the goal is narrow:

- summarize exact observed change signatures
- classify current evidence as supported, mixed, contradicted, or inconclusive
- show where effects appear to concentrate by case family and proof role

## Location

The hypothesis artifact lives at:

- `artifacts/analysis/hypotheses.jsonl`

This placement is intentional.
The file lives under `artifacts/` rather than `memory/` because it is a downstream analysis view, not a proposer-adjacent memory surface.

## Input Source

The hypothesis layer is derived only from:

- `artifacts/registry/experiments.jsonl`

It does not reread:

- `artifacts/runs/*`
- `memory/lessons.jsonl`
- `memory/runs.jsonl`

That keeps the dependency surface small and makes the registry the canonical experiment-history source in v1.

## Regeneration Model

The hypothesis file is regenerated from the full registry after a successful registry append.

It is not append-only.

That design is deliberate:

- hypotheses represent current beliefs, not immutable events
- contradictory new evidence must be able to downgrade or reclassify an older belief
- full regeneration is simpler and more deterministic than incremental belief updates

If the registry is missing or empty, the refresh step writes an empty `hypotheses.jsonl`.

If the registry contains malformed rows, the hypothesis refresh fails by itself and leaves any previously written hypothesis artifact unchanged.
That failure is non-semantic and must not affect scoring, acceptance, proposer behavior, incumbent mutation, registry append, or memory refresh.

## One Record Per Exact Signature

In v1, each hypothesis record represents one exact non-empty `change_signature`.

This means:

- no generalized parameter theories
- no similarity clustering across signatures
- no proposer guidance
- no freeform inference

The artifact is intentionally conservative.

## Record Shape

Each hypothesis record includes:

- `hypothesis_format_version`
- `hypothesis_id`
- `status`
- `confidence`
- `claim_type`
- `claim_text`
- `change_signature`
- `target_changes`
- `evidence_counts`
- `evidence_run_refs`
- `target_case_families`
- `target_proof_roles`
- `case_family_evidence`
- `proof_role_evidence`
- `evidence_summary`
- `promoted_lesson_signals`
- `suggested_next_moves`
- `warnings`

## Deterministic Rules

### Status

Allowed values:

- `supported`
- `mixed`
- `contradicted`
- `inconclusive`

Current classification is based only on grouped registry evidence for one signature.

### Confidence

Allowed values:

- `low`
- `medium`
- `high`

Confidence is deterministic and derived only from evidence counts and consistency.

### Claim Text

`claim_text` is templated from the signature and status.
It is not freeform generated text.

## Bounded Run References

The hypothesis layer must not become a second run ledger.

Because of that, v1 stores:

- full evidence counts
- only a small bounded reference list of run ids

`evidence_run_refs` includes:

- `supporting_run_ids`
- `opposing_run_ids`
- `inconclusive_run_ids`

Each list is capped to a small deterministic limit and sorted stably before truncation.

The rationale is:

- keep the artifact lightweight
- avoid duplicating the full registry history
- preserve `artifacts/registry/experiments.jsonl` as the canonical experiment-history source

If a full run ledger is needed, the registry remains the place to inspect it.

## Case-Family and Proof-Role Evidence

Case-family and proof-role summaries are aggregated from the registry’s existing summary fields:

- `case_family_summary`
- `proof_role_summary`

The hypothesis layer does not reread case artifacts and does not invent new classifications.

If an `unlabeled` bucket exists in the registry-derived summaries, it is preserved.

## Relationship to Other Artifacts

Current roles are:

- `artifacts/runs/<run_id>/run.json`: canonical per-run summary
- `artifacts/registry/experiments.jsonl`: append-only experiment index and canonical experiment-history source
- `artifacts/analysis/hypotheses.jsonl`: regenerated belief snapshot
- `memory/runs.jsonl`: distillation feed for proposer-adjacent memory
- `memory/lessons.jsonl`: promoted lesson artifacts

The hypothesis layer supersedes none of these in v1.

## Non-Semantic Guardrail

The hypothesis layer is non-semantic in v1.

It must not affect:

- scoring inputs
- acceptance logic
- proposer logic
- memory refresh
- incumbent mutation

It exists to make current beliefs legible and auditable, not to steer the optimizer yet.
