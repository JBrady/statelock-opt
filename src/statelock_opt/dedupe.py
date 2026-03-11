import hashlib
import json


def normalize_bundle(bundle):
    return json.loads(json.dumps(bundle, sort_keys=True))


def fingerprint_bundle(bundle):
    payload = json.dumps(normalize_bundle(bundle), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
