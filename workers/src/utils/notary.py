"""Helper utilities for creating and signing notary attestations from workers."""

from __future__ import annotations

import hashlib
import json
from typing import Tuple

try:
    from eth_account import Account
    from eth_account.messages import encode_defunct
    from eth_utils import keccak
except Exception:
    Account = None
    encode_defunct = None
    keccak = None


def make_data_hash(*parts: str) -> str:
    """Create a hex-prefixed keccak256 hash from the provided string parts.

    The workers will typically call this with (post_id, score_str, timestamp_iso).
    Returns 0x-prefixed hex string.
    """
    concatenated = "|".join(parts)
    if keccak is not None:
        # eth_utils.keccak returns bytes; hex() available on bytes
        h = keccak(text=concatenated)
        return "0x" + h.hex()
    # fallback to sha256 if eth_utils not available
    h = hashlib.sha256(concatenated.encode("utf-8")).hexdigest()
    return "0x" + h


def sign_data_hash(privkey_hex: str, data_hash_hex: str) -> str:
    """Sign the given hex-prefixed data hash with an Ethereum private key.

    Returns signature as 0x-prefixed hex string.
    Requires `eth_account` installed.
    """
    if Account is None or encode_defunct is None:
        raise RuntimeError("eth_account required for signing")

    acct = Account.from_key(privkey_hex)
    msg = encode_defunct(hexstr=data_hash_hex)
    signed = acct.sign_message(msg)
    return signed.signature.hex()


def make_and_sign(privkey_hex: str, *parts: str) -> Tuple[str, str]:
    """Convenience: create data hash from parts and sign it.

    Returns (data_hash_hex, signature_hex)
    """
    data_hash = make_data_hash(*parts)
    sig = sign_data_hash(privkey_hex, data_hash)
    return data_hash, sig
