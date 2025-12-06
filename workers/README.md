# SentiBridge Workers

Off-chain Python workers for the SentiBridge sentiment oracle system.

## Components

- **Collectors**: Social media data collection from Twitter, Discord, Telegram
- **Processors**: NLP sentiment analysis and manipulation detection
- **Oracle**: Blockchain transaction submission

## Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
# Edit .env with your credentials
```

## Development

```bash
# Run tests
pytest

# Run linting
ruff check src tests
mypy src

# Format code
black src tests
```

## Security

- Never commit `.env` files
- Use AWS Secrets Manager or HashiCorp Vault for production secrets
- Private keys should be stored in HSM/KMS, never in application memory
