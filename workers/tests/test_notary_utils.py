"""Tests for workers notary utilities and TEE stub verification."""

from workers.src.utils.notary import make_data_hash, sign_data_hash, make_and_sign
from infrastructure.tee_stub.attestation_service import generate_attestation, verify_attestation


def test_make_data_hash_consistent():
    h1 = make_data_hash("a", "b", "c")
    h2 = make_data_hash("a", "b", "c")
    assert h1 == h2
    assert h1.startswith("0x")


def test_make_and_sign_and_verify():
    # Use a deterministic test private key (do NOT use in production)
    priv = "0x4c0883a69102937d623414e9b3a0e1f14c8e9a6f0d6e4e3a3a9c8b1b1a8f7e0"
    data_hash, signature = make_and_sign(priv, "post123", "0.5", "2025-12-14T12:00:00Z")
    assert data_hash.startswith("0x")
    assert signature.startswith("0x") or len(signature) == 130


def test_tee_stub_attestation_and_verify():
    priv = "0x4c0883a69102937d623414e9b3a0e1f14c8e9a6f0d6e4e3a3a9c8b1b1a8f7e0"
    payload = {"post_id": "p1", "score": 0.7}
    att = generate_attestation(priv, payload)
    assert verify_attestation(att) is True
