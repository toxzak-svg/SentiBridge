# SentiBridge Security Documentation

## Security Overview

This document outlines the security architecture, threat model, and best practices implemented in SentiBridge. Security is a first-class concern across all system components.

## Threat Model

### Assets to Protect

1. **Oracle Private Key** - Controls sentiment updates on-chain
2. **Social API Credentials** - Access to Twitter, Discord, Telegram APIs
3. **Customer Data** - API keys, usage data, webhook configurations
4. **Sentiment Data Integrity** - Accuracy of published sentiment scores

### Threat Actors

| Actor | Motivation | Capability |
|-------|------------|------------|
| Competitors | Disrupt service | Medium - DDoS, API abuse |
| Manipulators | Influence sentiment | High - Social media campaigns |
| Attackers | Financial gain | High - Exploit vulnerabilities |
| Insiders | Various | High - Privileged access |

### Attack Vectors

#### 1. Smart Contract Attacks

| Attack | Description | Mitigation |
|--------|-------------|------------|
| Unauthorized Updates | Attacker submits fake sentiment | Role-based access control |
| Replay Attacks | Resubmit old transactions | Timestamp validation, nonces |
| DoS via Gas | Exhaust oracle's gas | Gas price limits, monitoring |
| Frontrunning | MEV extraction | Flashbots, private mempool |
| Reentrancy | Recursive calls | ReentrancyGuard, CEI pattern |
| Storage DoS | Unbounded arrays | Circular buffer (fixed size) |

#### 2. Off-Chain Worker Attacks

| Attack | Description | Mitigation |
|--------|-------------|------------|
| Credential Theft | Steal API keys | AWS Secrets Manager, rotation |
| Key Compromise | Oracle private key leak | AWS KMS (HSM-backed) |
| Data Injection | Malicious sentiment data | Input validation, sanitization |
| Supply Chain | Malicious dependencies | Dependabot, lock files, audits |

#### 3. API Layer Attacks

| Attack | Description | Mitigation |
|--------|-------------|------------|
| DDoS | Overwhelm service | Cloudflare, rate limiting |
| API Key Abuse | Exceed rate limits | Per-key tracking, anomaly detection |
| Injection | SQL/NoSQL injection | Parameterized queries, ORMs |
| Webhook Spoofing | Fake webhook calls | HMAC-SHA256 signatures |

#### 4. Data Integrity Attacks

| Attack | Description | Mitigation |
|--------|-------------|------------|
| Social Manipulation | Coordinated fake posts, campaigns, or cross-platform attacks | Multi-layered manipulation detection: bot/fake account filtering, content similarity, campaign detection, cross-platform divergence, temporal/volume anomaly checks |
| Volume Attacks | Flood with low-quality data or sudden spikes | Volume and temporal anomaly detection, exclusion of high-manipulation tokens |
| Sybil Attacks | Multiple fake accounts | Account age/quality weighting, bot/fake account filtering |
#
# Manipulation Detection Technical Details
#
SentiBridge employs a multi-layered manipulation detection engine in its off-chain workers:

- **Volume Spike & Anomaly Detection**: Detects sudden surges in message volume for a token or topic, flagging potential coordinated activity.
- **Bot/Fake Account Filtering**: Uses account metadata (age, followers, activity) and ML heuristics to downweight or exclude likely bots.
- **Content Similarity & Campaign Detection**: Clusters messages by semantic similarity to identify coordinated campaigns or repeated narratives.
- **Cross-Platform Divergence**: Compares sentiment and message patterns across Twitter, Discord, and Telegram to detect manipulation isolated to a single platform.
- **Temporal Pattern Analysis**: Flags unnatural posting intervals or bursts indicative of automation.

Tokens with a manipulation score above a configurable threshold (default: 0.7) are excluded from on-chain submission. All manipulation signals are logged and available for monitoring and alerting.

## Smart Contract Security

### Access Control Model

```solidity
// Role hierarchy
DEFAULT_ADMIN_ROLE (can grant/revoke all roles)
    ├── ADMIN_ROLE (can pause, configure)
    ├── OPERATOR_ROLE (can update sentiment)
    └── UPGRADER_ROLE (can upgrade contract)
```

