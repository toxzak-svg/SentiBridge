# SentiBridge
## Proposed Solution: SentiBridge

### High-Level Architecture

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚   Web2 Social Streams        â”‚
â”‚  (Twitter, Discord, Telegram)â”‚
â”‚   Real-Time Feeds            â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
               â”‚
               â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚   SentiBridge Aggregator             â”‚
â”‚   (Off-Chain Node / Workers)         â”‚
â”‚  â€¢ Stream Parsing & NLP              â”‚
â”‚  â€¢ Spam/Bot Detection                â”‚
â”‚  â€¢ Weighted Sentiment Scoring        â”‚
â”‚  â€¢ 5-Min Update Cycles               â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
               â”‚
               â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚   Polygon Smart Contract Oracle      â”‚
â”‚  (Stores Historical Sentiment Data)  â”‚
â”‚  â€¢ Update Function (Permissioned)    â”‚
â”‚  â€¢ Read Functions (Public)           â”‚
â”‚  â€¢ Events (Indexable by Subgraph)    â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
               â”‚
       â”Œâ”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
       â”‚                â”‚             â”‚             â”‚
       â–¼                â–¼             â–¼             â–¼
   AI Agents       DeFi Protocols  Founder Dashboards  Memecoin DAOs
   (Trading,      (Aave, Idle,    (Sentiment KPIs)   (Community Health
    Lending,       Risk Mgmt)      (Impact Metrics)    Monitors)
    Governance)
```

### Core Components

#### **Component 1: Real-Time Social Data Aggregator (Off-Chain)**

**Purpose:** Fetch, parse, and score social sentiment with minimal latency

**Tech Stack:**
- Python (Tweepy for Twitter API v2, Discord.py, Telegram Bot API)
- Redis (caching, deduplication)
- PostgreSQL (historical storage)
- AWS Lambda / Railway (serverless execution every 5 minutes)

**Features:**
- **Multi-Platform Ingestion:**
  - Twitter: Stream tweets mentioning target tokens (e.g., #MATIC, $USDC)
  - Discord: Parse message activity in ecosystem servers
  - Telegram: Monitor community channels
- **Spam Detection:** Filter bot tweets, fake engagement, coordinated pushes
- **Keyword Extraction:** NLP to identify sentiment-bearing words ("bullish," "rug," "scam," "based," etc.)
- **Volume Weighting:** Weight sentiment from verified accounts / influencers higher
- **5-Minute Windows:** Calculate rolling sentiment score every 5 minutes per token/project

**Output:** Structured JSON with sentiment score (-1.0 to +1.0), confidence, volume, timestamp

#### **Component 2: NLP Sentiment Analyzer**

**Purpose:** Convert text â†’ sentiment scores with crypto-specific accuracy

**Models:**
- **Primary:** Fine-tuned DistilBERT on crypto community social data
  - Training data: 50k+ labeled tweets/posts from crypto communities
  - Optimized for memecoin slang ("diamond hands," "paper hands," "based," "gmi," "ngmi")
- **Fallback:** Lexicon-based VADER sentiment adapted for crypto terminology
- **Ensemble:** Combine predictions, take weighted average

**Accuracy Target:** 85%+ agreement with manual labeling on crypto posts

**Output:** Confidence-weighted sentiment per post, aggregated to per-token score

#### **Component 3: Polygon Smart Contract Oracle**

**Purpose:** Store sentiment data on-chain and expose to AI agents / DeFi

**Solidity Contract:**

```solidity
pragma solidity ^0.8.0;

