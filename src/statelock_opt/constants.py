from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "evals" / "dataset.jsonl"
EVAL_SCHEMA_PATH = ROOT / "evals" / "schema.json"
INCUMBENT_DIR = ROOT / "state" / "incumbent"
MEMORY_DIR = ROOT / "memory"
PROMPTS_DIR = ROOT / "prompts"
ARTIFACTS_DIR = ROOT / "artifacts" / "runs"
ARTIFACT_FORMAT_VERSION = 2
REGISTRY_FORMAT_VERSION = 1
HYPOTHESIS_FORMAT_VERSION = 1
HYPOTHESIS_RUN_REF_LIMIT = 3

MIN_ACCEPT_DELTA = 1.5
CLOSE_CALL_MAX_DELTA = 3.0
CLOSE_CALL_RERUNS = 3
LARGE_WIN_DELTA = 4.0

PROPOSAL_BATCH_SIZE = 8
EXPLOIT_RATIO = 0.7
STRICT_DEDUPE = True
MAX_ACTIVE_LESSONS = 100

ANTI_CHEESE_TOLERANCE = {
    "false_refusal_rate": 0.03,
    "unsupported_answer_rate": 0.02,
}

HARD_THRESHOLDS = {
    "correctness": 0.75,
    "refusal_correctness": 0.80,
    "unsupported_answer_control": 0.90,
    "citation_quality": 0.85,
    "groundedness_proxy": 0.85,
    "false_refusal_rate": 0.10,
    "unsupported_answer_rate": 0.05,
    "latency_multiplier": 2.0,
    "prompt_token_multiplier": 1.5,
}

TOTAL_SCORE_WEIGHTS = {
    "correctness": 35.0,
    "refusal_correctness": 15.0,
    "unsupported_answer_control": 15.0,
    "citation_quality": 10.0,
    "groundedness_proxy": 10.0,
    "context_cleanliness": 5.0,
    "latency_score": 5.0,
    "token_efficiency": 5.0,
}

RETRIEVAL_ENUMS = {
    "strategy": {"lexical"},
}

PROMPT_ENUMS = {
    "answer_style": {"concise", "balanced", "evidence_first"},
    "citation_instruction": {
        "required_inline_ids",
        "required_footnotes",
        "concise_inline_ids",
    },
    "refusal_behavior": {
        "strict_missing_evidence",
        "cautious_missing_evidence",
        "answer_if_partial_with_warning",
    },
}

CONFIG_LIMITS = {
    "retrieval": {
        "top_k_pre": (5, 40),
        "top_k_final": (1, 10),
        "min_term_overlap": (1, 5),
        "bm25_k1": (0.8, 2.0),
        "bm25_b": (0.0, 1.0),
        "recency_weight": (0.0, 0.35),
        "dedupe_overlap_threshold": (0.5, 0.95),
        "max_same_source": (1, 4),
    },
    "memory_policy": {
        "max_memories_total": (1, 10),
        "max_items_per_type": (1, 6),
        "promote_threshold": (0.5, 0.95),
        "drop_low_confidence_below": (0.0, 0.8),
        "stale_decay_days": (1, 180),
        "conflict_penalty": (0.0, 1.0),
        "redundancy_penalty": (0.0, 1.0),
    },
    "prompt_fragments": {
        "max_context_tokens": (800, 5000),
        "quote_budget_tokens": (0, 300),
    },
}

MUTABLE_CONFIG_FILES = (
    "retrieval.yaml",
    "memory_policy.yaml",
    "prompt_fragments.yaml",
)
