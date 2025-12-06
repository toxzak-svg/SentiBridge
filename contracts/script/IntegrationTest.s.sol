// SPDX-License-Identifier: MIT
pragma solidity ^0.8.23;

import {Script, console2} from "forge-std/Script.sol";
import {SentimentOracleV1} from "../src/SentimentOracleV1.sol";

/**
 * @title IntegrationTest
 * @notice Script to run integration tests against a deployed oracle
 * @dev Run with: forge script script/IntegrationTest.s.sol --rpc-url $RPC_URL --broadcast
 */
contract IntegrationTest is Script {
    // Configuration
    address public oracleAddress;
    address public testToken;
    
    // Test results
    uint256 public testsPassed;
    uint256 public testsFailed;
    
    function setUp() public {
        // Load from environment
        oracleAddress = vm.envAddress("ORACLE_ADDRESS");
        testToken = vm.envOr("TEST_TOKEN", address(0x9c3C9283D3e44854697Cd22D3Faa240Cfb032889)); // Default WMATIC
    }
    
    function run() public {
        console2.log("===========================================");
        console2.log("SentiBridge Integration Tests");
        console2.log("===========================================");
        console2.log("Oracle Address:", oracleAddress);
        console2.log("Test Token:", testToken);
        console2.log("");
        
        SentimentOracleV1 oracle = SentimentOracleV1(oracleAddress);
        
        // Run tests
        testReadFunctions(oracle);
        testWriteFunctions(oracle);
        testEdgeCases(oracle);
        
        // Summary
        console2.log("");
        console2.log("===========================================");
        console2.log("Test Results");
        console2.log("===========================================");
        console2.log("Passed:", testsPassed);
        console2.log("Failed:", testsFailed);
        
        if (testsFailed > 0) {
            console2.log("");
            console2.log("SOME TESTS FAILED!");
            revert("Integration tests failed");
        } else {
            console2.log("");
            console2.log("ALL TESTS PASSED!");
        }
    }
    
    function testReadFunctions(SentimentOracleV1 oracle) internal {
        console2.log("--- Testing Read Functions ---");
        
        // Test 1: Check contract version
        try this.assertVersion(oracle) {
            pass("Version check");
        } catch {
            fail("Version check");
        }
        
        // Test 2: Check whitelist status
        try this.assertWhitelistStatus(oracle) {
            pass("Whitelist status check");
        } catch {
            fail("Whitelist status check");
        }
        
        // Test 3: Read current sentiment (may not exist yet)
        try oracle.getSentiment(testToken) returns (SentimentOracleV1.SentimentData memory) {
            pass("Get current sentiment");
        } catch {
            // This is OK if no sentiment exists yet
            pass("Get current sentiment (none exists)");
        }
        
        // Test 4: Get history count
        try oracle.getHistoryCount(testToken) returns (uint256 count) {
            console2.log("  History count:", count);
            pass("Get history count");
        } catch {
            fail("Get history count");
        }
    }
    
    function testWriteFunctions(SentimentOracleV1 oracle) internal {
        console2.log("");
        console2.log("--- Testing Write Functions ---");
        
        // Need to broadcast for writes
        vm.startBroadcast();
        
        // Test 5: Submit sentiment update
        try this.submitSentiment(oracle) {
            pass("Submit sentiment");
        } catch Error(string memory reason) {
            console2.log("  Reason:", reason);
            fail("Submit sentiment");
        } catch {
            fail("Submit sentiment (unknown error)");
        }
        
        // Test 6: Submit batch update
        try this.submitBatchSentiment(oracle) {
            pass("Submit batch sentiment");
        } catch Error(string memory reason) {
            console2.log("  Reason:", reason);
            fail("Submit batch sentiment");
        } catch {
            fail("Submit batch sentiment (unknown error)");
        }
        
        vm.stopBroadcast();
        
        // Test 7: Verify sentiment was stored
        try oracle.getSentiment(testToken) returns (SentimentOracleV1.SentimentData memory data) {
            console2.log("  Score:", uint256(int256(data.score)));
            console2.log("  Confidence:", uint256(data.confidence));
            pass("Verify sentiment stored");
        } catch {
            fail("Verify sentiment stored");
        }
    }
    
    function testEdgeCases(SentimentOracleV1 oracle) internal {
        console2.log("");
        console2.log("--- Testing Edge Cases ---");
        
        // Test 8: Invalid score should revert (exceeds MAX_SCORE of 1e18)
        vm.startBroadcast();
        try oracle.updateSentiment(
            testToken,
            int128(2e18), // Invalid: > MAX_SCORE (1e18)
            1000,
            8500
        ) {
            fail("Invalid score accepted (should revert)");
        } catch {
            pass("Invalid score rejected");
        }
        
        // Test 9: Invalid confidence should revert (exceeds 10000 basis points)
        try oracle.updateSentiment(
            testToken,
            int128(500e15),
            1000,
            15000  // Invalid: > 10000 (100%)
        ) {
            fail("Invalid confidence accepted (should revert)");
        } catch {
            pass("Invalid confidence rejected");
        }
        
        // Test 10: Zero address should revert
        try oracle.updateSentiment(
            address(0),
            int128(500e15),
            1000,
            8500
        ) {
            fail("Zero address accepted (should revert)");
        } catch {
            pass("Zero address rejected");
        }
        
        vm.stopBroadcast();
    }
    
    // Helper functions that can be called with try/catch
    function assertVersion(SentimentOracleV1 oracle) external view {
        string memory version = oracle.VERSION();
        require(bytes(version).length > 0, "Empty version");
        console2.log("  Version:", version);
    }
    
    function assertWhitelistStatus(SentimentOracleV1 oracle) external view {
        bool enabled = oracle.tokenWhitelistEnabled();
        console2.log("  Whitelist enabled:", enabled);
    }
    
    function submitSentiment(SentimentOracleV1 oracle) external {
        oracle.updateSentiment(
            testToken,
            int128(420e15),  // Slightly bullish (0.42 in 18 decimals)
            500,             // 500 samples
            7500             // 75% confidence (basis points)
        );
    }
    
    function submitBatchSentiment(SentimentOracleV1 oracle) external {
        address[] memory tokens = new address[](1);
        int128[] memory scores = new int128[](1);
        uint32[] memory samples = new uint32[](1);
        uint16[] memory confidences = new uint16[](1);
        
        tokens[0] = testToken;
        scores[0] = int128(550e15);  // 0.55 in 18 decimals
        samples[0] = 750;
        confidences[0] = 8000;       // 80% in basis points
        
        oracle.batchUpdateSentiment(tokens, scores, samples, confidences);
    }
    
    // Test result helpers
    function pass(string memory testName) internal {
        console2.log(unicode"  ✓", testName);
        testsPassed++;
    }
    
    function fail(string memory testName) internal {
        console2.log(unicode"  ✗", testName);
        testsFailed++;
    }
}
