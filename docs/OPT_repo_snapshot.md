# statelock-opt Repo Snapshot

This snapshot reflects the repository state as inspected on March 12, 2026.

## Current Status

`statelock-opt` is a narrow v0.1 proof artifact repository. Its current demonstrated milestone is that the offline optimizer can:

- reject a weak candidate
- reject a no-op candidate
- accept a genuinely better candidate

The checked-in proof artifact is:

- incumbent bundle: `state/incumbent/`
- winning candidate: `state/candidates/proof_top_k_final_4/`
- accepted change: `retrieval.top_k_final: 3 -> 4`

Verified proof numbers on March 12, 2026:

- incumbent total score: `93.7536`
- proof candidate total score: `96.9094`
- delta: `+3.1558`
- acceptance result: accepted

The proof is documented in `docs/OPT_PROOF.md`.

The core proof is complete.
Current repo work is focused on post-proof hardening rather than new optimizer behavior.

## Top-Level Inventory

### Source and Configuration

- `src/statelock_opt/`: Python package implementing replay, scoring, candidate generation, acceptance, and memory distillation
- `configs/`: reference config defaults for retrieval, memory policy, and prompt fragments
- `prompts/`: base prompt and bounded fragment inventory

### Evaluation and State

- `evals/`: replay dataset plus JSON schema
- `state/incumbent/`: current accepted bundle
- `state/candidates/`: saved candidate bundles, including the proof artifact
- `memory/`: run log and distilled experiment memory

### Outputs and Documentation

- `artifacts/reports/`: ad hoc evaluation outputs
- `artifacts/runs/`: acceptance-run artifacts
- `artifacts/registry/`: append-only experiment index
- `artifacts/analysis/`: regenerated hypothesis snapshot
- `docs/`: proof notes, build log, ship plan, bootstrap notes, and now repo-level reference docs
- new hardening references:
  - `docs/OPT_HARDENING_AUDIT.md`
  - `docs/OPT_EVAL_STRATEGY.md`
  - `docs/OPT_MEMORY_HARDENING.md`
  - `docs/OPT_EXPERIMENT_REGISTRY.md`
  - `docs/OPT_HYPOTHESES.md`
  - `docs/OPT_ENGINE_CONTRACT_SKETCH.md`
- `README.md`: public project overview and reproducible proof commands
- `program.md`: operational instructions for the optimizer loop
- `tests/`: regression checks protecting proof invariants and proposer stability

### Tooling

- `pyproject.toml`: package metadata and dependency declaration
- `uv.lock`: locked dependency resolution for `uv`

## Current Directory Contents

### `src/statelock_opt/`

Runtime package modules present:

- `__init__.py`
- `accept.py`
- `assemble.py`
- `constants.py`
- `dedupe.py`
- `distill.py`
- `hypotheses.py`
- `model_adapter.py`
- `prompt_render.py`
- `proposer.py`
- `replay.py`
- `retrieve_lexical.py`
- `run.py`
- `scorer.py`
- `signatures.py`

There is also a `__pycache__/` directory from local compilation.

### `prompts/`

Prompt inventory on disk:

- base template:
  - `prompts/base_system.txt`
- answer-style fragments:
  - `balanced.txt`
  - `concise.txt`
  - `evidence_first.txt`
- citation-mode fragments:
  - `concise_inline.txt`
  - `required_footnote.txt`
  - `required_inline.txt`
- refusal-mode fragments:
  - `answer_if_partial_with_warning.txt`
  - `cautious_missing_evidence.txt`
  - `strict_missing_evidence.txt`

Total prompt text files: `10`.

### `configs/`

Reference defaults:

- `configs/retrieval.yaml`
- `configs/memory_policy.yaml`
- `configs/prompt_fragments.yaml`

The reference defaults in `configs/` currently match the incumbent bundle.

### `state/incumbent/`

Files present:

- `memory_policy.yaml`
- `prompt_fragments.yaml`
- `retrieval.yaml`

Current incumbent values:

