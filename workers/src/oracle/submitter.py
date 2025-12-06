"""Oracle submission module for secure blockchain transaction signing."""

import asyncio
import hashlib
import json
import struct
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.config import get_settings
from src.utils.logging import get_logger
from src.utils.validation import SentimentScore

logger = get_logger(__name__)


class TransactionStatus(str, Enum):
    """Transaction status enumeration."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REPLACED = "replaced"


@dataclass
class TransactionReceipt:
    """Transaction receipt data."""

    tx_hash: str
    status: TransactionStatus
    block_number: int | None = None
    gas_used: int | None = None
    effective_gas_price: int | None = None
    timestamp: float = field(default_factory=time.time)
    error: str | None = None


class PendingUpdate(BaseModel):
    """Pending sentiment update awaiting submission."""

    token_symbol: str = Field(..., min_length=1, max_length=20)
    score: int = Field(..., ge=0, le=10000)
    volume: int = Field(..., ge=0)
    source_hash: str = Field(..., min_length=64, max_length=64)
    timestamp: float = Field(default_factory=time.time)
    retry_count: int = Field(default=0, ge=0)
    nonce: int | None = None


class GasEstimate(BaseModel):
    """Gas price estimation."""

    base_fee: int = Field(..., ge=0)
    priority_fee: int = Field(..., ge=0)
    max_fee: int = Field(..., ge=0)
    estimated_cost_wei: int = Field(..., ge=0)
    estimated_cost_matic: Decimal = Field(default=Decimal("0"))


class BaseKeyManager(ABC):
    """Abstract base class for key management."""

    @abstractmethod
    async def sign_transaction(self, tx_dict: dict[str, Any]) -> bytes:
        """Sign a transaction and return the signed bytes."""
        pass

    @abstractmethod
    async def get_address(self) -> str:
        """Get the signer address."""
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the key manager."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources."""
        pass


class LocalKeyManager(BaseKeyManager):
    """Local private key management (for development only)."""

    def __init__(self, private_key: str | None = None):
        """Initialize with optional private key."""
        self._private_key: bytes | None = None
        self._address: str | None = None
        self._provided_key = private_key

    async def initialize(self) -> None:
        """Initialize from environment or provided key."""
        # Import web3 components only when needed
        try:
            from eth_account import Account
        except ImportError as e:
            raise RuntimeError(
                "eth_account package required for LocalKeyManager"
            ) from e

        settings = get_settings()

        key_source = self._provided_key or settings.operator_private_key
        if not key_source:
            raise ValueError(
                "No private key provided. Set OPERATOR_PRIVATE_KEY "
                "or use AWS KMS in production."
            )

        # Normalize key format
        key_hex = (
            key_source if key_source.startswith("0x") else f"0x{key_source}"
        )

        # Validate key
        try:
            account = Account.from_key(key_hex)
            self._private_key = bytes.fromhex(key_hex[2:])
            self._address = account.address
            logger.warning(
                "local_key_manager_initialized",
                warning="LOCAL KEY MANAGER IS FOR DEVELOPMENT ONLY",
                address=self._address,
            )
        except Exception as e:
            logger.error("invalid_private_key", error=str(e))
            raise ValueError("Invalid private key format") from e

    async def sign_transaction(self, tx_dict: dict[str, Any]) -> bytes:
        """Sign transaction with local key."""
        if not self._private_key:
            raise RuntimeError("Key manager not initialized")

        try:
            from eth_account import Account
        except ImportError as e:
            raise RuntimeError(
                "eth_account package required for transaction signing"
            ) from e

        account = Account.from_key(self._private_key)
        signed = account.sign_transaction(tx_dict)
        return signed.raw_transaction

    async def get_address(self) -> str:
        """Get signer address."""
        if not self._address:
            raise RuntimeError("Key manager not initialized")
        return self._address

    async def close(self) -> None:
        """Clear sensitive data from memory."""
        if self._private_key:
            # Attempt to clear from memory (limited effectiveness in Python)
            self._private_key = b"\x00" * len(self._private_key)
            self._private_key = None
        self._address = None


