from collections import Counter
from datetime import datetime, timezone

from .retrieve_lexical import jaccard, parse_ts, tokenize


def estimate_tokens(text):
    return max(len(tokenize(text)), 1)


def _memory_allowed(record, policy):
    memory_type = record.get("memory_type", "long_term")
    if memory_type == "short_term" and not policy["include_short_term"]:
        return False
    if memory_type == "long_term" and not policy["include_long_term"]:
        return False
    if record.get("confidence", 0.0) < policy["drop_low_confidence_below"]:
        return False
    if policy["require_source_for_use"] and not record.get("source"):
        return False
    return True


def _staleness_multiplier(query_timestamp, record_timestamp, stale_decay_days):
    query_dt = parse_ts(query_timestamp)
    record_dt = parse_ts(record_timestamp)
    if not query_dt or not record_dt:
        return 1.0
    age_days = max((query_dt - record_dt).days, 0)
    if age_days <= 0:
        return 1.0
    return 1.0 / (1.0 + age_days / max(stale_decay_days, 1))


def assemble_context(retrieved_records, case, retrieval_config, memory_policy, prompt_config):
    candidate_records = [record for record in retrieved_records if _memory_allowed(record, memory_policy)]
    candidate_records.sort(key=lambda item: (-item["retrieval_score"], item["id"]))

    selected = []
    selected_ids = set()
    counts_by_type = Counter()
    token_budget = prompt_config["max_context_tokens"]
    used_tokens = 0
    max_items = min(memory_policy["max_memories_total"], retrieval_config["top_k_final"])

    while candidate_records and len(selected) < max_items:
        best_index = None
        best_score = None
        for index, record in enumerate(candidate_records):
            memory_type = record.get("memory_type", "long_term")
            if counts_by_type[memory_type] >= memory_policy["max_items_per_type"]:
                continue

            record_tokens = estimate_tokens(record["text"])
            if used_tokens + record_tokens > token_budget:
                continue

            score = record["retrieval_score"]
            if memory_type == "long_term" and record.get("confidence", 0.0) < memory_policy["promote_threshold"]:
                score *= 0.85
            score *= _staleness_multiplier(
                case.get("query_timestamp"), record.get("timestamp"), memory_policy["stale_decay_days"]
            )

            conflicting_selected = [
                existing for existing in selected if existing["id"] in record.get("contradicts_ids", [])
            ]
            if conflicting_selected:
                strongest_conflict = max(conflicting_selected, key=lambda item: item.get("confidence", 0.0))
                if strongest_conflict.get("confidence", 0.0) >= record.get("confidence", 0.0) + 0.15:
                    continue
                score -= memory_policy["conflict_penalty"]

            if any(record["source"] == existing["source"] for existing in selected):
                score -= 0.5 * memory_policy["redundancy_penalty"]

            if any(jaccard(tokenize(record["text"]), tokenize(existing["text"])) > 0.45 for existing in selected):
                score -= memory_policy["redundancy_penalty"]

            if best_score is None or score > best_score:
                best_index = index
                best_score = score

        if best_index is None:
            break

        chosen = candidate_records.pop(best_index)
        selected.append(chosen)
        selected_ids.add(chosen["id"])
        counts_by_type[chosen.get("memory_type", "long_term")] += 1
        used_tokens += estimate_tokens(chosen["text"])

    context_lines = [f"{record['id']} | {record['text']}" for record in selected]
    return {
        "retrieved_records": retrieved_records,
        "selected_records": selected,
        "retrieved_ids": [record["id"] for record in retrieved_records],
        "selected_ids": [record["id"] for record in selected],
        "context_text": "\n".join(context_lines),
        "prompt_context_tokens": used_tokens,
    }
