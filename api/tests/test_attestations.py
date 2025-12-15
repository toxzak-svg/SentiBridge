import os
import json
from fastapi.testclient import TestClient
from src.main import create_app

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import keccak


def test_attestation_endpoint_local_verify():
    app = create_app()
    client = TestClient(app)

    # create data hash
    data_bytes = b"post:1|0.5|2025-12-14T12:00:00Z"
    data_hash = "0x" + keccak(data_bytes).hex()

    # sign using a deterministic private key
    priv = "0x4c0883a69102937d623414e9b3a0e1f14c8e9a6f0d6e4e3a3a9c8b1b1a8f7e0"
    acct = Account.from_key(priv)
    msg = encode_defunct(hexstr=data_hash)
    signed = acct.sign_message(msg)

    payload = {
        "data_hash": data_hash,
        "signer": acct.address,
        "signature": signed.signature.hex(),
        "metadata": {"note": "test"},
    }

    resp = client.post("/api/v1/attestations", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("accepted") is True

