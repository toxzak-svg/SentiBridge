"""
NLP Sentiment Analyzer.

Implements ensemble sentiment analysis:
1. Fine-tuned DistilBERT (primary)
2. VADER with crypto terminology (fallback)

Optimized for crypto community language.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from dataclasses import field

import numpy as np
import asyncio

from src.utils.logging import get_logger
from src.utils.validation import SentimentScore, SocialPost

logger = get_logger(__name__)


@dataclass
class ModelPrediction:
    """Raw prediction from a single model."""

    score: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    model_name: str


@dataclass
class SentimentResult:
    """Backward-compatible result used by unit tests and lightweight callers."""

    score: float
    confidence: float
    label: str | None = None
    metadata: dict | None = field(default_factory=dict)


class BaseSentimentModel(ABC):
    """Abstract base class for sentiment models."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return model identifier."""
        pass

    @abstractmethod
    async def predict(self, text: str) -> ModelPrediction:
        """Predict sentiment for a single text."""
        pass

    @abstractmethod
    async def predict_batch(self, texts: list[str]) -> list[ModelPrediction]:
        """Predict sentiment for multiple texts."""
        pass


class VADERSentimentModel(BaseSentimentModel):
    """
    VADER sentiment model adapted for crypto terminology.

    VADER (Valence Aware Dictionary and sEntiment Reasoner) is a
    lexicon and rule-based sentiment analysis tool.
    """

    def __init__(self) -> None:
        self._analyzer: Any = None
        self._crypto_lexicon = self._build_crypto_lexicon()

    @property
    def model_name(self) -> str:
        return "vader-crypto-v1"

    def _build_crypto_lexicon(self) -> dict[str, float]:
        """Build crypto-specific sentiment lexicon."""
        return {
            # Positive terms
            "bullish": 3.0,
            "moon": 2.5,
            "mooning": 3.0,
            "pump": 1.5,
            "hodl": 2.0,
            "diamond hands": 3.0,
            "based": 2.5,
            "gmi": 3.0,  # gonna make it
            "wagmi": 3.0,  # we're all gonna make it
            "lfg": 2.5,  # let's f***ing go
            "alpha": 2.0,
            "gem": 2.5,
            "degen": 1.0,  # can be positive in crypto
            "aped": 1.5,  # bought in aggressively
            "bags": 1.0,  # holding position
            "whale": 1.5,
            "accumulate": 2.0,
            "undervalued": 2.0,
            # Negative terms
            "bearish": -3.0,
            "dump": -2.5,
            "dumping": -3.0,
            "rug": -4.0,
            "rugpull": -4.0,
            "scam": -4.0,
            "paper hands": -2.5,
            "ngmi": -3.0,  # not gonna make it
            "rekt": -3.5,
            "exit scam": -4.0,
            "ponzi": -4.0,
            "honeypot": -4.0,
            "fud": -1.5,
            "selling": -1.5,
            "crash": -3.0,
            "dead": -3.0,
            "overvalued": -2.0,
            "bag holder": -2.0,
            # Neutral/context-dependent
            "dip": 0.0,  # could be buy the dip or it's dipping
            "volatile": 0.0,
        }

    async def _ensure_loaded(self) -> None:
        """Lazy load VADER analyzer."""
        if self._analyzer is None:
            try:
                from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

                self._analyzer = SentimentIntensityAnalyzer()

                # Update lexicon with crypto terms
                self._analyzer.lexicon.update(self._crypto_lexicon)

                logger.info("VADER model loaded with crypto lexicon")

            except ImportError:
                raise RuntimeError(
                    "vaderSentiment is required. Install with: pip install vaderSentiment"
                )

    async def predict(self, text: str) -> ModelPrediction:
        """Predict sentiment using VADER."""
        await self._ensure_loaded()

        # Get VADER scores
        scores = self._analyzer.polarity_scores(text)

        # compound score is already normalized to [-1, 1]
        compound = scores["compound"]

        # Calculate confidence based on score strength
        confidence = abs(compound)

        # Boost confidence if text contains crypto terms
        crypto_term_count = sum(1 for term in self._crypto_lexicon if term in text.lower())
        if crypto_term_count > 0:
            confidence = min(1.0, confidence + 0.1 * crypto_term_count)

        return ModelPrediction(
            score=compound,
            confidence=confidence,
            model_name=self.model_name,
        )

    def analyze(self, text: str) -> SentimentResult:
        """Synchronous compatibility wrapper used by tests.

        Returns `SentimentResult` with score normalized to [0,1].
        """
        # Run async predict synchronously for compatibility
        pred = asyncio.run(self.predict(text))

        # Normalize VADER compound (-1..1) to 0..1
        norm_score = max(0.0, min(1.0, (pred.score + 1.0) / 2.0))

        # Simple label mapping
        label = None
        if pred.score >= 0.5:
            label = "positive"
        elif pred.score <= -0.5:
            label = "negative"

        return SentimentResult(score=norm_score, confidence=pred.confidence, label=label)

    async def predict_batch(self, texts: list[str]) -> list[ModelPrediction]:
        """Predict sentiment for multiple texts."""
        return [await self.predict(text) for text in texts]


