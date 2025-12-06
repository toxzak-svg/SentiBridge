# SentiBridge Architecture

## Overview

SentiBridge is a decentralized sentiment oracle system that aggregates real-time social media sentiment data from Web2 platforms (Twitter, Discord, Telegram), processes it through NLP analysis with manipulation detection, and makes it available on-chain via a Polygon smart contract oracle for consumption by AI agents, DeFi protocols, and dashboards.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Web2 Social Data Sources                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │   Twitter   │    │   Discord   │    │  Telegram   │                     │
│  │  (X API v2) │    │  (Bot API)  │    │  (Bot API)  │                     │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                     │
└─────────┼──────────────────┼──────────────────┼─────────────────────────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SentiBridge Off-Chain Workers (VPC Isolated)             │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Social Media Collectors                          │   │
│  │  • Rate-limited API consumption                                      │   │
│  │  • Deduplication via Redis                                          │   │
│  │  • Credential rotation support                                       │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     NLP Sentiment Analyzer                           │   │
│  │  • Fine-tuned DistilBERT for crypto terminology                     │   │
│  │  • VADER fallback with crypto lexicon                               │   │
│  │  • Ensemble scoring with confidence weighting                        │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                   Manipulation Detection Engine                      │   │
│  │  • Volume spike detection                                           │   │
│  │  • Bot/fake account filtering                                       │   │
│  │  • Content similarity (coordinated campaign detection)              │   │
│  │  • Cross-platform divergence analysis                               │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Oracle Submitter Service                        │   │
│  │  • AWS KMS / Vault for transaction signing                          │   │
│  │  • Nonce management                                                  │   │
│  │  • Gas price optimization                                           │   │
│  │  • Flashbots integration (MEV protection)                           │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
└─────────────────────────────────┼───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Polygon Blockchain (Mainnet/Amoy)                       │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              SentimentOracleV1 (UUPS Upgradeable)                   │   │
│  │                                                                      │   │
│  │  Storage:                                                            │   │
│  │  • latestSentiment: mapping(address => SentimentData)               │   │
│  │  • _history: mapping(address => CircularBuffer[288])                │   │
│  │                                                                      │   │
│  │  Access Control:                                                     │   │
│  │  • OPERATOR_ROLE: Can update sentiment                              │   │
│  │  • ADMIN_ROLE: Can pause, whitelist tokens                          │   │
│  │  • UPGRADER_ROLE: Can upgrade implementation                        │   │
│  │                                                                      │   │
│  │  Security Features:                                                  │   │
│  │  • Pausable for emergencies                                         │   │
│  │  • Rate limiting (MIN_UPDATE_INTERVAL)                              │   │
│  │  • Score bounds validation                                          │   │
│  │  • Optional token whitelist                                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
┌──────────────────┐  ┌──────────────┐  ┌──────────────────────┐
│   The Graph      │  │  SentiBridge │  │    External          │
│   Subgraph       │  │  REST API    │  │    Consumers         │
│                  │  │              │  │                      │
│  • Historical    │  │  Tiers:      │  │  • AI Agents         │
│    queries       │  │  • Free      │  │  • DeFi Protocols    │
│  • Real-time     │  │  • Pro       │  │  • Trading Bots      │
│    subscriptions │  │  • Enterprise│  │  • Dashboards        │
└──────────────────┘  └──────────────┘  └──────────────────────┘
```

## Component Details

### 1. Smart Contracts (`contracts/`)

**SentimentOracleV1.sol** - Core oracle contract
- UUPS upgradeable proxy pattern for future improvements
- Role-based access control (Operator, Admin, Upgrader)
- Circular buffer storage (288 entries = 24 hours at 5-min intervals)
- Emergency pause functionality
- Input validation and bounds checking

**Key Security Fixes from Original Design:**
- ✅ Proper operator initialization in constructor
- ✅ Bounded array growth via circular buffer
- ✅ Paginated historical queries
- ✅ Minimum update interval to prevent spam
- ✅ Score deviation bounds for anomaly detection

### 2. Off-Chain Workers (`workers/`)

**Collectors** - Social media data ingestion
- `twitter.py` - Twitter/X API v2 streaming
- `discord.py` - Discord bot for server monitoring
- `telegram.py` - Telegram channel listener

**Processors** - Data analysis pipeline
- `nlp_analyzer.py` - Sentiment scoring (DistilBERT + VADER)
- `manipulation_detector.py` - Coordinated attack detection

**Oracle** - Blockchain interaction
- `submitter.py` - Transaction construction and submission
- `signer.py` - AWS KMS/Vault signing abstraction

### 3. API Layer (`api/`)

**FastAPI Application**
- Rate limiting per tier (Redis-backed sliding window)
- API key authentication (hashed storage)
- Webhook delivery with HMAC-SHA256 signing
- OpenAPI documentation

**Tiers:**
| Tier | Rate Limit | Data Lag | Features |
|------|-----------|----------|----------|
| Free | 500/day | 10 min | Public tokens |
| Pro | 10,000/day | <1 min | Custom tokens, webhooks |
| Enterprise | Unlimited | Real-time | White-label, SLA |

### 4. Subgraph (`subgraph/`)

**GraphQL Indexer**
- Indexes `SentimentUpdated` events
- Enables efficient historical queries
- Supports real-time subscriptions

### 5. Infrastructure (`infrastructure/`)

**Terraform Modules**
- VPC with private subnets
- RDS PostgreSQL (encrypted, row-level security)
- ElastiCache Redis (TLS, auth)
- Lambda/ECS for workers
- KMS for signing keys

## Security Model

### Defense in Depth

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Edge Protection                                    │
│ • Cloudflare WAF / AWS Shield                              │
│ • DDoS mitigation                                          │
│ • Bot detection                                            │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: API Gateway                                        │
│ • Rate limiting                                            │
│ • Request validation                                       │
│ • API key verification                                     │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Application Security                               │
│ • Input sanitization                                       │
│ • SQL injection prevention (parameterized queries)         │
│ • XSS prevention                                           │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Data Protection                                    │
│ • Encryption at rest (RDS, Redis)                          │
│ • Encryption in transit (TLS 1.3)                          │
│ • Secret management (AWS Secrets Manager / Vault)          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│ Layer 5: Smart Contract Security                            │
│ • Access control (OpenZeppelin)                            │
│ • Reentrancy protection                                    │
│ • Pausable for emergencies                                 │
│ • Upgradeable via UUPS                                     │
└─────────────────────────────────────────────────────────────┘
```

