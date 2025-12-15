import os
from unittest.mock import patch
from src.config import Settings

invalid_addresses = [
    "not_an_address",
    "0x123",
    "0x" + "g" * 40,
]

for addr in invalid_addresses:
    with patch.dict(os.environ, {"ORACLE_CONTRACT_ADDRESS": addr}):
        try:
            s = Settings(_env_file=None)
            print(f"Addr={addr!r} -> constructed, value={s.oracle_contract_address!r}")
        except Exception as e:
            print(f"Addr={addr!r} -> Exception type={type(e).__name__}: {e}")
