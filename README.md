# SentiBridge

> **Decentralized Sentiment Oracle for Crypto Markets**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Solidity](https://img.shields.io/badge/Solidity-0.8.19-blue.svg)](https://docs.soliditylang.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)
[![Polygon](https://img.shields.io/badge/Network-Polygon-purple.svg)](https://polygon.technology/)

SentiBridge is a decentralized sentiment oracle that aggregates real-time social media sentiment data from Twitter, Discord, and Telegram, processes it through NLP analysis with manipulation detection, and makes it available on-chain for AI agents, DeFi protocols, and dashboards.

## 🎯 Features

- **Multi-Platform Aggregation**: Real-time data from Twitter, Discord, and Telegram
- **Advanced NLP**: Fine-tuned DistilBERT + VADER ensemble for crypto-specific sentiment
- **Manipulation Detection**: Bot filtering, coordinated campaign detection, volume anomaly alerts
- **On-Chain Oracle**: UUPS-upgradeable Polygon smart contract with role-based access
- **Tiered API**: Free, Pro, and Enterprise tiers with rate limiting and webhooks
- **GraphQL Indexing**: The Graph subgraph for efficient historical queries

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│     Web2 Social Streams                 │
│  (Twitter, Discord, Telegram)           │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│     Off-Chain Workers (VPC Isolated)    │
│  • Collectors → NLP → Manipulation Det. │
│  • AWS KMS Signing → Polygon Submit     │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│     SentimentOracleV1 (Polygon)         │
│  • Role-Based Access Control            │
│  • Circular Buffer History (24h)        │
│  • Pausable, Upgradeable                │
└─────────────────┬───────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
 Subgraph      REST API      DeFi/AI
(GraphQL)    (Tiered)      Consumers
```

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/ARCHITECTURE.md) | System design and component details |
| [Security](docs/SECURITY.md) | Security model, threat analysis, best practices |
| [Security Audit Checklist](docs/SECURITY_AUDIT_CHECKLIST.md) | Pre-audit checklist and Slither results |
| [Testnet Deployment](docs/TESTNET_DEPLOYMENT.md) | Guide to deploying on Polygon Amoy |
| [Development](docs/DEVELOPMENT.md) | Local setup, testing, and contribution guide |
| [API Reference](docs/API.md) | REST API endpoints, authentication, SDKs |

## 🚀 Quick Start

### Prerequisites

- Node.js 18+
- Python 3.11+
- Docker & Docker Compose
- Foundry (`curl -L https://foundry.paradigm.xyz | bash`)

### Local Development

```bash
# Clone repository
git clone https://github.com/toxzak-svg/SentiBridge.git
cd SentiBridge

# Start infrastructure
docker-compose up -d

# Deploy contracts locally
cd contracts
forge build && forge test
anvil &  # Start local chain
forge script script/Deploy.s.sol --rpc-url http://localhost:8545 --broadcast

# Start API
cd ../api
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload
```

## 📁 Project Structure

```
sentibridge/
├── contracts/          # Solidity smart contracts (Foundry)
├── workers/            # Off-chain Python services
├── api/                # FastAPI REST API
├── subgraph/           # The Graph indexer
├── infrastructure/     # Terraform & Docker configs
├── docs/               # Documentation
└── .github/            # CI/CD workflows
```

## 🔐 Security

SentiBridge implements defense-in-depth security:

- **Smart Contracts**: OpenZeppelin AccessControl, Pausable, ReentrancyGuard, UUPS upgradeable
- **Timelock**: 48-hour delay on admin functions for production deployments
- **Key Management**: AWS KMS (HSM-backed) for oracle signing
- **API**: Rate limiting, API key hashing (Argon2), JWT authentication
- **Infrastructure**: VPC isolation, encrypted databases, TLS everywhere
- **Static Analysis**: Slither verified (11 low/info findings, all documented)

See [SECURITY.md](docs/SECURITY.md) and [Security Audit Checklist](docs/SECURITY_AUDIT_CHECKLIST.md) for full details.

## 🧪 Testing

```bash
# Run all smart contract tests (58 tests)
cd contracts && forge test

# Run with gas reporting
forge test --gas-report

# Run fuzz tests
forge test --match-contract Fuzz

# Run invariant tests
forge test --match-contract Invariant

# Run worker integration tests
cd workers && python integration_test.py --mock
```

## 🛣️ Roadmap

- [x] **Phase 1**: Core architecture and documentation
- [x] **Phase 2**: Smart contract implementation (UUPS upgradeable, AccessControl, circuit breaker)
- [x] **Phase 3**: Off-chain workers (collectors, NLP analyzer, manipulation detection)
- [x] **Phase 4**: API layer (tiered FastAPI with rate limiting)
- [x] **Phase 5**: Subgraph schema and mappings
- [x] **Phase 6**: CI/CD pipelines and infrastructure
- [x] **Phase 7**: Security hardening (timelock, production deploy scripts, Slither analysis)
- [ ] **Phase 8**: Testnet deployment (Polygon Amoy) - [Guide](docs/TESTNET_DEPLOYMENT.md)
- [ ] **Phase 9**: External security audit
- [ ] **Phase 10**: Mainnet launch

## 🤝 Contributing

Contributions are welcome! Please read the [Development Guide](docs/DEVELOPMENT.md) for details on our code of conduct and the process for submitting pull requests.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is provided "as is" without warranty of any kind. Use at your own risk. Sentiment data should not be the sole basis for financial decisions.

---

<p align="center">
  <strong>Built for the decentralized future 🌐</strong>
</p>
