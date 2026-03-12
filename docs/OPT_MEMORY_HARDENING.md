# OPT Memory Hardening

## Purpose

This document describes the post-proof hardening rules for experiment memory in `statelock-opt`.

The goal is to make memory outputs more inspectable and deterministic without changing proposer search behavior.

## Current Role of Experiment Memory

The optimizer writes:

- `memory/runs.jsonl`
- `memory/lessons.jsonl`
- `memory/priors.yaml`
- `memory/bad_regions.yaml`
- `memory/known_slow.yaml`
- `memory/tradeoffs.yaml`
- `memory/failures.yaml`

Only a subset of those files influence proposer behavior today:

- `priors.yaml`
- `bad_regions.yaml`
- `known_slow.yaml`

That must remain true in this hardening pass.

The experiment registry is separate from this memory layer.

- `memory/runs.jsonl` feeds distillation
- `artifacts/registry/experiments.jsonl` is an additive audit/index artifact
- `artifacts/analysis/hypotheses.jsonl` is a regenerated downstream belief snapshot

The registry must not become a proposer input in this pass.
The hypothesis layer must also remain outside proposer inputs in this pass.

## Lesson Schema

Promoted lessons in `lessons.jsonl` now use a more explicit structure:

- `lesson_id`
- `lesson_type`
- `status`
- `scope`
- `pattern`
- `observed_effect`
- `evidence_runs`
- `confidence`
- `promotion_rule`

Current lesson types:

- `positive`
- `negative`

Current promotion rules:

- `large_accepted_win`
- `repeated_accepted_pattern`
- `repeated_rejected_pattern`

## Hardening Rules

Memory hardening is artifact-layer only.

This means:

- `lessons.jsonl` may become richer and easier to inspect
- `priors.yaml`, `bad_regions.yaml`, and `failures.yaml` may become clearer
- proposer search logic must not change
- lesson artifacts must not become a new proposer input

The required regression property is:

For the same checked-in memory state, candidate-selection behavior must remain unchanged.

## Minimal Reproduction Flow

The memory-hardening proof should be run against a temporary memory directory, not the checked-in `memory/` directory.

Suggested flow:

1. create a temp directory
2. write a synthetic `runs.jsonl` with:
   - one large accepted win
   - three repeated rejected runs with the same signature
3. call `refresh_memory(temp_memory_dir)`
4. inspect the resulting:
   - `lessons.jsonl`
   - `priors.yaml`
   - `bad_regions.yaml`
   - `failures.yaml`

Expected result:

- one structured positive lesson
- one structured negative lesson
- no change to repo-tracked memory files

## What This Does Not Prove

This hardening work does not claim:

- long-horizon learned search is solved
- proposer should read lessons directly
- experiment memory is now a complete optimization policy

It only makes the current memory layer more legible, more reproducible, and safer to extend later.
