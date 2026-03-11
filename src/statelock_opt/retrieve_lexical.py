import math
import re
from collections import Counter
from datetime import datetime, timezone


TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text):
    return TOKEN_RE.findall(text.lower())


def parse_ts(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def jaccard(a, b):
    if not a or not b:
        return 0.0
    a_set = set(a)
    b_set = set(b)
    return len(a_set & b_set) / len(a_set | b_set)


def bm25_score(query_tokens, doc_tokens, avgdl, k1, b, idf_map):
    if not doc_tokens:
        return 0.0
    tf = Counter(doc_tokens)
    doc_len = len(doc_tokens)
    score = 0.0
    for token in query_tokens:
        freq = tf.get(token, 0)
        if not freq:
            continue
        idf = idf_map.get(token, 0.0)
        denom = freq + k1 * (1.0 - b + b * (doc_len / max(avgdl, 1.0)))
        score += idf * ((freq * (k1 + 1.0)) / max(denom, 1e-6))
    return score


def rank_records(query, records, query_timestamp, config):
    query_tokens = tokenize(query)
    doc_tokens = [tokenize(record["text"]) for record in records]
    avgdl = sum(len(tokens) for tokens in doc_tokens) / max(len(doc_tokens), 1)

    doc_freq = Counter()
    for tokens in doc_tokens:
        for token in set(tokens):
            doc_freq[token] += 1
    num_docs = max(len(doc_tokens), 1)
    idf_map = {
        token: math.log(1.0 + (num_docs - freq + 0.5) / (freq + 0.5))
        for token, freq in doc_freq.items()
    }

    query_dt = parse_ts(query_timestamp)
    scored = []
    for record, tokens in zip(records, doc_tokens):
        overlap = len(set(tokens) & set(query_tokens))
        if overlap < config["min_term_overlap"]:
            continue
        score = bm25_score(
            query_tokens=query_tokens,
            doc_tokens=tokens,
            avgdl=avgdl,
            k1=config["bm25_k1"],
            b=config["bm25_b"],
            idf_map=idf_map,
        )
        record_dt = parse_ts(record.get("timestamp"))
        if query_dt and record_dt and config["recency_weight"] > 0:
            age_days = max((query_dt - record_dt).days, 0)
            recency = 1.0 / (1.0 + age_days / 30.0)
            score += config["recency_weight"] * recency
        scored.append(
            {
                **record,
                "_tokens": tokens,
                "retrieval_score": score,
                "term_overlap": overlap,
            }
        )

    scored.sort(
        key=lambda item: (
            -item["retrieval_score"],
            -parse_ts(item.get("timestamp")).timestamp() if item.get("timestamp") else 0,
            item["id"],
        )
    )

    selected = []
    source_counts = Counter()
    for record in scored:
        if source_counts[record["source"]] >= config["max_same_source"]:
            continue
        if any(
            jaccard(record["_tokens"], existing["_tokens"]) >= config["dedupe_overlap_threshold"]
            for existing in selected
        ):
            continue
        selected.append(record)
        source_counts[record["source"]] += 1
        if len(selected) >= config["top_k_pre"]:
            break
    return selected
