"""Manipulation detection utilities used by the workers.

Provides multiple lightweight heuristics (volume, content similarity,
duplicate detection, temporal clustering, burst detection, new-account ratio,
and cross-platform divergence) and a backward-compatible synchronous wrapper
used by older tests.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
import asyncio

import numpy as np

from src.utils.logging import get_logger
from src.utils.validation import ManipulationFlags, SocialPost

logger = get_logger(__name__)


class ManipulationDetector:
    def __init__(
        self,
        volume_baseline_window: int = 24,  # hours
        volume_spike_threshold: float = 3.0,
        similarity_threshold: float = 0.8,
        clustering_threshold: float = 0.95,
        new_account_threshold: float = 0.5,
        divergence_threshold: float = 0.5,
        manipulation_threshold: float = 0.6,
        duplicate_threshold: float = 0.6,
        burst_window_seconds: int = 300,
        burst_ratio_threshold: float = 0.6,
    ) -> None:
        self.volume_baseline_window = volume_baseline_window
        self.volume_spike_threshold = volume_spike_threshold
        self.similarity_threshold = similarity_threshold
        self.clustering_threshold = clustering_threshold
        self.new_account_threshold = new_account_threshold
        self.divergence_threshold = divergence_threshold
        self.manipulation_threshold = manipulation_threshold
        self.duplicate_threshold = duplicate_threshold
        self.burst_window_seconds = burst_window_seconds
        self.burst_ratio_threshold = burst_ratio_threshold

        # Simple in-memory history for baseline calculations
        self._volume_history: dict[str, list[tuple[datetime, int]]] = defaultdict(list)

    async def analyze(self, posts: list[SocialPost], token: str) -> ManipulationFlags:
        if not posts:
            return ManipulationFlags(is_suspicious=False, confidence=1.0)

        reasons: list[str] = []
        adjustments: list[float] = []

        # Volume anomaly
        volume_result = await self._check_volume_anomaly(posts, token)
        if volume_result["is_anomaly"]:
            reasons.append("volume_spike")
            adjustments.append(0.7)

        # Content similarity
        similarity_score = await self._check_content_similarity(posts)
        if similarity_score > self.similarity_threshold:
            reasons.append("content_similarity")
            adjustments.append(0.6)

        # Duplicate / near-duplicate
        duplicate_ratio = await self._check_duplicate_ratio(posts)
        if duplicate_ratio > self.duplicate_threshold:
            reasons.append("duplicate_content")
            adjustments.append(0.55)

        # Temporal clustering
        clustering_score = await self._check_temporal_clustering(posts)
        if clustering_score > self.clustering_threshold:
            reasons.append("temporal_clustering")
            adjustments.append(0.7)

        # New / low-quality accounts
        new_account_ratio = await self._check_new_accounts(posts)
        if new_account_ratio > self.new_account_threshold:
            reasons.append("new_account_concentration")
            adjustments.append(0.8)

        # Burst activity
        burst_score = await self._check_burst_activity(posts)
        if burst_score > self.burst_ratio_threshold:
            reasons.append("burst_activity")
            adjustments.append(0.65)

        # Cross-platform divergence
        divergence = await self._check_cross_platform_divergence(posts)

        # Combine per-signal adjustments into an overall manipulation score
        # Confidence is a probability-like score in [0,1], 0.0 means no manipulation.
        confidence = float(1.0 - np.prod([1.0 - a for a in adjustments])) if adjustments else 0.0

        return ManipulationFlags(
            is_suspicious=len(reasons) > 0,
            reasons=reasons,
            confidence=confidence,
            volume_anomaly=volume_result["is_anomaly"],
            content_similarity_score=similarity_score,
            temporal_clustering_score=clustering_score,
            new_account_ratio=new_account_ratio,
            cross_platform_divergence=divergence,
            duplicate_ratio=duplicate_ratio,
            burst_score=burst_score,
        )

    async def _check_volume_anomaly(self, posts: list[SocialPost], token: str) -> dict[str, Any]:
        current_volume = len(posts)

        history = self._volume_history.get(token, [])
        # If no historical baseline exists, record current and
        # treat very large single-batch volumes as anomalies.
        if not history:
            self._volume_history[token].append((datetime.utcnow(), current_volume))
            if current_volume >= 50:
                # Large absolute spike on first observation
                return {"is_anomaly": True, "current": current_volume, "baseline": 0}
            return {"is_anomaly": False, "current": current_volume, "baseline": current_volume}

        cutoff = datetime.utcnow() - timedelta(hours=self.volume_baseline_window)
        recent_volumes = [vol for ts, vol in history if ts >= cutoff]

        baseline = current_volume if not recent_volumes else sum(recent_volumes) / len(recent_volumes)

        self._volume_history[token].append((datetime.utcnow(), current_volume))
        self._volume_history[token] = [(ts, vol) for ts, vol in self._volume_history[token] if ts >= cutoff]

        is_anomaly = current_volume > baseline * self.volume_spike_threshold
        return {"is_anomaly": is_anomaly, "current": current_volume, "baseline": baseline}

    async def _check_content_similarity(self, posts: list[SocialPost]) -> float:
        if len(posts) < 2:
            return 0.0

        def get_ngrams(text: str, n: int = 3) -> set[str]:
            text = text.lower()
            return {text[i : i + n] for i in range(len(text) - n + 1)}

        def jaccard(a: set[str], b: set[str]) -> float:
            if not a or not b:
                return 0.0
            inter = len(a & b)
            uni = len(a | b)
            return inter / uni if uni > 0 else 0.0

        ngram_sets = [get_ngrams(p.text) for p in posts]
        sims = []
        n = len(ngram_sets)
        max_pairs = 1000
        if n * (n - 1) / 2 > max_pairs:
            import random

            indices = list(range(n))
            for _ in range(max_pairs):
                i, j = random.sample(indices, 2)
                sims.append(jaccard(ngram_sets[i], ngram_sets[j]))
        else:
            for i in range(n):
                for j in range(i + 1, n):
                    sims.append(jaccard(ngram_sets[i], ngram_sets[j]))

        if not sims:
            return 0.0

        high = sum(1 for s in sims if s > self.similarity_threshold)
        return high / len(sims)

    async def _check_duplicate_ratio(self, posts: list[SocialPost]) -> float:
        if len(posts) < 2:
            return 0.0

        texts = [p.text.strip().lower() for p in posts]
        from collections import Counter

        counts = Counter(texts)
        dup_count = sum(c - 1 for c in counts.values() if c > 1)

        def jaccard_tokens(a: str, b: str) -> float:
            sa = set(a.split())
            sb = set(b.split())
            if not sa or not sb:
                return 0.0
            return len(sa & sb) / len(sa | sb)

        near_dup = 0
        pairs_checked = 0
        max_pairs = 500
        n = len(texts)
        for i in range(n):
            for j in range(i + 1, n):
                if pairs_checked >= max_pairs:
                    break
                pairs_checked += 1
                if jaccard_tokens(texts[i], texts[j]) > self.similarity_threshold:
                    near_dup += 1
            if pairs_checked >= max_pairs:
                break

        approx_part = min(1.0, (dup_count + near_dup) / max(1, n))
        return approx_part

    async def _check_temporal_clustering(self, posts: list[SocialPost]) -> float:
        if len(posts) < 5:
            return 0.0

        sorted_posts = sorted(posts, key=lambda p: p.timestamp)
        gaps = []
        for i in range(1, len(sorted_posts)):
            gaps.append((sorted_posts[i].timestamp - sorted_posts[i - 1].timestamp).total_seconds())

        if not gaps:
            return 0.0

        mean_gap = np.mean(gaps)
        std_gap = np.std(gaps)
        if mean_gap == 0:
            return 1.0
        cv = std_gap / mean_gap
        if cv < 0.3:
            return 0.9
        elif cv < 0.5:
            return 0.6
        elif cv > 2.0:
            return 0.4
        else:
            return 0.2

    async def _check_burst_activity(self, posts: list[SocialPost]) -> float:
        if len(posts) < 3:
            return 0.0

        times = sorted(p.timestamp.timestamp() if hasattr(p.timestamp, "timestamp") else p.timestamp for p in posts)
        n = len(times)
        left = 0
        max_frac = 0.0
        for right in range(n):
            while times[right] - times[left] > self.burst_window_seconds:
                left += 1
            window_size = right - left + 1
            frac = window_size / n
            if frac > max_frac:
                max_frac = frac
        return max_frac

    async def _check_new_accounts(self, posts: list[SocialPost]) -> float:
        if not posts:
            return 0.0
        low_quality = 0
        for post in posts:
            if post.author_followers is not None:
                if post.author_followers < 50:
                    low_quality += 1
            elif not post.author_verified:
                low_quality += 0.5
        return low_quality / len(posts)

    async def _check_cross_platform_divergence(self, posts: list[SocialPost]) -> float:
        by_source: dict[str, list[float]] = defaultdict(list)
        for post in posts:
            engagement = getattr(post, "engagement_count", 0)
            if getattr(post, "author_followers", None) and post.author_followers > 0:
                normalized = engagement / post.author_followers
            else:
                normalized = 0.0
            by_source[getattr(post, "source", "")] .append(normalized)

        if len(by_source) < 2:
            return 0.0
        means = {s: np.mean(v) for s, v in by_source.items()}
        values = list(means.values())
        if not values:
            return 0.0
        max_val = max(values)
        min_val = min(values)
        if max_val == 0:
            return 0.0
        return (max_val - min_val) / max_val

    def calculate_quality_weights(self, posts: list[SocialPost]) -> dict[str, float]:
        weights: dict[str, float] = {}
        for post in posts:
            weight = 1.0
            if getattr(post, "author_verified", False):
                weight *= 1.5
            if getattr(post, "author_followers", None):
                af = post.author_followers
                if af > 10000:
                    weight *= 2.0
                elif af > 1000:
                    weight *= 1.5
                elif af < 100:
                    weight *= 0.7
            if getattr(post, "author_account_age_days", None) is not None:
                age = post.author_account_age_days
                if age < 30:
                    weight *= 0.6
                elif age > 365:
                    weight *= 1.2
            if getattr(post, "engagement_count", 0) > 100:
                weight *= 1.3
            elif getattr(post, "engagement_count", 0) > 10:
                weight *= 1.1
            weights[getattr(post, "post_id", str(id(post)))] = weight
        if weights:
            max_w = max(weights.values())
            weights = {k: v / max_w for k, v in weights.items()}
        return weights


# Backward-compatible dataclass and wrapper expected by older tests
def _map_flags_to_result(flags: ManipulationFlags) -> "ManipulationResult":
    return ManipulationResult(
        is_manipulated=flags.is_suspicious,
        confidence=flags.confidence,
        detection_reasons=flags.reasons,
        flagged_posts=[],
    )


@dataclass
class ManipulationResult:
    is_manipulated: bool
    confidence: float
    detection_reasons: list[str] = field(default_factory=list)
    flagged_posts: list[str] = field(default_factory=list)

    def json(self) -> str:
        import json

        return json.dumps(
            {
                "is_manipulated": self.is_manipulated,
                "confidence": self.confidence,
                "detection_reasons": self.detection_reasons,
                "flagged_posts": self.flagged_posts,
            }
        )


def analyze_batch(self, posts: list[SocialPost], token: str = "") -> ManipulationResult:
    if not posts:
        return ManipulationResult(is_manipulated=False, confidence=0.0)
    flags = asyncio.run(self.analyze(posts, token))
    return _map_flags_to_result(flags)


# Attach wrapper for backward compatibility
ManipulationDetector.analyze_batch = analyze_batch
