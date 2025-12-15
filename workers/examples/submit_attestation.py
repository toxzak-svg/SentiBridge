"""Example: create data hash, sign it, and submit to API /attestations.

Usage:
    python workers/examples/submit_attestation.py

Requires `requests` or `httpx` installed in the environment.
"""

import os
import json
import requests
from workers.src.utils.notary import make_and_sign

API_URL = os.environ.get("SENTIBRIDGE_API_URL", "http://localhost:8000/api/v1/attestations")
PRIV_KEY = os.environ.get("NOTARY_OPERATOR_PRIVATE_KEY")

if not PRIV_KEY:
    print("Set NOTARY_OPERATOR_PRIVATE_KEY in environment to run this example")
    raise SystemExit(1)

# Example payload parts
post_id = "tweet_12345"
score_str = "0.42"
timestamp = "2025-12-14T12:00:00Z"

data_hash, signature = make_and_sign(PRIV_KEY, post_id, score_str, timestamp)

payload = {
    "data_hash": data_hash,
    "signer": os.environ.get("NOTARY_SIGNER_ADDRESS"),
    "signature": signature,
    "metadata": {"post_id": post_id, "score": score_str, "timestamp": timestamp},
}

resp = requests.post(API_URL, json=payload)
print(resp.status_code, resp.text)
