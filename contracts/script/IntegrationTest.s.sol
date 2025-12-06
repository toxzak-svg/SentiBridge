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
        try oracle.getCurrentSentiment(testToken) returns (SentimentOracleV1.SentimentData memory) {
            pass("Get current sentiment");
        } catch {
            // This is OK if no sentiment exists yet
            pass("Get current sentiment (none exists)");
        }
        
        // Test 4: Get sentiment count
        try oracle.getSentimentCount(testToken) returns (uint256 count) {
            console2.log("  Sentiment count:", count);
            pass("Get sentiment count");
        } catch {
            fail("Get sentiment count");
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
        try oracle.getCurrentSentiment(testToken) returns (SentimentOracleV1.SentimentData memory data) {
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
        
        // Test 8: Invalid score should revert
        vm.startBroadcast();
        try oracle.updateSentiment(
            testToken,
            1500, // Invalid: > 1000
            85,
            1000,
            uint32(block.timestamp)
        ) {
            fail("Invalid score accepted (should revert)");
        } catch {
            pass("Invalid score rejected");
        }
        
        // Test 9: Invalid confidence should revert
        try oracle.updateSentiment(
            testToken,
            500,
            150, // Invalid: > 100
            1000,
            uint32(block.timestamp)
        ) {
            fail("Invalid confidence accepted (should revert)");
        } catch {
            pass("Invalid confidence rejected");
        }
        
        // Test 10: Zero address should revert
        try oracle.updateSentiment(
            address(0),
            500,
            85,
            1000,
            uint32(block.timestamp)
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
            420, // Slightly bullish
            75,  // 75% confidence
            500, // 500 samples
            uint32(block.timestamp)
        );
    }
    
    function submitBatchSentiment(SentimentOracleV1 oracle) external {
        address[] memory tokens = new address[](1);
        int16[] memory scores = new int16[](1);
        uint8[] memory confidences = new uint8[](1);
        uint32[] memory samples = new uint32[](1);
        uint32[] memory timestamps = new uint32[](1);
        
        tokens[0] = testToken;
        scores[0] = 550;
        confidences[0] = 80;
        samples[0] = 750;
        timestamps[0] = uint32(block.timestamp);
        
        oracle.batchUpdateSentiment(tokens, scores, confidences, samples, timestamps);
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
