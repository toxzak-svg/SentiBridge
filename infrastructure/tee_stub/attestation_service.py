"""Simple TEE attestation stub for development and testing.

This module simulates a TEE attestation service by signing a canonical JSON
statement with a locally-held key. In production you'd replace this with
remote attestation from OpenEnclave / SGX or an attestation provider.
"""

import json
import time
from typing import Dict

from eth_account import Account
from eth_account.messages import encode_defunct


def generate_attestation(private_key_hex: str, payload: Dict) -> Dict:
    """Produce an attestation: sign the keccak of canonical payload and return a bundle.

    Returns a dict: {payload, timestamp, signer_address, signature}
    """
    # Canonicalize payload
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    timestamp = int(time.time())

    message = canonical + "|" + str(timestamp)
    acct = Account.from_key(private_key_hex)
    msg = encode_defunct(text=message)
    signed = acct.sign_message(msg)

    return {
        "payload": payload,
        "timestamp": timestamp,
        "signer": acct.address,
        "signature": signed.signature.hex(),
        "message": message,
    }


def verify_attestation(attestation: Dict) -> bool:
    """Verify the attestation bundle produced by `generate_attestation`.

    This replicates verification that the API router also performs for data hashes.
    """
    message = attestation.get("message")
    signature = attestation.get("signature")
    signer = attestation.get("signer")

    if not message or not signature or not signer:
        return False

    msg = encode_defunct(text=message)
    recovered = Account.recover_message(msg, signature=signature)
    return recovered.lower() == signer.lower()
