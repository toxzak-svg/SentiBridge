# SentiBridge Development Guide

## Prerequisites

- **Node.js** 18+ (for Subgraph)
- **Python** 3.11+ (for workers and API)
- **Rust** (for Foundry)
- **Docker** and Docker Compose
- **Git**

## Project Structure

```
sentibridge/
├── contracts/                      # Solidity smart contracts (Foundry)
│   ├── src/
│   │   ├── SentimentOracleV1.sol  # Main oracle contract
│   │   ├── interfaces/
│   │   │   └── ISentimentOracle.sol
│   │   └── libraries/
│   │       └── SentimentMath.sol
│   ├── test/
│   │   ├── SentimentOracle.t.sol  # Unit tests
│   │   └── SentimentOracle.fuzz.t.sol  # Fuzz tests
│   ├── script/
│   │   ├── Deploy.s.sol           # Deployment script
│   │   └── Upgrade.s.sol          # Upgrade script
│   └── foundry.toml
│
├── workers/                        # Off-chain Python services
│   ├── src/
│   │   ├── collectors/            # Social media collectors
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── twitter.py
│   │   │   ├── discord.py
│   │   │   └── telegram.py
│   │   ├── processors/            # NLP and validation
│   │   │   ├── __init__.py
│   │   │   ├── nlp_analyzer.py
│   │   │   └── manipulation_detector.py
│   │   ├── oracle/                # Blockchain interaction
│   │   │   ├── __init__.py
│   │   │   ├── submitter.py
│   │   │   └── signer.py
│   │   ├── security/              # Security utilities
│   │   │   ├── __init__.py
│   │   │   ├── secrets_manager.py
│   │   │   └── rate_limiter.py
│   │   └── config.py
│   ├── tests/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── pyproject.toml
│
├── api/                            # FastAPI application
│   ├── src/
│   │   ├── main.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── sentiment.py
│   │   │   ├── webhooks.py
│   │   │   └── health.py
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   └── rate_limit.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── requests.py
│   │   │   └── responses.py
│   │   └── security/
│   │       ├── __init__.py
│   │       └── api_keys.py
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
│
├── subgraph/                       # The Graph indexer
│   ├── src/
│   │   └── mapping.ts
│   ├── schema.graphql
│   ├── subgraph.yaml
│   └── package.json
│
├── infrastructure/                 # Infrastructure as Code
│   ├── terraform/
│   │   ├── modules/
│   │   │   ├── vpc/
│   │   │   ├── rds/
│   │   │   ├── elasticache/
│   │   │   └── lambda/
│   │   ├── environments/
│   │   │   ├── staging/
│   │   │   └── production/
│   │   └── main.tf
│   └── docker/
│       ├── api.Dockerfile
│       └── worker.Dockerfile
│
├── docs/                           # Documentation
│   ├── ARCHITECTURE.md
│   ├── SECURITY.md
│   ├── DEVELOPMENT.md
│   └── API.md
│
├── scripts/                        # Utility scripts
│   ├── setup.sh
│   └── deploy.sh
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── security.yml
│       └── deploy.yml
│
├── .env.example
├── docker-compose.yml
└── README.md
```

## Local Development Setup

### 1. Clone and Install Dependencies

```bash
# Clone repository
git clone https://github.com/your-org/sentibridge.git
cd sentibridge

# Install Foundry (smart contracts)
curl -L https://foundry.paradigm.xyz | bash
foundryup

# Install Python dependencies
cd workers
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Install API dependencies
cd ../api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install Subgraph dependencies
cd ../subgraph
npm install
```

### 2. Environment Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit with your local settings
# NEVER commit real secrets to git
```

**.env.example**:
```bash
# Environment
ENVIRONMENT=development

# Blockchain
RPC_URL=http://localhost:8545
CHAIN_ID=31337

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sentibridge

# Redis
REDIS_URL=redis://localhost:6379

# API (for local development only)
API_SECRET_KEY=dev-secret-key-change-in-production

