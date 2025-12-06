#!/bin/bash
# =============================================================================
# SentiBridge Local Deployment Script (Anvil)
# =============================================================================
# This script deploys SentiBridge to a local Anvil node for testing
# No external funds required!
# =============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "SentiBridge Local Deployment (Anvil)"
echo "=========================================="

# Check if Anvil is running
if ! curl -s http://localhost:8545 -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}' > /dev/null 2>&1; then
    echo -e "${YELLOW}Starting Anvil in background...${NC}"
    anvil --chain-id 31337 &
    ANVIL_PID=$!
    sleep 2
    echo "Anvil started with PID: $ANVIL_PID"
else
    echo "Anvil already running"
fi

# Use Anvil's default funded account
DEPLOYER_KEY="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
DEPLOYER_ADDR="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

echo ""
echo "Deployer: $DEPLOYER_ADDR"

# Set environment for deployment
export DEPLOYER_PRIVATE_KEY=$DEPLOYER_KEY
export ADMIN_ADDRESS=$DEPLOYER_ADDR
export OPERATOR_ADDRESS=$DEPLOYER_ADDR

# Deploy
echo ""
echo -e "${GREEN}Deploying contracts...${NC}"

forge script script/Deploy.s.sol:DeployScript \
    --rpc-url http://localhost:8545 \
    --broadcast \
    -vvv

echo ""
echo -e "${GREEN}Deployment complete!${NC}"
echo ""
echo "You can now run integration tests against localhost:8545"
