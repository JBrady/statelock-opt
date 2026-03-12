import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

from statelock_opt import run as run_module
from statelock_opt.registry import append_registry_record, build_registry_record, load_jsonl_rows


ROOT = Path(__file__).resolve().parents[1]
INCUMBENT_DIR = ROOT / "state" / "incumbent"
NOOP_CANDIDATE_DIR = ROOT / "state" / "candidates" / "generated_0001"


def _case_result(case_id, score, case_family=None, proof_role=None):
    case = {"id": case_id}
    case_metadata = {}
    if case_family is not None:
        case_metadata["case_family"] = case_family
    if proof_role is not None:
        case_metadata["proof_role"] = proof_role
    if case_metadata:
        case["case_metadata"] = case_metadata
    return {"case": case, "metrics": {"total_score": score}}


class ExperimentRegistryTests(unittest.TestCase):
    def test_build_registry_record_derives_expected_summaries(self):
        run_id = "20260312T111111111111Z_deadbeef"
        run_record = {
            "artifact_format_version": 2,
            "run_id": run_id,
            "candidate_path": "state/candidates/proof_top_k_final_4",
            "dataset_identity": {"dataset_sha256": "abc", "schema_sha256": "def", "case_count": 3, "case_ids": ["case_001"]},
            "incumbent_bundle_identity": {"fingerprint": "inc", "bundle_path": "state/incumbent"},
            "candidate_bundle_identity": {"fingerprint": "cand", "bundle_path": "state/candidates/proof_top_k_final_4"},
            "changed_fields": {"retrieval.top_k_final": {"from": 3, "to": 4}},
            "aggregate": {"total_score": 96.9},
            "incumbent_aggregate": {"total_score": 93.7},
            "metric_deltas": {"correctness": 0.1},
            "decision": {"accepted": True, "reason": "accepted", "delta": 3.2},
            "case_types": ["partial_evidence"],
            "artifacts_dir": str(ROOT / "artifacts" / "runs" / run_id),
        }
        incumbent_eval = {
            "run_id": f"{run_id}_incumbent_1",
            "cases": [
                _case_result("case_001", 80.0, case_family="partial_evidence", proof_role="wedge"),
                _case_result("case_002", 90.0, case_family="distractor_retrieval", proof_role="guardrail"),
                _case_result("case_003", 88.0),
            ],
        }
        candidate_eval = {
            "run_id": f"{run_id}_candidate_1",
            "cases": [
                _case_result("case_001", 95.0, case_family="partial_evidence", proof_role="wedge"),
                _case_result("case_002", 85.0, case_family="distractor_retrieval", proof_role="guardrail"),
                _case_result("case_003", 88.0),
            ],
        }
        post_lessons = [
            {
                "lesson_type": "positive",
                "promotion_rule": "large_accepted_win",
                "pattern": {"retrieval.top_k_final": {"from": 3, "to": 4}},
                "scope": {"case_types": ["partial_evidence"]},
                "evidence_runs": [run_id],
            }
        ]

        record = build_registry_record(run_record, incumbent_eval, candidate_eval, [], post_lessons)

        self.assertEqual(record["registry_format_version"], 1)
        self.assertIsNone(record["run_timestamp_utc"])
        self.assertEqual(record["change_signature"], "retrieval.top_k_final:3->4")
        self.assertEqual(
            record["artifact_paths"]["run_json"],
            f"artifacts/runs/{run_id}/run.json",
        )
        self.assertEqual(record["case_delta_summary"], {"improved_count": 1, "regressed_count": 1, "unchanged_count": 1})
        self.assertEqual(record["case_family_summary"]["partial_evidence"]["improved_count"], 1)
        self.assertEqual(record["case_family_summary"]["partial_evidence"]["net_score_delta"], 15.0)
        self.assertEqual(record["proof_role_summary"]["guardrail"]["regressed_count"], 1)
        self.assertEqual(record["proof_role_summary"]["unlabeled"]["unchanged_count"], 1)
        self.assertEqual(
            record["promoted_lessons"],
            [
                {
                    "lesson_type": "positive",
                    "promotion_rule": "large_accepted_win",
                    "pattern_signature": "retrieval.top_k_final:3->4",
                    "scope_case_types": ["partial_evidence"],
                }
            ],
        )
        self.assertEqual(record["registry_warnings"], [])

    def test_build_registry_record_degrades_gracefully_when_lesson_attribution_fails(self):
        run_id = "20260312T111111111111Z_deadbeef"
        run_record = {
            "artifact_format_version": 2,
            "run_id": run_id,
            "candidate_path": "state/candidates/generated_0001",
            "dataset_identity": {"dataset_sha256": "abc", "schema_sha256": "def", "case_count": 1, "case_ids": ["case_001"]},
            "incumbent_bundle_identity": {"fingerprint": "inc", "bundle_path": "state/incumbent"},
            "candidate_bundle_identity": {"fingerprint": "cand", "bundle_path": "state/candidates/generated_0001"},
            "changed_fields": {},
            "aggregate": {"total_score": 10.0},
            "incumbent_aggregate": {"total_score": 10.0},
            "metric_deltas": {"correctness": 0.0},
            "decision": {"accepted": False, "reason": "score delta below minimum acceptance threshold", "delta": 0.0},
            "case_types": ["direct_recall"],
            "artifacts_dir": str(ROOT / "artifacts" / "runs" / run_id),
        }
        incumbent_eval = {"run_id": f"{run_id}_incumbent_1", "cases": [_case_result("case_001", 10.0, case_family="direct_recall")]}
        candidate_eval = {"run_id": f"{run_id}_candidate_1", "cases": [_case_result("case_001", 10.0, case_family="direct_recall")]}
        malformed_post_lessons = [
            {
                "lesson_type": "positive",
                "promotion_rule": "large_accepted_win",
                "pattern": "not-a-change-map",
                "scope": {"case_types": ["direct_recall"]},
                "evidence_runs": [run_id],
            }
        ]

        record = build_registry_record(run_record, incumbent_eval, candidate_eval, [], malformed_post_lessons)

        self.assertEqual(record["promoted_lessons"], [])
        self.assertEqual(record["registry_warnings"], ["lesson_attribution_unavailable"])

    def test_append_registry_record_is_idempotent_on_run_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "artifacts" / "registry" / "experiments.jsonl"
            record = {"run_id": "run_001", "registry_format_version": 1}

            self.assertTrue(append_registry_record(registry_path, record))
            self.assertFalse(append_registry_record(registry_path, record))
            rows = load_jsonl_rows(registry_path)

        self.assertEqual(rows, [record])

    def test_registry_presence_does_not_change_run_acceptance_or_memory_outputs(self):
        without_registry = self._run_with_temp_state(precreate_registry=False)
        with_registry = self._run_with_temp_state(precreate_registry=True)

        for key in ("accepted", "reason", "incumbent_score", "candidate_score", "delta"):
            self.assertEqual(without_registry["summary"][key], with_registry["summary"][key])
        self.assertEqual(
            self._normalized_memory_outputs(without_registry["memory_files"]),
            self._normalized_memory_outputs(with_registry["memory_files"]),
        )
        self.assertEqual(len(without_registry["registry_rows"]), 1)
        self.assertEqual(len(with_registry["registry_rows"]), 2)

    def _run_with_temp_state(self, precreate_registry):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            artifacts_runs_dir = tmp_path / "artifacts" / "runs"
            memory_dir = tmp_path / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)
            registry_path = artifacts_runs_dir.parent / "registry" / "experiments.jsonl"
            if precreate_registry:
                registry_path.parent.mkdir(parents=True, exist_ok=True)
                registry_path.write_text(json.dumps({"run_id": "existing_run", "registry_format_version": 1}) + "\n")

            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()
            argv = [
                "statelock_opt.run",
                "--candidate",
                str(NOOP_CANDIDATE_DIR),
                "--incumbent",
                str(INCUMBENT_DIR),
            ]
            with patch.object(run_module, "ARTIFACTS_DIR", artifacts_runs_dir), patch.object(run_module, "MEMORY_DIR", memory_dir):
                with patch.object(sys, "argv", argv), redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                    run_module.main()

            memory_files = {}
            for filename in (
                "runs.jsonl",
                "lessons.jsonl",
                "priors.yaml",
                "bad_regions.yaml",
                "known_slow.yaml",
                "tradeoffs.yaml",
                "failures.yaml",
            ):
                path = memory_dir / filename
                memory_files[filename] = path.read_text() if path.exists() else ""

            return {
                "summary": json.loads(stdout_buffer.getvalue()),
                "registry_rows": load_jsonl_rows(registry_path),
                "memory_files": memory_files,
                "stderr": stderr_buffer.getvalue(),
            }

    def _normalized_memory_outputs(self, memory_files):
        normalized = {}
        for filename, contents in memory_files.items():
            if filename == "runs.jsonl":
                continue
            if filename == "lessons.jsonl":
                normalized[filename] = contents
                continue
            loaded = yaml.safe_load(contents) if contents else {}
            normalized[filename] = self._strip_runtime_ids(loaded)
        return normalized

    def _strip_runtime_ids(self, value):
        if isinstance(value, dict):
            return {
                key: self._strip_runtime_ids(item)
                for key, item in value.items()
                if key not in {"run_id", "evidence_runs"}
            }
        if isinstance(value, list):
            return [self._strip_runtime_ids(item) for item in value]
        return value


if __name__ == "__main__":
    unittest.main()
