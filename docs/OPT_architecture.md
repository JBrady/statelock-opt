# StateLock-Opt Architecture

As of March 12, 2026, `statelock-opt` is a bounded offline optimizer for StateLock-style memory policies.

statelock-engine = runtime memory system
statelock-opt = offline policy optimizer

It does not train models, call external judges, or run live integrations. Its job is narrower: evaluate candidate retrieval/context/prompt-policy bundles against a fixed replay dataset, score the results deterministically, and accept or reject the candidate.

This document explains the architecture of the statelock-opt repository.
This is the primary orientation document for the statelock-opt repository.

Recommended reading order for this subsystem:

1. `docs/OPT_architecture.md`
2. `docs/OPT_repo_snapshot.md`
3. `docs/OPT_HARDENING_AUDIT.md`
4. `docs/OPT_PROOF.md`
5. `docs/OPT_EVAL_STRATEGY.md`
6. `docs/OPT_MEMORY_HARDENING.md`
7. `docs/OPT_ENGINE_CONTRACT_SKETCH.md`
8. `docs/OPT_BUILD_LOG.md`
9. `docs/OPT_SHIP_PLAN.md`

## Architectural Summary

The system is built around a closed offline loop:

1. A bundle is loaded from disk.
2. The bundle is replayed against the fixed eval dataset.
3. Retrieval, context assembly, prompt rendering, and response generation are executed locally.
4. Each case is scored deterministically.
5. Aggregate metrics are compared against the incumbent.
6. The candidate is accepted or rejected.
7. Run history is distilled into lightweight experiment memory.

The core entry points are:

- `src/statelock_opt/run.py`: evaluate a candidate against an incumbent and perform acceptance.
- `src/statelock_opt/proposer.py`: generate a bounded candidate bundle from the incumbent plus distilled priors.
- `src/statelock_opt/replay.py`: load bundles, replay the dataset, and emit reports.

## Top-Level System Boundaries

In scope:

- offline replay
- lexical retrieval only
- deterministic scoring
- bounded config mutation
- bounded prompt-fragment selection
- strict accept/reject decisions
- distilled experiment memory

Out of scope by design:

- embeddings or hybrid retrieval
- arbitrary code mutation during normal search
- live model calls
- local LLM judges
- broader StateLock platform/runtime work
- UI expansion

## Primary Data Surfaces

### 1. Config Surface

Mutable policy state is a three-file bundle:

- `retrieval.yaml`
- `memory_policy.yaml`
- `prompt_fragments.yaml`

These appear in:

- `configs/`: reference defaults
- `state/incumbent/`: current accepted bundle
- `state/candidates/*`: candidate bundles

Runtime validation happens in `src/statelock_opt/replay.py::validate_bundle`, using enums and numeric ranges defined in `src/statelock_opt/constants.py`.

### 2. Eval Surface

The benchmark lives in `evals/dataset.jsonl`, with the expected shape documented in `evals/schema.json`.

The runtime now validates replay rows against `evals/schema.json` before evaluation.

Eval integrity metadata is derived from the raw file bytes of:

- `evals/dataset.jsonl`
- `evals/schema.json`

That metadata is audit and provenance information only.
It is not a scoring or acceptance input.

### 3. Prompt Surface

Prompt composition uses:

- `prompts/base_system.txt`
- `prompts/answer_style/*.txt`
- `prompts/citation_mode/*.txt`
- `prompts/refusal_mode/*.txt`

`src/statelock_opt/prompt_render.py` renders a textual prompt from those fragments, but the current model adapter is deterministic and does not send the prompt to an external model. Behavior is driven mainly by structured prompt settings plus retrieved records.

### 4. Experiment Memory

The optimizer keeps lightweight local memory under `memory/`:

- `runs.jsonl`: immutable run history
- `lessons.jsonl`: promoted lessons
- `priors.yaml`: proposer bias toward previously successful values
- `bad_regions.yaml`: blocked change signatures
- `known_slow.yaml`: slow patterns
- `tradeoffs.yaml`: recurring metric tradeoffs
- `failures.yaml`: recorded failure patterns

## End-to-End Evaluation Flow

### Candidate Generation

`src/statelock_opt/proposer.py`:

- loads the incumbent bundle
- loads priors and blocked patterns from `memory/`
- chooses either exploit or explore mode
- mutates only bounded fields
- avoids duplicate fingerprints
- avoids blocked or known-slow signatures
- writes a novel bundle to the requested output directory

