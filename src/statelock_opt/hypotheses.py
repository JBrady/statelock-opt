import hashlib
import json
from collections import defaultdict
from pathlib import Path
from statistics import median
from tempfile import NamedTemporaryFile

from .constants import HYPOTHESIS_FORMAT_VERSION, HYPOTHESIS_RUN_REF_LIMIT
from .registry import load_jsonl_rows


MIXED_EVIDENCE_WARNING = "mixed_evidence"
INCONCLUSIVE_ONLY_WARNING = "inconclusive_only"
REGISTRY_ROW_WARNING_PRESENT = "registry_row_warning_present"
CLAIM_TYPE = "change_effect"


def refresh_hypotheses(registry_path, hypotheses_path):
    registry_path = Path(registry_path)
    hypotheses_path = Path(hypotheses_path)

    rows = load_jsonl_rows(registry_path)
    if not rows:
        _write_jsonl_atomic(hypotheses_path, [])
        return []

    grouped = defaultdict(list)
    for row in rows:
        _validate_registry_row(row)
        signature = row["change_signature"]
        if not signature:
            continue
        grouped[signature].append(row)

    hypotheses = [
        _build_hypothesis(signature, grouped_rows)
        for signature, grouped_rows in sorted(grouped.items())
    ]
    _write_jsonl_atomic(hypotheses_path, hypotheses)
    return hypotheses


