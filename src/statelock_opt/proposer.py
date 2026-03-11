import argparse
import random
from pathlib import Path

import yaml

from .constants import (
    CONFIG_LIMITS,
    EXPLOIT_RATIO,
    INCUMBENT_DIR,
    MEMORY_DIR,
    MUTABLE_CONFIG_FILES,
    PROMPT_ENUMS,
    RETRIEVAL_ENUMS,
)
from .dedupe import fingerprint_bundle
from .replay import load_bundle, validate_bundle, write_bundle


def _load_yaml(path):
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def _load_existing_fingerprints():
    path = MEMORY_DIR / "runs.jsonl"
    fingerprints = set()
    if not path.exists():
        return fingerprints
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        import json

        fingerprints.add(json.loads(line)["fingerprint"])
    return fingerprints


def _coerce_numeric(value, low, high):
    if isinstance(low, int) and isinstance(high, int):
        return int(max(low, min(high, round(value))))
    return max(low, min(high, round(float(value), 3)))


def _mutate_numeric(randomizer, current, low, high):
    span = max(high - low, 1)
    if isinstance(low, int):
        step = max(1, span // 5)
        delta = randomizer.choice([-step, -1, 1, step])
    else:
        step = span / 6
        delta = randomizer.choice([-step, -step / 2, step / 2, step])
    return _coerce_numeric(current + delta, low, high)


def _mutate_bundle(bundle, priors, randomizer):
    candidate = {
        "retrieval": dict(bundle["retrieval"]),
        "memory_policy": dict(bundle["memory_policy"]),
        "prompt_fragments": dict(bundle["prompt_fragments"]),
    }

    mode = "exploit" if randomizer.random() < EXPLOIT_RATIO else "explore"
    sections = ["retrieval", "memory_policy", "prompt_fragments"]
    section = randomizer.choice(sections)
    fields = list(CONFIG_LIMITS[section].keys())
    if section == "prompt_fragments":
        fields.extend(PROMPT_ENUMS.keys())
    if section == "retrieval":
        fields.extend([key for key in RETRIEVAL_ENUMS.keys() if key not in fields])

    field = randomizer.choice(fields)
    current = candidate[section].get(field)
    favored = priors.get("favored_exact_values", {}).get(f"{section}.{field}")

    if field in PROMPT_ENUMS:
        options = sorted(PROMPT_ENUMS[field])
        candidate[section][field] = favored if mode == "exploit" and favored in options else randomizer.choice(options)
    elif field in RETRIEVAL_ENUMS:
        candidate[section][field] = "lexical"
    else:
        low, high = CONFIG_LIMITS[section][field]
        if mode == "exploit" and favored is not None:
            candidate[section][field] = _coerce_numeric(float(favored), low, high)
        else:
            candidate[section][field] = _mutate_numeric(randomizer, current, low, high)

    candidate["retrieval"]["strategy"] = "lexical"
    if candidate["retrieval"]["top_k_final"] > candidate["retrieval"]["top_k_pre"]:
        candidate["retrieval"]["top_k_final"] = candidate["retrieval"]["top_k_pre"]
    return candidate


def main():
    parser = argparse.ArgumentParser(description="Generate a bounded candidate config bundle.")
    parser.add_argument("--output", required=True, help="Directory to write the candidate bundle into")
    args = parser.parse_args()

    incumbent = load_bundle(INCUMBENT_DIR)
    priors = _load_yaml(MEMORY_DIR / "priors.yaml")
    bad_regions = _load_yaml(MEMORY_DIR / "bad_regions.yaml")
    known_slow = _load_yaml(MEMORY_DIR / "known_slow.yaml")
    fingerprints = _load_existing_fingerprints()

    seed = len(fingerprints) + 7
    randomizer = random.Random(seed)

    attempt = 0
    while attempt < 64:
        attempt += 1
        candidate = _mutate_bundle(incumbent, priors, randomizer)
        validate_bundle(candidate)
        fingerprint = fingerprint_bundle(candidate)
        if fingerprint in fingerprints:
            continue
        signature = "|".join(
            f"{section}.{field}:{incumbent[section].get(field)}->{candidate[section].get(field)}"
            for section in candidate
            for field in candidate[section]
            if candidate[section].get(field) != incumbent[section].get(field)
        )
        if any(block.get("signature") == signature for block in bad_regions.get("blocked_regions", [])):
            continue
        if any(block.get("signature") == signature for block in known_slow.get("patterns", [])):
            continue
        write_bundle(candidate, Path(args.output))
        print(f"Wrote candidate to {args.output}")
        print(f"Fingerprint: {fingerprint}")
        return

    raise SystemExit("Failed to generate a novel candidate outside blocked regions.")


if __name__ == "__main__":
    main()