Important details:

- the mutation surface is intentionally narrow
- when there are no priors, the proposer focuses on three retrieval fields first:
  - `retrieval.top_k_final`
  - `retrieval.min_term_overlap`
  - `retrieval.max_same_source`
- the bundle fingerprint comes from a normalized SHA-256 hash in `src/statelock_opt/dedupe.py`

### Evaluation Replay

`src/statelock_opt/replay.py::evaluate_bundle` performs the evaluation for one bundle:

1. Load and validate the bundle.
2. Load every case from `evals/dataset.jsonl`.
3. Rank records with lexical retrieval.
4. Assemble the final context subset.
5. Render the prompt.
6. Generate a deterministic response.
7. Score the case.
8. Aggregate metrics and write artifacts.

Per-eval outputs are:

- `summary.json`: aggregate metrics plus additive artifact metadata
- `cases.json`: case-level results, selected ids, response, and metrics

Important guardrail:

- eval validation and fingerprinting are semantically read-only
- the loader must not reorder rows, inject defaults, coerce values, normalize fields, or otherwise transform dataset meaning
- invalid datasets fail hard

### Retrieval Layer

`src/statelock_opt/retrieve_lexical.py` implements the current retriever:

- tokenization via a simple lowercase alphanumeric regex
- BM25-style lexical scoring
- optional recency bonus
- minimum term-overlap gate
- per-source cap (`max_same_source`)
- near-duplicate suppression using token Jaccard overlap
- pre-selection cap at `top_k_pre`

The retriever returns ranked records with derived fields such as `retrieval_score` and `term_overlap`.

### Context Assembly Layer

`src/statelock_opt/assemble.py` turns retrieved records into the final prompt context.

Selection logic includes:

- short-term / long-term inclusion flags
- confidence floor
- source requirement
- type caps via `max_items_per_type`
- total memory cap via `max_memories_total`
- prompt token budget
- staleness decay
- conflict penalty
- redundancy penalty for same-source or overlapping content

The final output contains:

- `retrieved_records`
- `selected_records`
- `retrieved_ids`
- `selected_ids`
- `context_text`
- `prompt_context_tokens`

### Prompt Rendering Layer

`src/statelock_opt/prompt_render.py` combines:

- the base system template
- one answer-style fragment
- one citation-mode fragment
- one refusal-mode fragment
- the user query
- the assembled context text

The rendered prompt object also carries normalized settings used later by the model adapter.

### Model Adapter Layer

`src/statelock_opt/model_adapter.py` is not a live model client. It is a deterministic rule-based simulator that:

- decides whether to refuse
- chooses which records were actually used
- emits inline or footnote citations
- marks whether the answer contains a warning
- estimates prompt and output token counts

Behavior is based on:

- selected records
- record kinds such as `decision`, `fact`, and `preference`
- uncertainty markers like `pending`, `did not choose`, and `still open`
- contradiction structure
- prompt settings such as refusal mode and citation mode

This makes the system reproducible and fast, but also means prompt text wording is less influential than it would be in a real LLM-backed system.

### Scoring Layer

`src/statelock_opt/scorer.py` computes case-level and aggregate metrics:

- `correctness`
- `refusal_correctness`
- `unsupported_answer_control`
- `citation_quality`
- `groundedness_proxy`
- `context_cleanliness`
- `latency_score`
- `token_efficiency`
- `false_refusal_rate`
- `unsupported_answer_rate`

The aggregate `total_score` is a weighted sum using `TOTAL_SCORE_WEIGHTS` in `src/statelock_opt/constants.py`.

Hard rejection gates are applied in `evaluate_thresholds` for:

- minimum quality thresholds
- maximum false refusal rate
- maximum unsupported answer rate
- latency budget violations
- prompt token budget violations

### Acceptance Layer

`src/statelock_opt/accept.py::compare_runs` compares candidate and incumbent results.

Acceptance order is:

1. reject threshold failures
2. reject anti-cheese regressions
3. reject insufficient score delta
4. accept if delta clears the minimum and no gates fail

Key constants from `src/statelock_opt/constants.py`:

