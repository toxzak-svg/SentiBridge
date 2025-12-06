# SentiBridge API Reference

## Overview

The SentiBridge API provides access to real-time and historical sentiment data for crypto tokens. Authentication is required for all endpoints.

**Base URL:** `https://api.sentibridge.io/v1`

## Authentication

All requests require an API key in the header:

```
Authorization: Bearer sb_your_api_key_here
```

API keys are prefixed with `sb_` for identification.

## Rate Limits

| Tier | Requests/Day | Requests/Minute | Data Lag |
|------|-------------|-----------------|----------|
| Free | 500 | 10 | 10 minutes |
| Pro | 10,000 | 100 | < 1 minute |
| Enterprise | Unlimited | 10,000 | Real-time |

Rate limit headers are included in all responses:

```
X-RateLimit-Limit-Day: 500
X-RateLimit-Remaining-Day: 499
X-RateLimit-Limit-Minute: 10
X-RateLimit-Remaining-Minute: 9
```

## Endpoints

### Get Current Sentiment

Retrieve the latest sentiment score for a token.

```
GET /sentiment/{token_address}
```

**Parameters:**

| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| token_address | string | path | Yes | Token contract address (checksummed) |

**Response:**

```json
{
  "token": "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0",
  "score": 0.45,
  "confidence": 0.92,
  "sample_size": 1247,
  "timestamp": "2024-01-15T12:30:00Z",
  "sources": {
    "twitter": 856,
    "discord": 245,
    "telegram": 146
  }
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| token | string | Token contract address |
| score | number | Sentiment score (-1.0 to 1.0) |
| confidence | number | Confidence level (0.0 to 1.0) |
| sample_size | integer | Number of posts analyzed |
| timestamp | string | ISO 8601 timestamp |
| sources | object | Post count by platform |

**Example:**

```bash
curl -X GET "https://api.sentibridge.io/v1/sentiment/0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0" \
  -H "Authorization: Bearer sb_your_api_key"
```

---

### Get Sentiment History

Retrieve historical sentiment data for a token.

```
GET /sentiment/{token_address}/history
```

**Parameters:**

| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| token_address | string | path | Yes | Token contract address |
| from | string | query | No | Start timestamp (ISO 8601) |
| to | string | query | No | End timestamp (ISO 8601) |
| interval | string | query | No | Aggregation interval: `5m`, `1h`, `1d` (default: `5m`) |
| limit | integer | query | No | Max results (default: 100, max: 1000) |

**Response:**

```json
{
  "token": "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0",
  "interval": "1h",
  "data": [
    {
      "timestamp": "2024-01-15T12:00:00Z",
      "score": 0.42,
      "confidence": 0.91,
      "sample_size": 5420,
      "high": 0.55,
      "low": 0.31
    },
    {
      "timestamp": "2024-01-15T11:00:00Z",
      "score": 0.38,
      "confidence": 0.89,
      "sample_size": 4892,
      "high": 0.48,
      "low": 0.28
    }
  ],
  "pagination": {
    "total": 168,
    "limit": 100,
    "offset": 0,
    "has_more": true
  }
}
```

**Example:**

```bash
curl -X GET "https://api.sentibridge.io/v1/sentiment/0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0/history?interval=1h&limit=24" \
  -H "Authorization: Bearer sb_your_api_key"