### Key Management

| Secret | Storage | Rotation |
|--------|---------|----------|
| Social API keys | AWS Secrets Manager | 90 days |
| Database credentials | AWS Secrets Manager | 30 days |
| Oracle private key | AWS KMS (HSM-backed) | Annual |
| API customer keys | PostgreSQL (hashed) | On request |
| Webhook secrets | PostgreSQL (encrypted) | On request |

## Data Flow

### Sentiment Update Cycle (Every 5 Minutes)

```
1. COLLECT
   Twitter API → Filter mentions → Deduplicate → Store raw

2. ANALYZE  
   Raw posts → DistilBERT → VADER → Ensemble score

3. VALIDATE
   Check manipulation signals → Adjust confidence → Flag anomalies

4. AGGREGATE
   Per-token scores → Weighted average → Final sentiment

5. SUBMIT
   Build transaction → Sign with KMS → Submit to Polygon

6. INDEX
   Event emitted → Subgraph indexes → API cache invalidated
```

## Deployment Environments

| Environment | Network | Purpose |
|-------------|---------|---------|
| Local | Anvil | Development |
| Staging | Polygon Amoy | Integration testing |
| Production | Polygon Mainnet | Live system |

## Monitoring & Alerting

### Key Metrics

- **Oracle Health**: Last update timestamp, transaction success rate
- **Data Quality**: Manipulation score, cross-platform divergence
- **API Performance**: Latency p50/p95/p99, error rate
- **Infrastructure**: CPU, memory, database connections

### Alert Thresholds

| Alert | Condition | Severity |
|-------|-----------|----------|
| Oracle Stale | No update > 10 min | Critical |
| High Manipulation | Score > 0.8 | Critical |
| API Error Spike | Error rate > 5% | Warning |
| Rate Limit Exhaustion | Any tier > 90% | Info |

## Future Roadmap

1. **Phase 1** (Current): Single operator, core functionality
2. **Phase 2**: Multi-operator consensus (2-of-3 multisig)
3. **Phase 3**: Decentralized operator set with staking
4. **Phase 4**: Cross-chain deployment (Arbitrum, Base)
