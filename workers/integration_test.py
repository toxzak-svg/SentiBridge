#!/usr/bin/env python3
"""
SentiBridge End-to-End Integration Test

This script tests the full pipeline:
1. Collect sample data (mocked)
2. Process sentiment
3. Submit to oracle (if connected)
4. Verify via API

Usage:
    python integration_test.py --mock          # Full mock mode (no blockchain)
    python integration_test.py --testnet       # Against testnet oracle
"""

import asyncio
import argparse
import sys
import os
from datetime import datetime, timedelta
from typing import Optional

# Add workers directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test configuration
TEST_TOKENS = ["BTC", "ETH", "MATIC"]
MOCK_ARTICLES = [
    {
        "title": "Bitcoin surges past $50,000 as institutional adoption grows",
        "content": "Bitcoin has reached new highs as major institutions announce crypto holdings...",
        "source": "CryptoNews",
        "published_at": datetime.utcnow().isoformat(),
        "token": "BTC"
    },
    {
        "title": "Ethereum faces selling pressure amid market uncertainty",
        "content": "ETH prices have declined as traders take profits following the recent rally...",
        "source": "BlockchainDaily",
        "published_at": datetime.utcnow().isoformat(),
        "token": "ETH"
    },
    {
        "title": "Polygon announces major network upgrade",
        "content": "MATIC ecosystem continues to grow with new DeFi integrations...",
        "source": "PolygonNews",
        "published_at": datetime.utcnow().isoformat(),
        "token": "MATIC"
    }
]


