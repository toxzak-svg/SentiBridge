**Overview**: Short-lived guide for AI coding agents working on SentiBridge.

- **Project purpose**: Decentralized sentiment oracle — off-chain workers collect and analyze social data, submit aggregated scores on-chain via `SentimentOracleV1` (contracts/src), and expose results through a tiered FastAPI (`api/src`).

**Architecture (high level)**
- **Workers**: `workers/src/worker.py` orchestrates collectors (`workers/src/collectors/*`), NLP analyzers (`workers/src/processors/*`), manipulation detection, and `OracleSubmitter` for on-chain submissions.
- **API**: `api/src/main.py` creates a FastAPI app, includes routers in `api/src/routers/` (notably `sentiment.py`) and enforces usage middleware (`api/src/middleware/usage.py`). Config is in `api/src/config.py` (Pydantic Settings — `.env` supported).
- **Contracts**: `contracts/src/` contains Foundry-based Solidity contracts (UUPS upgradeable Oracle). Use `forge` for build/test/deploy.
- **Indexing**: `subgraph/` contains The Graph mapping (`subgraph/src/mapping.ts`) and schema; used for history queries.

**Key files to inspect for patterns**
- API entry: `api/src/main.py` — lifecycle, Redis, Prometheus, Sentry initialization.
- API routers: `api/src/routers/*.py` — implement tier checks, dependencies, response models in `api/src/models.py`.
- Worker orchestrator: `workers/src/worker.py` — collection/submission loops, batching, weighting, and manipulation thresholds.
- Collectors & processors: `workers/src/collectors/` and `workers/src/processors/` — conform to `BaseCollector` and analyzer interfaces.
- On-chain submitter & keys: `workers/src/oracle/submitter.py` and `contracts/` — signing may use AWS KMS (check config flag `use_aws_kms`).

**Developer workflows & useful commands**
- Install all deps: `make install` (runs install for contracts, workers, api).
- Start API locally: `make dev-api` or `cd api && uvicorn src.main:app --reload --port 8000`.
- Start workers locally (dev): `make dev-workers` (Makefile calls `python -m orchestrator.main`).
- Contracts: `make build-contracts`, tests: `make test-contracts` (`forge test`).
- Run Python tests: `make test-workers` and `make test-api` (use `pytest -v`).
- Run everything via Docker: `make docker-up` / `make docker-down`.

**Conventions & patterns to follow**
- Env/config: services use Pydantic `Settings` with `env_file=".env"` — prefer reading/writing env-vars via this model.
- API auth: API keys expected in header `X-API-Key`; rate limits and tier checks are enforced in `api/src/auth` and middleware — look there before changing auth flows.
- Worker design: components are injected but default to constructing from config; unit tests commonly instantiate components with mocks.
- Sentiment scoring: scores are 0–10000 (see `workers/src/worker.py` and `api/src/routers/sentiment.py` conversions).
- Manipulation: tokens with `manipulation_score > 0.7` are skipped; update tests if changing thresholds.

**Integration points & external deps**
- Polygon RPC & contracts: `polygon_rpc_url` and `oracle_contract_address` in API config and workers; deploy via Foundry scripts in `contracts/script/`.
- Redis: initialized in `api/src/main.py` (used by auth/middleware). Ensure Redis URL in env.
- Prometheus / Sentry hooks are optional flags in config (`prometheus_enabled`, `sentry_dsn`).
- AWS KMS: optional key manager (workers) controlled by config flag — check `workers/src/oracle/create_key_manager`.

**Testing & debugging tips**
- Use `make test-workers` and `make test-api` for unit tests. For contracts use `forge test` in `contracts/`.
- Developer quick-run: `make dev-api` and `make dev-workers` (or run `workers/run.py`) while pointing to a local Anvil/Anvil-like node for end-to-end testing.
- Logs: worker logger uses structured logs (`workers/src/utils/logging.py`) — search for `get_logger` to format debugging output.

**What AI agents should avoid changing without review**
- On-chain contract interfaces and storage layout in `contracts/src/` (UUPS + proxy). Any change requires careful migration and re-deployment.
- API authentication and rate-limit logic in `api/src/auth` and `api/src/middleware/usage.py`.
- Signing and key-management code paths (AWS KMS toggles) used by the `OracleSubmitter`.

**If you need to make a code change**
1. Run the relevant tests: `make test-api`, `make test-workers`, `make test-contracts`.
2. Follow formatting/lint: `make format` and `make lint`.
3. For contract changes run `forge build` and `forge test` and check sizes with `make check-sizes`.

**Where to ask for context**
- For API design questions: inspect `api/src/routers/` and `api/src/models.py` and open a short PR with tests.
- For worker/runtime changes: inspect `workers/src/worker.py` and processors/collectors; prefer adding unit tests under `workers/tests/`.

If any section is unclear or you want more detail (examples, env vars list, or component diagrams), say which area to expand.
