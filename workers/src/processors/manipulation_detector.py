"""
Manipulation Detection System.

Detects coordinated manipulation attempts in sentiment data:
- Volume anomalies
- Content similarity (copy-paste campaigns)
- Temporal clustering
- New account floods
- Cross-platform divergence
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from src.utils.logging import get_logger
from src.utils.validation import ManipulationFlags, SocialPost

logger = get_logger(__name__)


class ManipulationDetector:
    """
    Detect coordinated manipulation in social media data.

    Uses multiple signals to identify suspicious patterns
    that may indicate coordinated pump/dump schemes or
    fake sentiment campaigns.
    """

    def __init__(
        self,
        volume_baseline_window: int = 24,  # hours
        volume_spike_threshold: float = 3.0,  # 3x baseline
        similarity_threshold: float = 0.7,
        clustering_threshold: float = 0.8,
        new_account_threshold: float = 0.5,
        divergence_threshold: float = 0.5,
    ) -> None:
        self.volume_baseline_window = volume_baseline_window
        self.volume_spike_threshold = volume_spike_threshold
        self.similarity_threshold = similarity_threshold
        self.clustering_threshold = clustering_threshold
        self.new_account_threshold = new_account_threshold
        self.divergence_threshold = divergence_threshold

        # Historical data for baseline calculations
        self._volume_history: dict[str, list[tuple[datetime, int]]] = defaultdict(list)
        self._author_history: dict[str, list[SocialPost]] = defaultdict(list)

    async def analyze(
        self,
        posts: list[SocialPost],
        token: str,
    ) -> ManipulationFlags:
        """
        Analyze a batch of posts for manipulation signals.

        Args:
            posts: List of posts to analyze
            token: Token being analyzed

        Returns:
            ManipulationFlags with detection results
        """
        if not posts:
            return ManipulationFlags(is_suspicious=False, confidence=1.0)

        reasons = []
        adjustments = []

        # 1. Volume anomaly detection
        volume_result = await self._check_volume_anomaly(posts, token)
        if volume_result["is_anomaly"]:
            reasons.append(
                f"Volume spike: {volume_result['current']} vs baseline {volume_result['baseline']}"
            )
            adjustments.append(0.7)

        # 2. Content similarity check
        similarity_score = await self._check_content_similarity(posts)
        if similarity_score > self.similarity_threshold:
            reasons.append(f"High content similarity: {similarity_score:.2%}")
            adjustments.append(0.6)

        # 3. Temporal clustering
        clustering_score = await self._check_temporal_clustering(posts)
        if clustering_score > self.clustering_threshold:
            reasons.append(f"Suspicious temporal clustering: {clustering_score:.2%}")
            adjustments.append(0.7)

        # 4. New account ratio
        new_account_ratio = await self._check_new_accounts(posts)
        if new_account_ratio > self.new_account_threshold:
            reasons.append(f"High new account ratio: {new_account_ratio:.2%}")
            adjustments.append(0.8)

        # 5. Cross-platform divergence
        divergence = await self._check_cross_platform_divergence(posts)

        # Calculate overall confidence adjustment
        confidence = float(np.prod(adjustments)) if adjustments else 1.0

        return ManipulationFlags(
            is_suspicious=len(reasons) > 0,
            reasons=reasons,
            confidence=confidence,
            volume_anomaly=volume_result["is_anomaly"],
            content_similarity_score=similarity_score,
            temporal_clustering_score=clustering_score,
            new_account_ratio=new_account_ratio,
            cross_platform_divergence=divergence,
        )

    async def _check_volume_anomaly(
        self,
        posts: list[SocialPost],
        token: str,
    ) -> dict[str, Any]:
        """Check for unusual volume spikes."""
        current_volume = len(posts)

        # Get baseline from history
        history = self._volume_history.get(token, [])
        if not history:
            # No baseline yet, record and don't flag
            self._volume_history[token].append((datetime.utcnow(), current_volume))
            return {"is_anomaly": False, "current": current_volume, "baseline": current_volume}

        # Calculate baseline average
        cutoff = datetime.utcnow() - timedelta(hours=self.volume_baseline_window)
        recent_volumes = [vol for ts, vol in history if ts >= cutoff]

        if not recent_volumes:
            baseline = current_volume
        else:
            baseline = sum(recent_volumes) / len(recent_volumes)

        # Update history
        self._volume_history[token].append((datetime.utcnow(), current_volume))

        # Keep only recent history
        self._volume_history[token] = [
            (ts, vol) for ts, vol in self._volume_history[token] if ts >= cutoff
        ]

        is_anomaly = current_volume > baseline * self.volume_spike_threshold

        return {
            "is_anomaly": is_anomaly,
            "current": current_volume,
            "baseline": baseline,
        }

    async def _check_content_similarity(self, posts: list[SocialPost]) -> float:
        """
        Check for high content similarity (copy-paste campaigns).

        Uses simple n-gram similarity. For production, consider
        MinHash LSH for efficiency at scale.
        """
        if len(posts) < 2:
            return 0.0

        def get_ngrams(text: str, n: int = 3) -> set[str]:
            """Extract character n-grams."""
            text = text.lower()
            return {text[i : i + n] for i in range(len(text) - n + 1)}

        def jaccard_similarity(set1: set[str], set2: set[str]) -> float:
            """Calculate Jaccard similarity."""
            if not set1 or not set2:
                return 0.0
            intersection = len(set1 & set2)
            union = len(set1 | set2)
            return intersection / union if union > 0 else 0.0

        # Calculate pairwise similarities
        ngram_sets = [get_ngrams(p.text) for p in posts]
        similarities = []

        # Sample pairs if too many posts
        max_pairs = 1000
        n = len(posts)

        if n * (n - 1) / 2 > max_pairs:
            # Random sampling
            import random

            indices = list(range(n))
            for _ in range(max_pairs):
                i, j = random.sample(indices, 2)
                sim = jaccard_similarity(ngram_sets[i], ngram_sets[j])
                similarities.append(sim)
        else:
            for i in range(n):
                for j in range(i + 1, n):
                    sim = jaccard_similarity(ngram_sets[i], ngram_sets[j])
                    similarities.append(sim)

        if not similarities:
            return 0.0

        # Return proportion of highly similar pairs
        high_similarity_count = sum(1 for s in similarities if s > self.similarity_threshold)
        return high_similarity_count / len(similarities)

    async def _check_temporal_clustering(self, posts: list[SocialPost]) -> float:
        """
        Check for suspicious temporal clustering.

        Coordinated campaigns often show posts clustered
        in tight time windows.
        """
        if len(posts) < 5:
            return 0.0

        # Sort by timestamp
        sorted_posts = sorted(posts, key=lambda p: p.timestamp)

        # Calculate time gaps between consecutive posts
        gaps = []
        for i in range(1, len(sorted_posts)):
            gap = (sorted_posts[i].timestamp - sorted_posts[i - 1].timestamp).total_seconds()
            gaps.append(gap)

        if not gaps:
            return 0.0

        # Calculate coefficient of variation
        mean_gap = np.mean(gaps)
        std_gap = np.std(gaps)

        if mean_gap == 0:
            return 1.0  # All posts at same time

        cv = std_gap / mean_gap

        # Low CV indicates suspicious regularity
        # Very high CV is normal (sporadic posting)
        # Values around 0.5-1.0 are expected for organic activity

        if cv < 0.3:  # Suspiciously regular
            return 0.9
        elif cv < 0.5:
            return 0.6
        elif cv > 2.0:  # Very sporadic, potentially burst activity
            return 0.4
        else:
            return 0.2

    async def _check_new_accounts(self, posts: list[SocialPost]) -> float:
        """
        Check ratio of posts from new/low-quality accounts.

        Uses follower count as a proxy for account quality.
        """
        if not posts:
            return 0.0

        low_quality_count = 0
        for post in posts:
            # Consider account "new" if few followers
            if post.author_followers is not None:
                if post.author_followers < 50:
                    low_quality_count += 1
            elif not post.author_verified:
                # Unknown followers and not verified
                low_quality_count += 0.5

        return low_quality_count / len(posts)

    async def _check_cross_platform_divergence(self, posts: list[SocialPost]) -> float:
        """
        Check for divergence in sentiment across platforms.

        If one platform shows dramatically different sentiment
        than others, it may indicate targeted manipulation.
        """
        # Group by source
        by_source: dict[str, list[float]] = defaultdict(list)

        for post in posts:
            # Use engagement as a simple sentiment proxy for this check
            # In production, this would use actual sentiment scores
            engagement = post.engagement_count
            if post.author_followers and post.author_followers > 0:
                normalized = engagement / post.author_followers
            else:
                normalized = 0.0
            by_source[post.source].append(normalized)

        if len(by_source) < 2:
            return 0.0

        # Calculate mean per source
        means = {source: np.mean(vals) for source, vals in by_source.items()}

        if len(means) < 2:
            return 0.0

        # Calculate divergence as max difference between platform means
        values = list(means.values())
        max_val = max(values)
        min_val = min(values)

        if max_val == 0:
            return 0.0

        return (max_val - min_val) / max_val

    def calculate_quality_weights(
        self,
        posts: list[SocialPost],
    ) -> dict[str, float]:
        """
        Calculate quality weights for each post.

        Higher weights for:
        - Verified accounts
        - Accounts with more followers
        - Posts with higher engagement
        """
        weights = {}

        for post in posts:
            weight = 1.0

            # Verified bonus
            if post.author_verified:
                weight *= 1.5

            # Follower-based weight
            if post.author_followers:
                if post.author_followers > 10000:
                    weight *= 2.0
                elif post.author_followers > 1000:
                    weight *= 1.5
                elif post.author_followers < 100:
                    weight *= 0.7

            # Engagement bonus
            if post.engagement_count > 100:
                weight *= 1.3
            elif post.engagement_count > 10:
                weight *= 1.1

            weights[post.post_id] = weight

        # Normalize weights
        if weights:
            max_weight = max(weights.values())
            weights = {k: v / max_weight for k, v in weights.items()}

        return weights
