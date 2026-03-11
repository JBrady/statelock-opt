import math

from .constants import HARD_THRESHOLDS, TOTAL_SCORE_WEIGHTS


def _contains_all(text, phrases):
    lowered = text.lower()
    return all(phrase.lower() in lowered for phrase in phrases)


def _contains_any(text, phrases):
    lowered = text.lower()
    return any(phrase.lower() in lowered for phrase in phrases)


def _clamp(value):
    return max(0.0, min(1.0, value))


def _score_answer_case(case, response):
    if response["refused"]:
        return 0.0
    must_include = case["expected"].get("must_include", [])
    must_not = case["expected"].get("must_not_include", [])
    include_score = (
        sum(1 for phrase in must_include if phrase.lower() in response["text"].lower()) / max(len(must_include), 1)
    )
    forbidden_score = 0.0 if _contains_any(response["text"], must_not) else 1.0
    return _clamp((include_score + forbidden_score) / 2.0)


def _score_refusal_case(case, response):
    if response["refused"]:
        return 1.0 if _contains_any(response["text"], case["expected"].get("must_include", [])) else 0.8
    return 0.0


def _citation_format_valid(response_text, citation_instruction):
    if citation_instruction == "required_footnotes":
        return "[^" in response_text
    return "[" in response_text and "]" in response_text


def score_case(case, assembled, prompt, response):
    expected_behavior = case["expected_behavior"]
    required_support_ids = set(case["expected"].get("required_support_ids", []))
    forbidden_support_ids = set(case["expected"].get("forbidden_support_ids", []))
    retrieved_ids = set(assembled["retrieved_ids"])
    selected_ids = set(assembled["selected_ids"])
    cited_ids = set(response["cited_ids"])
    used_ids = set(response["used_record_ids"])
    distractor_ids = set(case.get("distractor_ids", []))

    if expected_behavior in {"answer", "answer_with_caution"}:
        correctness = _score_answer_case(case, response)
        refusal_correctness = 0.0 if response["refused"] else 1.0
        false_refusal_rate = 1.0 if response["refused"] else 0.0
    else:
        correctness = 1.0 if response["refused"] else 0.0
        refusal_correctness = _score_refusal_case(case, response)
        false_refusal_rate = 0.0

    support_present = required_support_ids.issubset(retrieved_ids)
    cited_support = required_support_ids.issubset(cited_ids) if required_support_ids else True
    used_support = required_support_ids.issubset(used_ids) if required_support_ids else True
    forbidden_claims_absent = not _contains_any(response["text"], case["expected"].get("must_not_include", []))

    if response["refused"]:
        unsupported_answer_control = 1.0 if expected_behavior == "refuse" else 1.0
    else:
        unsupported_answer_control = 1.0
        if expected_behavior == "refuse":
            unsupported_answer_control = 0.0
        elif not support_present or not used_support:
            unsupported_answer_control = 0.0
        elif not forbidden_claims_absent:
            unsupported_answer_control = 0.0

    unsupported_answer_rate = 1.0 if unsupported_answer_control == 0.0 and not response["refused"] else 0.0

    if response["refused"]:
        citation_quality = 1.0 if not response["cited_ids"] else 0.5
        groundedness_proxy = 1.0 if expected_behavior == "refuse" else 0.0
    else:
        citation_checks = [
            1.0 if cited_ids else 0.0,
            1.0 if required_support_ids.issubset(cited_ids) else 0.0,
            1.0 if cited_ids.issubset(retrieved_ids) else 0.0,
            1.0 if _citation_format_valid(response["text"], prompt["settings"]["citation_instruction"]) else 0.0,
            1.0 if not forbidden_support_ids.intersection(cited_ids) else 0.0,
        ]
        citation_quality = sum(citation_checks) / len(citation_checks)
        groundedness_checks = [
            1.0 if required_support_ids.issubset(cited_ids) or required_support_ids.issubset(used_ids) else 0.0,
            1.0 if cited_ids.issubset(retrieved_ids) else 0.0,
            1.0 if required_support_ids.issubset(retrieved_ids) else 0.0,
            1.0 if forbidden_claims_absent else 0.0,
        ]
        groundedness_proxy = sum(groundedness_checks) / len(groundedness_checks)

    distractor_ratio = len(selected_ids & distractor_ids) / max(len(selected_ids), 1)
    unused_selected = len(selected_ids - used_ids)
    unused_ratio = unused_selected / max(len(selected_ids), 1)
    context_cleanliness = _clamp(1.0 - (0.7 * distractor_ratio + 0.3 * unused_ratio))

    latency_budget = case["budgets"]["max_latency_ms"]
    prompt_budget = case["budgets"]["max_prompt_tokens"]
    output_budget = case["budgets"]["max_output_tokens"]

    latency_score = _clamp(1.0 - max(0.0, case["_latency_ms"] - latency_budget) / max(latency_budget, 1))
    total_budget = prompt_budget + output_budget
    used_tokens = response["prompt_tokens"] + response["output_tokens"]
    token_efficiency = _clamp(1.0 - max(0, used_tokens - total_budget) / max(total_budget, 1))

    metrics = {
        "correctness": correctness,
        "refusal_correctness": refusal_correctness,
        "unsupported_answer_control": unsupported_answer_control,
        "citation_quality": citation_quality,
        "groundedness_proxy": groundedness_proxy,
        "context_cleanliness": context_cleanliness,
        "latency_score": latency_score,
        "token_efficiency": token_efficiency,
        "false_refusal_rate": false_refusal_rate,
        "unsupported_answer_rate": unsupported_answer_rate,
        "latency_ms": case["_latency_ms"],
        "prompt_tokens": response["prompt_tokens"],
        "output_tokens": response["output_tokens"],
    }

    total_score = 0.0
    for metric_name, weight in TOTAL_SCORE_WEIGHTS.items():
        total_score += weight * metrics[metric_name]
    metrics["total_score"] = total_score

    failure_tags = []
    if false_refusal_rate:
        failure_tags.append("false_refusal")
    if unsupported_answer_rate:
        failure_tags.append("unsupported_answer")
    if citation_quality < 1.0:
        failure_tags.append("citation_gap")
    if groundedness_proxy < 1.0:
        failure_tags.append("grounding_gap")
    if context_cleanliness < 0.85:
        failure_tags.append("context_pollution")

    return metrics, failure_tags