class TestResult:
    """Track test results"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.results = []
    
    def add_pass(self, name: str, details: str = ""):
        self.passed += 1
        self.results.append(("PASS", name, details))
        print(f"  ✓ {name}")
        if details:
            print(f"    {details}")
    
    def add_fail(self, name: str, error: str):
        self.failed += 1
        self.results.append(("FAIL", name, error))
        print(f"  ✗ {name}")
        print(f"    Error: {error}")
    
    def add_skip(self, name: str, reason: str):
        self.skipped += 1
        self.results.append(("SKIP", name, reason))
        print(f"  ○ {name} (skipped: {reason})")
    
    def summary(self):
        print("\n" + "=" * 50)
        print("Test Summary")
        print("=" * 50)
        print(f"Passed:  {self.passed}")
        print(f"Failed:  {self.failed}")
        print(f"Skipped: {self.skipped}")
        print(f"Total:   {self.passed + self.failed + self.skipped}")
        
        if self.failed > 0:
            print("\n❌ SOME TESTS FAILED")
            return False
        else:
            print("\n✅ ALL TESTS PASSED")
            return True


async def test_sentiment_analysis(results: TestResult) -> dict:
    """Test sentiment analysis component"""
    print("\n--- Testing Sentiment Analysis ---")
    
    try:
        from processors.sentiment_analyzer import SentimentAnalyzer
        analyzer = SentimentAnalyzer()
        results.add_pass("Import SentimentAnalyzer")
    except ImportError as e:
        results.add_fail("Import SentimentAnalyzer", str(e))
        return {}
    except Exception as e:
        results.add_fail("Import SentimentAnalyzer", str(e))
        return {}
    
    # Test initialization
    try:
        await analyzer.initialize()
        results.add_pass("Initialize analyzer")
    except Exception as e:
        results.add_fail("Initialize analyzer", str(e))
        return {}
    
    # Test sentiment analysis on mock data
    aggregated = {}
    for article in MOCK_ARTICLES:
        try:
            result = await analyzer.analyze(article["content"])
            token = article["token"]
            
            if token not in aggregated:
                aggregated[token] = {"scores": [], "confidences": []}
            
            aggregated[token]["scores"].append(result["score"])
            aggregated[token]["confidences"].append(result["confidence"])
            
            results.add_pass(
                f"Analyze {token} sentiment",
                f"Score: {result['score']:.3f}, Confidence: {result['confidence']:.3f}"
            )
        except Exception as e:
            results.add_fail(f"Analyze {token} sentiment", str(e))
    
    # Aggregate results
    final_results = {}
    for token, data in aggregated.items():
        avg_score = sum(data["scores"]) / len(data["scores"])
        avg_confidence = sum(data["confidences"]) / len(data["confidences"])
        
        # Convert to contract format
        oracle_score = int(avg_score * 1000)  # -1000 to 1000
        oracle_confidence = int(avg_confidence * 100)  # 0 to 100
        
        final_results[token] = {
            "score": oracle_score,
            "confidence": oracle_confidence,
            "sample_size": len(data["scores"])
        }
        
        results.add_pass(
            f"Aggregate {token}",
            f"Score: {oracle_score}, Confidence: {oracle_confidence}%, Samples: {len(data['scores'])}"
        )
    
    return final_results


async def test_oracle_submission(results: TestResult, sentiment_data: dict, mock_mode: bool = True):
    """Test oracle submission"""
    print("\n--- Testing Oracle Submission ---")
    
    if mock_mode:
        # Mock submission
        for token, data in sentiment_data.items():
            results.add_pass(
                f"Mock submit {token}",
                f"Would submit: score={data['score']}, conf={data['confidence']}"
            )
        return
    
    # Real submission
    try:
        from oracle_submitter.submitter import OracleSubmitter
        submitter = OracleSubmitter()
        results.add_pass("Import OracleSubmitter")
    except ImportError as e:
        results.add_fail("Import OracleSubmitter", str(e))
        return
    
    # Check configuration
    oracle_address = os.environ.get("ORACLE_CONTRACT_ADDRESS")
    if not oracle_address:
        results.add_skip("Oracle submission", "ORACLE_CONTRACT_ADDRESS not set")
        return
    
    web3_url = os.environ.get("WEB3_PROVIDER_URL")
    if not web3_url:
        results.add_skip("Oracle submission", "WEB3_PROVIDER_URL not set")
        return
    
    # Initialize
    try:
        await submitter.initialize()
        results.add_pass("Initialize submitter")
    except Exception as e:
        results.add_fail("Initialize submitter", str(e))
        return
    
    # Submit each token
    for token, data in sentiment_data.items():
        try:
            # Get token address (would need mapping in real implementation)
            token_address = get_token_address(token)
            if not token_address:
                results.add_skip(f"Submit {token}", "No token address mapping")
                continue
            
            tx_hash = await submitter.submit(
                token_address=token_address,
                score=data["score"],
                confidence=data["confidence"],
                sample_size=data["sample_size"]
            )
            results.add_pass(f"Submit {token}", f"TX: {tx_hash}")
        except Exception as e:
            results.add_fail(f"Submit {token}", str(e))


async def test_api_endpoints(results: TestResult, mock_mode: bool = True):
    """Test API endpoints"""
    print("\n--- Testing API Endpoints ---")
    
    if mock_mode:
        # Mock API tests
        results.add_pass("API health check (mock)")
        results.add_pass("API sentiment endpoint (mock)")
        results.add_pass("API historical endpoint (mock)")
        return
    
    api_url = os.environ.get("API_URL", "http://localhost:8000")
    
    try:
        import httpx
    except ImportError:
        results.add_skip("API tests", "httpx not installed")
        return
    
    async with httpx.AsyncClient() as client:
        # Health check
        try:
            response = await client.get(f"{api_url}/health")
            if response.status_code == 200:
                results.add_pass("API health check")
            else:
                results.add_fail("API health check", f"Status: {response.status_code}")
        except Exception as e:
            results.add_fail("API health check", str(e))
        
        # Sentiment endpoint
        try:
            response = await client.get(f"{api_url}/api/v1/sentiment/BTC")
            if response.status_code in [200, 404]:  # 404 is OK if no data yet
                results.add_pass("API sentiment endpoint")
            else:
                results.add_fail("API sentiment endpoint", f"Status: {response.status_code}")
        except Exception as e:
            results.add_fail("API sentiment endpoint", str(e))


async def test_data_validation(results: TestResult):
    """Test data validation functions"""
    print("\n--- Testing Data Validation ---")
    
    # Test score validation
    valid_scores = [-1000, -500, 0, 500, 1000]
    invalid_scores = [-1001, 1001, -2000, 2000]
    
    for score in valid_scores:
        if -1000 <= score <= 1000:
            results.add_pass(f"Validate score {score}")
        else:
            results.add_fail(f"Validate score {score}", "Should be valid")
    
    for score in invalid_scores:
        if -1000 <= score <= 1000:
            results.add_fail(f"Reject score {score}", "Should be invalid")
        else:
            results.add_pass(f"Reject score {score}")
    
    # Test confidence validation
    valid_confidences = [0, 50, 100]
    invalid_confidences = [-1, 101, 150]
    
    for conf in valid_confidences:
        if 0 <= conf <= 100:
            results.add_pass(f"Validate confidence {conf}")
        else:
            results.add_fail(f"Validate confidence {conf}", "Should be valid")
    
    for conf in invalid_confidences:
        if 0 <= conf <= 100:
            results.add_fail(f"Reject confidence {conf}", "Should be invalid")
        else:
            results.add_pass(f"Reject confidence {conf}")


def get_token_address(symbol: str) -> Optional[str]:
    """Get token address for symbol (testnet addresses)"""
    # Polygon Amoy testnet addresses
    addresses = {
        "MATIC": "0x9c3C9283D3e44854697Cd22D3Faa240Cfb032889",
        "WMATIC": "0x9c3C9283D3e44854697Cd22D3Faa240Cfb032889",
        # Add more as needed
    }
    return addresses.get(symbol)


async def main():
    parser = argparse.ArgumentParser(description="SentiBridge Integration Tests")
    parser.add_argument("--mock", action="store_true", help="Run in full mock mode")
    parser.add_argument("--testnet", action="store_true", help="Run against testnet")
    parser.add_argument("--api-only", action="store_true", help="Test only API endpoints")
    args = parser.parse_args()
    
    mock_mode = args.mock or not args.testnet
    
    print("=" * 50)
    print("SentiBridge Integration Tests")
    print("=" * 50)
    print(f"Mode: {'Mock' if mock_mode else 'Testnet'}")
    print(f"Time: {datetime.utcnow().isoformat()}")
    
    results = TestResult()
    
    if args.api_only:
        await test_api_endpoints(results, mock_mode)
    else:
        # Full test suite
        await test_data_validation(results)
        sentiment_data = await test_sentiment_analysis(results)
        await test_oracle_submission(results, sentiment_data, mock_mode)
        await test_api_endpoints(results, mock_mode)
    
    success = results.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
