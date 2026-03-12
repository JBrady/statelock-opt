# StateLock-Opt Session Bootstrap
Date: 2026-03-11
Author: John Brady

## 1. What This Repository Is

`statelock-opt` is an offline optimizer that searches for better retrieval and context policies for AI memory systems.

Key concept:
Most AI agent failures are policy failures rather than model failures.

Instead of retraining models, `statelock-opt` explores the policy search space for:

• retrieval parameters  
• memory selection policies  
• prompt framing fragments  

It uses offline replay of past conversations and deterministic scoring to determine whether a candidate policy improves system behavior.

## 2. Relationship to statelock-engine

`statelock-engine` = runtime memory sidecar  
`statelock-opt` = offline policy optimizer

Engine stores and retrieves memory.  
Opt finds better policies for how that memory should be used.

Engine = body  
Opt = brain tuner

## 3. What Was Achieved Today

`statelock-opt` now has a reproducible proof artifact demonstrating that the optimizer loop works.

The system can:

• reject weak candidates  
• reject no-op candidates  
• accept a genuinely better candidate  

Winning policy change:

`retrieval.top_k_final: 3 → 4`

Benchmark results:

incumbent score: 93.7536  
candidate score: 96.9094  
delta: +3.1558  
accepted: true

The winning candidate is stored at:

`state/candidates/proof_top_k_final_4`

## 4. Key Benchmark Improvements Made

A benchmark wedge was added to expose more discriminative cases.

Added cases:

`case_021`  
`case_022`  
`case_023`

These cases specifically stress:

• retrieval fanout  
• distractor pressure  
• same-source evidence limits  

The goal was to ensure the benchmark had real improvement headroom.

## 5. Current Proof Artifact

The reproducible proof commands are already documented in `README.md`.

The proof flow is:

Evaluate incumbent

Evaluate proof candidate

Run acceptance check

Use the commands from `README.md` so the proof is rerun the same way each time.

## 6. Known Quirks / Observations

No-op candidates may report threshold failures such as:

`unsupported_answer_rate above threshold`

This happens because acceptance checks currently evaluate thresholds before checking whether the candidate differs from the incumbent.

Future improvement:

detect zero-delta candidates earlier and return a clearer reason.

## 7. Why This Project Exists

John's thesis:

Long-running AI agents suffer from context rot and memory clutter.

Most developers try to solve this by:

• increasing model size  
• increasing context window  
• adding more RAG  

StateLock's thesis:

Memory quality and selection policy matter more than model size.

StateLock aims to provide:

• context hygiene  
• memory governance  
• optimized memory policies  

## 8. Developer Working Style

John's development workflow:

• Solo builder  
• Uses AI tools (Codex / ChatGPT) heavily  
• Iterates quickly  
• Prefers proof-driven development  
• Wants reproducible artifacts rather than vague ideas  

Important preference:

When documenting work, keep things deterministic and reproducible.

## 9. Psychological Context (Important)

During this session the developer expressed frustration about a long-standing pattern:

starting ambitious projects but rarely shipping visible artifacts.

This milestone matters because it establishes the first reproducible proof artifact in the StateLock ecosystem.

Future sessions should prioritize:

• stabilizing artifacts  
• incremental improvements  
• avoiding endless redesign cycles  

## 10. Future Work Ideas

• improved proposer search strategies  
• richer benchmark cases  
• policy search beyond lexical retrieval  
• better acceptance-reason reporting  
• deeper integration with statelock-engine  

## 11. Notes on Project Management

The developer expressed interest in possibly using a lightweight issue-tracking system to capture ideas and future tasks.

Possible options:

• GitHub Issues  
• lightweight TODO.md  
• project board  

Avoid heavy tools like Jira unless the project becomes a team effort.

## 12. How to Bootstrap a New ChatGPT Session

A new AI session should:

1. Read this document
2. Read `README.md`
3. Read `docs/OPT_PROOF.md`
4. Inspect `state/incumbent` and the proof candidate
5. Confirm current development goal before proposing changes
