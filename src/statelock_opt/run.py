import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .accept import compare_runs
from .constants import ARTIFACTS_DIR, CLOSE_CALL_RERUNS, INCUMBENT_DIR, MEMORY_DIR
from .distill import append_run_record, refresh_memory
from .replay import diff_bundle, evaluate_bundle, load_bundle, validate_bundle


def _reserve_run_dir():
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    for _ in range(32):
        run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}_{uuid4().hex[:8]}"
        base_artifact_dir = ARTIFACTS_DIR / run_id
        try:
            base_artifact_dir.mkdir(parents=False, exist_ok=False)
        except FileExistsError:
            continue
        return run_id, base_artifact_dir
    raise RuntimeError("Failed to reserve a unique artifact directory.")


def _metric_deltas(incumbent_aggregate, candidate_aggregate):
    keys = (
        "correctness",
        "refusal_correctness",
        "unsupported_answer_control",
        "citation_quality",
        "groundedness_proxy",
        "context_cleanliness",
        "latency_score",
        "token_efficiency",
        "false_refusal_rate",
        "unsupported_answer_rate",
    )
    return {
        key: round(candidate_aggregate[key] - incumbent_aggregate[key], 6)
        for key in keys
    }


def _copy_bundle(source_dir, dest_dir):
    dest_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("retrieval.yaml", "memory_policy.yaml", "prompt_fragments.yaml"):
        shutil.copy2(source_dir / filename, dest_dir / filename)


def main():
    parser = argparse.ArgumentParser(description="Run the StateLock optimizer against a candidate config bundle.")
    parser.add_argument("--candidate", required=True, help="Path to the candidate bundle directory")
    parser.add_argument("--incumbent", default=str(INCUMBENT_DIR), help="Path to the incumbent bundle directory")
    args = parser.parse_args()

    candidate_dir = Path(args.candidate)
    incumbent_dir = Path(args.incumbent)

    candidate_bundle = load_bundle(candidate_dir)
    incumbent_bundle = load_bundle(incumbent_dir)
    validate_bundle(candidate_bundle)
    validate_bundle(incumbent_bundle)

    run_stamp, base_artifact_dir = _reserve_run_dir()

    incumbent_evals = [evaluate_bundle(incumbent_dir, f"{run_stamp}_incumbent_1", base_artifact_dir / "incumbent_1")]
    candidate_evals = [evaluate_bundle(candidate_dir, f"{run_stamp}_candidate_1", base_artifact_dir / "candidate_1")]

    decision = compare_runs(incumbent_evals, candidate_evals)
    if decision["accepted"] and decision["close_call"]:
        incumbent_evals = []
        candidate_evals = []
        for index in range(CLOSE_CALL_RERUNS):
            incumbent_evals.append(
                evaluate_bundle(incumbent_dir, f"{run_stamp}_incumbent_{index+1}", base_artifact_dir / f"incumbent_{index+1}")
            )
            candidate_evals.append(
                evaluate_bundle(candidate_dir, f"{run_stamp}_candidate_{index+1}", base_artifact_dir / f"candidate_{index+1}")
            )
        decision = compare_runs(incumbent_evals, candidate_evals)

    incumbent_eval = incumbent_evals[-1]
    candidate_eval = candidate_evals[-1]
    metric_deltas = _metric_deltas(incumbent_eval["aggregate"], candidate_eval["aggregate"])
    changed_fields = diff_bundle(incumbent_bundle, candidate_bundle)

    if decision["accepted"]:
        snapshot_dir = base_artifact_dir / "previous_incumbent"
        _copy_bundle(incumbent_dir, snapshot_dir)
        _copy_bundle(candidate_dir, incumbent_dir)

    record = {
        "run_id": run_stamp,
        "candidate_path": str(candidate_dir),
        "fingerprint": candidate_eval["fingerprint"],
        "changed_fields": changed_fields,
        "aggregate": candidate_eval["aggregate"],
        "incumbent_aggregate": incumbent_eval["aggregate"],
        "metric_deltas": metric_deltas,
        "decision": decision,
        "case_types": candidate_eval["case_types"],
        "artifacts_dir": str(base_artifact_dir),
        "prompt_fragments": candidate_bundle["prompt_fragments"],
    }
    (base_artifact_dir / "run.json").write_text(json.dumps(record, indent=2, sort_keys=True))
    append_run_record(MEMORY_DIR, record)
    refresh_memory(MEMORY_DIR)

    summary = {
        "accepted": decision["accepted"],
        "reason": decision["reason"],
        "incumbent_score": round(decision["incumbent_score"], 3),
        "candidate_score": round(decision["candidate_score"], 3),
        "delta": round(decision["delta"], 3),
        "false_refusal_rate": round(candidate_eval["aggregate"]["false_refusal_rate"], 3),
        "unsupported_answer_rate": round(candidate_eval["aggregate"]["unsupported_answer_rate"], 3),
        "artifacts_dir": str(base_artifact_dir),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
