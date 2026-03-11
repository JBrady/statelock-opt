from statistics import median

from .constants import ANTI_CHEESE_TOLERANCE, CLOSE_CALL_MAX_DELTA, MIN_ACCEPT_DELTA
from .scorer import evaluate_thresholds


def _median_score(evaluations):
    return median(result["aggregate"]["total_score"] for result in evaluations)


def compare_runs(incumbent_evals, candidate_evals):
    incumbent_median = _median_score(incumbent_evals)
    candidate_median = _median_score(candidate_evals)
    delta = candidate_median - incumbent_median

    threshold_reasons = evaluate_thresholds(candidate_evals[-1]["aggregate"], candidate_evals[-1]["cases"])
    if threshold_reasons:
        return {
            "accepted": False,
            "reason": "; ".join(threshold_reasons),
            "incumbent_score": incumbent_median,
            "candidate_score": candidate_median,
            "delta": delta,
            "close_call": False,
        }

    incumbent_aggregate = incumbent_evals[-1]["aggregate"]
    candidate_aggregate = candidate_evals[-1]["aggregate"]
    for metric, tolerance in ANTI_CHEESE_TOLERANCE.items():
        if candidate_aggregate[metric] > incumbent_aggregate[metric] + tolerance:
            return {
                "accepted": False,
                "reason": f"{metric} regressed beyond tolerance",
                "incumbent_score": incumbent_median,
                "candidate_score": candidate_median,
                "delta": delta,
                "close_call": False,
            }

    if delta < MIN_ACCEPT_DELTA:
        return {
            "accepted": False,
            "reason": "score delta below minimum acceptance threshold",
            "incumbent_score": incumbent_median,
            "candidate_score": candidate_median,
            "delta": delta,
            "close_call": False,
        }

    close_call = delta < CLOSE_CALL_MAX_DELTA
    return {
        "accepted": True,
        "reason": "accepted",
        "incumbent_score": incumbent_median,
        "candidate_score": candidate_median,
        "delta": delta,
        "close_call": close_call,
    }
