"""Main worker orchestrator coordinating collection, analysis, and submission."""

import asyncio
import signal
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.collectors.base import BaseCollector, SocialPost
from src.collectors.discord import DiscordCollector
from src.collectors.telegram import TelegramCollector
from src.collectors.twitter import TwitterCollector
from src.config import get_settings
from src.oracle.submitter import OracleSubmitter, TransactionStatus, create_key_manager
from src.processors.manipulation_detector import ManipulationDetector
from src.processors.nlp_analyzer import EnsembleSentimentAnalyzer
from src.utils.logging import get_logger
from src.utils.validation import SentimentScore

logger = get_logger(__name__)


class WorkerState(str, Enum):
    """Worker lifecycle state."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class TokenSentimentData:
    """Aggregated sentiment data for a token."""

    token_symbol: str
    posts: list[SocialPost] = field(default_factory=list)
    total_score: float = 0.0
    total_weight: float = 0.0
    volume: int = 0
    manipulation_score: float = 0.0
    last_update: float = 0.0

    @property
    def weighted_score(self) -> int:
        """Calculate weighted average score (0-10000)."""
        if self.total_weight == 0:
            return 5000  # Neutral
        raw = self.total_score / self.total_weight
        # Clamp to valid range
        return max(0, min(10000, int(raw)))


@dataclass
class WorkerMetrics:
    """Worker operational metrics."""

    posts_collected: int = 0
    posts_analyzed: int = 0
    posts_filtered: int = 0
    transactions_submitted: int = 0
    transactions_confirmed: int = 0
    transactions_failed: int = 0
    errors: int = 0
    uptime_seconds: float = 0.0
    last_submission: float = 0.0


class SentimentWorker:
    """Main worker orchestrating the sentiment pipeline."""

    def __init__(
        self,
        collectors: list[BaseCollector] | None = None,
        analyzer: EnsembleSentimentAnalyzer | None = None,
        detector: ManipulationDetector | None = None,
        submitter: OracleSubmitter | None = None,
        collection_interval: int = 300,  # 5 minutes
        submission_interval: int = 300,  # 5 minutes
        batch_size: int = 20,
    ):
        """Initialize worker with optional component injection."""
        self._collectors = collectors or []
        self._analyzer = analyzer
        self._detector = detector
        self._submitter = submitter
        self._collection_interval = collection_interval
        self._submission_interval = submission_interval
        self._batch_size = batch_size

        self._state = WorkerState.STOPPED
        self._metrics = WorkerMetrics()
        self._start_time: float | None = None

        # Token tracking
        self._token_data: dict[str, TokenSentimentData] = {}
        self._tracked_tokens: set[str] = set()

        # Task management
        self._tasks: list[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()

    @property
    def state(self) -> WorkerState:
        """Get current worker state."""
        return self._state

    @property
    def metrics(self) -> WorkerMetrics:
        """Get worker metrics."""
        if self._start_time:
            self._metrics.uptime_seconds = time.time() - self._start_time
        return self._metrics

    async def initialize(self) -> None:
        """Initialize all worker components."""
        logger.info("worker_initializing")
        self._state = WorkerState.STARTING

        settings = get_settings()

        try:
            # Initialize collectors if not provided
            if not self._collectors:
                self._collectors = await self._create_default_collectors()

            # Initialize analyzer
            if not self._analyzer:
                self._analyzer = EnsembleSentimentAnalyzer()
                await self._analyzer.initialize()

            # Initialize manipulation detector
            if not self._detector:
                self._detector = ManipulationDetector()

            # Initialize submitter
            if not self._submitter:
                key_manager = create_key_manager(use_kms=settings.use_aws_kms)
                self._submitter = OracleSubmitter(key_manager=key_manager)
                await self._submitter.initialize()

            # Load tracked tokens from config
            self._tracked_tokens = set(settings.tracked_tokens or ["BTC", "ETH"])

            # Initialize token data
            for token in self._tracked_tokens:
                self._token_data[token] = TokenSentimentData(token_symbol=token)

            logger.info(
                "worker_initialized",
                collectors=len(self._collectors),
                tracked_tokens=list(self._tracked_tokens),
            )

        except Exception as e:
            logger.error("worker_initialization_failed", error=str(e))
            self._state = WorkerState.ERROR
            raise

    async def _create_default_collectors(self) -> list[BaseCollector]:
        """Create default collectors based on configuration."""
        collectors: list[BaseCollector] = []
        settings = get_settings()

        # Twitter/X collector
        if settings.twitter_bearer_token:
            try:
                twitter = TwitterCollector()
                await twitter.initialize()
                collectors.append(twitter)
                logger.info("twitter_collector_enabled")
            except Exception as e:
                logger.warning("twitter_collector_failed", error=str(e))

        # Discord collector
        if settings.discord_bot_token:
            try:
                discord = DiscordCollector()
                await discord.initialize()
                collectors.append(discord)
                logger.info("discord_collector_enabled")
            except Exception as e:
                logger.warning("discord_collector_failed", error=str(e))

        # Telegram collector
        if settings.telegram_api_id and settings.telegram_api_hash:
            try:
                telegram = TelegramCollector()
                await telegram.initialize()
                collectors.append(telegram)
                logger.info("telegram_collector_enabled")
            except Exception as e:
                logger.warning("telegram_collector_failed", error=str(e))

        if not collectors:
            logger.warning("no_collectors_available")

        return collectors

    async def start(self) -> None:
        """Start the worker."""
        if self._state not in (WorkerState.STOPPED, WorkerState.ERROR):
            raise RuntimeError(f"Cannot start worker in state {self._state}")

        await self.initialize()

        self._state = WorkerState.RUNNING
        self._start_time = time.time()
        self._shutdown_event.clear()

        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._collection_loop(), name="collection"),
            asyncio.create_task(self._submission_loop(), name="submission"),
            asyncio.create_task(self._health_check_loop(), name="health"),
        ]

        logger.info("worker_started")

    async def stop(self) -> None:
        """Stop the worker gracefully."""
        if self._state != WorkerState.RUNNING:
            return

        logger.info("worker_stopping")
        self._state = WorkerState.STOPPING
        self._shutdown_event.set()

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)

        # Close components
        for collector in self._collectors:
            await collector.close()

        if self._analyzer:
            await self._analyzer.close()

        if self._submitter:
            await self._submitter.close()

        self._state = WorkerState.STOPPED
        logger.info("worker_stopped", metrics=self._metrics.__dict__)

    async def _collection_loop(self) -> None:
        """Main collection loop."""
        while not self._shutdown_event.is_set():
            try:
                await self._collect_and_analyze()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("collection_loop_error", error=str(e))
                self._metrics.errors += 1

            # Wait for next interval
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self._collection_interval,
                )
            except asyncio.TimeoutError:
                pass

    async def _collect_and_analyze(self) -> None:
        """Collect posts from all sources and analyze."""
        logger.debug("collection_cycle_starting")

        for token in self._tracked_tokens:
            all_posts: list[SocialPost] = []

            # Collect from all sources
            for collector in self._collectors:
                try:
                    # Build search query for this token
                    keywords = self._get_token_keywords(token)
                    posts = await collector.collect(keywords, max_results=100)
                    all_posts.extend(posts)
                    self._metrics.posts_collected += len(posts)
                except Exception as e:
                    logger.warning(
                        "collector_error",
                        collector=collector.__class__.__name__,
                        token=token,
                        error=str(e),
                    )

            if not all_posts:
                continue

            # Check for manipulation
            manipulation_result = self._detector.analyze_batch(all_posts)

            if manipulation_result.is_manipulated:
                logger.warning(
                    "manipulation_detected",
                    token=token,
                    score=manipulation_result.confidence,
                    reasons=manipulation_result.detection_reasons,
                )
                self._metrics.posts_filtered += len(all_posts)
                continue

            # Analyze sentiment for each post
            token_data = self._token_data[token]

            for post in all_posts:
                # Apply manipulation-based weight reduction
                weight = 1.0 - (manipulation_result.confidence * 0.5)

                # Additional weight factors
                if post.is_verified:
                    weight *= 1.5
                if post.account_age_days and post.account_age_days < 30:
                    weight *= 0.5
                if post.follower_count and post.follower_count > 10000:
                    weight *= 1.2

                # Analyze sentiment
                try:
                    result = await self._analyzer.analyze(post.content)
                    score_scaled = int(result.score * 10000)  # Convert to 0-10000

                    token_data.total_score += score_scaled * weight
                    token_data.total_weight += weight
                    token_data.volume += 1
                    token_data.posts.append(post)

                    self._metrics.posts_analyzed += 1
                except Exception as e:
                    logger.warning("analysis_error", post_id=post.id, error=str(e))

            token_data.manipulation_score = manipulation_result.confidence
            token_data.last_update = time.time()

        logger.debug(
            "collection_cycle_complete",
            posts_collected=self._metrics.posts_collected,
            posts_analyzed=self._metrics.posts_analyzed,
        )

    def _get_token_keywords(self, token: str) -> list[str]:
        """Get search keywords for a token."""
        # Common variations
        keywords = [f"${token}", token]

        # Add common name mappings
        name_map = {
            "BTC": ["bitcoin", "btc"],
            "ETH": ["ethereum", "eth", "ether"],
            "SOL": ["solana", "sol"],
            "DOGE": ["dogecoin", "doge"],
            "MATIC": ["polygon", "matic"],
            "LINK": ["chainlink", "link"],
            "UNI": ["uniswap", "uni"],
            "AAVE": ["aave"],
            "CRV": ["curve", "crv"],
        }

        if token.upper() in name_map:
            keywords.extend(name_map[token.upper()])

        return keywords

    async def _submission_loop(self) -> None:
        """Main submission loop."""
        while not self._shutdown_event.is_set():
            try:
                await self._submit_updates()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("submission_loop_error", error=str(e))
                self._metrics.errors += 1

            # Wait for next interval
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self._submission_interval,
                )
            except asyncio.TimeoutError:
                pass

    async def _submit_updates(self) -> None:
        """Submit accumulated sentiment updates."""
        if not self._submitter:
            return

        # Prepare batch
        updates: list[tuple[str, SentimentScore, int, dict[str, Any]]] = []

        for token, data in self._token_data.items():
            if data.volume == 0:
                continue

            # Skip if manipulation score is too high
            if data.manipulation_score > 0.7:
                logger.warning(
                    "skipping_manipulated_token",
                    token=token,
                    manipulation_score=data.manipulation_score,
                )
                continue

            score = SentimentScore(
                score=data.weighted_score,
                confidence=max(0, 1 - data.manipulation_score),
            )

            source_data = {
                "token": token,
                "posts_analyzed": data.volume,
                "manipulation_score": data.manipulation_score,
                "timestamp": data.last_update,
                "sources": len(self._collectors),
            }

            updates.append((token, score, data.volume, source_data))

        if not updates:
            logger.debug("no_updates_to_submit")
            return

        # Submit in batches
        for i in range(0, len(updates), self._batch_size):
            batch = updates[i : i + self._batch_size]

            try:
                receipt = await self._submitter.submit_batch(batch)
                self._metrics.transactions_submitted += 1

                if receipt.status == TransactionStatus.CONFIRMED:
                    self._metrics.transactions_confirmed += 1
                    logger.info(
                        "batch_submitted",
                        tx_hash=receipt.tx_hash,
                        tokens=[u[0] for u in batch],
                    )
                else:
                    self._metrics.transactions_failed += 1
                    logger.error(
                        "batch_submission_failed",
                        error=receipt.error,
                        tokens=[u[0] for u in batch],
                    )

                self._metrics.last_submission = time.time()

            except Exception as e:
                logger.error("batch_submission_error", error=str(e))
                self._metrics.transactions_failed += 1

        # Reset token data for next cycle
        for token in self._tracked_tokens:
            self._token_data[token] = TokenSentimentData(token_symbol=token)

    async def _health_check_loop(self) -> None:
        """Periodic health checks."""
        while not self._shutdown_event.is_set():
            try:
                # Log metrics periodically
                logger.info(
                    "worker_health_check",
                    state=self._state,
                    posts_collected=self._metrics.posts_collected,
                    posts_analyzed=self._metrics.posts_analyzed,
                    transactions_confirmed=self._metrics.transactions_confirmed,
                    uptime=self.metrics.uptime_seconds,
                )

                # Check component health
                for collector in self._collectors:
                    if not await collector.health_check():
                        logger.warning(
                            "collector_unhealthy",
                            collector=collector.__class__.__name__,
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("health_check_error", error=str(e))

            # Check every 60 seconds
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=60,
                )
            except asyncio.TimeoutError:
                pass


async def main() -> None:
    """Main entry point."""
    worker = SentimentWorker()

    # Setup signal handlers
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("shutdown_signal_received")
        asyncio.create_task(worker.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await worker.start()

        # Keep running until shutdown
        while worker.state == WorkerState.RUNNING:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        if worker.state == WorkerState.RUNNING:
            await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
