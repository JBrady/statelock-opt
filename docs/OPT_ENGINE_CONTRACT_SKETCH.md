# OPT Engine Contract Sketch

## Status

This document is a provisional interface sketch.

It is not a stable integration contract.
It exists to describe what `statelock-opt` emits today and what a future engine-facing interface would likely need if integration work happens later.

## Current Output Surface

Today, `statelock-opt` emits:

- CLI stdout summary from `python -m statelock_opt.run`
- per-eval `summary.json`
- per-eval `cases.json`
- top-level `run.json`
- experiment-memory side outputs under `memory/`
- an additive experiment registry under `artifacts/registry/experiments.jsonl`

The most integration-friendly artifacts are:

- `run.json`
- `summary.json`

`cases.json` should still be treated as detailed debug/audit output rather than the primary interface.
The experiment registry should also be treated as a local audit/index layer rather than the primary engine-facing interface.

## Current Artifact Metadata

Post-hardening artifacts include additive metadata for:

- `artifact_format_version`
- dataset identity
- bundle identity

Dataset identity includes:

- `dataset_path`
- `dataset_sha256`
- `schema_path`
- `schema_sha256`
- `case_count`
- ordered `case_ids`

Bundle identity includes the evaluated bundle fingerprint.

This metadata is non-semantic in the hardening pass.
It exists for integrity, provenance, and auditability only.
It must not become an input to scoring logic, aggregation logic, or acceptance decisions.

## Provisional Engine-Facing Shape

A future engine-facing consumer would likely need:

- `run_id`
- bundle identity for incumbent and candidate
- changed fields
- candidate aggregate
- incumbent aggregate
- metric deltas
- decision
- case-type coverage
- dataset identity
- artifacts directory

That information already lives primarily in `run.json` plus the per-eval `summary.json` files.

## Decoupling Rules

Any future engine integration must preserve these boundaries:

- no engine imports inside optimizer runtime paths
- no live engine calls during replay
- no engine-owned schemas in scoring logic
- no dependency on engine runtime state to evaluate a bundle

`statelock-opt` should stay file-based and offline unless scope is explicitly broadened.

## Future Additive Fields

If integration work happens later, likely additive fields include:

- `bundle_snapshot`
- `provenance`
- `notes`
- proof-related annotations

Those should be added additively and versioned through artifact metadata rather than by repurposing existing fields.
