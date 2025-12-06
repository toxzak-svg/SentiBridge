// SPDX-License-Identifier: MIT
pragma solidity ^0.8.23;

import {Script, console2} from "forge-std/Script.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

import {SentimentOracleV1} from "../src/SentimentOracleV1.sol";

/**
 * @title UpgradeScript
 * @notice Script to upgrade the SentimentOracle contract
 * @dev Run with: forge script script/Upgrade.s.sol --rpc-url $RPC_URL --broadcast
 * 
 * IMPORTANT: Before running:
 * 1. Ensure the new implementation is compatible with storage layout
 * 2. Run storage layout checks: forge inspect SentimentOracleV1 storage --pretty
 * 3. Compare with previous version's storage layout
 */
contract UpgradeScript is Script {
    function run() public returns (address newImplementation) {
        address proxyAddress = vm.envAddress("PROXY_ADDRESS");
        uint256 upgraderPrivateKey = vm.envUint("UPGRADER_PRIVATE_KEY");

        require(proxyAddress != address(0), "PROXY_ADDRESS not set");

        SentimentOracleV1 proxy = SentimentOracleV1(proxyAddress);
        
        console2.log("Current version:", proxy.VERSION());
        console2.log("Upgrading proxy at:", proxyAddress);

        vm.startBroadcast(upgraderPrivateKey);

        // Deploy new implementation
        SentimentOracleV1 newImpl = new SentimentOracleV1();
        console2.log("New implementation deployed at:", address(newImpl));

        // Upgrade proxy to new implementation
        proxy.upgradeToAndCall(address(newImpl), "");

        vm.stopBroadcast();

        // Verify upgrade
        console2.log("New version:", proxy.VERSION());
        
        // Verify data persisted (check total updates)
        console2.log("Total updates (should persist):", proxy.totalUpdates());

        return address(newImpl);
    }
}

/**
 * @title VerifyUpgradeScript
 * @notice Script to verify storage layout compatibility before upgrade
 */
contract VerifyUpgradeScript is Script {
    function run() public view {
        address proxyAddress = vm.envAddress("PROXY_ADDRESS");
        SentimentOracleV1 proxy = SentimentOracleV1(proxyAddress);

        console2.log("=== Pre-Upgrade Verification ===");
        console2.log("Proxy address:", proxyAddress);
        console2.log("Current version:", proxy.VERSION());
        console2.log("Total updates:", proxy.totalUpdates());
        console2.log("Circuit breaker enabled:", proxy.circuitBreakerEnabled());
        console2.log("Token whitelist enabled:", proxy.tokenWhitelistEnabled());
        console2.log("Max score change:", uint256(int256(proxy.maxScoreChange())));
        
        console2.log("");
        console2.log("Storage layout check: Run 'forge inspect SentimentOracleV1 storage --pretty'");
        console2.log("Compare with previous version to ensure compatibility.");
    }
}
