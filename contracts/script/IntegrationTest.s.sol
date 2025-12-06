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
        string memory version = oracle.VERSION();
        if (bytes(version).length > 0) {
            console2.log("  Version:", version);
            pass("Version check");
        } else {
            fail("Version check");
        }
        
        // Test 2: Check whitelist status
        bool whitelistEnabled = oracle.tokenWhitelistEnabled();
        console2.log("  Whitelist enabled:", whitelistEnabled);
        pass("Whitelist status check");
        
        // Test 3: Get history count
        uint256 count = oracle.getHistoryCount(testToken);
        console2.log("  History count:", count);
        pass("Get history count");
    }
    
    function testWriteFunctions(SentimentOracleV1 oracle) internal {
        console2.log("");
        console2.log("--- Testing Write Functions ---");
        
        // Need to broadcast for writes
        vm.startBroadcast();
        
        // Test 4: Submit sentiment update
        bool sentimentSuccess = false;
        try oracle.updateSentiment(
            testToken,
            int128(420e15),  // Slightly bullish (0.42 in 18 decimals)
            500,             // 500 samples
            7500             // 75% confidence (basis points)
        ) {
            sentimentSuccess = true;
        } catch Error(string memory reason) {
            console2.log("  Reason:", reason);
        } catch {
            console2.log("  Unknown error");
        }
        
        if (sentimentSuccess) {
            pass("Submit sentiment");
        } else {
            fail("Submit sentiment");
        }
        
        // Test 5: Submit batch update
        bool batchSuccess = false;
        {
            address[] memory tokens = new address[](1);
            int128[] memory scores = new int128[](1);
            uint32[] memory samples = new uint32[](1);
            uint16[] memory confidences = new uint16[](1);
            
            tokens[0] = testToken;
            scores[0] = int128(550e15);  // 0.55 in 18 decimals
            samples[0] = 750;
            confidences[0] = 8000;       // 80% in basis points
            
            try oracle.batchUpdateSentiment(tokens, scores, samples, confidences) {
                batchSuccess = true;
            } catch Error(string memory reason) {
                console2.log("  Batch reason:", reason);
            } catch {
                console2.log("  Batch unknown error");
            }
        }
        
        if (batchSuccess) {
            pass("Submit batch sentiment");
        } else {
            fail("Submit batch sentiment");
        }
        
        vm.stopBroadcast();
        
        // Test 6: Verify sentiment was stored
        SentimentOracleV1.SentimentData memory data = oracle.getSentiment(testToken);
        if (data.score != 0 || data.sampleSize != 0) {
            console2.log("  Score:", uint256(int256(data.score)));
            console2.log("  Confidence:", uint256(data.confidence));
            console2.log("  Samples:", uint256(data.sampleSize));
            pass("Verify sentiment stored");
        } else {
            fail("Verify sentiment stored");
        }
    }
    
    function testEdgeCases(SentimentOracleV1 oracle) internal {
        console2.log("");
        console2.log("--- Testing Edge Cases ---");
        
        vm.startBroadcast();
        
        // Test 7: Invalid score should revert (exceeds MAX_SCORE of 1e18)
        bool invalidScoreReverted = false;
        try oracle.updateSentiment(
            testToken,
            int128(2e18), // Invalid: > MAX_SCORE (1e18)
            1000,
            8500
        ) {
            // Should not reach here
        } catch {
            invalidScoreReverted = true;
        }
        
        if (invalidScoreReverted) {
            pass("Invalid score rejected");
        } else {
            fail("Invalid score accepted (should revert)");
        }
        
        // Test 8: Invalid confidence should revert (exceeds 10000 basis points)
        bool invalidConfidenceReverted = false;
        try oracle.updateSentiment(
            testToken,
            int128(500e15),
            1000,
            15000  // Invalid: > 10000 (100%)
        ) {
            // Should not reach here
        } catch {
            invalidConfidenceReverted = true;
        }
        
        if (invalidConfidenceReverted) {
            pass("Invalid confidence rejected");
        } else {
            fail("Invalid confidence accepted (should revert)");
        }
        
        // Test 9: Zero address should revert
        bool zeroAddressReverted = false;
        try oracle.updateSentiment(
            address(0),
            int128(500e15),
            1000,
            8500
        ) {
            // Should not reach here
        } catch {
            zeroAddressReverted = true;
        }
        
        if (zeroAddressReverted) {
            pass("Zero address rejected");
        } else {
            fail("Zero address accepted (should revert)");
        }
        
        vm.stopBroadcast();
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
