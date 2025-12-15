"""Attestation endpoints: accepts signed attestations and optionally forwards to on-chain Notary."""

from fastapi import APIRouter, Depends, HTTPException
from web3 import Web3

from src.config import get_settings
from src.models import AttestationRequest, AttestationResponse, ErrorResponse

router = APIRouter(tags=["attestations"])


@router.post("/attestations", response_model=AttestationResponse, responses={400: {"model": ErrorResponse}})
async def submit_attestation(payload: AttestationRequest):
    """Accept an attestation and optionally forward it to the on-chain Notary contract.

    The endpoint will verify the provided signature locally. If blockchain configuration
    is provided via environment/settings (RPC URL, notary contract address, operator key),
    it will submit a transaction; otherwise it will return accepted without broadcasting.
    """
    settings = get_settings()

    # Basic validation of hex formats
    if not payload.data_hash.startswith("0x"):
        raise HTTPException(status_code=400, detail="data_hash must be hex prefixed with 0x")

    try:
        # Lazy import to keep startup light if not used
        from eth_account.messages import encode_defunct
        from eth_account import Account

        msg = encode_defunct(hexstr=payload.data_hash)
        recovered = Account.recover_message(msg, signature=payload.signature)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"signature verification failed: {e}")

    if recovered.lower() != payload.signer.lower():
        raise HTTPException(status_code=400, detail="signature does not match signer address")

    # Optionally submit to chain if configured
    rpc = getattr(settings, "polygon_rpc_url", None)
    notary_addr = getattr(settings, "notary_contract_address", None)
    operator_key = None

    # Read optional env var for submission key
    import os

    operator_key = os.environ.get("NOTARY_OPERATOR_PRIVATE_KEY")

    if rpc and notary_addr and operator_key:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc))
            acct = w3.eth.account.from_key(operator_key)

            # Notary contract ABI minimal call: notarize(bytes32,address,bytes,string)
            # Keep ABI light and dynamic
            abi = [
                {
                    "inputs": [
                        {"internalType": "bytes32", "name": "dataHash", "type": "bytes32"},
                        {"internalType": "address", "name": "signerAddress", "type": "address"},
                        {"internalType": "bytes", "name": "signature", "type": "bytes"},
                        {"internalType": "string", "name": "metadata", "type": "string"},
                    ],
                    "name": "notarize",
                    "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                    "stateMutability": "nonpayable",
                    "type": "function",
                }
            ]

            contract = w3.eth.contract(address=Web3.to_checksum_address(notary_addr), abi=abi)

            tx = contract.functions.notarize(
                Web3.to_bytes(hexstr=payload.data_hash),
                Web3.to_checksum_address(payload.signer),
                bytes.fromhex(payload.signature[2:]) if payload.signature.startswith("0x") else bytes.fromhex(payload.signature),
                ""
            ).build_transaction({
                "from": acct.address,
                "nonce": w3.eth.get_transaction_count(acct.address),
                "gas": 200000,
                "gasPrice": w3.to_wei("30", "gwei"),
            })

            signed = acct.sign_transaction(tx)
            txhash = w3.eth.send_raw_transaction(signed.rawTransaction)

            return AttestationResponse(accepted=True, on_chain_tx=txhash.hex(), message="Submitted to notary contract")

        except Exception as e:
            # Log in real app
            return AttestationResponse(accepted=True, on_chain_tx=None, message=f"verified locally but on-chain submit failed: {e}")

    # If chain not configured, just accept and return
    return AttestationResponse(accepted=True, on_chain_tx=None, message="Verified locally; not forwarded on-chain.")
