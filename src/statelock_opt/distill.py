import json
from collections import Counter, defaultdict
from pathlib import Path

from .constants import LARGE_WIN_DELTA, MAX_ACTIVE_LESSONS, MEMORY_DIR


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


def _change_signature(changed_fields):
    parts = []
    for key in sorted(changed_fields):
        change = changed_fields[key]
        parts.append(f"{key}:{change['from']}->{change['to']}")
    return "|".join(parts)


def refresh_memory(memory_dir):
    runs = _load_jsonl(memory_dir / "runs.jsonl")
    accepted_runs = [run for run in runs if run["decision"]["accepted"]]
    rejected_runs = [run for run in runs if not run["decision"]["accepted"]]

    lessons = []
    success_groups = defaultdict(list)
    failure_groups = defaultdict(list)

    for run in runs:
        signature = _change_signature(run.get("changed_fields", {}))
        if not signature:
            continue
        if run["decision"]["accepted"]:
            success_groups[signature].append(run)
        else:
            failure_groups[signature].append(run)

    for signature, grouped_runs in success_groups.items():
        if len(grouped_runs) >= 2 or any(run["decision"]["delta"] >= LARGE_WIN_DELTA for run in grouped_runs):
            sample = grouped_runs[-1]
            improvements = [
                metric
                for metric, delta in sample["metric_deltas"].items()
                if delta > 0.03 and metric not in {"false_refusal_rate", "unsupported_answer_rate"}
            ]
            harms = [metric for metric, delta in sample["metric_deltas"].items() if delta < -0.03]
            lessons.append(
                {
                    "lesson_id": f"lesson_{len(lessons) + 1:03d}",
                    "scope": {"case_types": sorted({tag for run in grouped_runs for tag in run.get("case_types", [])})},
                    "pattern": sample["changed_fields"],
                    "observed_effect": {"improves": improvements, "hurts": harms},
                    "evidence_runs": [run["run_id"] for run in grouped_runs],
                    "confidence": round(min(0.55 + 0.1 * len(grouped_runs), 0.95), 2),
                    "status": "active",
                }
            )

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
                    "signature": _change_signature(run.get("changed_fields", {})),
                    "description": "stricter refusal reduced unsupported answers but increased false refusals",
                    "run_id": run["run_id"],
                }
            )
        if run["metric_deltas"].get("latency_score", 0.0) < 0 and run["metric_deltas"].get("correctness", 0.0) > 0:
            tradeoffs["tradeoffs"].append(
                {
                    "signature": _change_signature(run.get("changed_fields", {})),
                    "description": "broader retrieval improved correctness but hurt latency",
                    "run_id": run["run_id"],
                }
            )

    for run in rejected_runs:
        failures["patterns"].append(
            {
                "signature": _change_signature(run.get("changed_fields", {})),
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