class TransformerSentimentModel(BaseSentimentModel):
    """
    Transformer-based sentiment model using DistilBERT.

    In production, this would use a fine-tuned model on crypto data.
    """

    def __init__(self, model_name: str = "distilbert-base-uncased-finetuned-sst-2-english") -> None:
        self._model_id = model_name
        self._pipeline: Any = None

    @property
    def model_name(self) -> str:
        return f"transformer-{self._model_id}"

    async def _ensure_loaded(self) -> None:
        """Lazy load transformer model."""
        if self._pipeline is None:
            try:
                from transformers import pipeline

                logger.info("Loading transformer model", model=self._model_id)

                self._pipeline = pipeline(
                    "sentiment-analysis",
                    model=self._model_id,
                    device=-1,  # CPU; use 0 for GPU
                )

                logger.info("Transformer model loaded")

            except ImportError:
                raise RuntimeError(
                    "transformers is required. Install with: pip install transformers torch"
                )

    async def predict(self, text: str) -> ModelPrediction:
        """Predict sentiment using transformer."""
        await self._ensure_loaded()

        # Truncate text to model's max length
        text = text[:512]

        result = self._pipeline(text)[0]

        # Convert label to score
        label = result["label"]
        confidence = result["score"]

        if label == "POSITIVE":
            score = confidence
        else:
            score = -confidence

        return ModelPrediction(
            score=score,
            confidence=confidence,
            model_name=self.model_name,
        )

    async def predict_batch(self, texts: list[str]) -> list[ModelPrediction]:
        """Predict sentiment for multiple texts."""
        await self._ensure_loaded()

        # Truncate all texts
        texts = [t[:512] for t in texts]

        results = self._pipeline(texts)

        predictions = []
        for result in results:
            label = result["label"]
            confidence = result["score"]

            if label == "POSITIVE":
                score = confidence
            else:
                score = -confidence

            predictions.append(
                ModelPrediction(
                    score=score,
                    confidence=confidence,
                    model_name=self.model_name,
                )
            )

        return predictions


class LightweightLLMModel(BaseSentimentModel):
    """
    Lightweight LLM wrapper used for ambiguous / high-volatility text.

    Behavior:
    - If `openai` is available and `OPENAI_API_KEY` is set, use ChatCompletion
      to ask for a numeric sentiment score and confidence.
    - Otherwise fall back to the transformer sentiment model above.
    """

    def __init__(self, model_name: str | None = None) -> None:
        # model_name kept for compatibility with Transformer fallback
        self._model_name = model_name or "lightweight-llm"
        self._fallback_transformer = TransformerSentimentModel()

    @property
    def model_name(self) -> str:
        return f"light-llm-{self._model_name}"

    async def predict(self, text: str) -> ModelPrediction:
        # Try OpenAI ChatCompletion if available
        try:
            import os

            key = os.environ.get("OPENAI_API_KEY")
            if key is None:
                raise RuntimeError("OPENAI_API_KEY not set")

            try:
                import openai
            except Exception:
                raise RuntimeError("openai package not installed")

            openai.api_key = key

            system = (
                "You are a concise sentiment analysis assistant. "
                "Given the input text, respond with a JSON object containing 'score' and 'confidence'. "
                "'score' must be a number between -1.0 (very negative) and 1.0 (very positive). "
                "'confidence' must be a number between 0.0 and 1.0 representing your confidence."
            )

            prompt = (
                "Text:\n\"\"\"" + text + "\"\"\"\n\n"
                "Return only valid JSON: {\"score\": float, \"confidence\": float}."
            )

            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0.0,
            )

            content = resp["choices"][0]["message"]["content"]

            # Try to parse JSON from content
            import json

            parsed = json.loads(content)

            score = float(parsed.get("score", 0.0))
            confidence = float(parsed.get("confidence", 0.0))

            # clamp
            score = max(-1.0, min(1.0, score))
            confidence = max(0.0, min(1.0, confidence))

            return ModelPrediction(score=score, confidence=confidence, model_name=self.model_name)

        except Exception:
            # OpenAI not available or failed - fallback to transformer model
            return await self._fallback_transformer.predict(text)

    async def predict_batch(self, texts: list[str]) -> list[ModelPrediction]:
        return [await self.predict(t) for t in texts]


