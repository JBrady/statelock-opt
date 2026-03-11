import json
import shutil
import time
from pathlib import Path

import yaml

from .assemble import assemble_context
from .constants import CONFIG_LIMITS, DATASET_PATH, INCUMBENT_DIR, MUTABLE_CONFIG_FILES, PROMPT_ENUMS, RETRIEVAL_ENUMS
from .dedupe import fingerprint_bundle
from .model_adapter import generate_response
from .prompt_render import render_prompt
from .retrieve_lexical import rank_records
from .scorer import aggregate_cases, score_case


def _load_yaml(path):
    return yaml.safe_load(path.read_text()) or {}


def load_bundle(bundle_dir):
    bundle_dir = Path(bundle_dir)
    return {
        "retrieval": _load_yaml(bundle_dir / "retrieval.yaml"),
        "memory_policy": _load_yaml(bundle_dir / "memory_policy.yaml"),
        "prompt_fragments": _load_yaml(bundle_dir / "prompt_fragments.yaml"),
    }


def write_bundle(bundle, bundle_dir):
    bundle_dir = Path(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    for key, filename in (
        ("retrieval", "retrieval.yaml"),
        ("memory_policy", "memory_policy.yaml"),
        ("prompt_fragments", "prompt_fragments.yaml"),
    ):
        (bundle_dir / filename).write_text(yaml.safe_dump(bundle[key], sort_keys=False))


def validate_bundle(bundle):
    if bundle["retrieval"].get("strategy") not in RETRIEVAL_ENUMS["strategy"]:
        raise ValueError("Only lexical retrieval is allowed in v1.")
    for section, limits in CONFIG_LIMITS.items():
        config = bundle[section]
        for field, (low, high) in limits.items():
            value = config[field]
            if value < low or value > high:
                raise ValueError(f"{section}.{field} out of range: {value}")
    for field, allowed in PROMPT_ENUMS.items():
        if bundle["prompt_fragments"][field] not in allowed:
            raise ValueError(f"Invalid prompt fragment value for {field}")
    if bundle["retrieval"]["top_k_final"] > bundle["retrieval"]["top_k_pre"]:
        raise ValueError("top_k_final must be <= top_k_pre")


def load_dataset(dataset_path=DATASET_PATH):
    rows = []
    for line in Path(dataset_path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def diff_bundle(incumbent, candidate):
    changes = {}
    for section in ("retrieval", "memory_policy", "prompt_fragments"):
        for key, incumbent_value in incumbent[section].items():
            candidate_value = candidate[section].get(key)
            if candidate_value != incumbent_value:
                changes[f"{section}.{key}"] = {"from": incumbent_value, "to": candidate_value}
    return changes


def evaluate_bundle(bundle_dir, run_id, artifact_dir):
    bundle = load_bundle(bundle_dir)
    validate_bundle(bundle)
    dataset = load_dataset()
    case_results = []
    case_types = set()

    for case in dataset:
        started = time.perf_counter()
        retrieved = rank_records(case["query"], case["memory_bank"], case["query_timestamp"], bundle["retrieval"])
        assembled = assemble_context(retrieved, case, bundle["retrieval"], bundle["memory_policy"], bundle["prompt_fragments"])
        prompt = render_prompt(case["query"], assembled, bundle["prompt_fragments"])
        response = generate_response(case, assembled, prompt)
        latency_ms = (time.perf_counter() - started) * 1000.0
        case["_latency_ms"] = latency_ms
        metrics, failure_tags = score_case(case, assembled, prompt, response)
        case_results.append(
            {
                "case": case,
                "assembled": {
                    "retrieved_ids": assembled["retrieved_ids"],
                    "selected_ids": assembled["selected_ids"],
                },
                "response": response,
                "metrics": metrics,
                "failure_tags": failure_tags,
            }
        )
        case_types.add(expected_type(case))

    aggregate = aggregate_cases(case_results)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "summary.json").write_text(json.dumps({"aggregate": aggregate}, indent=2, sort_keys=True))
    (artifact_dir / "cases.json").write_text(json.dumps(case_results, indent=2, sort_keys=True))
    return {
        "run_id": run_id,
        "bundle": bundle,
        "fingerprint": fingerprint_bundle(bundle),
        "aggregate": aggregate,
        "cases": case_results,
        "case_types": sorted(case_types),
    }


def expected_type(case):
    behavior = case["expected_behavior"]
    if behavior == "refuse":
        return "missing_evidence_refusal"
    if behavior == "answer_with_caution":
        return "partial_evidence"
    if any(record.get("contradicts_ids") for record in case["memory_bank"]):
        return "conflict_resolution"
    if case.get("distractor_ids"):
        return "distractor_retrieval"
    return "direct_recall"