### Security Features

#### 1. Initialization Protection
```solidity
/// @custom:oz-upgrades-unsafe-allow constructor
constructor() {
    _disableInitializers();
}

function initialize(address admin, address operator) public initializer {
    require(admin != address(0), "Invalid admin");
    require(operator != address(0), "Invalid operator");
    // ... initialization
}
```

#### 2. Input Validation
```solidity
function updateSentiment(
    address token,
    int128 score,
    uint32 sampleSize,
    uint16 confidence
) external onlyRole(OPERATOR_ROLE) whenNotPaused nonReentrant {
    require(token != address(0), "Invalid token");
    require(confidence <= 10000, "Confidence > 100%");
    require(score >= -1e18 && score <= 1e18, "Score out of bounds");
    require(sampleSize > 0, "Sample size must be > 0");
    require(
        block.timestamp >= lastUpdateTime[token] + MIN_UPDATE_INTERVAL,
        "Update too frequent"
    );
    // ...
}
```

#### 3. Bounded Storage
```solidity
uint256 public constant MAX_HISTORY_SIZE = 288; // 24h at 5-min intervals

struct CircularBuffer {
    SentimentData[288] entries;
    uint256 head;
    uint256 count;
}
```

#### 4. Emergency Controls
```solidity
function pause() external onlyRole(ADMIN_ROLE) {
    _pause();
}

function unpause() external onlyRole(ADMIN_ROLE) {
    _unpause();
}
```

### Audit Checklist

- [ ] Slither static analysis (0 high/medium findings)
- [ ] Foundry fuzz testing (10,000+ runs)
- [ ] Manual code review
- [ ] External audit (before mainnet)
- [ ] Bug bounty program

## API Security

### Authentication

```python
# API Key Security
class APIKeyManager:
    """
    Best practices:
    1. Never store plaintext keys
    2. Use constant-time comparison
    3. Include prefix for identification
    4. Support rotation
    """
    
    @staticmethod
    def generate_key() -> tuple[str, str]:
        """Returns (full_key, hashed_key)"""
        raw_key = secrets.token_urlsafe(32)
        full_key = f"sb_{raw_key}"
        hashed = hashlib.sha256(full_key.encode()).hexdigest()
        return full_key, hashed
    
    @staticmethod
    def verify_key(provided: str, stored_hash: str) -> bool:
        """Constant-time comparison"""
        provided_hash = hashlib.sha256(provided.encode()).hexdigest()
        return secrets.compare_digest(provided_hash, stored_hash)
```

### Rate Limiting

```python
# Sliding window rate limiter
TIER_LIMITS = {
    "free": {"per_day": 500, "per_minute": 10},
    "pro": {"per_day": 10000, "per_minute": 100},
    "enterprise": {"per_day": 1000000, "per_minute": 10000},
}
```

### Webhook Security

```python
def sign_webhook(payload: bytes, secret: str, timestamp: int) -> str:
    """
    Generate webhook signature:
    1. Include timestamp to prevent replay
    2. Use HMAC-SHA256
    3. Format: t={timestamp},v1={signature}
    """
    message = f"{timestamp}.{payload.decode()}"
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signature}"
```

## Infrastructure Security

### Network Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Public Internet                   │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│              Cloudflare / AWS Shield                 │
│              (DDoS Protection, WAF)                  │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│                    Public Subnet                     │
│  ┌─────────────────────────────────────────────┐   │
│  │           Application Load Balancer          │   │
│  │           (TLS termination)                  │   │
│  └─────────────────────┬───────────────────────┘   │
└────────────────────────┼────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│                   Private Subnet                     │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │  API Service │  │   Workers    │  │  Redis    │ │
│  │  (ECS/Lambda)│  │  (Lambda)    │  │ (ElastiC) │ │
│  └──────────────┘  └──────────────┘  └───────────┘ │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │               RDS PostgreSQL                  │  │
│  │  (Encrypted, Private, Multi-AZ)              │  │
│  └──────────────────────────────────────────────┘  │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Secret Management

