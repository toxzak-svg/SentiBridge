#!/bin/bash
# =============================================================================
# SentiBridge Testnet Deployment Script
# =============================================================================
# This script deploys SentiBridge to Polygon Amoy testnet
# 
# Prerequisites:
# 1. Fund your deployer wallet with testnet MATIC from:
#    https://faucet.polygon.technology/
# 2. Set environment variables in .env file
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "SentiBridge Testnet Deployment"
echo "=========================================="

# Load environment
if [ -f .env ]; then
    source .env
else
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please copy .env.example to .env and fill in your values"
    exit 1
fi

# Validate required variables
if [ -z "$PRIVATE_KEY" ]; then
    echo -e "${RED}Error: PRIVATE_KEY not set${NC}"
    exit 1
fi

# Use public RPC if not set
AMOY_RPC_URL=${AMOY_RPC_URL:-"https://rpc-amoy.polygon.technology"}
echo "RPC URL: $AMOY_RPC_URL"

# Get deployer address
DEPLOYER=$(cast wallet address --private-key $PRIVATE_KEY)
echo "Deployer: $DEPLOYER"

# Check balance
BALANCE=$(cast balance $DEPLOYER --rpc-url $AMOY_RPC_URL)
BALANCE_ETH=$(cast from-wei $BALANCE)
echo "Balance: $BALANCE_ETH MATIC"

# Minimum required balance (0.1 MATIC for deployment)
MIN_BALANCE="100000000000000000"
if [ $(echo "$BALANCE < $MIN_BALANCE" | bc -l 2>/dev/null || echo "1") -eq 1 ] && [ "$BALANCE" = "0" ]; then
    echo -e "${YELLOW}Warning: Insufficient balance for deployment${NC}"
    echo "Please get testnet MATIC from: https://faucet.polygon.technology/"
    echo "Deployer address: $DEPLOYER"
    exit 1
fi

echo ""
echo -e "${GREEN}Starting deployment...${NC}"

# Deploy the contracts
forge script script/Deploy.s.sol:DeployScript \
    --rpc-url $AMOY_RPC_URL \
    --private-key $PRIVATE_KEY \
    --broadcast \
    -vvvv

echo ""
echo -e "${GREEN}Deployment complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Save the deployed addresses from the output above"
echo "2. Verify contracts on Polygonscan (optional but recommended)"
echo "3. Run integration tests against the deployed contracts"
