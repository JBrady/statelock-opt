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
from statelock_opt.hypotheses import refresh_hypotheses
from statelock_opt.registry import load_jsonl_rows


ROOT = Path(__file__).resolve().parents[1]
INCUMBENT_DIR = ROOT / "state" / "incumbent"
NOOP_CANDIDATE_DIR = ROOT / "state" / "candidates" / "generated_0001"


def _registry_row(
    run_id,
    signature,
    changed_fields,
    *,
    accepted,
    delta,
    case_family_summary=None,
    proof_role_summary=None,
    promoted_lessons=None,
    registry_warnings=None,
):
    return {
        "registry_format_version": 1,
        "run_id": run_id,
        "artifact_format_version": 2,
        "candidate_path": "state/candidates/generated_0001",
        "dataset_identity": {"dataset_sha256": "abc", "schema_sha256": "def"},
        "incumbent_bundle_identity": {"fingerprint": "inc", "bundle_path": "state/incumbent"},
        "candidate_bundle_identity": {"fingerprint": "cand", "bundle_path": "state/candidates/generated_0001"},
        "changed_fields": changed_fields,
        "change_signature": signature,
        "aggregate": {"total_score": 90.0 + delta},
        "incumbent_aggregate": {"total_score": 90.0},
        "metric_deltas": {"correctness": delta},
        "decision": {"accepted": accepted, "reason": "accepted" if accepted else "rejected", "delta": delta},
        "case_types": ["partial_evidence"],
        "case_delta_summary": {"improved_count": 1, "regressed_count": 0, "unchanged_count": 0},
        "case_family_summary": case_family_summary
        or {
            "partial_evidence": {
                "case_count": 1,
                "improved_count": 1 if delta > 0 else 0,
                "regressed_count": 1 if delta < 0 else 0,
                "unchanged_count": 1 if delta == 0 else 0,
                "net_score_delta": delta,
            }
        },
        "proof_role_summary": proof_role_summary
        or {
            "wedge": {
                "case_count": 1,
                "improved_count": 1 if delta > 0 else 0,
                "regressed_count": 1 if delta < 0 else 0,
                "unchanged_count": 1 if delta == 0 else 0,
                "net_score_delta": delta,
            }
        },
        "promoted_lessons": promoted_lessons or [],
        "registry_warnings": registry_warnings or [],
    }


