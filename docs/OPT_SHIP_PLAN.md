# statelock-opt Shipping Plan

## Purpose of This Repo

statelock-opt is an experimental optimizer for StateLock retrieval and context policies.

It runs offline experiments that:

- mutate candidate configurations
- replay evaluation datasets
- score candidate performance
- accept or reject candidates deterministically
- accumulate lessons from experiment results

This repo exists to prove that context policies can be improved through
replay-based optimization rather than model retraining.

## v0.1 Goal

Ship a working offline optimizer loop that can:

1. Generate candidate configs
2. Replay an evaluation dataset
3. Score candidate performance
4. Accept or reject candidates
5. Distill lessons from experiment results

## What Counts As Success

The optimizer must demonstrate:

- one bad candidate rejected for the correct reason
- one no-op candidate rejected
- one improved candidate accepted
- at least one repeated failure pattern distilled into a lesson

## Current Priorities

Focus only on components that make the optimizer trustworthy:

- artifact generation
- replay stability
- scoring correctness
- deterministic accept/reject behavior
- dataset quality

## Explicitly Out of Scope

Do NOT implement these in this repo right now:

- StateLock platform architecture
- memory graph
- promotion engine
- hybrid retrieval
- embeddings experimentation
- UI expansion
- local LLM judges
- production integrations

Those belong in statelock-engine.

## Working Rule

If a change does not directly improve the optimizer loop,
do not implement it.
