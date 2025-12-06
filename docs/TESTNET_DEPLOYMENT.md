# SentiBridge Testnet Deployment Guide

This guide walks through deploying SentiBridge to **Polygon Amoy Testnet** for integration testing.

## Prerequisites

### 1. Get Testnet MATIC

1. Visit [Polygon Faucet](https://faucet.polygon.technology/)
2. Connect your wallet and request Amoy testnet MATIC
3. Ensure you have at least 0.5 MATIC for deployment

### 2. Get an RPC Endpoint

- **Free Options:**
  - [Alchemy](https://www.alchemy.com/) - Create free account, create Polygon Amoy app
  - [Infura](https://www.infura.io/) - Create free account, enable Polygon
  - [QuickNode](https://www.quicknode.com/) - Free tier available

### 3. Set Up Environment

Create a `.env` file in the `contracts/` directory:

```bash
cd contracts
cp .env.example .env
```

Edit `.env` with your values:

```env
# Deployer private key (DO NOT use mainnet keys!)
PRIVATE_KEY=0x...your_testnet_private_key...

# RPC URLs
AMOY_RPC_URL=https://polygon-amoy.g.alchemy.com/v2/YOUR_API_KEY

# Etherscan API key for verification (optional but recommended)
POLYGONSCAN_API_KEY=your_polygonscan_api_key

# Initial operator address (can be same as deployer for testnet)
OPERATOR_ADDRESS=0x...your_address...
```

## Deployment Options

### Option 1: Simple Development Deployment

For testing, use the basic deployment script (no timelock):

```bash
cd contracts

# Load environment
source .env

# Deploy to Amoy
forge script script/Deploy.s.sol:DeployScript \
  --rpc-url $AMOY_RPC_URL \
  --private-key $PRIVATE_KEY \
  --broadcast \
  --verify \
  -vvvv
```

### Option 2: Production-like Deployment

For testing the full production setup with timelock:

```bash
cd contracts

# Load environment  
source .env

# Deploy with timelock (uses shorter delay for testnet)
TIMELOCK_DELAY=3600 forge script script/DeployProduction.s.sol:DeployProductionScript \
  --rpc-url $AMOY_RPC_URL \
  --private-key $PRIVATE_KEY \
  --broadcast \
  --verify \
  -vvvv
```

**Note:** For testnet, we use a 1-hour timelock delay instead of 48 hours.

## Deployment Verification

After deployment, verify the contracts on Polygonscan:

```bash
# Get the deployed addresses from the broadcast output
# Then verify each contract

# Verify implementation
forge verify-contract \
  --chain-id 80002 \
  --constructor-args $(cast abi-encode "constructor()") \
  <IMPLEMENTATION_ADDRESS> \
  src/SentimentOracleV1.sol:SentimentOracleV1 \
  --etherscan-api-key $POLYGONSCAN_API_KEY

# Verify proxy
forge verify-contract \
  --chain-id 80002 \
  <PROXY_ADDRESS> \
  @openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol:ERC1967Proxy \
  --etherscan-api-key $POLYGONSCAN_API_KEY
```

## Post-Deployment Setup

### 1. Configure Token Whitelist

After deployment, add test tokens to the whitelist:

```bash
# Using cast to interact with the deployed contract
ORACLE_PROXY=0x...deployed_proxy_address...

# Add a test token (replace with actual test token addresses)
cast send $ORACLE_PROXY \
  "addSupportedToken(address)" \
  0x...test_token_address... \
  --rpc-url $AMOY_RPC_URL \
  --private-key $PRIVATE_KEY
```

### 2. Test Token Addresses on Polygon Amoy

| Token | Address |
|-------|---------|
| WMATIC | `0x9c3C9283D3e44854697Cd22D3Faa240Cfb032889` |
| Test USDC | Deploy your own mock token |

### 3. Verify Configuration

```bash
# Check whitelist status
cast call $ORACLE_PROXY "tokenWhitelistEnabled()(bool)" --rpc-url $AMOY_RPC_URL

# Check if token is supported
cast call $ORACLE_PROXY "supportedTokens(address)(bool)" 0x...token... --rpc-url $AMOY_RPC_URL

# Check current fee
cast call $ORACLE_PROXY "updateFee()(uint256)" --rpc-url $AMOY_RPC_URL
```

## Running the Full System

### 1. Start Workers

Update worker configuration:

```bash
cd workers

# Create .env file
cat > .env << EOF
# Blockchain
WEB3_PROVIDER_URL=$AMOY_RPC_URL
ORACLE_CONTRACT_ADDRESS=$ORACLE_PROXY
PRIVATE_KEY=$PRIVATE_KEY

# Data Sources
NEWS_API_KEY=your_newsapi_key
TWITTER_BEARER_TOKEN=your_twitter_token

# Redis
REDIS_URL=redis://localhost:6379

# Model
SENTIMENT_MODEL=ProsusAI/finbert

# Tokens to track
TRACKED_TOKENS=MATIC,BTC,ETH
EOF

# Start with Docker
docker-compose up -d
```

### 2. Start API

```bash
cd api

# Create .env file
cat > .env << EOF
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sentibridge
REDIS_URL=redis://localhost:6379
JWT_SECRET=$(openssl rand -hex 32)
WEB3_PROVIDER_URL=$AMOY_RPC_URL
ORACLE_CONTRACT_ADDRESS=$ORACLE_PROXY
EOF

# Start with Docker
docker-compose up -d
```

### 3. Start Subgraph (Optional)

If using The Graph for indexing:

```bash
cd subgraph

# Update subgraph.yaml with deployed addresses
# Then deploy to Graph Studio or hosted service
graph deploy --studio sentibridge-amoy
```

## Integration Testing

### Manual Testing

```bash
# 1. Submit a sentiment update
cast send $ORACLE_PROXY \
  "updateSentiment(address,int16,uint8,uint32,uint32)" \
  0x9c3C9283D3e44854697Cd22D3Faa240Cfb032889 \
  500 \
  85 \
  1000 \
  $(date +%s) \
  --rpc-url $AMOY_RPC_URL \
  --private-key $PRIVATE_KEY

# 2. Read the sentiment
cast call $ORACLE_PROXY \
  "getCurrentSentiment(address)((int16,uint8,uint32,uint32))" \
  0x9c3C9283D3e44854697Cd22D3Faa240Cfb032889 \
  --rpc-url $AMOY_RPC_URL

# 3. Get historical sentiment
cast call $ORACLE_PROXY \
  "getHistoricalSentiment(address,uint256,uint256)((int16,uint8,uint32,uint32)[])" \
  0x9c3C9283D3e44854697Cd22D3Faa240Cfb032889 \
  0 \
  10 \
  --rpc-url $AMOY_RPC_URL
```

### Automated Integration Tests

```bash
cd contracts

# Run integration tests against live testnet
FORK_URL=$AMOY_RPC_URL forge test --match-contract Integration -vvv
```

## Monitoring

### Contract Events

Monitor contract events using cast:

```bash
# Watch for SentimentUpdated events
cast logs --from-block latest --address $ORACLE_PROXY \
  "SentimentUpdated(address,int16,uint8,uint32,uint32)" \
  --rpc-url $AMOY_RPC_URL
```

### Polygonscan

View your contract at:
```
https://amoy.polygonscan.com/address/<ORACLE_PROXY>
```

## Troubleshooting

### Common Issues

1. **"Insufficient funds"**
   - Get more testnet MATIC from the faucet
   - Check you're using the correct private key

2. **"execution reverted: AccessControlUnauthorizedAccount"**
   - Ensure the deployer has OPERATOR_ROLE
   - Check you're using the correct account

3. **"Token not whitelisted"**
   - Add the token to the whitelist first
   - Or disable whitelist for testing

4. **RPC errors**
   - Try a different RPC provider
   - Check rate limits on free tier

### Getting Help

- Check the [GitHub Issues](https://github.com/your-org/sentibridge/issues)
- Review the [Security Audit Checklist](./SECURITY_AUDIT_CHECKLIST.md)

## Next Steps

After successful testnet deployment:

1. ✅ Verify all contracts on Polygonscan
2. ✅ Test sentiment submission and retrieval
3. ✅ Test API endpoints
4. ✅ Monitor for any issues over 24-48 hours
5. ✅ Proceed to mainnet deployment with full timelock

## Mainnet Deployment Checklist

Before deploying to mainnet:

- [ ] Complete external security audit
- [ ] Test all scenarios on testnet
- [ ] Set up multisig wallet for admin
- [ ] Configure 48-hour timelock delay
- [ ] Prepare incident response plan
- [ ] Set up monitoring and alerting
- [ ] Document all deployed addresses