def _write_jsonl_atomic(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        if rows:
            handle.write("\n".join(json.dumps(row, sort_keys=True) for row in rows))
            handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _validate_registry_row(row):
    required = (
        "change_signature",
        "changed_fields",
        "decision",
        "metric_deltas",
        "aggregate",
        "incumbent_aggregate",
        "case_family_summary",
        "proof_role_summary",
        "promoted_lessons",
        "registry_warnings",
        "run_id",
    )
    for key in required:
        if key not in row:
            raise ValueError(f"Registry row missing required field: {key}")


def _build_hypothesis(signature, rows):
    rows = sorted(rows, key=lambda row: row["run_id"])
    target_changes = rows[0]["changed_fields"]
    for row in rows[1:]:
        if row["changed_fields"] != target_changes:
            raise ValueError(f"Inconsistent changed_fields for signature: {signature}")

    supporting_rows = [row for row in rows if row["decision"]["accepted"]]
    opposing_rows = [row for row in rows if not row["decision"]["accepted"] and row["decision"]["delta"] < 0]
    inconclusive_rows = [row for row in rows if not row["decision"]["accepted"] and row["decision"]["delta"] >= 0]

    status = _status_for_group(supporting_rows, opposing_rows, inconclusive_rows)
    confidence = _confidence_for_group(status, len(rows))
    case_family_evidence = _aggregate_bucket_evidence(rows, "case_family_summary")
    proof_role_evidence = _aggregate_bucket_evidence(rows, "proof_role_summary")
    warnings = _derive_warnings(rows, status)

    return {
        "hypothesis_format_version": HYPOTHESIS_FORMAT_VERSION,
        "hypothesis_id": _hypothesis_id(signature),
        "status": status,
        "confidence": confidence,
        "claim_type": CLAIM_TYPE,
        "claim_text": _claim_text(signature, status),
        "change_signature": signature,
        "target_changes": target_changes,
        "evidence_counts": _evidence_counts(rows, supporting_rows, opposing_rows, inconclusive_rows),
        "evidence_run_refs": {
            "supporting_run_ids": _bounded_run_ids(supporting_rows),
            "opposing_run_ids": _bounded_run_ids(opposing_rows),
            "inconclusive_run_ids": _bounded_run_ids(inconclusive_rows),
        },
        "target_case_families": _target_buckets(case_family_evidence),
        "target_proof_roles": _target_buckets(proof_role_evidence),
        "case_family_evidence": case_family_evidence,
        "proof_role_evidence": proof_role_evidence,
        "evidence_summary": _evidence_summary(rows, supporting_rows, opposing_rows, inconclusive_rows),
        "promoted_lesson_signals": _promoted_lesson_signals(rows),
        "suggested_next_moves": _suggested_next_moves(status, confidence),
        "warnings": warnings,
    }


def _status_for_group(supporting_rows, opposing_rows, inconclusive_rows):
    if supporting_rows and not opposing_rows and not inconclusive_rows:
        return "supported"
    if supporting_rows and (opposing_rows or inconclusive_rows):
        return "mixed"
    if not supporting_rows and opposing_rows:
        return "contradicted"
    return "inconclusive"


def _confidence_for_group(status, total_runs):
    if status != "mixed" and total_runs >= 3:
        return "high"
    if status != "mixed" and total_runs >= 2:
        return "medium"
    return "low"


def _hypothesis_id(signature):
    return f"hypothesis_{hashlib.sha256(signature.encode('utf-8')).hexdigest()[:12]}"


def _claim_text(signature, status):
    templates = {
        "supported": f"Evidence currently supports the effect of `{signature}`.",
        "mixed": f"Evidence for `{signature}` is currently mixed.",
        "contradicted": f"Evidence currently contradicts the effect of `{signature}`.",
        "inconclusive": f"Evidence for `{signature}` is currently inconclusive.",
    }
    return templates[status]


def _evidence_counts(rows, supporting_rows, opposing_rows, inconclusive_rows):
    return {
        "total_runs": len(rows),
        "supporting_runs": len(supporting_rows),
        "opposing_runs": len(opposing_rows),
        "inconclusive_runs": len(inconclusive_rows),
        "accepted_runs": sum(1 for row in rows if row["decision"]["accepted"]),
        "rejected_runs": sum(1 for row in rows if not row["decision"]["accepted"]),
    }


def _bounded_run_ids(rows):
    return [row["run_id"] for row in sorted(rows, key=lambda row: row["run_id"])[:HYPOTHESIS_RUN_REF_LIMIT]]


def _aggregate_bucket_evidence(rows, field_name):
    aggregated = defaultdict(lambda: {"run_count": 0, "improved_count": 0, "regressed_count": 0, "unchanged_count": 0, "net_score_delta": 0.0})
    for row in rows:
        for bucket, bucket_summary in row[field_name].items():
            target = aggregated[bucket]
            target["run_count"] += 1
            target["improved_count"] += bucket_summary["improved_count"]
            target["regressed_count"] += bucket_summary["regressed_count"]
            target["unchanged_count"] += bucket_summary["unchanged_count"]
            target["net_score_delta"] = round(target["net_score_delta"] + bucket_summary["net_score_delta"], 6)
    return {bucket: value for bucket, value in sorted(aggregated.items())}


def _target_buckets(bucket_evidence):
    return [bucket for bucket, summary in bucket_evidence.items() if summary["net_score_delta"] != 0]


def _evidence_summary(rows, supporting_rows, opposing_rows, inconclusive_rows):
    deltas = [row["decision"]["delta"] for row in rows]
    return {
        "total_runs": len(rows),
        "accepted_runs": sum(1 for row in rows if row["decision"]["accepted"]),
        "rejected_runs": sum(1 for row in rows if not row["decision"]["accepted"]),
        "supporting_runs": len(supporting_rows),
        "opposing_runs": len(opposing_rows),
        "inconclusive_runs": len(inconclusive_rows),
        "median_delta": median(deltas),
        "best_delta": max(deltas),
        "worst_delta": min(deltas),
        "registry_warning_count": sum(len(row.get("registry_warnings", [])) for row in rows),
    }


def _promoted_lesson_signals(rows):
    promotion_rules = set()
    lesson_types = set()
    count = 0
    for row in rows:
        for lesson in row.get("promoted_lessons", []):
            count += 1
            promotion_rules.add(lesson["promotion_rule"])
            lesson_types.add(lesson["lesson_type"])
    return {
        "promotion_rules": sorted(promotion_rules),
        "lesson_types": sorted(lesson_types),
        "count": count,
    }


def _suggested_next_moves(status, confidence):
    if status == "supported" and confidence in {"low", "medium"}:
        return ["replicate"]
    if status == "mixed":
        return ["disambiguate"]
    if status == "contradicted":
        return ["deprioritize"]
    return ["collect_more_evidence"]


def _derive_warnings(rows, status):
    warnings = []
    if any(row.get("registry_warnings") for row in rows):
        warnings.append(REGISTRY_ROW_WARNING_PRESENT)
    if status == "mixed":
        warnings.append(MIXED_EVIDENCE_WARNING)
    if status == "inconclusive":
        warnings.append(INCONCLUSIVE_ONLY_WARNING)
    return warnings
