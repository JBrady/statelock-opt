# OPT Eval Strategy

## Purpose

This document describes how `statelock-opt` should grow the replay benchmark after the core v0.1 proof without changing the proof into a moving target casually.

The benchmark exists to make policy quality measurable.
It is not a dumping ground for arbitrary scenarios.

## Current Benchmark Role

The current dataset serves two jobs:

- provide a stable proof surface for the v0.1 optimizer loop
- provide enough discriminative pressure to distinguish meaningful retrieval/context-policy changes

The current proof wedge depends on three tagged cases:

- `case_021`: `proof_role = wedge`
- `case_022`: `proof_role = guardrail`
- `case_023`: `proof_role = guardrail`

## Case Taxonomy

Every case may carry optional authoring metadata under `case_metadata`.

Current `case_family` vocabulary:

- `direct_recall`
- `partial_evidence`
- `conflict_resolution`
- `distractor_retrieval`
- `missing_evidence_refusal`

Current `proof_role` vocabulary:

- `baseline`
- `wedge`
- `guardrail`
- `regression`

The runtime does not score differently based on these fields in v0.1 hardening.
They are descriptive scaffolding only.

## Authoring Rules

When adding replay cases:

- keep the case self-contained
- make the expected behavior explicit
- make support and forbidden ids explicit
- keep distractors intentional rather than incidental
- avoid adding duplicate semantic coverage without a reason
- prefer small, legible memory banks over bloated synthetic bundles

If a new case is intended to create headroom for a policy change, it should be marked as a `wedge`.
If a case exists to stop a wedge from creating collateral regressions, it should be marked as a `guardrail`.

## Proof-Preserving Benchmark Changes

Changes to the dataset should be treated in one of two categories:

### Non-proof-affecting changes

- adding descriptive `case_metadata`
- clarifying comments or docs outside the runtime data
- adding new strategy documents

### Proof-affecting changes

- changing expected behavior
- changing support or forbidden ids
- changing budgets
- changing memory-bank content
- adding or removing replay rows
- changing the role of proof wedge or guardrail cases

Proof-affecting changes require re-verification of:

- incumbent aggregate score
- proof candidate aggregate score
- proof delta
- final accept/reject decision

## Dataset Integrity Rules

Eval validation and fingerprinting are semantically read-only.

Implementation must not:

- reorder rows
- inject defaults
- apply JSON Schema default-population behavior
- coerce values
- normalize fields
- deduplicate cases automatically
- otherwise transform dataset meaning

If the dataset is invalid, fail hard.
If it is valid, preserve exact row order and loaded values.

Dataset identity is derived from the raw bytes of:

- `evals/dataset.jsonl`
- `evals/schema.json`

Those fingerprints are provenance metadata, not scoring inputs.

## Future Growth Guidance

The next dataset expansions should bias toward:

- clearer conflict-resolution coverage
- stronger distractor pressure
- more refusal/answer boundary cases
- more explicit guardrail coverage for accepted retrieval improvements

Do not broaden into embeddings, semantic judges, or runtime integration behavior in this repo unless explicitly requested.
