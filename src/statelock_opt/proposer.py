import argparse
import random
from pathlib import Path

import yaml

from .constants import (
    CONFIG_LIMITS,
    EXPLOIT_RATIO,
    INCUMBENT_DIR,
    MEMORY_DIR,
    PROMPT_ENUMS,
)
from .dedupe import fingerprint_bundle
from .replay import diff_bundle, load_bundle, validate_bundle, write_bundle


BEHAVIORAL_FIELDS = {
    "retrieval": tuple(CONFIG_LIMITS["retrieval"].keys()),
    "memory_policy": tuple(CONFIG_LIMITS["memory_policy"].keys()),
    "prompt_fragments": ("max_context_tokens", *PROMPT_ENUMS.keys()),
}


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
        deltas = [-step, -1, 1, step]
    else:
        step = span / 6
        deltas = [-step, -step / 2, step / 2, step]
    randomizer.shuffle(deltas)
    for delta in deltas:
        mutated = _coerce_numeric(current + delta, low, high)
        if mutated != current:
            return mutated
    return low if current != low else high


def _mutate_field(candidate, section, field, priors, mode, randomizer):
    current = candidate[section].get(field)
    favored = priors.get("favored_exact_values", {}).get(f"{section}.{field}")

    if field in PROMPT_ENUMS:
        options = [option for option in sorted(PROMPT_ENUMS[field]) if option != current]
        if not options:
            return False
        candidate[section][field] = favored if mode == "exploit" and favored in options else randomizer.choice(options)
        return True

    low, high = CONFIG_LIMITS[section][field]
    if mode == "exploit" and favored is not None:
        mutated = _coerce_numeric(float(favored), low, high)
        if mutated != current:
            candidate[section][field] = mutated
            return True
    mutated = _mutate_numeric(randomizer, current, low, high)
    if mutated == current:
        return False
    candidate[section][field] = mutated
    return True


def _mutate_bundle(bundle, priors, randomizer):
    candidate = {
        "retrieval": dict(bundle["retrieval"]),
        "memory_policy": dict(bundle["memory_policy"]),
        "prompt_fragments": dict(bundle["prompt_fragments"]),
    }

    mode = "exploit" if randomizer.random() < EXPLOIT_RATIO else "explore"
    no_priors = not priors.get("favored_exact_values") and not priors.get("metric_priors")
    target_mutations = 2 if no_priors or mode == "explore" else 1
    mutable_pairs = [(section, field) for section, fields in BEHAVIORAL_FIELDS.items() for field in fields]
    randomizer.shuffle(mutable_pairs)

    mutated_pairs = 0
    for section, field in mutable_pairs:
        if _mutate_field(candidate, section, field, priors, mode, randomizer):
            mutated_pairs += 1
        if mutated_pairs >= target_mutations:
            break

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
    fingerprints.add(fingerprint_bundle(incumbent))

    seed = len(fingerprints) + 7
    randomizer = random.Random(seed)

    attempt = 0
    while attempt < 64:
        attempt += 1
        candidate = _mutate_bundle(incumbent, priors, randomizer)
        validate_bundle(candidate)
        changed_fields = diff_bundle(incumbent, candidate)
        if not changed_fields:
            continue
        fingerprint = fingerprint_bundle(candidate)
        if fingerprint in fingerprints:
            continue
        signature = "|".join(
            f"{field}:{change['from']}->{change['to']}"
            for field, change in sorted(changed_fields.items())
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
