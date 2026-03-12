# AGENTS.md

## Repo purpose

statelock-opt is an offline optimizer for memory retrieval and context policies.
It does not train models.
It evaluates bounded candidate policies through offline replay and deterministic scoring.

## Current goal

Protect and extend the v0.1 proof artifact without broadening scope.

The repo currently proves that the optimizer can:
- reject weak candidates
- reject no-op candidates
- accept a genuinely better candidate

Proof artifact:
- docs/OPT_PROOF.md
- state/candidates/proof_top_k_final_4

## Scope boundaries

Do not broaden scope unless explicitly asked.

Out of scope by default:
- hybrid retrieval
- embeddings
- local LLM judges
- live integrations
- UI expansion
- broader StateLock platform work

## Important files

- README.md
- docs/statelock_vision.md
- docs/OPT_architecture.md
- docs/OPT_repo_snapshot.md
- docs/OPT_HARDENING_AUDIT.md
- docs/OPT_PROOF.md
- docs/OPT_EVAL_STRATEGY.md
- docs/OPT_MEMORY_HARDENING.md
- docs/OPT_EXPERIMENT_REGISTRY.md
- docs/OPT_HYPOTHESES.md
- docs/OPT_ENGINE_CONTRACT_SKETCH.md
- docs/OPT_BUILD_LOG.md
- docs/STATELOCK-OPT_SESSION_2026_03_11_CODEX_BOOTSTRAP.md
- evals/dataset.jsonl
- evals/schema.json
- tests/test_hardening_regressions.py
- tests/test_experiment_registry.py
- tests/test_hypotheses.py
- src/statelock_opt/run.py
- src/statelock_opt/replay.py
- src/statelock_opt/proposer.py
- src/statelock_opt/scorer.py
- state/incumbent/
- state/candidates/proof_top_k_final_4/

## Development rules

- Prefer small, surgical changes
- Preserve deterministic behavior
- Do not change benchmark or scoring casually
- Do not modify proof artifact bundles unless explicitly asked
- Keep documentation factual and reproducible

## Session bootstrap

If the user says `Bootstrap yourself`, or says to read `AGENTS.md` and follow the instructions, do this before proposing changes:

1. Read:
   - `docs/OPT_architecture.md`
   - `docs/OPT_repo_snapshot.md`
   - `docs/OPT_HARDENING_AUDIT.md`
   - `docs/OPT_EVAL_STRATEGY.md`
   - `docs/OPT_MEMORY_HARDENING.md`
   - `docs/OPT_EXPERIMENT_REGISTRY.md`
   - `docs/OPT_HYPOTHESES.md`
   - `docs/OPT_ENGINE_CONTRACT_SKETCH.md`
   - `README.md`
   - `docs/OPT_PROOF.md`
   - `docs/OPT_BUILD_LOG.md`
   - `docs/STATELOCK-OPT_SESSION_2026_03_11_CODEX_BOOTSTRAP.md`
   - `docs/statelock_vision.md`
2. Inspect the current proof state:
   - `state/incumbent/`
   - `state/candidates/proof_top_k_final_4/`
3. Inspect the key optimizer architecture files:
   - `src/statelock_opt/run.py`
   - `src/statelock_opt/replay.py`
   - `src/statelock_opt/scorer.py`
   - `src/statelock_opt/proposer.py`
4. Inspect the current benchmark surface:
   - `evals/dataset.jsonl`
   - `evals/schema.json`
5. Inspect the current regression guardrails:
   - `tests/test_hardening_regressions.py`
   - `tests/test_experiment_registry.py`
   - `tests/test_hypotheses.py`
6. Summarize the current repo state, milestone, constraints, and likely next step before making changes.

The goal of bootstrap is to rehydrate both project context and implementation context so a new session can work effectively without re-deriving the repo from scratch.

## Verification

When changing behavior, verify with repo-grounded commands.
Prefer:
- `uv run python -m compileall src`
- `uv run python -m unittest discover -s tests -v`
- candidate evaluation via `evaluate_bundle`
- acceptance check via `python -m statelock_opt.run`

## Git workflow

- Do not commit directly to main/master
- Use a feature branch
- Keep commits focused

Workflow shorthand:

- `yeet`: create an appropriate branch, stage the intended changes, commit, push, and open a PR
- `full yeet`: do `yeet`, then after the PR is merged sync local `main` with remote and prune merged branches locally and remotely