class EnsembleSentimentAnalyzer:
    """
    Ensemble sentiment analyzer combining multiple models.

    Weighting:
    - Primary model (transformer): 70%
    - Fallback model (VADER): 30%

    Falls back to VADER-only if transformer fails.
    """

    def __init__(
        self,
        primary_model: BaseSentimentModel | None = None,
        fallback_model: BaseSentimentModel | None = None,
        llm_model: BaseSentimentModel | None = None,
        primary_weight: float = 0.7,
        volatility_prefilter: bool = True,
    ) -> None:
        self.primary_model = primary_model or TransformerSentimentModel()
        self.fallback_model = fallback_model or VADERSentimentModel()
        self.primary_weight = primary_weight
        self.fallback_weight = 1.0 - primary_weight
        self.llm_model = llm_model or LightweightLLMModel()
        self.volatility_prefilter = volatility_prefilter

    def _is_volatile(self, text: str, vader_pred: ModelPrediction | None = None) -> bool:
        """
        Heuristic to decide whether the text is 'volatile' and should be
        escalated to the lightweight LLM for a deeper, context-aware analysis.

        Criteria (any triggers volatility):
        - contains explicit volatility keywords (pump, dump, rug, crash, volatile, volatility)
        - VADER indicates strong but mixed sentiment (both pos and neg high)
        - presence of all-caps words or multiple exclamation marks
        """
        text_l = text.lower()
        volatility_keywords = [
            "volatile",
            "volatility",
            "pump",
            "dump",
            "rug",
            "rugpull",
            "rekt",
            "crash",
            "whale",
            "fud",
            "hodl",
            "moon",
            "dip",
        ]

        if any(k in text_l for k in volatility_keywords):
            return True

        # all-caps or strong punctuation
        if any(word.isupper() and len(word) > 2 for word in text.split()):
            return True
        if text.count("!") >= 2 or text.count("?") >= 3:
            return True

        # use vader_pred to check mixed sentiment
        if vader_pred is not None:
            # Mixed if confidence is moderate but score near neutral
            if vader_pred.confidence >= 0.4 and abs(vader_pred.score) <= 0.35:
                return True

        return False

    async def analyze(self, post: SocialPost) -> SentimentScore:
        """
        Analyze sentiment for a single post.

        Returns weighted ensemble prediction.
        """
        start_time = time.perf_counter()

        predictions: list[tuple[ModelPrediction, float]] = []

        # Run VADER as a fast prefilter
        try:
            vader_pred = await self.fallback_model.predict(post.text)
        except Exception as e:
            logger.warning("VADER prefilter failed", error=str(e))
            vader_pred = None

        # If volatility prefilter is enabled and VADER signals volatility, use LLM
        if self.volatility_prefilter and self._is_volatile(post.text, vader_pred):
            try:
                llm_pred = await self.llm_model.predict(post.text)
                # Combine VADER + LLM (small weight to VADER to preserve quick signal)
                if vader_pred is not None:
                    predictions.append((vader_pred, 0.25))
                    predictions.append((llm_pred, 0.75))
                else:
                    predictions.append((llm_pred, 1.0))

            except Exception as e:
                logger.warning("LLM escalation failed, falling back to primary ensemble", error=str(e))

        # If we didn't escalate to LLM, run the normal ensemble (primary + VADER)
        if not predictions:
            # Try primary model
            try:
                primary_pred = await self.primary_model.predict(post.text)
                predictions.append((primary_pred, self.primary_weight))
            except Exception as e:
                logger.warning(
                    "Primary model failed, using fallback only",
                    error=str(e),
                )

            # Always include VADER for ensemble
            try:
                fallback_pred = vader_pred or (await self.fallback_model.predict(post.text))
                # Adjust weight if primary failed
                fallback_weight = 1.0 if len(predictions) == 0 else self.fallback_weight
                predictions.append((fallback_pred, fallback_weight))
            except Exception as e:
                logger.error("Fallback model failed", error=str(e))
                if len(predictions) == 0:
                    raise RuntimeError("All sentiment models failed")

        # Calculate weighted ensemble
        total_weight = sum(w for _, w in predictions)
        ensemble_score = sum(p.score * w for p, w in predictions) / total_weight
        ensemble_confidence = sum(p.confidence * w for p, w in predictions) / total_weight

        # Clamp to valid range
        ensemble_score = max(-1.0, min(1.0, ensemble_score))
        ensemble_confidence = max(0.0, min(1.0, ensemble_confidence))

        processing_time = (time.perf_counter() - start_time) * 1000  # ms

        return SentimentScore(
            post_id=post.post_id,
            score=ensemble_score,
            confidence=ensemble_confidence,
            model_version=f"ensemble-v1-{len(predictions)}",
            processing_time_ms=processing_time,
        )

    async def analyze_batch(self, posts: list[SocialPost]) -> list[SentimentScore]:
        """Analyze sentiment for multiple posts."""
        return [await self.analyze(post) for post in posts]

    async def aggregate_sentiment(
        self,
        scores: list[SentimentScore],
        quality_weights: dict[str, float] | None = None,
    ) -> tuple[float, float]:
        """
        Aggregate multiple sentiment scores into a single score.

        Args:
            scores: List of individual sentiment scores
            quality_weights: Optional weights per post (by post_id)

        Returns:
            Tuple of (aggregated_score, aggregated_confidence)
        """
        if not scores:
            return 0.0, 0.0

        # Default equal weights
        if quality_weights is None:
            quality_weights = {s.post_id: 1.0 for s in scores}

        # Calculate weighted average
        total_weight = 0.0
        weighted_score = 0.0
        weighted_confidence = 0.0

        for score in scores:
            weight = quality_weights.get(score.post_id, 1.0) * score.confidence
            weighted_score += score.score * weight
            weighted_confidence += score.confidence * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0, 0.0

        return weighted_score / total_weight, weighted_confidence / total_weight
