"""Tests for NLP analyzer."""

import pytest


class TestSentimentAnalyzer:
    """Tests for sentiment analysis functionality."""

    def test_bullish_sentiment(self) -> None:
        """Test that bullish content produces positive scores."""
        # Import here to avoid loading ML models for all tests
        from src.processors.nlp_analyzer import VADERSentimentModel

        model = VADERSentimentModel()
        result = model.analyze(
            "Bitcoin is looking extremely bullish! Going to the moon! 🚀"
        )

        assert result.score > 0.5
        assert result.confidence > 0

    def test_bearish_sentiment(self) -> None:
        """Test that bearish content produces negative scores."""
        from src.processors.nlp_analyzer import VADERSentimentModel

        model = VADERSentimentModel()
        result = model.analyze(
            "Market is crashing badly. Very bearish. Expect more downside."
        )

        assert result.score < 0.5
        assert result.confidence > 0

    def test_neutral_sentiment(self) -> None:
        """Test that neutral content produces neutral scores."""
        from src.processors.nlp_analyzer import VADERSentimentModel

        model = VADERSentimentModel()
        result = model.analyze("Bitcoin price is $50000 today.")

        assert 0.3 <= result.score <= 0.7  # Near neutral

    def test_crypto_specific_terms(self) -> None:
        """Test that crypto-specific terms are recognized."""
        from src.processors.nlp_analyzer import VADERSentimentModel

        model = VADERSentimentModel()

        # Bullish crypto terms
        bullish_result = model.analyze("Diamond hands! HODL forever! To the moon!")
        assert bullish_result.score > 0.5

        # Bearish crypto terms
        bearish_result = model.analyze("Paper hands everywhere. Rug pull imminent.")
        assert bearish_result.score < 0.5

    def test_emoji_sentiment(self) -> None:
        """Test that emojis affect sentiment."""
        from src.processors.nlp_analyzer import VADERSentimentModel

        model = VADERSentimentModel()

        positive_emoji = model.analyze("Bitcoin 🚀🌙💎")
        negative_emoji = model.analyze("Bitcoin 📉💀😭")

        assert positive_emoji.score > negative_emoji.score

    def test_empty_content(self) -> None:
        """Test handling of empty content."""
        from src.processors.nlp_analyzer import VADERSentimentModel

        model = VADERSentimentModel()
        result = model.analyze("")

        assert 0.4 <= result.score <= 0.6  # Should be neutral
        assert result.confidence < 0.3  # Low confidence

    def test_score_normalization(self) -> None:
        """Test that scores are normalized to 0-1 range."""
        from src.processors.nlp_analyzer import VADERSentimentModel

        model = VADERSentimentModel()

        # Test various inputs
        test_cases = [
            "Amazing! Best investment ever! 🚀🚀🚀",
            "Terrible crash! Lost everything! 😭",
            "Normal market day",
            "!@#$%^&*()",  # Special characters
        ]

        for content in test_cases:
            result = model.analyze(content)
            assert 0.0 <= result.score <= 1.0
            assert 0.0 <= result.confidence <= 1.0


class TestSentimentResult:
    """Tests for SentimentResult dataclass."""

    def test_sentiment_result_creation(self) -> None:
        """Test creating sentiment result."""
        from src.processors.nlp_analyzer import SentimentResult

        result = SentimentResult(
            score=0.75,
            confidence=0.9,
            label="positive",
        )

        assert result.score == 0.75
        assert result.confidence == 0.9
        assert result.label == "positive"

    def test_sentiment_result_defaults(self) -> None:
        """Test sentiment result default values."""
        from src.processors.nlp_analyzer import SentimentResult

        result = SentimentResult(score=0.5, confidence=0.8)

        assert result.label is None
        assert result.metadata == {}


class TestPreprocessing:
    """Tests for text preprocessing."""

    def test_url_removal(self) -> None:
        """Test that URLs are handled properly."""
        from src.processors.nlp_analyzer import VADERSentimentModel

        model = VADERSentimentModel()

        # URL should not heavily influence sentiment
        with_url = model.analyze(
            "Check out this bullish analysis https://example.com/analysis"
        )
        without_url = model.analyze("Check out this bullish analysis")

        # Scores should be similar
        assert abs(with_url.score - without_url.score) < 0.2

    def test_mention_handling(self) -> None:
        """Test that @mentions are handled properly."""
        from src.processors.nlp_analyzer import VADERSentimentModel

        model = VADERSentimentModel()

        result = model.analyze("@elonmusk says Bitcoin is great!")
        assert result.score > 0.5

    def test_hashtag_handling(self) -> None:
        """Test that #hashtags contribute to sentiment."""
        from src.processors.nlp_analyzer import VADERSentimentModel

        model = VADERSentimentModel()

        result = model.analyze("#Bitcoin #bullish #tothemoon")
        assert result.score >= 0.5