class AWSKMSKeyManager(BaseKeyManager):
    """AWS KMS-based key management for production use."""

    def __init__(self, key_id: str | None = None, region: str | None = None):
        """Initialize with KMS key configuration."""
        self._key_id = key_id
        self._region = region
        self._client: Any = None
        self._address: str | None = None

    async def initialize(self) -> None:
        """Initialize AWS KMS client."""
        try:
            import boto3
            from eth_account._utils.signing import to_standard_signature_bytes
            from eth_keys import keys
        except ImportError as e:
            raise RuntimeError(
                "boto3, eth_keys packages required for AWS KMS"
            ) from e

        settings = get_settings()
        key_id = self._key_id or settings.aws_kms_key_id

        if not key_id:
            raise ValueError("AWS KMS Key ID not configured")

        region = self._region or settings.aws_region or "us-east-1"

        self._client = boto3.client("kms", region_name=region)
        self._key_id = key_id

        # Get public key to derive address
        try:
            response = self._client.get_public_key(KeyId=self._key_id)
            public_key_der = response["PublicKey"]

            # Parse DER-encoded public key
            # Skip DER header to get raw public key bytes
            public_key_bytes = self._parse_der_public_key(public_key_der)

            # Derive Ethereum address from public key
            public_key = keys.PublicKey(public_key_bytes)
            self._address = public_key.to_checksum_address()

            logger.info(
                "aws_kms_initialized",
                key_id=self._key_id[-8:],  # Log only last 8 chars
                address=self._address,
            )
        except Exception as e:
            logger.error("aws_kms_init_failed", error=str(e))
            raise

    def _parse_der_public_key(self, der_bytes: bytes) -> bytes:
        """Parse DER-encoded EC public key to get raw bytes."""
        # DER structure for EC public key:
        # SEQUENCE { SEQUENCE { OID, OID }, BIT STRING }
        # The actual public key is in the BIT STRING (last part)
        # For secp256k1, raw public key is 64 bytes (32 + 32 for x, y)

        # Find the BIT STRING (starts with 0x03)
        idx = der_bytes.find(b"\x03\x42\x00\x04")
        if idx >= 0:
            # Skip tag (0x03), length (0x42), padding (0x00), uncompressed marker (0x04)
            return der_bytes[idx + 4 : idx + 4 + 64]

        # Fallback: assume last 65 bytes are 0x04 || x || y
        if len(der_bytes) >= 65 and der_bytes[-65] == 0x04:
            return der_bytes[-64:]

        raise ValueError("Cannot parse DER public key")

    async def sign_transaction(self, tx_dict: dict[str, Any]) -> bytes:
        """Sign transaction using AWS KMS."""
        if not self._client or not self._key_id:
            raise RuntimeError("KMS client not initialized")

        try:
            from eth_account import Account
            from eth_account._utils.legacy_transactions import (
                serializable_unsigned_transaction_from_dict,
            )
            from eth_utils import keccak
        except ImportError as e:
            raise RuntimeError(
                "eth_account, eth_utils required for signing"
            ) from e

        # Serialize unsigned transaction
        unsigned_tx = serializable_unsigned_transaction_from_dict(tx_dict)
        tx_hash = keccak(unsigned_tx.as_bytes())

        # Sign with KMS
        response = self._client.sign(
            KeyId=self._key_id,
            Message=tx_hash,
            MessageType="DIGEST",
            SigningAlgorithm="ECDSA_SHA_256",
        )

        # Parse DER signature
        signature_der = response["Signature"]
        r, s = self._parse_der_signature(signature_der)

        # Determine v value (recovery id)
        # Try both v=27 and v=28
        for v in (27, 28):
            try:
                signed_tx = unsigned_tx.as_signed_transaction(
                    v=v, r=r, s=s
                )
                recovered = Account.recover_transaction(signed_tx.raw_transaction)
                if recovered.lower() == self._address.lower():
                    return signed_tx.raw_transaction
            except Exception:
                continue

        raise RuntimeError("Failed to determine recovery id")

    def _parse_der_signature(self, der_bytes: bytes) -> tuple[int, int]:
        """Parse DER-encoded ECDSA signature."""
        # DER structure: SEQUENCE { INTEGER r, INTEGER s }
        if der_bytes[0] != 0x30:
            raise ValueError("Invalid DER signature")

        idx = 2  # Skip SEQUENCE tag and length

        # Parse r
        if der_bytes[idx] != 0x02:
            raise ValueError("Invalid r integer tag")
        r_len = der_bytes[idx + 1]
        r_bytes = der_bytes[idx + 2 : idx + 2 + r_len]
        r = int.from_bytes(r_bytes, "big")
        idx += 2 + r_len

        # Parse s
        if der_bytes[idx] != 0x02:
            raise ValueError("Invalid s integer tag")
        s_len = der_bytes[idx + 1]
        s_bytes = der_bytes[idx + 2 : idx + 2 + s_len]
        s = int.from_bytes(s_bytes, "big")

        # Ensure low-s value (EIP-2)
        secp256k1_n = (
            0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
        )
        if s > secp256k1_n // 2:
            s = secp256k1_n - s

        return r, s

    async def get_address(self) -> str:
        """Get signer address."""
        if not self._address:
            raise RuntimeError("KMS client not initialized")
        return self._address

    async def close(self) -> None:
        """Close KMS client."""
        self._client = None
        self._address = None