- `MIN_ACCEPT_DELTA = 1.5`
- `CLOSE_CALL_MAX_DELTA = 3.0`
- `CLOSE_CALL_RERUNS = 3`
- anti-cheese tolerances:
  - `false_refusal_rate`: `0.03`
  - `unsupported_answer_rate`: `0.02`

Close-call reruns only happen if a candidate is tentatively accepted and the delta is below `3.0`.

### Run Orchestration and State Mutation

`src/statelock_opt/run.py` orchestrates the full comparison:

- reserves a unique run artifact directory
- captures dataset identity once per acceptance run
- evaluates incumbent and candidate
- optionally reruns close calls
- verifies incumbent-side and candidate-side dataset identity match within the run
- diffs changed fields
- writes `run.json`
- appends the run to experiment memory
- refreshes distilled memory
- if accepted, copies the candidate bundle into the incumbent directory and snapshots the prior incumbent

`run.json` now carries additive artifact metadata such as:

- `artifact_format_version`
- shared dataset identity
- incumbent bundle identity
- candidate bundle identity

That metadata is non-semantic.
It exists for integrity, provenance, and auditability only.

The only normal source-of-truth mutation to accepted policy state is replacing `state/incumbent/` after a successful run.

### Memory Distillation

`src/statelock_opt/distill.py` derives lightweight guidance from run history:

- promotes accepted repeated wins or large wins into `lessons.jsonl`
- promotes repeated rejected signatures into structured negative lessons when evidence is strong enough
- blocks repeatedly failing signatures in `bad_regions.yaml`
- records latency-heavy patterns in `known_slow.yaml`
- derives favored exact values in `priors.yaml`
- records recurring metric tradeoffs and failure reasons

This makes the proposer stateful without broadening the optimizer beyond local files.
In the current hardening pass, lesson structure became richer, but proposer search behavior was intentionally left unchanged.

## Repository Structure by Role

- `src/statelock_opt/`: executable optimizer logic
- `evals/`: replay dataset and schema
- `prompts/`: prompt template plus bounded fragment inventory
- `configs/`: reference editable config surface
- `state/incumbent/`: current accepted bundle
- `state/candidates/`: candidate bundles, including the proof artifact
- `memory/`: distilled experiment memory and run log
- `artifacts/reports/`: ad hoc evaluation outputs
- `artifacts/runs/`: acceptance-run artifacts
- `docs/`: proof, build log, ship plan, and repo documentation

Additional reference docs introduced in the hardening pass:

- `docs/OPT_HARDENING_AUDIT.md`
- `docs/OPT_EVAL_STRATEGY.md`
- `docs/OPT_MEMORY_HARDENING.md`
- `docs/OPT_ENGINE_CONTRACT_SKETCH.md`

## Determinism and Reproducibility

The repo is designed to be boring and inspectable:

- retrieval is lexical and local
- response generation is deterministic
- scoring is deterministic
- candidate mutation uses bounded fields and seeded randomness
- acceptance is rule-based
- proof commands are documented and reproducible

Reproducibility does not mean all outputs are immutable. Running `python -m statelock_opt.run` updates:

- `artifacts/runs/`
- `memory/`
- `state/incumbent/` if the candidate is accepted

For read-only proof checks, the documented workflow uses direct `evaluate_bundle` calls or a temporary incumbent copy.

## Important Current Quirk

The acceptance pipeline evaluates candidate threshold failures before checking whether a bundle is identical to the incumbent. As a result, a no-op candidate can receive a reason like `unsupported_answer_rate above threshold` instead of a clearer `no diff` or `delta below threshold` explanation. This behavior is documented in `docs/OPT_PROOF.md` and is part of the current architecture.

## Architecture in One Diagram

```text
state/incumbent + memory/* + proposer rules
                |
                v
      src/statelock_opt/proposer.py
                |
                v
      state/candidates/<candidate>
                |
                v
         src/statelock_opt/run.py
                |
      +---------+---------+
      |                   |
      v                   v
 evaluate incumbent   evaluate candidate
      |                   |
      +---------+---------+
                v
     src/statelock_opt/replay.py
                |
                v
 retrieval -> assemble -> prompt -> model_adapter -> scorer
                |
                v
      compare_runs / accept.py
                |
      +---------+---------+
      |                   |
 reject               accept
  |                      |
  v                      v
memory + artifacts   snapshot prior incumbent,
updated              promote candidate to incumbent,
                     then update memory + artifacts
```
