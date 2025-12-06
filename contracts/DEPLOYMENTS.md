# SentiBridge Deployments

This file tracks all SentiBridge contract deployments across networks.

## Local Development (Anvil)

| Contract | Address | Notes |
|----------|---------|-------|
| SentimentOracleV1 (Implementation) | `0x5FbDB2315678afecb367f032d93F642f64180aa3` | |
| SentimentOracleV1 (Proxy) | `0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512` | Main entry point |
| Admin/Operator | `0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266` | Anvil account #0 |

**Chain ID:** 31337  
**RPC:** http://localhost:8545  
**Deployed:** Local development

---

## Polygon Amoy Testnet

| Contract | Address | Notes |
|----------|---------|-------|
| SentimentOracleV1 (Implementation) | `0xDC528bf9D41b16B14c178D52474E700f0B9dee85` | |
| SentimentOracleV1 (Proxy) | `0x272441473a9994623e65A32890484809033fbB7f` | Main entry point |
| SentiBridgeTimelock | `TBD` | 1-hour delay (testnet) |

**Chain ID:** 80002  
**RPC:** https://rpc-amoy.polygon.technology  
**Explorer:** https://amoy.polygonscan.com  
**Deployer:** `0x252fdFd1732DF149D6AcfB3038aA4eB1258Ca637`  
**Deployed:** December 6, 2025  
**Deployment TX (Impl):** `0x01d7e4a61f3f6dd9e3da3cba960e1f3f8934229701957f6d432993d7a1c5bdcf`  
**Deployment TX (Proxy):** `0x6091f8111376a869ef755102c75aece17be38b64d82d1a275d0e1145ebee7bb7`

### Verification Links

- [Implementation on Polygonscan](https://amoy.polygonscan.com/address/0xDC528bf9D41b16B14c178D52474E700f0B9dee85)
- [Proxy on Polygonscan](https://amoy.polygonscan.com/address/0x272441473a9994623e65A32890484809033fbB7f)

---

## Polygon Mainnet

| Contract | Address | Notes |
|----------|---------|-------|
| SentimentOracleV1 (Implementation) | `TBD` | |
| SentimentOracleV1 (Proxy) | `TBD` | Main entry point |
| SentiBridgeTimelock | `TBD` | 48-hour delay |

**Chain ID:** 137  
**RPC:** https://polygon-rpc.com  
**Explorer:** https://polygonscan.com

### Pre-Deployment Checklist

- [ ] Complete external security audit
- [ ] Set up multisig wallet (Gnosis Safe)
- [ ] Configure 48-hour timelock
- [ ] Prepare monitoring and alerting
- [ ] Document incident response plan

---

## Contract Verification

To verify contracts on Polygonscan:

```bash
# Verify implementation
forge verify-contract \
  --chain-id <CHAIN_ID> \
  <IMPLEMENTATION_ADDRESS> \
  src/SentimentOracleV1.sol:SentimentOracleV1 \
  --etherscan-api-key $POLYGONSCAN_API_KEY

# Verify proxy (use OpenZeppelin's ERC1967Proxy)
forge verify-contract \
  --chain-id <CHAIN_ID> \
  <PROXY_ADDRESS> \
  lib/openzeppelin-contracts/contracts/proxy/ERC1967/ERC1967Proxy.sol:ERC1967Proxy \
  --etherscan-api-key $POLYGONSCAN_API_KEY
```

---

## Upgrade History

| Date | Version | Description | TX Hash |
|------|---------|-------------|---------|
| - | 1.0.0 | Initial deployment | - |

---

## ABI

The contract ABI can be generated with:

```bash
cd contracts && forge build
cat out/SentimentOracleV1.sol/SentimentOracleV1.json | jq '.abi'
```

Or use the proxy ABI for external integrations (same interface as implementation).