- retrieval:
  - `strategy: lexical`
  - `top_k_pre: 8`
  - `top_k_final: 3`
  - `min_term_overlap: 1`
  - `bm25_k1: 1.2`
  - `bm25_b: 0.75`
  - `recency_weight: 0.1`
  - `dedupe_overlap_threshold: 0.8`
  - `max_same_source: 2`
- memory policy:
  - `include_short_term: true`
  - `include_long_term: true`
  - `max_memories_total: 4`
  - `max_items_per_type: 3`
  - `promote_threshold: 0.7`
  - `drop_low_confidence_below: 0.35`
  - `stale_decay_days: 45`
  - `conflict_penalty: 0.25`
  - `redundancy_penalty: 0.2`
  - `require_source_for_use: true`
- prompt fragments:
  - `answer_style: balanced`
  - `citation_instruction: required_inline_ids`
  - `refusal_behavior: cautious_missing_evidence`
  - `max_context_tokens: 1800`
  - `quote_budget_tokens: 120`

### `state/candidates/`

Candidate directories currently present:

- `candidate_0001`
- `generated_0001`
- `generated_0002`
- `generated_0003`
- `generated_0004`
- `generated_0005`
- `proof_top_k_final_4`

The proof candidate bundle is identical to the incumbent except:

- `retrieval.top_k_final: 3 -> 4`

### `evals/`

Files present:

- `dataset.jsonl`
- `schema.json`
- `fixtures/.gitkeep`

Observed dataset facts:

- case count: `23`
- case ids run from `case_001` through `case_023`
- expected behavior classes present:
  - `answer`
  - `answer_with_caution`
  - `refuse`

Important benchmark wedge cases:

- `case_021`: creates the real headroom for `top_k_final=4`
- `case_022`: penalizes over-strict overlap gating
- `case_023`: penalizes over-restrictive same-source limits

The runtime also derives five coarse case-type labels during evaluation:

- `direct_recall`
- `partial_evidence`
- `conflict_resolution`
- `distractor_retrieval`
- `missing_evidence_refusal`

Post-hardening eval integrity notes:

- runtime validates dataset rows against `schema.json`
- dataset identity is derived from the raw bytes of `dataset.jsonl` and `schema.json`
- one shared dataset identity is captured once per acceptance run and reused for both incumbent and candidate evaluation
- optional `case_metadata` exists for taxonomy and proof-role scaffolding only

### `memory/`

Files present:

- `bad_regions.yaml`
- `failures.yaml`
- `known_slow.yaml`
- `lessons.jsonl`
- `priors.yaml`
- `runs.jsonl`
- `tradeoffs.yaml`

Observed state on March 12, 2026:

- `runs.jsonl` contains `2` historical run records
- `lessons.jsonl` is empty
- `priors.yaml` is empty
- `bad_regions.yaml` is empty
- `known_slow.yaml` is empty
- `tradeoffs.yaml` is empty
- `failures.yaml` contains:
  - rejection of `memory_policy.max_items_per_type:3->2` for `false_refusal_rate regressed beyond tolerance`
  - a no-op record with empty signature rejected for `score delta below minimum acceptance threshold`

This means the repository has early failure memory but has not yet accumulated promoted lessons in the current checked-in state.

Lesson schema is now more explicit, but the checked-in memory state is still intentionally sparse.

### `artifacts/`

Artifacts are divided into:

- `artifacts/reports/`: one-off evaluation outputs
- `artifacts/runs/`: acceptance-run directories created by `python -m statelock_opt.run`
- `artifacts/registry/`: additive run-summary index
- `artifacts/analysis/`: regenerated exact-signature belief snapshot

Observed counts on March 12, 2026:

- report directories: `83`
- run directories: `7`

Typical report directory contents:

- `summary.json`
- `cases.json`

`summary.json` now also carries additive artifact metadata for dataset identity, bundle identity, and artifact format version.

The hypothesis layer now derives:

- `artifacts/analysis/hypotheses.jsonl`

It is regenerated from the registry, remains non-semantic in v1, and stores bounded run references rather than a second full experiment ledger.