class HypothesisTests(unittest.TestCase):
    def test_missing_registry_writes_empty_hypotheses(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            hypotheses_path = tmp_path / "artifacts" / "analysis" / "hypotheses.jsonl"

            hypotheses = refresh_hypotheses(tmp_path / "artifacts" / "registry" / "experiments.jsonl", hypotheses_path)

            self.assertEqual(hypotheses, [])
            self.assertEqual(hypotheses_path.read_text(), "")

    def test_supported_hypothesis_from_single_accepted_run(self):
        rows = [
            _registry_row(
                "run_002",
                "retrieval.top_k_final:3->4",
                {"retrieval.top_k_final": {"from": 3, "to": 4}},
                accepted=True,
                delta=3.2,
                promoted_lessons=[
                    {
                        "lesson_type": "positive",
                        "promotion_rule": "large_accepted_win",
                        "pattern_signature": "retrieval.top_k_final:3->4",
                        "scope_case_types": ["partial_evidence"],
                    }
                ],
            )
        ]
        hypotheses = self._refresh_from_rows(rows)

        self.assertEqual(len(hypotheses), 1)
        hypothesis = hypotheses[0]
        self.assertEqual(hypothesis["status"], "supported")
        self.assertEqual(hypothesis["confidence"], "low")
        self.assertEqual(hypothesis["evidence_counts"]["supporting_runs"], 1)
        self.assertEqual(hypothesis["promoted_lesson_signals"]["count"], 1)
        self.assertEqual(hypothesis["suggested_next_moves"], ["replicate"])

    def test_mixed_hypothesis_from_conflicting_runs(self):
        signature = "retrieval.top_k_final:3->4"
        changed_fields = {"retrieval.top_k_final": {"from": 3, "to": 4}}
        hypotheses = self._refresh_from_rows(
            [
                _registry_row("run_001", signature, changed_fields, accepted=True, delta=2.5),
                _registry_row("run_002", signature, changed_fields, accepted=False, delta=-1.0),
            ]
        )

        hypothesis = hypotheses[0]
        self.assertEqual(hypothesis["status"], "mixed")
        self.assertEqual(hypothesis["confidence"], "low")
        self.assertEqual(hypothesis["warnings"], ["mixed_evidence"])
        self.assertEqual(hypothesis["suggested_next_moves"], ["disambiguate"])

    def test_contradicted_hypothesis_from_negative_rejection(self):
        hypotheses = self._refresh_from_rows(
            [
                _registry_row(
                    "run_001",
                    "memory_policy.max_items_per_type:3->2",
                    {"memory_policy.max_items_per_type": {"from": 3, "to": 2}},
                    accepted=False,
                    delta=-2.4,
                )
            ]
        )

        hypothesis = hypotheses[0]
        self.assertEqual(hypothesis["status"], "contradicted")
        self.assertEqual(hypothesis["suggested_next_moves"], ["deprioritize"])

    def test_inconclusive_hypothesis_from_nonnegative_rejection(self):
        hypotheses = self._refresh_from_rows(
            [
                _registry_row(
                    "run_001",
                    "retrieval.top_k_pre:8->8",
                    {"retrieval.top_k_pre": {"from": 8, "to": 8}},
                    accepted=False,
                    delta=0.0,
                )
            ]
        )

        hypothesis = hypotheses[0]
        self.assertEqual(hypothesis["status"], "inconclusive")
        self.assertEqual(hypothesis["warnings"], ["inconclusive_only"])
        self.assertEqual(hypothesis["suggested_next_moves"], ["collect_more_evidence"])

    def test_evidence_counts_and_refs_are_bounded_deterministically(self):
        signature = "retrieval.top_k_final:3->4"
        changed_fields = {"retrieval.top_k_final": {"from": 3, "to": 4}}
        rows = [
            _registry_row(f"run_{index:03d}", signature, changed_fields, accepted=True, delta=1.0 + index)
            for index in range(5)
        ]
        hypotheses = self._refresh_from_rows(rows)

        hypothesis = hypotheses[0]
        self.assertEqual(hypothesis["evidence_counts"]["total_runs"], 5)
        self.assertEqual(hypothesis["evidence_counts"]["supporting_runs"], 5)
        self.assertEqual(hypothesis["evidence_run_refs"]["supporting_run_ids"], ["run_000", "run_001", "run_002"])

    def test_inconsistent_changed_fields_leave_previous_hypotheses_unchanged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            registry_path = tmp_path / "artifacts" / "registry" / "experiments.jsonl"
            hypotheses_path = tmp_path / "artifacts" / "analysis" / "hypotheses.jsonl"
            hypotheses_path.parent.mkdir(parents=True, exist_ok=True)
            hypotheses_path.write_text(json.dumps({"hypothesis_id": "existing"}) + "\n")
            rows = [
                _registry_row("run_001", "retrieval.top_k_final:3->4", {"retrieval.top_k_final": {"from": 3, "to": 4}}, accepted=True, delta=1.0),
                _registry_row("run_002", "retrieval.top_k_final:3->4", {"retrieval.top_k_final": {"from": 3, "to": 5}}, accepted=True, delta=1.0),
            ]
            registry_path.parent.mkdir(parents=True, exist_ok=True)
            registry_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")

            with self.assertRaisesRegex(ValueError, "Inconsistent changed_fields"):
                refresh_hypotheses(registry_path, hypotheses_path)

            self.assertEqual(hypotheses_path.read_text(), json.dumps({"hypothesis_id": "existing"}) + "\n")

    def test_hypothesis_refresh_failure_is_non_semantic_to_run(self):
        baseline = self._run_with_temp_state(refresh_failure=False)
        failure = self._run_with_temp_state(refresh_failure=True)

        for key in ("accepted", "reason", "incumbent_score", "candidate_score", "delta"):
            self.assertEqual(baseline["summary"][key], failure["summary"][key])
        self.assertEqual(
            self._normalized_registry_rows(baseline["registry_rows"]),
            self._normalized_registry_rows(failure["registry_rows"]),
        )
        self.assertEqual(
            self._normalized_memory_outputs(baseline["memory_files"]),
            self._normalized_memory_outputs(failure["memory_files"]),
        )
        self.assertIn("Hypothesis refresh failed", failure["stderr"])

    def _refresh_from_rows(self, rows):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            registry_path = tmp_path / "artifacts" / "registry" / "experiments.jsonl"
            hypotheses_path = tmp_path / "artifacts" / "analysis" / "hypotheses.jsonl"
            registry_path.parent.mkdir(parents=True, exist_ok=True)
            registry_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")

            hypotheses = refresh_hypotheses(registry_path, hypotheses_path)
            loaded = load_jsonl_rows(hypotheses_path)

        self.assertEqual(loaded, hypotheses)
        return hypotheses

    def _run_with_temp_state(self, refresh_failure):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            artifacts_runs_dir = tmp_path / "artifacts" / "runs"
            memory_dir = tmp_path / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)

            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()
            argv = [
                "statelock_opt.run",
                "--candidate",
                str(NOOP_CANDIDATE_DIR),
                "--incumbent",
                str(INCUMBENT_DIR),
            ]
            refresh_patch = patch.object(run_module, "refresh_hypotheses", side_effect=RuntimeError("boom")) if refresh_failure else patch.object(run_module, "refresh_hypotheses", wraps=run_module.refresh_hypotheses)
            with patch.object(run_module, "ARTIFACTS_DIR", artifacts_runs_dir), patch.object(run_module, "MEMORY_DIR", memory_dir), refresh_patch:
                with patch.object(sys, "argv", argv), redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                    run_module.main()

            registry_rows = load_jsonl_rows(artifacts_runs_dir.parent / "registry" / "experiments.jsonl")
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
                "registry_rows": registry_rows,
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

    def _normalized_registry_rows(self, rows):
        normalized = []
        for row in rows:
            normalized.append(
                {
                    "changed_fields": row["changed_fields"],
                    "change_signature": row["change_signature"],
                    "decision": row["decision"],
                    "case_types": row["case_types"],
                    "case_delta_summary": row["case_delta_summary"],
                    "case_family_summary": row["case_family_summary"],
                    "proof_role_summary": row["proof_role_summary"],
                    "promoted_lessons": row["promoted_lessons"],
                    "registry_warnings": row["registry_warnings"],
                }
            )
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