def aggregate_cases(case_results):
    metric_names = [
        "correctness",
        "refusal_correctness",
        "unsupported_answer_control",
        "citation_quality",
        "groundedness_proxy",
        "context_cleanliness",
        "latency_score",
        "token_efficiency",
        "false_refusal_rate",
        "unsupported_answer_rate",
    ]
    aggregate = {
        metric: sum(case["metrics"][metric] for case in case_results) / max(len(case_results), 1)
        for metric in metric_names
    }

    latencies = sorted(case["metrics"]["latency_ms"] for case in case_results)
    index = max(math.ceil(len(latencies) * 0.95) - 1, 0)
    aggregate["p95_latency_ms"] = latencies[index] if latencies else 0.0
    aggregate["avg_prompt_tokens"] = sum(case["metrics"]["prompt_tokens"] for case in case_results) / max(len(case_results), 1)
    aggregate["avg_output_tokens"] = sum(case["metrics"]["output_tokens"] for case in case_results) / max(len(case_results), 1)

    total_score = 0.0
    for metric_name, weight in TOTAL_SCORE_WEIGHTS.items():
        total_score += weight * aggregate[metric_name]
    aggregate["total_score"] = total_score
    return aggregate


def evaluate_thresholds(aggregate, case_results):
    reasons = []
    for metric in (
        "correctness",
        "refusal_correctness",
        "unsupported_answer_control",
        "citation_quality",
        "groundedness_proxy",
    ):
        if aggregate[metric] < HARD_THRESHOLDS[metric]:
            reasons.append(f"{metric} below threshold")

    if aggregate["false_refusal_rate"] > HARD_THRESHOLDS["false_refusal_rate"]:
        reasons.append("false_refusal_rate above threshold")
    if aggregate["unsupported_answer_rate"] > HARD_THRESHOLDS["unsupported_answer_rate"]:
        reasons.append("unsupported_answer_rate above threshold")

    latency_violations = [
        case["metrics"]["latency_ms"] > case["case"]["budgets"]["max_latency_ms"] * HARD_THRESHOLDS["latency_multiplier"]
        for case in case_results
    ]
    if any(latency_violations):
        reasons.append("latency threshold exceeded")

    prompt_token_budget = sum(case["case"]["budgets"]["max_prompt_tokens"] for case in case_results) / max(len(case_results), 1)
    if aggregate["avg_prompt_tokens"] > prompt_token_budget * HARD_THRESHOLDS["prompt_token_multiplier"]:
        reasons.append("prompt token budget exceeded")

    return reasons
