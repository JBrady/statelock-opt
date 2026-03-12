import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from statelock_opt.accept import compare_runs
from statelock_opt.dedupe import fingerprint_bundle
from statelock_opt.distill import refresh_memory
from statelock_opt.replay import evaluate_bundle, load_bundle


ROOT = Path(__file__).resolve().parents[1]
INCUMBENT_DIR = ROOT / "state" / "incumbent"
PROOF_DIR = ROOT / "state" / "candidates" / "proof_top_k_final_4"
DATASET_PATH = ROOT / "evals" / "dataset.jsonl"
SCHEMA_PATH = ROOT / "evals" / "schema.json"
EXPECTED_CASE_IDS = [f"case_{index:03d}" for index in range(1, 24)]
EXPECTED_INCUMBENT_CASE_SCORES = [
    97.5,
    97.5,
    98.25,
    97.833333,
    100.0,
    100.0,
    97.666667,
    98.333333,
    97.5,
    100.0,
    97.5,
    97.666667,
    100.0,
    98.333333,
    97.666667,
    97.5,
    97.5,
    97.833333,
    69.583333,
    97.666667,
    24.666667,
    97.5,
    98.333333,
]
EXPECTED_PROOF_CASE_SCORES = [
    97.5,
    97.5,
    98.25,
    97.833333,
    100.0,
    100.0,
    97.666667,
    98.333333,
    97.5,
    100.0,
    97.5,
    97.666667,
    100.0,
    98.333333,
    97.666667,
    97.5,
    97.5,
    97.833333,
    68.875,
    97.375,
    98.25,
    97.5,
    98.333333,
]
EXPECTED_INCUMBENT_AGGREGATE = 93.7536231884058
EXPECTED_PROOF_AGGREGATE = 96.90942028985508
EXPECTED_PROPOSER_FINGERPRINT = "2a5996df536ff1c4bf5aa0117f923169e4c9b26be3707fd59228c322ec90f3ae"


def _evaluate(bundle_dir):
    with tempfile.TemporaryDirectory() as tmpdir:
        return evaluate_bundle(Path(bundle_dir), "test_run", Path(tmpdir))


class HardeningRegressionTests(unittest.TestCase):
    def test_dataset_identity_uses_raw_file_hashes(self):
        result = _evaluate(INCUMBENT_DIR)
        dataset_identity = result["dataset_identity"]
        self.assertEqual(dataset_identity["dataset_sha256"], hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest())
        self.assertEqual(dataset_identity["schema_sha256"], hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest())
        self.assertEqual(dataset_identity["case_ids"], EXPECTED_CASE_IDS)
        self.assertEqual(dataset_identity["case_count"], len(EXPECTED_CASE_IDS))

    def test_incumbent_case_order_and_scores_match_baseline(self):
        result = _evaluate(INCUMBENT_DIR)
        case_ids = [case["case"]["id"] for case in result["cases"]]
        case_scores = [round(case["metrics"]["total_score"], 6) for case in result["cases"]]
        self.assertEqual(case_ids, EXPECTED_CASE_IDS)
        self.assertEqual(case_scores, EXPECTED_INCUMBENT_CASE_SCORES)
        self.assertAlmostEqual(result["aggregate"]["total_score"], EXPECTED_INCUMBENT_AGGREGATE)

    def test_proof_candidate_case_order_and_scores_match_baseline(self):
        result = _evaluate(PROOF_DIR)
        case_ids = [case["case"]["id"] for case in result["cases"]]
        case_scores = [round(case["metrics"]["total_score"], 6) for case in result["cases"]]
        self.assertEqual(case_ids, EXPECTED_CASE_IDS)
        self.assertEqual(case_scores, EXPECTED_PROOF_CASE_SCORES)
        self.assertAlmostEqual(result["aggregate"]["total_score"], EXPECTED_PROOF_AGGREGATE)

    def test_proof_acceptance_decision_matches_baseline(self):
        incumbent = _evaluate(INCUMBENT_DIR)
        candidate = _evaluate(PROOF_DIR)
        decision = compare_runs([incumbent], [candidate])
        self.assertTrue(decision["accepted"])
        self.assertEqual(decision["reason"], "accepted")
        self.assertAlmostEqual(decision["incumbent_score"], EXPECTED_INCUMBENT_AGGREGATE)
        self.assertAlmostEqual(decision["candidate_score"], EXPECTED_PROOF_AGGREGATE)
        self.assertAlmostEqual(decision["delta"], EXPECTED_PROOF_AGGREGATE - EXPECTED_INCUMBENT_AGGREGATE)

    def test_checked_in_memory_proposer_output_matches_baseline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "candidate"
            subprocess.run(
                [sys.executable, "-m", "statelock_opt.proposer", "--output", str(output_dir)],
                check=True,
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            bundle = load_bundle(output_dir)
        self.assertEqual(fingerprint_bundle(bundle), EXPECTED_PROPOSER_FINGERPRINT)

    def test_refresh_memory_promotes_structured_lessons(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_dir = Path(tmpdir)
            runs = [
                {
                    "run_id": "accepted_large_win",
                    "case_types": ["partial_evidence"],
                    "changed_fields": {"retrieval.top_k_final": {"from": 3, "to": 4}},
                    "metric_deltas": {"correctness": 0.05, "unsupported_answer_rate": -0.04},
                    "decision": {"accepted": True, "delta": 4.2, "reason": "accepted"},
                    "aggregate": {"p95_latency_ms": 100.0},
                },
                {
                    "run_id": "rejected_pattern_1",
                    "case_types": ["distractor_retrieval"],
                    "changed_fields": {"retrieval.max_same_source": {"from": 2, "to": 1}},
                    "metric_deltas": {"correctness": -0.04},
                    "decision": {"accepted": False, "delta": -2.0, "reason": "unsupported_answer_rate above threshold"},
                    "aggregate": {"p95_latency_ms": 100.0},
                },
                {
                    "run_id": "rejected_pattern_2",
                    "case_types": ["distractor_retrieval"],
                    "changed_fields": {"retrieval.max_same_source": {"from": 2, "to": 1}},
                    "metric_deltas": {"correctness": -0.04},
                    "decision": {"accepted": False, "delta": -2.0, "reason": "unsupported_answer_rate above threshold"},
                    "aggregate": {"p95_latency_ms": 100.0},
                },
                {
                    "run_id": "rejected_pattern_3",
                    "case_types": ["distractor_retrieval"],
                    "changed_fields": {"retrieval.max_same_source": {"from": 2, "to": 1}},
                    "metric_deltas": {"correctness": -0.04},
                    "decision": {"accepted": False, "delta": -2.0, "reason": "unsupported_answer_rate above threshold"},
                    "aggregate": {"p95_latency_ms": 100.0},
                },
            ]
            (memory_dir / "runs.jsonl").write_text("\n".join(json.dumps(row, sort_keys=True) for row in runs) + "\n")
            refresh_memory(memory_dir)
            lessons = [
                json.loads(line)
                for line in (memory_dir / "lessons.jsonl").read_text().splitlines()
                if line.strip()
            ]
        lesson_types = {lesson["lesson_type"] for lesson in lessons}
        promotion_rules = {lesson["promotion_rule"] for lesson in lessons}
        self.assertEqual(lesson_types, {"positive", "negative"})
        self.assertIn("large_accepted_win", promotion_rules)
        self.assertIn("repeated_rejected_pattern", promotion_rules)


if __name__ == "__main__":
    unittest.main()
