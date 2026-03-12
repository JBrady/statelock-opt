import copy
import hashlib
import json
import shutil
import time
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from .assemble import assemble_context
from .constants import (
    ARTIFACT_FORMAT_VERSION,
    CONFIG_LIMITS,
    DATASET_PATH,
    EVAL_SCHEMA_PATH,
    INCUMBENT_DIR,
    MUTABLE_CONFIG_FILES,
    PROMPT_ENUMS,
    RETRIEVAL_ENUMS,
)
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


def _sha256_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def _parse_dataset_rows(raw_dataset):
    rows = []
    text = raw_dataset.decode("utf-8")
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Dataset JSON decode failed on line {line_number}: {exc.msg}") from exc
    return rows


def _validate_dataset_rows(rows, schema):
    validator = Draft202012Validator(schema)
    seen_case_ids = set()
    for index, row in enumerate(rows, start=1):
        errors = sorted(validator.iter_errors(row), key=lambda item: item.json_path)
        if errors:
            first = errors[0]
            raise ValueError(f"Dataset schema validation failed for row {index}: {first.message}")
        case_id = row["id"]
        if case_id in seen_case_ids:
            raise ValueError(f"Duplicate dataset case id: {case_id}")
        seen_case_ids.add(case_id)


def load_dataset_bundle(dataset_path=DATASET_PATH, schema_path=EVAL_SCHEMA_PATH):
    dataset_path = Path(dataset_path)
    schema_path = Path(schema_path)
    raw_dataset = dataset_path.read_bytes()
    raw_schema = schema_path.read_bytes()
    rows = _parse_dataset_rows(raw_dataset)
    schema = json.loads(raw_schema.decode("utf-8"))
    _validate_dataset_rows(rows, schema)
    case_ids = [row["id"] for row in rows]
    return {
        "rows": rows,
        "identity": {
            "dataset_path": str(dataset_path.resolve()),
            "dataset_sha256": _sha256_bytes(raw_dataset),
            "schema_path": str(schema_path.resolve()),
            "schema_sha256": _sha256_bytes(raw_schema),
            "case_count": len(rows),
            "case_ids": case_ids,
        },
    }


def load_dataset(dataset_path=DATASET_PATH, schema_path=EVAL_SCHEMA_PATH):
    return load_dataset_bundle(dataset_path=dataset_path, schema_path=schema_path)["rows"]


def diff_bundle(incumbent, candidate):
    changes = {}
    for section in ("retrieval", "memory_policy", "prompt_fragments"):
        for key, incumbent_value in incumbent[section].items():
            candidate_value = candidate[section].get(key)
            if candidate_value != incumbent_value:
                changes[f"{section}.{key}"] = {"from": incumbent_value, "to": candidate_value}
    return changes


def evaluate_bundle(bundle_dir, run_id, artifact_dir, dataset_bundle=None):
    bundle = load_bundle(bundle_dir)
    validate_bundle(bundle)
    prepared_dataset = dataset_bundle or load_dataset_bundle()
    dataset = copy.deepcopy(prepared_dataset["rows"])
    dataset_identity = copy.deepcopy(prepared_dataset["identity"])
    case_results = []
    case_types = set()
    bundle_identity = {
        "bundle_path": str(Path(bundle_dir)),
        "fingerprint": fingerprint_bundle(bundle),
    }

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
    summary_payload = {
        "aggregate": aggregate,
        "artifact_format_version": ARTIFACT_FORMAT_VERSION,
        "dataset_identity": dataset_identity,
        "bundle_identity": bundle_identity,
    }
    (artifact_dir / "summary.json").write_text(json.dumps(summary_payload, indent=2, sort_keys=True))
    (artifact_dir / "cases.json").write_text(json.dumps(case_results, indent=2, sort_keys=True))
    return {
        "run_id": run_id,
        "bundle": bundle,
        "fingerprint": bundle_identity["fingerprint"],
        "artifact_format_version": ARTIFACT_FORMAT_VERSION,
        "dataset_identity": dataset_identity,
        "bundle_identity": bundle_identity,
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