```yaml
# AWS Secrets Manager structure
sentibridge/production:
  TWITTER_BEARER_TOKEN: "..."
  DISCORD_BOT_TOKEN: "..."
  TELEGRAM_BOT_TOKEN: "..."
  DATABASE_URL: "..."
  REDIS_URL: "..."

# AWS KMS for blockchain signing
sentibridge-oracle-key:
  KeySpec: ECC_SECG_P256K1
  KeyUsage: SIGN_VERIFY
```

### Database Security

```sql
-- PostgreSQL security configuration

-- 1. Dedicated roles with minimal permissions
CREATE ROLE sentibridge_app LOGIN;
CREATE ROLE sentibridge_readonly LOGIN;

-- 2. Row-level security
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY org_isolation ON api_keys
    FOR ALL TO sentibridge_app
    USING (organization_id = current_setting('app.org_id')::uuid);

-- 3. Audit logging
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    user_name TEXT,
    action TEXT,
    table_name TEXT,
    old_data JSONB,
    new_data JSONB
);
```

## Operational Security

### Incident Response

#### Severity Levels

| Level | Description | Response Time | Example |
|-------|-------------|---------------|---------|
| P1 | Service down, data breach | 15 min | Oracle key compromised |
| P2 | Partial outage, security issue | 1 hour | API DDoS attack |
| P3 | Degraded performance | 4 hours | High error rate |
| P4 | Minor issue | 24 hours | Documentation bug |

#### Response Playbook

**Oracle Compromise (P1)**

1. **Immediate (0-5 min)**
   ```bash
   # Pause contract
   cast send $CONTRACT "pause()" --private-key $ADMIN_KEY
   
   # Alert team
   pagerduty trigger --severity critical
   ```

2. **Investigate (5-30 min)**
   - Check Vault audit logs
   - Review recent transactions
   - Identify compromise vector

3. **Remediate**
   - Rotate compromised credentials
   - Deploy new operator key via KMS
   - Update contract operator role

4. **Post-incident**
   - Root cause analysis
   - Security control improvements
   - Incident report

### Monitoring & Alerting

```yaml
# Prometheus alerts
groups:
  - name: security
    rules:
      - alert: UnauthorizedAccessAttempt
        expr: sentibridge_auth_failures > 100
        for: 5m
        labels:
          severity: warning
        
      - alert: OracleKeyUsageAnomaly
        expr: rate(kms_sign_operations[5m]) > 50
        labels:
          severity: critical
        
      - alert: SuspiciousSentimentPattern
        expr: sentibridge_manipulation_score > 0.8
        for: 10m
        labels:
          severity: critical
```

### Security Checklist

#### Pre-Deployment

- [ ] All secrets in Secrets Manager (not env vars)
- [ ] KMS key created for oracle signing
- [ ] VPC configured with private subnets
- [ ] TLS certificates provisioned
- [ ] WAF rules configured
- [ ] Slither scan passed
- [ ] Fuzz tests passed (10k+ runs)

#### Ongoing

- [ ] Weekly dependency updates (Dependabot)
- [ ] Monthly secret rotation
- [ ] Quarterly security review
- [ ] Annual penetration test
- [ ] Annual smart contract audit

## Compliance

### Data Handling

- **PII**: No personal data stored (only public social posts)
- **Retention**: Raw posts deleted after 30 days
- **Encryption**: AES-256 at rest, TLS 1.3 in transit

### Audit Trail

All sensitive operations are logged:
- API key creation/revocation
- Contract admin operations
- Secret access
- Configuration changes

## Bug Bounty Program

### Scope

| In Scope | Out of Scope |
|----------|--------------|
| Smart contracts | Third-party services |
| API endpoints | Social engineering |
| Worker services | Physical attacks |

### Rewards

| Severity | Reward |
|----------|--------|
| Critical | $10,000 |
| High | $5,000 |
| Medium | $1,000 |
| Low | $250 |

### Responsible Disclosure

1. Report to security@sentibridge.io
2. Do not disclose publicly for 90 days
3. Do not access/modify other users' data
4. Provide detailed reproduction steps
