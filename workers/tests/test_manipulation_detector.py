"""Tests for manipulation detection."""

import time

import pytest


class TestManipulationDetector:
    """Tests for ManipulationDetector."""

    def test_normal_posts_not_flagged(self) -> None:
        """Test that normal posts are not flagged as manipulation."""
        from src.collectors.base import SocialPost
        from src.processors.manipulation_detector import ManipulationDetector

        detector = ManipulationDetector()

        # Create diverse, natural-looking posts
        posts = [
            SocialPost(
                id=f"post{i}",
                platform="twitter",
                content=content,
                author_id=f"author{i}",
                author_username=f"user{i}",
                timestamp=time.time() - i * 3600,  # Spread over hours
                follower_count=1000 + i * 100,
                account_age_days=365 + i * 30,
            )
            for i, content in enumerate([
                "Just bought some BTC, feeling good about the market",
                "ETH is showing strong technical signals",
                "Interesting price action on SOL today",
                "What do you think about MATIC's new partnership?",
                "Been holding since 2017, still bullish long term",
            ])
        ]

        result = detector.analyze_batch(posts)
        assert not result.is_manipulated
        assert result.confidence < 0.5

    def test_volume_spike_detection(self) -> None:
        """Test detection of abnormal volume spikes."""
        from src.collectors.base import SocialPost
        from src.processors.manipulation_detector import ManipulationDetector

        detector = ManipulationDetector()

        # Create posts that simulate a coordinated volume spike
        base_time = time.time()
        posts = [
            SocialPost(
                id=f"spam{i}",
                platform="twitter",
                content=f"BUY $TOKEN NOW! Version {i}",
                author_id=f"bot{i}",
                author_username=f"account{i}",
                timestamp=base_time - i * 2,  # All within minutes
                follower_count=10,
                account_age_days=5,
            )
            for i in range(100)  # Abnormally high volume
        ]

        result = detector.analyze_batch(posts)
        assert "volume_spike" in result.detection_reasons or result.confidence > 0.3

    def test_similar_content_detection(self) -> None:
        """Test detection of similar/duplicate content."""
        from src.collectors.base import SocialPost
        from src.processors.manipulation_detector import ManipulationDetector

        detector = ManipulationDetector()

        # Create posts with very similar content
        base_content = "Buy $SCAMTOKEN now before it moons! 1000x potential!"
        posts = [
            SocialPost(
                id=f"similar{i}",
                platform="twitter",
                content=base_content + f" #{i}",  # Tiny variation
                author_id=f"user{i}",
                author_username=f"account{i}",
                timestamp=time.time() - i * 60,
                follower_count=50,
                account_age_days=10,
            )
            for i in range(20)
        ]

        result = detector.analyze_batch(posts)
        # Should detect high content similarity
        assert result.confidence > 0.3 or "content_similarity" in result.detection_reasons

    def test_new_account_concentration(self) -> None:
        """Test detection of new account concentration."""
        from src.collectors.base import SocialPost
        from src.processors.manipulation_detector import ManipulationDetector

        detector = ManipulationDetector()

        # Create posts mostly from new accounts
        posts = [
            SocialPost(
                id=f"new{i}",
                platform="twitter",
                content=f"Great project! Bullish on $TOKEN {i}",
                author_id=f"newuser{i}",
                author_username=f"crypto_fan_{i}",
                timestamp=time.time() - i * 300,
                follower_count=5,
                account_age_days=3,  # Very new accounts
            )
            for i in range(30)
        ]

        result = detector.analyze_batch(posts)
        # Account freshness should be a warning sign
        assert result.confidence > 0.2

    def test_temporal_clustering_detection(self) -> None:
        """Test detection of temporal clustering (burst pattern)."""
        from src.collectors.base import SocialPost
        from src.processors.manipulation_detector import ManipulationDetector

        detector = ManipulationDetector()

        # Create posts clustered in time
        base_time = time.time()
        posts = [
            SocialPost(
                id=f"burst{i}",
                platform="twitter",
                content=f"Amazing token! {i}",
                author_id=f"user{i}",
                author_username=f"trader{i}",
                timestamp=base_time - i * 0.5,  # All within seconds
                follower_count=100,
                account_age_days=180,
            )
            for i in range(50)
        ]

        result = detector.analyze_batch(posts)
        # Temporal clustering should raise flags
        assert "temporal_clustering" in result.detection_reasons or result.confidence > 0.3

    def test_empty_batch(self) -> None:
        """Test handling of empty post batch."""
        from src.processors.manipulation_detector import ManipulationDetector

        detector = ManipulationDetector()
        result = detector.analyze_batch([])

        assert not result.is_manipulated
        assert result.confidence == 0.0

    def test_single_post(self) -> None:
        """Test handling of single post."""
        from src.collectors.base import SocialPost
        from src.processors.manipulation_detector import ManipulationDetector

        detector = ManipulationDetector()

        post = SocialPost(
            id="single1",
            platform="twitter",
            content="Just a normal post about crypto",
            author_id="user1",
            author_username="normaluser",
            timestamp=time.time(),
            follower_count=5000,
            account_age_days=365,
        )

        result = detector.analyze_batch([post])
        assert not result.is_manipulated


class TestManipulationResult:
    """Tests for ManipulationResult dataclass."""

    def test_result_creation(self) -> None:
        """Test creating manipulation result."""
        from src.processors.manipulation_detector import ManipulationResult

        result = ManipulationResult(
            is_manipulated=True,
            confidence=0.85,
            detection_reasons=["volume_spike", "content_similarity"],
        )

        assert result.is_manipulated
        assert result.confidence == 0.85
        assert len(result.detection_reasons) == 2

    def test_result_defaults(self) -> None:
        """Test manipulation result defaults."""
        from src.processors.manipulation_detector import ManipulationResult

        result = ManipulationResult(
            is_manipulated=False,
            confidence=0.1,
        )

        assert result.detection_reasons == []
        assert result.flagged_posts == []


class TestDetectionThresholds:
    """Tests for detection threshold configuration."""

    def test_custom_thresholds(self) -> None:
        """Test that custom thresholds are respected."""
        from src.processors.manipulation_detector import ManipulationDetector

        # Create detector with strict thresholds
        detector = ManipulationDetector(
            volume_spike_threshold=1.5,  # Lower threshold
            similarity_threshold=0.7,  # Lower threshold
            manipulation_threshold=0.3,  # Lower threshold
        )

        assert detector.volume_spike_threshold == 1.5
        assert detector.similarity_threshold == 0.7
        assert detector.manipulation_threshold == 0.3

    def test_default_thresholds(self) -> None:
        """Test default threshold values."""
        from src.processors.manipulation_detector import ManipulationDetector

        detector = ManipulationDetector()

        assert detector.volume_spike_threshold == 3.0
        assert detector.similarity_threshold == 0.8
        assert detector.manipulation_threshold == 0.6