Typical top-level `run.json` contents now also include:

- `artifact_format_version`
- shared dataset identity
- incumbent bundle identity
- candidate bundle identity

That metadata is provenance-only and is not part of scoring or acceptance semantics.

The experiment registry now also appends one structured record per completed run to:

- `artifacts/registry/experiments.jsonl`

That registry is an audit/index layer only.
It does not replace `run.json` or `memory/runs.jsonl`.

### `tests/`

Repo-grounded regression coverage now includes:

- `tests/test_hardening_regressions.py`

The current regression suite protects:

- raw-byte dataset and schema fingerprinting
- proof-case order and per-case score preservation
- incumbent and proof-candidate aggregate-score preservation
- final proof accept/reject preservation
- proposer candidate-selection stability for the checked-in memory state
- structured lesson promotion in a temporary memory directory

Typical run directory contents:

- `incumbent_1/summary.json`
- `incumbent_1/cases.json`
- `candidate_1/summary.json`
- `candidate_1/cases.json`
- `run.json`

Accepted runs may also contain `previous_incumbent/` with the prior accepted bundle snapshot.

`run.json` now also carries additive artifact metadata for shared dataset identity and incumbent/candidate bundle identity.

## Behaviorally Important Code Facts

### Deterministic Runtime

The current stack is fully local and deterministic:

- lexical retrieval in `retrieve_lexical.py`
- rule-based context assembly in `assemble.py`
- deterministic prompt rendering in `prompt_render.py`
- deterministic simulated response generation in `model_adapter.py`
- deterministic scoring in `scorer.py`

There is no external model or network dependency in the evaluation path.

Eval validation and fingerprinting are non-semantic hardening metadata.
They must not alter scoring or acceptance behavior.

### Acceptance Rules

Key constants from `src/statelock_opt/constants.py`:

- minimum accept delta: `1.5`
- close-call rerun threshold: `3.0`
- close-call reruns: `3`
- anti-cheese tolerance:
  - `false_refusal_rate`: `0.03`
  - `unsupported_answer_rate`: `0.02`

### Current Acceptance Quirk

The no-op rejection reason can be unintuitive. Because threshold failures are checked before no-diff or zero-delta clarity checks, an identical bundle can report a reason like `unsupported_answer_rate above threshold`. This behavior is documented in `docs/OPT_PROOF.md` and visible in existing run artifacts.

### Prompt Surface vs Runtime Behavior

The prompt files are real inputs to prompt rendering, but the current model adapter is a deterministic simulator rather than an LLM call. In practice:

- prompt fragment selection affects structured behavior through the prompt settings
- prompt text contributes to rendered prompt size and therefore token counts
- prompt wording itself does not drive a live language model

This is important for interpreting how much leverage prompt changes have in v0.1.

## Packaging and Dependencies

`pyproject.toml` declares:

- package name: `statelock-opt`
- version: `0.1.0`
- Python requirement: `>=3.10`
- runtime dependency: `jsonschema>=4.25.1`
- runtime dependency: `pyyaml>=6.0.2`

Setuptools is used for packaging, with source under `src/`.

## Reproduction Commands

The repo’s canonical proof commands are the ones documented in `README.md`:

- evaluate the incumbent with `evaluate_bundle`
- evaluate the proof candidate with `evaluate_bundle`
- run the acceptance check against a temporary incumbent copy

Recommended verification commands from `AGENTS.md`:

- `uv run python -m compileall src`
- candidate evaluation via `evaluate_bundle`
- acceptance check via `python -m statelock_opt.run`

## Constraints That Define the Current Snapshot

The repository is intentionally narrow. The active constraints are:

- preserve deterministic behavior
- keep changes small and surgical
- do not casually change benchmark or scoring
- do not modify proof artifact bundles unless explicitly requested
- do not broaden scope into hybrid retrieval, embeddings, local judges, live integrations, or UI work

## Working Tree Note

The repository was inspected from a clean working tree before these documentation files were added.
