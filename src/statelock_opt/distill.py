import json
from collections import Counter, defaultdict
from pathlib import Path

from .constants import LARGE_WIN_DELTA, MAX_ACTIVE_LESSONS, MEMORY_DIR
from .signatures import change_signature


def _load_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _write_jsonl(path, rows):
    payload = "\n".join(json.dumps(row, sort_keys=True) for row in rows)
    path.write_text(payload + ("\n" if payload else ""))


def append_run_record(memory_dir, record):
    path = memory_dir / "runs.jsonl"
    existing = _load_jsonl(path)
    existing.append(record)
    _write_jsonl(path, existing)
    return existing


def _lesson_scope(grouped_runs):
    return {"case_types": sorted({tag for run in grouped_runs for tag in run.get("case_types", [])})}


def _positive_lesson(sample, grouped_runs, promotion_rule, lesson_index):
    improvements = [
        metric
        for metric, delta in sample["metric_deltas"].items()
        if delta > 0.03 and metric not in {"false_refusal_rate", "unsupported_answer_rate"}
    ]
    harms = [metric for metric, delta in sample["metric_deltas"].items() if delta < -0.03]
    return {
        "lesson_id": f"lesson_{lesson_index:03d}",
        "lesson_type": "positive",
        "status": "active",
        "scope": _lesson_scope(grouped_runs),
        "pattern": sample["changed_fields"],
        "observed_effect": {"improves": improvements, "hurts": harms},
        "evidence_runs": [run["run_id"] for run in grouped_runs],
        "confidence": round(min(0.55 + 0.1 * len(grouped_runs), 0.95), 2),
        "promotion_rule": promotion_rule,
    }


def _negative_lesson(sample, grouped_runs, lesson_index):
    return {
        "lesson_id": f"lesson_{lesson_index:03d}",
        "lesson_type": "negative",
        "status": "active",
        "scope": _lesson_scope(grouped_runs),
        "pattern": sample.get("changed_fields", {}),
        "observed_effect": {"reason": sample["decision"]["reason"]},
        "evidence_runs": [run["run_id"] for run in grouped_runs],
        "confidence": round(min(0.55 + 0.08 * len(grouped_runs), 0.9), 2),
        "promotion_rule": "repeated_rejected_pattern",
    }


def refresh_memory(memory_dir):
    runs = _load_jsonl(memory_dir / "runs.jsonl")
    accepted_runs = [run for run in runs if run["decision"]["accepted"]]
    rejected_runs = [run for run in runs if not run["decision"]["accepted"]]

    lessons = []
    success_groups = defaultdict(list)
    failure_groups = defaultdict(list)

    for run in runs:
        signature = change_signature(run.get("changed_fields", {}))
        if not signature:
            continue
        if run["decision"]["accepted"]:
            success_groups[signature].append(run)
        else:
            failure_groups[signature].append(run)

    for signature, grouped_runs in success_groups.items():
        if len(grouped_runs) >= 2 or any(run["decision"]["delta"] >= LARGE_WIN_DELTA for run in grouped_runs):
            sample = grouped_runs[-1]
            promotion_rule = "large_accepted_win" if any(
                run["decision"]["delta"] >= LARGE_WIN_DELTA for run in grouped_runs
            ) else "repeated_accepted_pattern"
            lessons.append(_positive_lesson(sample, grouped_runs, promotion_rule, len(lessons) + 1))

    for signature, grouped_runs in failure_groups.items():
        if signature and len(grouped_runs) >= 3:
            lessons.append(_negative_lesson(grouped_runs[-1], grouped_runs, len(lessons) + 1))

    lessons = lessons[:MAX_ACTIVE_LESSONS]
    _write_jsonl(memory_dir / "lessons.jsonl", lessons)

    bad_regions = {"blocked_regions": []}
    failures = {"patterns": []}
    known_slow = {"patterns": []}
    tradeoffs = {"tradeoffs": []}
    priors = {"favored_exact_values": {}, "favored_ranges": {}, "metric_priors": {}}

    for signature, grouped_runs in failure_groups.items():
        if len(grouped_runs) >= 3:
            bad_regions["blocked_regions"].append(
                {
                    "signature": signature,
                    "evidence_runs": [run["run_id"] for run in grouped_runs],
                    "reason": grouped_runs[-1]["decision"]["reason"],
                }
            )
        if any(run["aggregate"]["p95_latency_ms"] > 4500 for run in grouped_runs):
            known_slow["patterns"].append(
                {
                    "signature": signature,
                    "evidence_runs": [run["run_id"] for run in grouped_runs],
                }
            )

    field_successes = defaultdict(Counter)
    for run in accepted_runs:
        for field, change in run.get("changed_fields", {}).items():
            field_successes[field][str(change["to"])] += 1

    for field, counter in field_successes.items():
        value, count = counter.most_common(1)[0]
        if count >= 1:
            priors["favored_exact_values"][field] = value

    for run in runs:
        if run["metric_deltas"].get("false_refusal_rate", 0.0) > 0 and run["metric_deltas"].get("unsupported_answer_rate", 0.0) < 0:
            tradeoffs["tradeoffs"].append(
                {
                    "signature": change_signature(run.get("changed_fields", {})),
                    "description": "stricter refusal reduced unsupported answers but increased false refusals",
                    "run_id": run["run_id"],
                }
            )
        if run["metric_deltas"].get("latency_score", 0.0) < 0 and run["metric_deltas"].get("correctness", 0.0) > 0:
            tradeoffs["tradeoffs"].append(
                {
                    "signature": change_signature(run.get("changed_fields", {})),
                    "description": "broader retrieval improved correctness but hurt latency",
                    "run_id": run["run_id"],
                }
            )

    for run in rejected_runs:
        failures["patterns"].append(
            {
                "signature": change_signature(run.get("changed_fields", {})),
                "reason": run["decision"]["reason"],
                "run_id": run["run_id"],
            }
        )

    (memory_dir / "priors.yaml").write_text(_yaml_dump(priors))
    (memory_dir / "bad_regions.yaml").write_text(_yaml_dump(bad_regions))
    (memory_dir / "known_slow.yaml").write_text(_yaml_dump(known_slow))
    (memory_dir / "tradeoffs.yaml").write_text(_yaml_dump(tradeoffs))
    (memory_dir / "failures.yaml").write_text(_yaml_dump(failures))


def _yaml_dump(data):
    import yaml

    return yaml.safe_dump(data, sort_keys=True)