# Social APIs (use test credentials)
TWITTER_BEARER_TOKEN=
DISCORD_BOT_TOKEN=
TELEGRAM_BOT_TOKEN=
```

### 3. Start Local Infrastructure

```bash
# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Start local blockchain (Anvil)
anvil --chain-id 31337
```

### 4. Deploy Contracts Locally

```bash
cd contracts

# Build contracts
forge build

# Run tests
forge test

# Deploy to local Anvil
forge script script/Deploy.s.sol --rpc-url http://localhost:8545 --broadcast
```

### 5. Run Services

```bash
# Terminal 1: API
cd api
source venv/bin/activate
uvicorn src.main:app --reload --port 8000

# Terminal 2: Workers (manual trigger for development)
cd workers
source venv/bin/activate
python -m src.main --once
```

## Testing

### Smart Contract Tests

```bash
cd contracts

# Unit tests
forge test

# Verbose output
forge test -vvv

# Fuzz tests
forge test --match-test "Fuzz"

# Coverage
forge coverage

# Gas report
forge test --gas-report
```

### Python Tests

```bash
cd workers
source venv/bin/activate

# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/test_nlp_analyzer.py -v
```

### API Tests

```bash
cd api
source venv/bin/activate

# Run tests
pytest

# With coverage
pytest --cov=src --cov-report=html
```

## Code Quality

### Solidity

```bash
cd contracts

# Static analysis
slither src/

# Format
forge fmt

# Check formatting
forge fmt --check
```

### Python

```bash
# Lint
ruff check .

# Format
black .

# Type checking
mypy src/

# Security scan
bandit -r src/
```

## Deployment

### Staging (Polygon Amoy)

```bash
cd contracts

# Set environment variables
export RPC_URL="https://rpc-amoy.polygon.technology"
export PRIVATE_KEY="your-deployer-key"

# Deploy
forge script script/Deploy.s.sol \
    --rpc-url $RPC_URL \
    --private-key $PRIVATE_KEY \
    --broadcast \
    --verify
```

### Production (Polygon Mainnet)

Production deployments are handled through CI/CD. See `.github/workflows/deploy.yml`.

**Requirements:**
1. Approved PR merged to `main`
2. All tests passing
3. Security scan clean
4. Manual approval in GitHub Actions

## Adding a New Social Platform

1. Create collector in `workers/src/collectors/`:

```python
# workers/src/collectors/new_platform.py
from .base import BaseCollector, SocialPost

class NewPlatformCollector(BaseCollector):
    def __init__(self, credentials: dict):
        super().__init__()
        self.client = NewPlatformClient(credentials)
    
    async def collect(self, tokens: list[str]) -> list[SocialPost]:
        posts = []
        for token in tokens:
            raw_posts = await self.client.search(token)
            for post in raw_posts:
                posts.append(SocialPost(
                    source="new_platform",
                    text=post.content,
                    author_id=post.author_id,
                    timestamp=post.created_at,
                    metadata={"platform_specific": post.extra}
                ))
        return posts
```

2. Register in collector factory
3. Add tests
4. Update documentation

## Troubleshooting

### Common Issues

**Foundry compilation errors:**
```bash
# Update Foundry
foundryup

# Clear cache
forge clean
forge build
```

**Python import errors:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

**Database connection issues:**
```bash
# Check PostgreSQL is running
docker-compose ps

# Check connection
psql $DATABASE_URL -c "SELECT 1"
```

### Getting Help

1. Check existing issues on GitHub
2. Search documentation
3. Ask in Discord #dev-support channel
4. Create a new issue with reproduction steps

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`forge test && pytest`)
5. Commit with conventional commits (`git commit -m 'feat: add amazing feature'`)
6. Push to your fork (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Commit Message Format

```
type(scope): description

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
- `feat(contracts): add token whitelist functionality`
- `fix(api): correct rate limit calculation`
- `docs: update deployment guide`
