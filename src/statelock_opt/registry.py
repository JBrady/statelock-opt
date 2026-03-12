import json
from collections import defaultdict
from pathlib import Path

from .constants import REGISTRY_FORMAT_VERSION, ROOT
from .signatures import change_signature


LESSON_ATTRIBUTION_UNAVAILABLE = "lesson_attribution_unavailable"
UNLABELED_BUCKET = "unlabeled"

# Historical checked-in run ids already use more than one shape, so parsed
# timestamp fields are intentionally deferred in v1.
RUN_ID_TIMESTAMP_DERIVATION_ENABLED = False


def load_jsonl_rows(path):
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def append_registry_record(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_jsonl_rows(path)
    if any(row.get("run_id") == record["run_id"] for row in existing):
        return False
    with path.open("a") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return True


def build_registry_record(
    run_record,
    incumbent_eval,
    candidate_eval,
    pre_lessons,
    post_lessons,
    repo_root=ROOT,
    lesson_attribution_failed=False,
):
    repo_root = Path(repo_root)
    registry_warnings = []
    if lesson_attribution_failed:
        promoted_lessons = []
        registry_warnings.append(LESSON_ATTRIBUTION_UNAVAILABLE)
    else:
        try:
            promoted_lessons = _derive_promoted_lessons(pre_lessons, post_lessons, run_record["run_id"])
        except Exception:
            promoted_lessons = []
            registry_warnings.append(LESSON_ATTRIBUTION_UNAVAILABLE)

    case_delta_summary, case_family_summary, proof_role_summary = _derive_case_summaries(
        incumbent_eval["cases"],
        candidate_eval["cases"],
    )
    return {
        "registry_format_version": REGISTRY_FORMAT_VERSION,
        "run_id": run_record["run_id"],
        "run_timestamp_utc": _derive_run_timestamp_utc(run_record["run_id"]),
        "artifact_format_version": run_record["artifact_format_version"],
        "artifact_paths": _artifact_paths(run_record["artifacts_dir"], run_record["run_id"], incumbent_eval, candidate_eval, repo_root),
        "candidate_path": run_record["candidate_path"],
        "dataset_identity": run_record["dataset_identity"],
        "incumbent_bundle_identity": run_record["incumbent_bundle_identity"],
        "candidate_bundle_identity": run_record["candidate_bundle_identity"],
        "changed_fields": run_record["changed_fields"],
        "change_signature": change_signature(run_record.get("changed_fields", {})),
        "aggregate": run_record["aggregate"],
        "incumbent_aggregate": run_record["incumbent_aggregate"],
        "metric_deltas": run_record["metric_deltas"],
        "decision": run_record["decision"],
        "case_types": run_record["case_types"],
        "case_delta_summary": case_delta_summary,
        "case_family_summary": case_family_summary,
        "proof_role_summary": proof_role_summary,
        "promoted_lessons": promoted_lessons,
        "registry_warnings": registry_warnings,
    }


def _derive_run_timestamp_utc(run_id):
    if not RUN_ID_TIMESTAMP_DERIVATION_ENABLED:
        return None
    return None


def _artifact_paths(artifacts_dir, run_id, incumbent_eval, candidate_eval, repo_root):
    base_dir = Path(artifacts_dir)
    return {
        "run_json": _repo_local_path(base_dir / "run.json", repo_root),
        "incumbent_summary": _repo_local_path(base_dir / _eval_suffix(run_id, incumbent_eval["run_id"]) / "summary.json", repo_root),
        "candidate_summary": _repo_local_path(base_dir / _eval_suffix(run_id, candidate_eval["run_id"]) / "summary.json", repo_root),
        "incumbent_cases": _repo_local_path(base_dir / _eval_suffix(run_id, incumbent_eval["run_id"]) / "cases.json", repo_root),
        "candidate_cases": _repo_local_path(base_dir / _eval_suffix(run_id, candidate_eval["run_id"]) / "cases.json", repo_root),
    }


def _repo_local_path(path, repo_root):
    try:
        return str(Path(path).resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(Path(path))


def _eval_suffix(run_id, eval_run_id):
    prefix = f"{run_id}_"
    if not eval_run_id.startswith(prefix):
        raise ValueError(f"Unexpected eval run id {eval_run_id} for run {run_id}")
    return eval_run_id[len(prefix) :]


def _derive_case_summaries(incumbent_cases, candidate_cases):
    if len(incumbent_cases) != len(candidate_cases):
        raise ValueError("Case count mismatch during registry derivation.")
    case_delta_summary = {"improved_count": 0, "regressed_count": 0, "unchanged_count": 0}
    family_summary = defaultdict(lambda: _empty_bucket())
    proof_role_summary = defaultdict(lambda: _empty_bucket())

    for incumbent_case, candidate_case in zip(incumbent_cases, candidate_cases):
        incumbent_id = incumbent_case["case"]["id"]
        candidate_id = candidate_case["case"]["id"]
        if incumbent_id != candidate_id:
            raise ValueError(f"Case mismatch during registry derivation: {incumbent_id} != {candidate_id}")

        delta = round(candidate_case["metrics"]["total_score"] - incumbent_case["metrics"]["total_score"], 6)
        classification = _delta_classification(delta)
        metadata = candidate_case["case"].get("case_metadata") or {}
        case_family = metadata.get("case_family") or UNLABELED_BUCKET
        proof_role = metadata.get("proof_role") or UNLABELED_BUCKET

        _apply_delta(case_delta_summary, classification)
        _apply_bucket_delta(family_summary[case_family], classification, delta)
        _apply_bucket_delta(proof_role_summary[proof_role], classification, delta)

    return (
        case_delta_summary,
        _finalize_bucket_summary(family_summary),
        _finalize_bucket_summary(proof_role_summary),
    )


def _empty_bucket():
    return {
        "case_count": 0,
        "improved_count": 0,
        "regressed_count": 0,
        "unchanged_count": 0,
        "net_score_delta": 0.0,
    }


def _delta_classification(delta):
    if delta > 0:
        return "improved_count"
    if delta < 0:
        return "regressed_count"
    return "unchanged_count"


def _apply_delta(summary, classification):
    summary[classification] += 1


def _apply_bucket_delta(bucket, classification, delta):
    bucket["case_count"] += 1
    bucket[classification] += 1
    bucket["net_score_delta"] = round(bucket["net_score_delta"] + delta, 6)


def _finalize_bucket_summary(summary):
    return {key: value for key, value in sorted(summary.items())}


def _derive_promoted_lessons(pre_lessons, post_lessons, run_id):
    pre_keys = {_lesson_identity_key(lesson) for lesson in pre_lessons}
    promoted = []
    for lesson in post_lessons:
        lesson_key = _lesson_identity_key(lesson)
        if lesson_key in pre_keys:
            continue
        if run_id not in lesson.get("evidence_runs", []):
            continue
        promoted.append(
            {
                "lesson_type": lesson["lesson_type"],
                "promotion_rule": lesson["promotion_rule"],
                "pattern_signature": change_signature(lesson.get("pattern", {})),
                "scope_case_types": sorted(lesson.get("scope", {}).get("case_types", [])),
            }
        )
    return promoted


def _lesson_identity_key(lesson):
    stable_identity = {
        "lesson_type": lesson["lesson_type"],
        "promotion_rule": lesson["promotion_rule"],
        "pattern": lesson.get("pattern", {}),
        "scope": lesson.get("scope", {}),
    }
    return json.dumps(stable_identity, sort_keys=True)
