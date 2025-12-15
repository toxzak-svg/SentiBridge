"""API key management endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from src.auth import CurrentUser, generate_api_key, get_key_prefix, hash_api_key
from src.auth.dependencies import get_redis
from src.services.billing import billing_service
from src.models import APIKey, APIKeyCreate, APIKeyResponse, Tier

router = APIRouter(prefix="/keys", tags=["api-keys"])


@router.post(
    "/",
    response_model=APIKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new API key",
    description="Generate a new API key. The full key is only shown once!",
)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: CurrentUser,
    redis=Depends(get_redis),
) -> APIKeyResponse:
    """Create a new API key for the authenticated user."""
    # Check existing key count (limit per user)
    existing_keys = await redis.smembers(f"user:{current_user.sub}:keys")
    if len(existing_keys) >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 5 API keys per user",
        )

    # Generate new key
    full_key, key_hash = generate_api_key()
    key_id = f"key_{key_hash[:16]}"
    created_at = datetime.now(UTC)

    # Store key data in Redis
    await redis.hset(
        f"apikey:{key_hash}",
        mapping={
            "id": key_id,
            "user_id": current_user.sub,
            # Link API key to billing customer id (ensures customer exists)
            "customer_id": await billing_service.ensure_customer_for_user(current_user.sub),
            "name": key_data.name,
            "tier": key_data.tier.value,
            "created_at": created_at.isoformat(),
            "is_active": "true",
        },
    )

    # Add to user's key set
    await redis.sadd(f"user:{current_user.sub}:keys", key_hash)

    return APIKeyResponse(
        id=key_id,
        key=full_key,  # Only returned once!
        name=key_data.name,
        tier=key_data.tier,
        created_at=created_at,
    )


@router.get(
    "/",
    response_model=list[APIKey],
    summary="List API keys",
    description="List all API keys for the authenticated user.",
)
async def list_api_keys(
    current_user: CurrentUser,
    redis=Depends(get_redis),
) -> list[APIKey]:
    """List all API keys for the current user."""
    key_hashes = await redis.smembers(f"user:{current_user.sub}:keys")

    keys = []
    for key_hash in key_hashes:
        key_hash_str = key_hash.decode() if isinstance(key_hash, bytes) else key_hash
        data = await redis.hgetall(f"apikey:{key_hash_str}")

        if data:
            keys.append(
                APIKey(
                    id=data.get(b"id", b"").decode(),
                    key_prefix=f"sb_live_{key_hash_str[:8]}...",
                    name=data.get(b"name", b"").decode(),
                    tier=Tier(data.get(b"tier", b"free").decode()),
                    created_at=datetime.fromisoformat(
                        data.get(b"created_at", b"").decode()
                    ),
                    last_used=(
                        datetime.fromtimestamp(
                            int(data[b"last_used"].decode()), tz=UTC
                        )
                        if b"last_used" in data
                        else None
                    ),
                    is_active=data.get(b"is_active", b"true") == b"true",
                )
            )

    return keys


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an API key",
    description="Permanently revoke an API key.",
)
async def revoke_api_key(
    key_id: str,
    current_user: CurrentUser,
    redis=Depends(get_redis),
) -> None:
    """Revoke an API key."""
    # Find the key by ID
    key_hashes = await redis.smembers(f"user:{current_user.sub}:keys")

    for key_hash in key_hashes:
        key_hash_str = key_hash.decode() if isinstance(key_hash, bytes) else key_hash
        data = await redis.hgetall(f"apikey:{key_hash_str}")

        if data and data.get(b"id", b"").decode() == key_id:
            # Mark as inactive
            await redis.hset(f"apikey:{key_hash_str}", "is_active", "false")
            return

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="API key not found",
    )


@router.post(
    "/{key_id}/rotate",
    response_model=APIKeyResponse,
    summary="Rotate an API key",
    description="Generate a new API key and revoke the old one.",
)
async def rotate_api_key(
    key_id: str,
    current_user: CurrentUser,
    redis=Depends(get_redis),
) -> APIKeyResponse:
    """Rotate an API key - creates new key and revokes old one."""
    # Find the existing key
    key_hashes = await redis.smembers(f"user:{current_user.sub}:keys")
    old_key_hash = None
    old_data = None

    for key_hash in key_hashes:
        key_hash_str = key_hash.decode() if isinstance(key_hash, bytes) else key_hash
        data = await redis.hgetall(f"apikey:{key_hash_str}")

        if data and data.get(b"id", b"").decode() == key_id:
            old_key_hash = key_hash_str
            old_data = data
            break

    if not old_key_hash or not old_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    # Generate new key with same settings
    full_key, new_key_hash = generate_api_key()
    new_key_id = f"key_{new_key_hash[:16]}"
    created_at = datetime.now(UTC)

    # Store new key
    await redis.hset(
        f"apikey:{new_key_hash}",
        mapping={
            "id": new_key_id,
            "user_id": current_user.sub,
            "name": old_data.get(b"name", b"").decode(),
            "tier": old_data.get(b"tier", b"free").decode(),
            "created_at": created_at.isoformat(),
            "is_active": "true",
        },
    )

    # Update user's key set
    await redis.srem(f"user:{current_user.sub}:keys", old_key_hash)
    await redis.sadd(f"user:{current_user.sub}:keys", new_key_hash)

    # Revoke old key
    await redis.hset(f"apikey:{old_key_hash}", "is_active", "false")

    return APIKeyResponse(
        id=new_key_id,
        key=full_key,
        name=old_data.get(b"name", b"").decode(),
        tier=Tier(old_data.get(b"tier", b"free").decode()),
        created_at=created_at,
    )