```

---

### Get Multiple Tokens

Retrieve sentiment for multiple tokens in a single request.

```
POST /sentiment/batch
```

**Request Body:**

```json
{
  "tokens": [
    "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0",
    "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
  ]
}
```

**Response:**

```json
{
  "results": [
    {
      "token": "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0",
      "score": 0.45,
      "confidence": 0.92,
      "sample_size": 1247,
      "timestamp": "2024-01-15T12:30:00Z"
    },
    {
      "token": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
      "score": 0.12,
      "confidence": 0.87,
      "sample_size": 892,
      "timestamp": "2024-01-15T12:30:00Z"
    }
  ]
}
```

**Limits:**
- Free tier: 10 tokens per request
- Pro tier: 50 tokens per request
- Enterprise: 100 tokens per request

---

### List Supported Tokens

Get a list of all tokens with sentiment data.

```
GET /tokens
```

**Parameters:**

| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| search | string | query | No | Search by name or symbol |
| sort | string | query | No | Sort by: `volume`, `sentiment`, `name` |
| order | string | query | No | Sort order: `asc`, `desc` |
| limit | integer | query | No | Max results (default: 50) |
| offset | integer | query | No | Pagination offset |

**Response:**

```json
{
  "tokens": [
    {
      "address": "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0",
      "name": "Polygon",
      "symbol": "MATIC",
      "current_sentiment": 0.45,
      "sentiment_change_24h": 0.08,
      "volume_24h": 15420
    }
  ],
  "pagination": {
    "total": 250,
    "limit": 50,
    "offset": 0,
    "has_more": true
  }
}
```

---

## Webhooks (Pro & Enterprise)

### Create Webhook

Register a webhook to receive sentiment alerts.

```
POST /webhooks
```

**Request Body:**

```json
{
  "url": "https://your-app.com/webhook",
  "events": ["sentiment.alert"],
  "filters": {
    "tokens": ["0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0"],
    "threshold": {
      "type": "change",
      "value": 0.1
    }
  }
}
```

**Event Types:**

| Event | Description |
|-------|-------------|
| `sentiment.update` | Every sentiment update (every 5 minutes) |
| `sentiment.alert` | Significant sentiment change (exceeds threshold) |
| `sentiment.manipulation` | Potential manipulation detected |

**Response:**

```json
{
  "id": "wh_abc123",
  "url": "https://your-app.com/webhook",
  "events": ["sentiment.alert"],
  "secret": "whsec_...",
  "created_at": "2024-01-15T12:00:00Z",
  "status": "active"
}
```

### Webhook Payload

```json
{
  "id": "evt_xyz789",
  "type": "sentiment.alert",
  "created_at": "2024-01-15T12:35:00Z",
  "data": {
    "token": "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0",
    "previous_score": 0.45,
    "current_score": 0.62,
    "change": 0.17,
    "confidence": 0.91
  }
}
```

### Verifying Webhooks

Webhooks include a signature header for verification:

```
X-SentiBridge-Signature: t=1705326900,v1=abc123...
```

**Verification (Python):**

```python
import hmac
import hashlib
import time

def verify_webhook(payload: bytes, signature: str, secret: str) -> bool:
    parts = dict(p.split("=") for p in signature.split(","))
    timestamp = int(parts["t"])
    provided_sig = parts["v1"]
    
    # Check timestamp (5 minute tolerance)
    if abs(time.time() - timestamp) > 300:
        return False
    
    # Verify signature
    message = f"{timestamp}.{payload.decode()}"
    expected = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, provided_sig)
```

---

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again in 60 seconds.",
    "details": {
      "limit": 10,
      "reset_at": "2024-01-15T12:31:00Z"
    }
  }
}
```

**Error Codes:**

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `UNAUTHORIZED` | 401 | Invalid or missing API key |
| `FORBIDDEN` | 403 | Insufficient permissions for this tier |
| `NOT_FOUND` | 404 | Token or resource not found |
| `RATE_LIMIT_EXCEEDED` | 429 | Rate limit exceeded |
| `VALIDATION_ERROR` | 400 | Invalid request parameters |
| `INTERNAL_ERROR` | 500 | Server error |

---

## SDKs

### Python

```python
from sentibridge import SentiBridgeClient

client = SentiBridgeClient(api_key="sb_your_api_key")

# Get current sentiment
sentiment = client.get_sentiment("0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0")
print(f"Score: {sentiment.score}, Confidence: {sentiment.confidence}")

# Get history
history = client.get_sentiment_history(
    token="0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0",
    interval="1h",
    limit=24
)
for point in history:
    print(f"{point.timestamp}: {point.score}")
```

### JavaScript/TypeScript

```typescript
import { SentiBridge } from '@sentibridge/sdk';

const client = new SentiBridge({ apiKey: 'sb_your_api_key' });

// Get current sentiment
const sentiment = await client.getSentiment('0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0');
console.log(`Score: ${sentiment.score}, Confidence: ${sentiment.confidence}`);

// Subscribe to updates (WebSocket)
client.subscribe('0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0', (update) => {
  console.log('New sentiment:', update);
});
```

---

## On-Chain Integration

For direct smart contract integration, see the [Smart Contract Documentation](./ARCHITECTURE.md#smart-contracts).

```solidity
interface ISentimentOracle {
    struct SentimentData {
        int128 score;
        uint64 timestamp;
        uint32 sampleSize;
        uint16 confidence;
    }
    
    function getSentiment(address token) external view returns (SentimentData memory);
}

// Usage in your contract
ISentimentOracle oracle = ISentimentOracle(ORACLE_ADDRESS);
ISentimentOracle.SentimentData memory data = oracle.getSentiment(tokenAddress);

// Score is in 18 decimal fixed point (-1e18 to 1e18)
int256 score = int256(data.score); // 0.5 = 5e17
```

---

## Changelog

### v1.0.0 (2024-01-15)
- Initial release
- Support for Twitter, Discord, Telegram
- Polygon mainnet deployment
- Free, Pro, Enterprise tiers
