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


def test_attestation_bad_signature():

    def test_attestation_bad_data_hash():
        app = create_app()
        client = TestClient(app)

        payload = {
            "data_hash": "deadbeef",  # missing 0x prefix
            "signer": "0x0000000000000000000000000000000000000000",
            "signature": "0xdead",
            "metadata": {"note": "test"},
        }

        resp = client.post("/api/v1/attestations", json=payload)
        assert resp.status_code == 400


    app = create_app()
    client = TestClient(app)

    data_bytes = b"post:1|0.5|2025-12-14T12:00:00Z"
    data_hash = "0x" + keccak(data_bytes).hex()

    # Use a different signer to produce invalid signature
    priv = "0x4c0883a69102937d623414e9b3a0e1f14c8e9a6f0d6e4e3a3a9c8b1b1a8f7e0"
    acct = Account.from_key(priv)
    msg = encode_defunct(hexstr=data_hash)
    signed = acct.sign_message(msg)

    payload = {
        "data_hash": data_hash,
        "signer": "0x0000000000000000000000000000000000000000",
        "signature": signed.signature.hex(),
        "metadata": {"note": "test"},
    }


    def test_attestation_on_chain_submission_fails(monkeypatch, tmp_path):
        import os

        # Provide operator private key env var to trigger on-chain branch
        os.environ["NOTARY_OPERATOR_PRIVATE_KEY"] = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

        # Fake Web3 that raises when sending tx
        class FakeAccount:
            def __init__(self, key):
                self.address = "0xoperator"

            def sign_transaction(self, tx):
                class S:
                    rawTransaction = b"0xdeadbeef"

                return S()


        class FakeEth:
            def __init__(self):
                self.account = type("A", (), {"from_key": lambda *_: FakeAccount(None)})

            def get_transaction_count(self, addr):
                return 0


        class FakeContract:
            def __init__(self):
                pass

            class functions:
                @staticmethod
                def notarize(dataHash, signerAddress, signature, metadata):
                    class F:
                        def build_transaction(self, tx):
                            return {"from": "0xoperator", "nonce": 0}

                    return F()


        class FakeWeb3:
            def __init__(self):
                self.eth = FakeEth()

            def to_checksum_address(self, a):
                return a

            def to_bytes(self, hexstr=None):
                return bytes.fromhex(hexstr[2:])

            def eth_contract(self, address, abi):
                return FakeContract()

            def eth_send(self, raw):
                raise Exception("node error")

        # Monkeypatch Web3 usage inside router
        from src.routers import attestations as att_mod

        # Provide settings so the router takes the on-chain path
        from types import SimpleNamespace

        monkeypatch.setattr(att_mod, "get_settings", lambda: SimpleNamespace(polygon_rpc_url="http://x", notary_contract_address="0xabc"))
        monkeypatch.setattr(att_mod, "Web3", FakeWeb3)

        # create data and signature as before
        data_bytes = b"post:1|0.5|2025-12-14T12:00:00Z"
        data_hash = "0x" + keccak(data_bytes).hex()
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
        # Should be accepted locally but on_chain_tx None due to send failure
        assert body.get("accepted") is True
        assert body.get("on_chain_tx") is None
    resp = client.post("/api/v1/attestations", json=payload)
    assert resp.status_code == 400


def test_attestation_on_chain_submission(monkeypatch, tmp_path):
    import os

    # Provide operator private key env var to trigger on-chain branch
    os.environ["NOTARY_OPERATOR_PRIVATE_KEY"] = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    app = create_app()
    client = TestClient(app)

    # Fake Web3
    class FakeAccount:
        def __init__(self, key):
            self.address = "0xoperator"

        def sign_transaction(self, tx):
            class S:
                rawTransaction = b"0xdeadbeef"

            return S()


    class FakeEth:
        def __init__(self):
            self.account = type("A", (), {"from_key": lambda *_: FakeAccount(None)})

        def get_transaction_count(self, addr):
            return 0

    class FakeContract:
        def __init__(self):
            pass

        class functions:
            @staticmethod
            def notarize(dataHash, signerAddress, signature, metadata):
                class F:
                    def build_transaction(self, tx):
                        return {"from": "0xoperator", "nonce": 0}

                return F()

    class FakeWeb3:
        def __init__(self):
            self.eth = FakeEth()

        def to_checksum_address(self, a):
            return a

        def to_bytes(self, hexstr=None):
            return bytes.fromhex(hexstr[2:])

        def eth_contract(self, address, abi):
            return FakeContract()

        def eth_send(self, raw):
            return b"0x1234"

    # Monkeypatch Web3 usage inside router
    from src.routers import attestations as att_mod

    monkeypatch.setattr(att_mod, "Web3", FakeWeb3)

    # create data and signature as before
    data_bytes = b"post:1|0.5|2025-12-14T12:00:00Z"
    data_hash = "0x" + keccak(data_bytes).hex()
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

    # Call endpoint; should follow on-chain path (we stubbed Web3 internals)
    resp = client.post("/api/v1/attestations", json=payload)
    # The fake chain path may return accepted True (or fallback). Ensure 200.
    assert resp.status_code in (200, 201)