class OracleSubmitter:
    """Secure oracle submission with transaction management."""

    # Contract ABI for updateSentiment and batchUpdateSentiment
    UPDATE_SENTIMENT_ABI = [
        {
            "inputs": [
                {"name": "tokenSymbol", "type": "string"},
                {"name": "score", "type": "uint256"},
                {"name": "volume", "type": "uint256"},
                {"name": "sourceHash", "type": "bytes32"},
            ],
            "name": "updateSentiment",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"name": "tokenSymbols", "type": "string[]"},
                {"name": "scores", "type": "uint256[]"},
                {"name": "volumes", "type": "uint256[]"},
                {"name": "sourceHashes", "type": "bytes32[]"},
            ],
            "name": "batchUpdateSentiment",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
    ]

    def __init__(
        self,
        key_manager: BaseKeyManager,
        contract_address: str | None = None,
        rpc_url: str | None = None,
        max_retries: int = 3,
        confirmation_blocks: int = 2,
    ):
        """Initialize oracle submitter."""
        self._key_manager = key_manager
        self._contract_address = contract_address
        self._rpc_url = rpc_url
        self._max_retries = max_retries
        self._confirmation_blocks = confirmation_blocks
        self._web3: Any = None
        self._contract: Any = None
        self._nonce: int | None = None
        self._nonce_lock = asyncio.Lock()
        self._pending_txs: dict[str, PendingUpdate] = {}

    async def initialize(self) -> None:
        """Initialize Web3 connection and contract."""
        try:
            from web3 import AsyncHTTPProvider, AsyncWeb3
            from web3.middleware import ExtraDataToPOAMiddleware
        except ImportError as e:
            raise RuntimeError("web3 package required") from e

        settings = get_settings()

        rpc_url = self._rpc_url or settings.polygon_rpc_url
        if not rpc_url:
            raise ValueError("Polygon RPC URL not configured")

        contract_address = self._contract_address or settings.oracle_contract_address
        if not contract_address:
            raise ValueError("Oracle contract address not configured")

        # Initialize Web3
        self._web3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))

        # Add POA middleware for Polygon
        self._web3.middleware_onion.inject(
            ExtraDataToPOAMiddleware, layer=0
        )

        # Verify connection
        if not await self._web3.is_connected():
            raise ConnectionError(f"Failed to connect to {rpc_url}")

        chain_id = await self._web3.eth.chain_id
        logger.info("web3_connected", chain_id=chain_id, rpc_url=rpc_url[:30])

        # Initialize contract
        self._contract_address = self._web3.to_checksum_address(contract_address)
        self._contract = self._web3.eth.contract(
            address=self._contract_address,
            abi=self.UPDATE_SENTIMENT_ABI,
        )

        # Initialize key manager
        await self._key_manager.initialize()

        # Get initial nonce
        signer_address = await self._key_manager.get_address()
        self._nonce = await self._web3.eth.get_transaction_count(signer_address)

        logger.info(
            "oracle_submitter_initialized",
            contract=self._contract_address,
            signer=signer_address,
            nonce=self._nonce,
        )

    async def estimate_gas(
        self, token_symbol: str, score: int, volume: int, source_hash: bytes
    ) -> GasEstimate:
        """Estimate gas for a sentiment update."""
        if not self._web3 or not self._contract:
            raise RuntimeError("Submitter not initialized")

        signer_address = await self._key_manager.get_address()

        # Estimate gas for the transaction
        try:
            gas_estimate = await self._contract.functions.updateSentiment(
                token_symbol, score, volume, source_hash
            ).estimate_gas({"from": signer_address})
        except Exception as e:
            logger.warning("gas_estimation_failed", error=str(e))
            gas_estimate = 150000  # Fallback estimate

        # Get current gas prices
        base_fee = await self._web3.eth.gas_price
        priority_fee = await self._web3.eth.max_priority_fee

        max_fee = base_fee * 2 + priority_fee
        estimated_cost = gas_estimate * max_fee

        return GasEstimate(
            base_fee=base_fee,
            priority_fee=priority_fee,
            max_fee=max_fee,
            estimated_cost_wei=estimated_cost,
            estimated_cost_matic=Decimal(estimated_cost) / Decimal(10**18),
        )

    def _compute_source_hash(self, data: dict[str, Any]) -> bytes:
        """Compute deterministic hash of source data."""
        # Sort keys for deterministic ordering
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).digest()

    async def submit_update(
        self,
        token_symbol: str,
        score: SentimentScore,
        volume: int,
        source_data: dict[str, Any],
        max_gas_price_gwei: float = 100.0,
    ) -> TransactionReceipt:
        """Submit a single sentiment update."""
        if not self._web3 or not self._contract:
            raise RuntimeError("Submitter not initialized")

        # Validate inputs
        if not 0 <= score.score <= 10000:
            raise ValueError(f"Invalid score: {score.score}")

        # Compute source hash
        source_hash = self._compute_source_hash(source_data)

        # Check gas price
        gas_estimate = await self.estimate_gas(
            token_symbol, score.score, volume, source_hash
        )

        max_gas_wei = int(max_gas_price_gwei * 10**9)
        if gas_estimate.base_fee > max_gas_wei:
            raise ValueError(
                f"Gas price too high: {gas_estimate.base_fee / 10**9:.2f} gwei"
            )

        # Build transaction
        signer_address = await self._key_manager.get_address()

        async with self._nonce_lock:
            nonce = self._nonce
            self._nonce += 1

        tx_dict = await self._contract.functions.updateSentiment(
            token_symbol, score.score, volume, source_hash
        ).build_transaction(
            {
                "from": signer_address,
                "nonce": nonce,
                "maxFeePerGas": gas_estimate.max_fee,
                "maxPriorityFeePerGas": gas_estimate.priority_fee,
                "chainId": await self._web3.eth.chain_id,
            }
        )

        # Sign and send
        try:
            signed_tx = await self._key_manager.sign_transaction(tx_dict)
            tx_hash = await self._web3.eth.send_raw_transaction(signed_tx)
            tx_hash_hex = tx_hash.hex() if hasattr(tx_hash, "hex") else tx_hash

            logger.info(
                "transaction_submitted",
                tx_hash=tx_hash_hex,
                token=token_symbol,
                score=score.score,
                nonce=nonce,
            )

            # Wait for confirmation
            receipt = await self._wait_for_confirmation(tx_hash_hex)
            return receipt

        except Exception as e:
            logger.error(
                "transaction_failed",
                error=str(e),
                token=token_symbol,
                nonce=nonce,
            )

            # Reset nonce on failure
            async with self._nonce_lock:
                self._nonce = await self._web3.eth.get_transaction_count(
                    signer_address
                )

            return TransactionReceipt(
                tx_hash="",
                status=TransactionStatus.FAILED,
                error=str(e),
            )

    async def submit_batch(
        self,
        updates: list[tuple[str, SentimentScore, int, dict[str, Any]]],
        max_gas_price_gwei: float = 100.0,
    ) -> TransactionReceipt:
        """Submit batch of sentiment updates."""
        if not self._web3 or not self._contract:
            raise RuntimeError("Submitter not initialized")

        if not updates:
            raise ValueError("No updates to submit")

        if len(updates) > 50:  # Contract limit
            raise ValueError("Batch size exceeds maximum of 50")

        # Prepare batch data
        token_symbols = []
        scores = []
        volumes = []
        source_hashes = []

        for token_symbol, score, volume, source_data in updates:
            if not 0 <= score.score <= 10000:
                raise ValueError(f"Invalid score for {token_symbol}: {score.score}")

            token_symbols.append(token_symbol)
            scores.append(score.score)
            volumes.append(volume)
            source_hashes.append(self._compute_source_hash(source_data))

        # Check gas price
        gas_price = await self._web3.eth.gas_price
        max_gas_wei = int(max_gas_price_gwei * 10**9)
        if gas_price > max_gas_wei:
            raise ValueError(
                f"Gas price too high: {gas_price / 10**9:.2f} gwei"
            )

        # Estimate gas
        signer_address = await self._key_manager.get_address()
        try:
            gas_estimate = await self._contract.functions.batchUpdateSentiment(
                token_symbols, scores, volumes, source_hashes
            ).estimate_gas({"from": signer_address})
        except Exception as e:
            logger.warning("batch_gas_estimation_failed", error=str(e))
            gas_estimate = 50000 + 100000 * len(updates)  # Rough estimate

        # Build transaction
        priority_fee = await self._web3.eth.max_priority_fee
        max_fee = gas_price * 2 + priority_fee

        async with self._nonce_lock:
            nonce = self._nonce
            self._nonce += 1

        tx_dict = await self._contract.functions.batchUpdateSentiment(
            token_symbols, scores, volumes, source_hashes
        ).build_transaction(
            {
                "from": signer_address,
                "nonce": nonce,
                "gas": int(gas_estimate * 1.2),  # 20% buffer
                "maxFeePerGas": max_fee,
                "maxPriorityFeePerGas": priority_fee,
                "chainId": await self._web3.eth.chain_id,
            }
        )

        # Sign and send
        try:
            signed_tx = await self._key_manager.sign_transaction(tx_dict)
            tx_hash = await self._web3.eth.send_raw_transaction(signed_tx)
            tx_hash_hex = tx_hash.hex() if hasattr(tx_hash, "hex") else tx_hash

            logger.info(
                "batch_transaction_submitted",
                tx_hash=tx_hash_hex,
                token_count=len(updates),
                nonce=nonce,
            )

            # Wait for confirmation
            receipt = await self._wait_for_confirmation(tx_hash_hex)
            return receipt

        except Exception as e:
            logger.error(
                "batch_transaction_failed",
                error=str(e),
                token_count=len(updates),
                nonce=nonce,
            )

            # Reset nonce on failure
            async with self._nonce_lock:
                self._nonce = await self._web3.eth.get_transaction_count(
                    signer_address
                )

            return TransactionReceipt(
                tx_hash="",
                status=TransactionStatus.FAILED,
                error=str(e),
            )

    async def _wait_for_confirmation(
        self, tx_hash: str, timeout: int = 180
    ) -> TransactionReceipt:
        """Wait for transaction confirmation."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                receipt = await self._web3.eth.get_transaction_receipt(tx_hash)

                if receipt is not None:
                    # Check confirmation depth
                    current_block = await self._web3.eth.block_number
                    confirmations = current_block - receipt["blockNumber"]

                    if confirmations >= self._confirmation_blocks:
                        status = (
                            TransactionStatus.CONFIRMED
                            if receipt["status"] == 1
                            else TransactionStatus.FAILED
                        )

                        logger.info(
                            "transaction_confirmed",
                            tx_hash=tx_hash,
                            status=status,
                            block=receipt["blockNumber"],
                            gas_used=receipt["gasUsed"],
                        )

                        return TransactionReceipt(
                            tx_hash=tx_hash,
                            status=status,
                            block_number=receipt["blockNumber"],
                            gas_used=receipt["gasUsed"],
                            effective_gas_price=receipt.get("effectiveGasPrice"),
                        )

            except Exception as e:
                logger.debug("confirmation_check_error", error=str(e))

            await asyncio.sleep(2)

        logger.warning("transaction_timeout", tx_hash=tx_hash)
        return TransactionReceipt(
            tx_hash=tx_hash,
            status=TransactionStatus.PENDING,
            error="Confirmation timeout",
        )

    async def get_transaction_status(self, tx_hash: str) -> TransactionStatus:
        """Check status of a submitted transaction."""
        if not self._web3:
            raise RuntimeError("Submitter not initialized")

        try:
            receipt = await self._web3.eth.get_transaction_receipt(tx_hash)
            if receipt is None:
                return TransactionStatus.PENDING
            return (
                TransactionStatus.CONFIRMED
                if receipt["status"] == 1
                else TransactionStatus.FAILED
            )
        except Exception:
            return TransactionStatus.PENDING

    async def close(self) -> None:
        """Clean up resources."""
        await self._key_manager.close()
        self._web3 = None
        self._contract = None
        logger.info("oracle_submitter_closed")


def create_key_manager(use_kms: bool = False) -> BaseKeyManager:
    """Factory function to create appropriate key manager."""
    settings = get_settings()

    if use_kms or settings.use_aws_kms:
        logger.info("creating_aws_kms_key_manager")
        return AWSKMSKeyManager(
            key_id=settings.aws_kms_key_id,
            region=settings.aws_region,
        )
    else:
        logger.warning(
            "creating_local_key_manager",
            warning="Use AWS KMS in production!",
        )
        return LocalKeyManager()
