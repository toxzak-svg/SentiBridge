# Contributing to SentiBridge

Thank you for your interest in contributing to SentiBridge! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Submitting Changes](#submitting-changes)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Security](#security)

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct:

- Be respectful and inclusive
- Focus on constructive feedback
- Assume good intentions
- Report unacceptable behavior to the maintainers

## Getting Started

### Prerequisites

- **Foundry** (v1.0.0+): Smart contract development
- **Python 3.11+**: Workers and API development
- **Docker & Docker Compose**: Local development environment
- **Node.js 18+**: Subgraph development (optional)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/sentibridge.git
   cd sentibridge
   ```

2. **Install dependencies**
   ```bash
   make install
   ```

3. **Set up environment**
   ```bash
   cp contracts/.env.example contracts/.env
   cp workers/.env.example workers/.env
   cp api/.env.example api/.env
   ```

4. **Run tests**
   ```bash
   make test
   ```

### Project Structure

```
sentibridge/
├── contracts/          # Solidity smart contracts (Foundry)
│   ├── src/           # Contract source files
│   ├── test/          # Contract tests
│   └── script/        # Deployment scripts
├── workers/           # Python off-chain workers
│   ├── collectors/    # Data collection modules
│   ├── processors/    # Sentiment analysis
│   └── oracle_submitter/  # Chain submission
├── api/               # FastAPI REST API
├── subgraph/          # The Graph indexer
└── docs/              # Documentation
```

## Development Workflow

### 1. Create a Branch

```bash
# For features
git checkout -b feature/your-feature-name

# For bugs
git checkout -b fix/bug-description

# For documentation
git checkout -b docs/what-you-are-documenting
```

### 2. Make Changes

- Follow the coding standards below
- Write tests for new functionality
- Update documentation as needed

### 3. Test Your Changes

```bash
# Run all tests
make test

# Run specific tests
cd contracts && forge test --match-test testYourFunction

# Run linting
make lint

# Run security checks
make security
```

### 4. Commit Your Changes

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Format: <type>(<scope>): <description>

# Examples:
git commit -m "feat(contracts): add batch update function"
git commit -m "fix(api): correct rate limiting calculation"
git commit -m "docs: update deployment guide"
git commit -m "test(oracle): add fuzz tests for validation"
git commit -m "chore: update dependencies"
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, semicolons, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `test`: Adding/updating tests
- `chore`: Maintenance tasks

### 5. Push and Create PR

```bash
git push origin your-branch-name
```

Then create a Pull Request on GitHub.

## Submitting Changes

### Pull Request Guidelines

1. **Title**: Use conventional commit format
2. **Description**: Include:
   - What changes were made
   - Why changes were needed
   - How to test the changes
   - Any breaking changes
3. **Link Issues**: Reference related issues with `Fixes #123`
4. **Tests**: Ensure all tests pass
5. **Reviews**: Request review from maintainers

### Review Process

1. Automated checks must pass (CI/CD, linting, tests)
2. At least one maintainer approval required
3. All conversations must be resolved
4. Squash merge to main branch

## Coding Standards

### Solidity

- Follow [Solidity Style Guide](https://docs.soliditylang.org/en/latest/style-guide.html)
- Use NatSpec comments for all public functions
- Maximum line length: 100 characters
- Run `forge fmt` before committing

```solidity
/**
 * @notice Updates sentiment for a token
 * @dev Only callable by OPERATOR_ROLE
 * @param token The token address
 * @param score Sentiment score (-1e18 to +1e18)
 * @param sampleSize Number of posts analyzed
 * @param confidence Confidence in basis points (0-10000)
 */
function updateSentiment(
    address token,
    int128 score,
    uint32 sampleSize,
    uint16 confidence
) external;
```

### Python

- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use type hints for all functions
- Run `ruff check` and `ruff format` before committing

```python
async def analyze_sentiment(
    text: str,
    model: str = "finbert"
) -> SentimentResult:
    """
    Analyze sentiment of text using specified model.
    
    Args:
        text: The text to analyze
        model: Model identifier (default: finbert)
    
    Returns:
        SentimentResult with score and confidence
    
    Raises:
        ValueError: If text is empty
    """
    ...
```

### Git Commit Messages

- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit first line to 72 characters
- Reference issues and PRs in body

## Testing Guidelines

### Smart Contracts

We use Foundry for testing with three levels:

1. **Unit Tests**: Test individual functions
   ```solidity
   function test_UpdateSentiment_ValidInput() public { ... }
   ```

2. **Fuzz Tests**: Property-based testing
   ```solidity
   function testFuzz_ScoreValidation(int128 score) public { ... }
   ```

3. **Invariant Tests**: State invariants
   ```solidity
   function invariant_TotalUpdatesMonotonic() public { ... }
   ```

**Coverage target**: >90% for critical paths

### Python

- Use pytest for testing
- Mock external services
- Test both happy path and error cases

```bash
cd workers && pytest -v --cov=src
```

## Security

### Reporting Vulnerabilities

**DO NOT** open public issues for security vulnerabilities.

Instead:
1. Email security@sentibridge.io
2. Include detailed description
3. Wait for acknowledgment within 48 hours
4. Allow 90 days for fix before disclosure

### Security Best Practices

- Never commit private keys or secrets
- Use `.env` files for sensitive configuration
- Review all dependencies for vulnerabilities
- Follow the [Security Checklist](docs/SECURITY_AUDIT_CHECKLIST.md)

## Questions?

- Open a [Discussion](https://github.com/your-org/sentibridge/discussions)
- Join our [Discord](https://discord.gg/sentibridge)
- Read the [Documentation](docs/)

---

Thank you for contributing to SentiBridge! 🚀