contract SentimentOracle {
    // Sentiment data structure
    struct SentimentData {
        int256 score;          // -1e18 to 1e18 (FixedPoint 18 decimals)
        uint256 timestamp;
        uint256 sampleSize;    // number of posts analyzed
        uint256 confidence;    // 0â€“10000 (basis points, e.g., 9500 = 95%)
    }

    // Primary storage: token â†’ latest sentiment
    mapping(address => SentimentData) public latestSentiment;

    // History: token â†’ array of sentiment snapshots
    mapping(address => SentimentData[]) public sentimentHistory;

    // Access control: only oracle operator can write
    address public operator;

    // Events
    event SentimentUpdated(
        address indexed token,
        int256 score,
        uint256 timestamp,
        uint256 confidence
    );
    event OperatorChanged(address indexed newOperator);

    // Write: Update sentiment for a token
    function updateSentiment(
        address token,
        int256 score,
        uint256 sampleSize,
        uint256 confidence
    ) external onlyOperator {
        require(confidence <= 10000, "Confidence > 100%");
        require(score >= -1e18 && score <= 1e18, "Score out of bounds");

        SentimentData memory data = SentimentData(
            score,
            block.timestamp,
            sampleSize,
            confidence
        );

        latestSentiment[token] = data;
        sentimentHistory[token].push(data);

        emit SentimentUpdated(token, score, block.timestamp, confidence);
    }

    // Read: Fetch latest sentiment for a token
    function getSentiment(address token)
        external
        view
        returns (SentimentData memory)
    {
        return latestSentiment[token];
    }

    // Read: Fetch sentiment change over time window
    function getSentimentTrend(address token, uint256 lookbackSeconds)
        external
        view
        returns (SentimentData[] memory)
    {
        uint256 cutoff = block.timestamp - lookbackSeconds;
        uint256 count = 0;

        // Count entries in range
        for (uint i = sentimentHistory[token].length; i > 0; i--) {
            if (sentimentHistory[token][i - 1].timestamp >= cutoff) {
                count++;
            } else {
                break;
            }
        }

        // Build result array
        SentimentData[] memory result = new SentimentData[](count);
        uint256 idx = 0;
        for (uint i = sentimentHistory[token].length; i > 0; i--) {
            if (sentimentHistory[token][i - 1].timestamp >= cutoff) {
                result[idx] = sentimentHistory[token][i - 1];
                idx++;
            } else {
                break;
            }
        }

        return result;
    }

    // Admin: Change operator
    function setOperator(address newOperator) external {
        require(msg.sender == operator, "Only operator");
        operator = newOperator;
        emit OperatorChanged(newOperator);
    }

    modifier onlyOperator() {
        require(msg.sender == operator, "Only operator");
        _;
    }
}
```

**Key Features:**
- `updateSentiment()`: Called by oracle operator every 5 minutes with latest score
- `getSentiment()`: Returns current sentiment for any token (read by AI agents/DeFi)
- `getSentimentTrend()`: Returns historical data for analysis (used by dashboards)
- Events emitted for off-chain indexing (Subgraph)
- Permissioned writes to prevent spam

#### **Component 4: Open-Source Subgraph Indexer**

**Purpose:** Make sentiment data easily queryable for dashboards and AI agents

**GraphQL Queries:**
```graphql
query getSentimentHistory {
  sentimentUpdated(where: { token: "0x..." }) {
    score
    timestamp
    confidence
  }
}
```

**Enables:**
- Real-time dashboards tracking sentiment
- Historical analysis (did sentiment predict price moves?)
- AI agent integrations (query via Subgraph instead of direct contract calls)

#### **Component 5: API Layer (Freemium SaaS)**

**Tier 1 - Free (for founders, early-stage teams, hobbyists)**
- 500 API calls/day
- Delayed data (10-minute lag)
- Public token sentiment
- Read-only access
- Community Slack support

**Tier 2 - Pro ($49/month)**
- 10,000 API calls/day
- Real-time data (< 1-minute lag)
- Custom token tracking (up to 50 tokens)
- Webhook support for sentiment alerts
- Priority email support

**Tier 3 - Enterprise (Custom)**
- Unlimited API calls
- White-label deployment
- Custom integrations (SDK for proprietary languages)
- SLA-backed 99.9% uptime
- Dedicated Slack channel

-----
