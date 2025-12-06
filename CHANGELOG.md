# Changelog

All notable changes to SentiBridge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial implementation of SentiBridge sentiment oracle
- UUPS upgradeable smart contracts with role-based access control
- Python workers for sentiment collection and analysis
- FastAPI-based tiered REST API
- The Graph subgraph for data indexing
- Docker Compose infrastructure
- CI/CD pipelines for testing and deployment
- Comprehensive documentation

## [1.0.0] - 2024-XX-XX (Planned)

### Smart Contracts
- `SentimentOracleV1`: Main sentiment oracle with circular buffer history
- `SentiBridgeTimelock`: Timelock controller for admin function delays
- Role-based access control (Admin, Operator, Upgrader)
- Circuit breaker for anomalous score changes
- Token whitelist support
- Batch sentiment updates

### Off-Chain Workers
- News collectors (NewsAPI, CryptoCompare)
- Social media collectors (Twitter, Discord, Telegram)
- FinBERT-based sentiment analyzer
- Manipulation detection system
- Oracle submitter with gas optimization
- Orchestrator for workflow management

### API
- Tiered access (Free, Basic, Pro, Enterprise)
- JWT authentication
- Rate limiting per tier
- Webhook notifications
- Historical data endpoints
- Batch query support

### Infrastructure
- Docker Compose for local development
- GitHub Actions CI/CD
- Slither static analysis integration
- 58+ automated tests (unit, fuzz, invariant)

### Security
- OpenZeppelin upgradeable contracts
- 48-hour timelock on admin functions
- Slither-verified (11 low/info findings)
- Security audit checklist

---

## Version History Summary

| Version | Date | Description |
|---------|------|-------------|
| 1.0.0 | TBD | Initial production release |

## Migration Guides

### Upgrading to 1.0.0

This is the initial release. No migration needed.

### Future Upgrades

The contract uses UUPS proxy pattern. To upgrade:

1. Deploy new implementation
2. Call `upgradeTo(newImplementation)` via timelock
3. Wait for timelock delay (48 hours in production)
4. Execute the upgrade

---

## Links

- [Documentation](docs/)
- [Security Policy](docs/SECURITY.md)
- [Contributing Guide](CONTRIBUTING.md)
