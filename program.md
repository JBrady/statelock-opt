# StateLock Optimizer Program

This repo is a bounded local optimizer for StateLock-style memory systems.

## Mission

Improve the incumbent retrieval/context/prompt-policy bundle using:
- offline replay only
- lexical retrieval only
- deterministic-first scoring only
- bounded config mutation
- bounded prompt-fragment mutation only

The optimizer is not allowed to mutate arbitrary code for normal experiments. The editable surface is:
- `configs/retrieval.yaml`
- `configs/memory_policy.yaml`
- `configs/prompt_fragments.yaml`

## Ground Rules

1. Read `README.md` and the three editable config files before proposing any change.
2. Do not modify evaluator code, replay harness code, dataset files, model adapter code, or memory distillation code during normal search.
3. Do not rewrite `prompts/base_system.txt`.
4. Do not invent new prompt fragments during the MVP loop.
5. Treat `state/incumbent/` as the current accepted config.

## Canonical Commands

Evaluate a candidate:

```bash
uv run python -m statelock_opt.run --candidate state/candidates/candidate_XXXX
```

Generate a new candidate:

```bash
uv run python -m statelock_opt.proposer --output state/candidates/generated_XXXX
```

## Acceptance Standard

A candidate is accepted only if:
- it passes all hard rejection thresholds
- it improves total score over the incumbent by at least `1.5`
- close-call wins survive reruns
- false-refusal and unsupported-answer behavior do not regress materially

Reject by default if the result is noisy or ambiguous.

## Distilled Experiment Memory

The optimizer must treat experiment memory as first-class.

Use:
- `memory/runs.jsonl` for immutable raw run history
- `memory/lessons.jsonl` for promoted lessons
- `memory/priors.yaml` for proposal bias
- `memory/bad_regions.yaml` for blocked regions
- `memory/known_slow.yaml` for slow patterns
- `memory/tradeoffs.yaml` for recurring tradeoffs
- `memory/failures.yaml` for repeated failure modes

Promote a lesson only when there is real evidence:
- 2 or more independent runs with similar directionality
- 1 clearly large accepted win
- repeated failures in the same bounded region

## Search Behavior

Keep the loop boring and inspectable:
- prefer small config deltas
- prefer the current weakest metric
- avoid duplicate runs
- avoid known bad regions
- avoid known slow patterns
- do not "win" by refusing too often

When in doubt, prefer rejection over promoting weak evidence.
