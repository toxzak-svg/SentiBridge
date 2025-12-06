# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take security seriously at SentiBridge. If you discover a security vulnerability, please follow these steps:

### For Critical Vulnerabilities

**DO NOT** open a public GitHub issue.

1. **Email**: Send details to security@sentibridge.io
2. **Encrypt**: Use our PGP key (available at keys.sentibridge.io)
3. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes

### Response Timeline

| Phase | Timeframe |
|-------|-----------|
| Initial response | Within 48 hours |
| Severity assessment | Within 7 days |
| Fix timeline provided | Within 14 days |
| Public disclosure | 90 days after fix |

### Bug Bounty

We offer rewards for responsibly disclosed vulnerabilities:

| Severity | Reward Range |
|----------|-------------|
| Critical | $5,000 - $50,000 |
| High | $1,000 - $5,000 |
| Medium | $500 - $1,000 |
| Low | $100 - $500 |

Rewards are determined based on:
- Severity and exploitability
- Quality of the report
- Suggested fixes

### Scope

**In Scope:**
- Smart contracts (SentimentOracleV1, SentiBridgeTimelock)
- API authentication and authorization
- Worker key management
- Data integrity issues

**Out of Scope:**
- Social engineering attacks
- Physical attacks
- Third-party services
- Known issues in dependencies (unless exploitable)

## Security Measures

### Smart Contracts

- UUPS upgradeable proxy pattern
- OpenZeppelin AccessControl for role management
- Timelock controller (48-hour delay) for admin functions
- Circuit breaker for anomalous updates
- Slither static analysis in CI/CD
- 58+ automated tests (unit, fuzz, invariant)

### Infrastructure

- Environment variables for sensitive configuration
- API rate limiting per tier
- JWT authentication with secure secrets
- TLS encryption for all communications

### Development

- Pre-commit hooks for security scanning
- Dependency scanning with Dependabot
- Code review required for all changes
- Security-focused CI/CD checks

## Contact

- **Security Email**: security@sentibridge.io
- **General Contact**: contact@sentibridge.io
- **GitHub Security Advisories**: [Security Advisories](https://github.com/toxzak-svg/SentiBridge/security/advisories)

## Acknowledgments

We thank all security researchers who help keep SentiBridge secure. Contributors will be acknowledged (with permission) in our Hall of Fame.
