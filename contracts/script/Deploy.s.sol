// SPDX-License-Identifier: MIT
pragma solidity ^0.8.23;

import {Script, console2} from "forge-std/Script.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

import {SentimentOracleV1} from "../src/SentimentOracleV1.sol";

/**
 * @title DeployScript
 * @notice Deployment script for SentimentOracleV1
 * @dev Run with: forge script script/Deploy.s.sol --rpc-url $RPC_URL --broadcast
 */
contract DeployScript is Script {
    // Configuration
    address public admin;
    address public operator;

    function setUp() public {
        // Load from environment or use defaults for testing
        admin = vm.envOr("ADMIN_ADDRESS", address(0));
        operator = vm.envOr("OPERATOR_ADDRESS", address(0));

        // Validate configuration
        require(admin != address(0), "ADMIN_ADDRESS not set");
        require(operator != address(0), "OPERATOR_ADDRESS not set");
    }

    function run() public returns (address proxy, address implementation) {
        uint256 deployerPrivateKey = vm.envUint("DEPLOYER_PRIVATE_KEY");

        console2.log("Deploying SentimentOracleV1...");
        console2.log("Admin:", admin);
        console2.log("Operator:", operator);

        vm.startBroadcast(deployerPrivateKey);

        // Deploy implementation
        SentimentOracleV1 impl = new SentimentOracleV1();
        console2.log("Implementation deployed at:", address(impl));

        // Prepare initialization data
        bytes memory initData = abi.encodeWithSelector(
            SentimentOracleV1.initialize.selector,
            admin,
            operator
        );

        // Deploy proxy
        ERC1967Proxy proxyContract = new ERC1967Proxy(address(impl), initData);
        console2.log("Proxy deployed at:", address(proxyContract));

        vm.stopBroadcast();

        // Verify deployment
        SentimentOracleV1 oracle = SentimentOracleV1(address(proxyContract));
        require(oracle.hasRole(oracle.ADMIN_ROLE(), admin), "Admin role not set");
        require(oracle.hasRole(oracle.OPERATOR_ROLE(), operator), "Operator role not set");

        console2.log("Deployment verified successfully!");
        console2.log("Version:", oracle.VERSION());

        return (address(proxyContract), address(impl));
    }
}

/**
 * @title DeployTestnetScript
 * @notice Deployment script for testnet with test configuration
 */
contract DeployTestnetScript is Script {
    function run() public returns (address proxy, address implementation) {
        uint256 deployerPrivateKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);

        console2.log("Deploying to testnet...");
        console2.log("Deployer:", deployer);

        vm.startBroadcast(deployerPrivateKey);

        // Deploy implementation
        SentimentOracleV1 impl = new SentimentOracleV1();

        // For testnet, deployer is both admin and operator
        bytes memory initData = abi.encodeWithSelector(
            SentimentOracleV1.initialize.selector,
            deployer,
            deployer
        );

        // Deploy proxy
        ERC1967Proxy proxyContract = new ERC1967Proxy(address(impl), initData);

        // Add some test tokens to whitelist (common Polygon tokens)
        SentimentOracleV1 oracle = SentimentOracleV1(address(proxyContract));
        
        // MATIC wrapped
        oracle.setTokenWhitelist(0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270, true);
        // USDC
        oracle.setTokenWhitelist(0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359, true);
        // USDT
        oracle.setTokenWhitelist(0xc2132D05D31c914a87C6611C10748AEb04B58e8F, true);

        vm.stopBroadcast();

        console2.log("Implementation:", address(impl));
        console2.log("Proxy:", address(proxyContract));

        return (address(proxyContract), address(impl));
    }
}
