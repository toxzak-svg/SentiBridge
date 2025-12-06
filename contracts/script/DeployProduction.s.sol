// SPDX-License-Identifier: MIT
pragma solidity ^0.8.23;

import {Script, console2} from "forge-std/Script.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

import {SentimentOracleV1} from "../src/SentimentOracleV1.sol";
import {SentiBridgeTimelock} from "../src/SentiBridgeTimelock.sol";

/**
 * @title DeployProductionScript
 * @notice Production deployment with timelock and multi-sig integration
 * @dev Run with: forge script script/DeployProduction.s.sol --rpc-url $RPC_URL --broadcast --verify
 *
 * Required environment variables:
 * - DEPLOYER_PRIVATE_KEY: Private key for deployment
 * - MULTISIG_ADDRESS: Gnosis Safe address for admin operations
 * - OPERATOR_ADDRESS: Hot wallet for oracle updates
 * - TIMELOCK_DELAY: Delay in seconds (recommended: 86400 for 24h)
 */
contract DeployProductionScript is Script {
    // Configuration from environment
    address public multisig;
    address public operator;
    uint256 public timelockDelay;

    // Deployed addresses
    address public implementation;
    address public proxy;
    address public timelock;

    function setUp() public {
        // Load configuration
        multisig = vm.envAddress("MULTISIG_ADDRESS");
        operator = vm.envAddress("OPERATOR_ADDRESS");
        timelockDelay = vm.envOr("TIMELOCK_DELAY", uint256(86400)); // 24h default

        // Validate
        require(multisig != address(0), "MULTISIG_ADDRESS required");
        require(operator != address(0), "OPERATOR_ADDRESS required");
        require(timelockDelay >= 3600, "TIMELOCK_DELAY must be >= 1 hour");

        console2.log("=== Production Deployment Configuration ===");
        console2.log("Multi-sig:", multisig);
        console2.log("Operator:", operator);
        console2.log("Timelock delay:", timelockDelay, "seconds");
    }

    function run() public {
        uint256 deployerPrivateKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);

        console2.log("Deployer:", deployer);
        console2.log("");

        vm.startBroadcast(deployerPrivateKey);

        // Step 1: Deploy Timelock
        console2.log("Step 1: Deploying Timelock...");
        _deployTimelock();

        // Step 2: Deploy Oracle Implementation
        console2.log("Step 2: Deploying Oracle Implementation...");
        _deployImplementation();

        // Step 3: Deploy Proxy with Timelock as Admin
        console2.log("Step 3: Deploying Proxy...");
        _deployProxy();

        // Step 4: Configure Oracle
        console2.log("Step 4: Configuring Oracle...");
        _configureOracle();

        vm.stopBroadcast();

        // Output summary
        _printSummary();
    }

    function _deployTimelock() internal {
        // Proposers: multi-sig can propose
        address[] memory proposers = new address[](1);
        proposers[0] = multisig;

        // Executors: anyone can execute after delay (address(0))
        address[] memory executors = new address[](1);
        executors[0] = address(0);

        // No additional admin (renounced)
        address admin = address(0);

        SentiBridgeTimelock timelockContract = new SentiBridgeTimelock(
            timelockDelay,
            proposers,
            executors,
            admin
        );

        timelock = address(timelockContract);
        console2.log("  Timelock deployed:", timelock);
    }

    function _deployImplementation() internal {
        SentimentOracleV1 impl = new SentimentOracleV1();
        implementation = address(impl);
        console2.log("  Implementation deployed:", implementation);
    }

    function _deployProxy() internal {
        // Initialize with timelock as admin (for upgrades and admin functions)
        // Operator is hot wallet for updates
        bytes memory initData = abi.encodeWithSelector(
            SentimentOracleV1.initialize.selector,
            timelock,  // Admin = timelock (controlled by multi-sig)
            operator   // Operator = hot wallet
        );

        ERC1967Proxy proxyContract = new ERC1967Proxy(implementation, initData);
        proxy = address(proxyContract);
        console2.log("  Proxy deployed:", proxy);
    }

    function _configureOracle() internal {
        SentimentOracleV1 oracle = SentimentOracleV1(proxy);

        // Grant UPGRADER_ROLE to timelock
        oracle.grantRole(oracle.UPGRADER_ROLE(), timelock);
        console2.log("  UPGRADER_ROLE granted to timelock");

        // Note: Token whitelisting should be done via timelock after deployment
        console2.log("  Token whitelisting should be done via timelock");
    }

    function _printSummary() internal view {
        console2.log("");
        console2.log("=== Deployment Summary ===");
        console2.log("Timelock:", timelock);
        console2.log("Implementation:", implementation);
        console2.log("Proxy:", proxy);
        console2.log("");
        console2.log("=== Role Assignments ===");
        console2.log("ADMIN_ROLE: Timelock (controlled by multi-sig)");
        console2.log("OPERATOR_ROLE:", operator);
        console2.log("UPGRADER_ROLE: Timelock");
        console2.log("");
        console2.log("=== Next Steps ===");
        console2.log("1. Verify contracts on Polygonscan");
        console2.log("2. Add tokens via timelock proposal");
        console2.log("3. Configure operator hot wallet");
        console2.log("4. Set up monitoring and alerts");
        console2.log("5. Deploy subgraph with proxy address");
    }
}

/**
 * @title AddTokensViaTimelock
 * @notice Helper script to create timelock proposal for adding tokens
 */
contract AddTokensViaTimelock is Script {
    function run() public view {
        address timelockAddr = vm.envAddress("TIMELOCK_ADDRESS");
        address oracleProxy = vm.envAddress("ORACLE_PROXY_ADDRESS");

        // Example tokens to add (Polygon mainnet)
        address[] memory tokens = new address[](5);
        tokens[0] = 0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270; // WMATIC
        tokens[1] = 0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619; // WETH
        tokens[2] = 0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6; // WBTC
        tokens[3] = 0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359; // USDC
        tokens[4] = 0xc2132D05D31c914a87C6611C10748AEb04B58e8F; // USDT

        console2.log("=== Timelock Proposal Data ===");
        console2.log("Target:", oracleProxy);
        console2.log("");

        for (uint256 i = 0; i < tokens.length; i++) {
            bytes memory callData = abi.encodeWithSelector(
                SentimentOracleV1.setTokenWhitelist.selector,
                tokens[i],
                true
            );
            console2.log("Token", i + 1, ":", tokens[i]);
            console2.logBytes(callData);
            console2.log("");
        }

        console2.log("Submit these to timelock via multi-sig");
    }
}
