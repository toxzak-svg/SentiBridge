// SPDX-License-Identifier: MIT
pragma solidity ^0.8.23;

import {Test, console2} from "forge-std/Test.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

import {SentimentOracleV1} from "../src/SentimentOracleV1.sol";
import {ISentimentOracle} from "../src/interfaces/ISentimentOracle.sol";
import {SentimentMath} from "../src/libraries/SentimentMath.sol";

/**
 * @title SentimentOracleV1Test
 * @notice Comprehensive test suite for the SentimentOracleV1 contract
 */
contract SentimentOracleV1Test is Test {
    // ============ State Variables ============

    SentimentOracleV1 public implementation;
    SentimentOracleV1 public oracle;
    ERC1967Proxy public proxy;

    address public admin = makeAddr("admin");
    address public operator = makeAddr("operator");
    address public user = makeAddr("user");
    address public upgrader = makeAddr("upgrader");

    address public tokenA = makeAddr("tokenA");
    address public tokenB = makeAddr("tokenB");
    address public tokenC = makeAddr("tokenC");

    // ============ Setup ============

    function setUp() public {
        // Deploy implementation
        implementation = new SentimentOracleV1();

        // Deploy proxy with initialization
        bytes memory initData = abi.encodeWithSelector(
            SentimentOracleV1.initialize.selector,
            admin,
            operator
        );
        proxy = new ERC1967Proxy(address(implementation), initData);

        // Get oracle reference through proxy
        oracle = SentimentOracleV1(address(proxy));

        // Grant upgrader role (get role hash first, then prank for grantRole)
        bytes32 upgraderRole = oracle.UPGRADER_ROLE();
        vm.prank(admin);
        oracle.grantRole(upgraderRole, upgrader);
    }

    // ============ Initialization Tests ============

    function test_Initialize_SetsCorrectRoles() public view {
        assertTrue(oracle.hasRole(oracle.DEFAULT_ADMIN_ROLE(), admin));
        assertTrue(oracle.hasRole(oracle.ADMIN_ROLE(), admin));
        assertTrue(oracle.hasRole(oracle.OPERATOR_ROLE(), operator));
        assertTrue(oracle.hasRole(oracle.UPGRADER_ROLE(), admin));
    }

    function test_Initialize_SetsDefaultValues() public view {
        assertEq(oracle.maxScoreChange(), SentimentMath.DEFAULT_MAX_CHANGE);
        assertTrue(oracle.circuitBreakerEnabled());
        assertFalse(oracle.tokenWhitelistEnabled());
        assertEq(oracle.totalUpdates(), 0);
    }

    function test_Initialize_CannotReinitialize() public {
        vm.expectRevert();
        oracle.initialize(admin, operator);
    }

    function test_Initialize_RejectsZeroAdmin() public {
        SentimentOracleV1 newImpl = new SentimentOracleV1();
        bytes memory initData = abi.encodeWithSelector(
            SentimentOracleV1.initialize.selector,
            address(0),
            operator
        );
        vm.expectRevert("Invalid admin address");
        new ERC1967Proxy(address(newImpl), initData);
    }

    function test_Initialize_RejectsZeroOperator() public {
        SentimentOracleV1 newImpl = new SentimentOracleV1();
        bytes memory initData = abi.encodeWithSelector(
            SentimentOracleV1.initialize.selector,
            admin,
            address(0)
        );
        vm.expectRevert("Invalid operator address");
        new ERC1967Proxy(address(newImpl), initData);
    }

    // ============ Update Sentiment Tests ============

    function test_UpdateSentiment_Success() public {
        int128 score = 5e17; // 0.5 (positive sentiment)
        uint32 sampleSize = 1000;
        uint16 confidence = 8500; // 85%

        vm.prank(operator);
        oracle.updateSentiment(tokenA, score, sampleSize, confidence);

        ISentimentOracle.SentimentData memory data = oracle.getSentiment(tokenA);
        assertEq(data.score, score);
        assertEq(data.sampleSize, sampleSize);
        assertEq(data.confidence, confidence);
        assertEq(data.timestamp, block.timestamp);
    }

    function test_UpdateSentiment_EmitsEvent() public {
        int128 score = 5e17;
        uint32 sampleSize = 1000;
        uint16 confidence = 8500;

        vm.expectEmit(true, false, false, true);
        emit ISentimentOracle.SentimentUpdated(
            tokenA,
            score,
            uint64(block.timestamp),
            confidence,
            sampleSize
        );

        vm.prank(operator);
        oracle.updateSentiment(tokenA, score, sampleSize, confidence);
    }

    function test_UpdateSentiment_IncrementsTotalUpdates() public {
        assertEq(oracle.totalUpdates(), 0);

        vm.prank(operator);
        oracle.updateSentiment(tokenA, 5e17, 1000, 8500);

        assertEq(oracle.totalUpdates(), 1);
    }

    function test_UpdateSentiment_RevertsForNonOperator() public {
        vm.prank(user);
        vm.expectRevert();
        oracle.updateSentiment(tokenA, 5e17, 1000, 8500);
    }

    function test_UpdateSentiment_RevertsForZeroAddress() public {
        vm.prank(operator);
        vm.expectRevert(SentimentOracleV1.InvalidToken.selector);
        oracle.updateSentiment(address(0), 5e17, 1000, 8500);
    }

    function test_UpdateSentiment_RevertsForScoreOutOfBounds() public {
        vm.prank(operator);
        vm.expectRevert(abi.encodeWithSelector(SentimentMath.ScoreOutOfBounds.selector, int128(2e18)));
        oracle.updateSentiment(tokenA, 2e18, 1000, 8500);
    }

    function test_UpdateSentiment_RevertsForNegativeScoreOutOfBounds() public {
        vm.prank(operator);
        vm.expectRevert(abi.encodeWithSelector(SentimentMath.ScoreOutOfBounds.selector, int128(-2e18)));
        oracle.updateSentiment(tokenA, -2e18, 1000, 8500);
    }

    function test_UpdateSentiment_RevertsForConfidenceOutOfBounds() public {
        vm.prank(operator);
        vm.expectRevert(abi.encodeWithSelector(SentimentMath.ConfidenceOutOfBounds.selector, uint16(10001)));
        oracle.updateSentiment(tokenA, 5e17, 1000, 10001);
    }

    function test_UpdateSentiment_RevertsForZeroSampleSize() public {
        vm.prank(operator);
        vm.expectRevert(SentimentMath.InvalidSampleSize.selector);
        oracle.updateSentiment(tokenA, 5e17, 0, 8500);
    }

    // ============ Rate Limiting Tests ============

    function test_UpdateSentiment_RateLimiting() public {
        vm.prank(operator);
        oracle.updateSentiment(tokenA, 5e17, 1000, 8500);

        // Try to update again immediately - should fail
        vm.prank(operator);
        vm.expectRevert();
        oracle.updateSentiment(tokenA, 6e17, 1000, 8500);

        // Advance time past minimum interval
        vm.warp(block.timestamp + 4 minutes + 1);

        // Should succeed now
        vm.prank(operator);
        oracle.updateSentiment(tokenA, 6e17, 1000, 8500);
    }

    function test_UpdateSentiment_RateLimitingDifferentTokens() public {
        vm.startPrank(operator);
        
        // Can update different tokens without waiting
        oracle.updateSentiment(tokenA, 5e17, 1000, 8500);
        oracle.updateSentiment(tokenB, 3e17, 500, 7500);
        oracle.updateSentiment(tokenC, -2e17, 2000, 9000);

        vm.stopPrank();

        // Verify all updates
        assertEq(oracle.getSentiment(tokenA).score, 5e17);
        assertEq(oracle.getSentiment(tokenB).score, 3e17);
        assertEq(oracle.getSentiment(tokenC).score, -2e17);
    }

    // ============ Circuit Breaker Tests ============

    function test_CircuitBreaker_TripsOnLargeChange() public {
        // First update
        vm.prank(operator);
        oracle.updateSentiment(tokenA, 5e17, 1000, 8500);

        vm.warp(block.timestamp + 5 minutes);

        // Second update with >20% change (from 0.5 to -0.5 = 100% change)
        vm.prank(operator);
        vm.expectRevert();
        oracle.updateSentiment(tokenA, -5e17, 1000, 8500);
    }

    function test_CircuitBreaker_AllowsSmallChange() public {
        // First update
        vm.prank(operator);
        oracle.updateSentiment(tokenA, 5e17, 1000, 8500);

        vm.warp(block.timestamp + 5 minutes);

        // Second update with small change (0.5 to 0.6 = 20% of range, at the limit)
        vm.prank(operator);
        oracle.updateSentiment(tokenA, 6e17, 1000, 8500);

        assertEq(oracle.getSentiment(tokenA).score, 6e17);
    }

    function test_CircuitBreaker_CanBeDisabled() public {
        // Disable circuit breaker
        vm.prank(admin);
        oracle.setCircuitBreakerEnabled(false);

        // First update
        vm.prank(operator);
        oracle.updateSentiment(tokenA, 5e17, 1000, 8500);

        vm.warp(block.timestamp + 5 minutes);

        // Large change should now work
        vm.prank(operator);
        oracle.updateSentiment(tokenA, -5e17, 1000, 8500);

        assertEq(oracle.getSentiment(tokenA).score, -5e17);
    }

    function test_CircuitBreaker_FirstUpdateBypassesCheck() public {
        // First update to a token can be any value
        vm.prank(operator);
        oracle.updateSentiment(tokenA, 1e18, 1000, 8500);

        assertEq(oracle.getSentiment(tokenA).score, 1e18);
    }

    // ============ Token Whitelist Tests ============

    function test_Whitelist_DisabledByDefault() public {
        // Should be able to update any token when whitelist is disabled
        vm.prank(operator);
        oracle.updateSentiment(tokenA, 5e17, 1000, 8500);

        assertTrue(oracle.isTokenSupported(tokenA));
    }

    function test_Whitelist_BlocksNonWhitelistedToken() public {
        // Enable whitelist
        vm.prank(admin);
        oracle.setTokenWhitelistEnabled(true);

        // Try to update non-whitelisted token
        vm.prank(operator);
        vm.expectRevert(abi.encodeWithSelector(SentimentOracleV1.TokenNotWhitelisted.selector, tokenA));
        oracle.updateSentiment(tokenA, 5e17, 1000, 8500);
    }

    function test_Whitelist_AllowsWhitelistedToken() public {
        // Enable whitelist and add token
        vm.startPrank(admin);
        oracle.setTokenWhitelistEnabled(true);
        oracle.setTokenWhitelist(tokenA, true);
        vm.stopPrank();

        // Should succeed
        vm.prank(operator);
        oracle.updateSentiment(tokenA, 5e17, 1000, 8500);

        assertEq(oracle.getSentiment(tokenA).score, 5e17);
    }

    function test_Whitelist_EmitsEvent() public {
        vm.expectEmit(true, false, false, true);
        emit ISentimentOracle.TokenWhitelisted(tokenA, true);

        vm.prank(admin);
        oracle.setTokenWhitelist(tokenA, true);
    }

    function test_Whitelist_BatchSet() public {
        address[] memory tokens = new address[](3);
        tokens[0] = tokenA;
        tokens[1] = tokenB;
        tokens[2] = tokenC;

        bool[] memory statuses = new bool[](3);
        statuses[0] = true;
        statuses[1] = true;
        statuses[2] = false;

        vm.prank(admin);
        oracle.batchSetTokenWhitelist(tokens, statuses);

        assertTrue(oracle.supportedTokens(tokenA));
        assertTrue(oracle.supportedTokens(tokenB));
        assertFalse(oracle.supportedTokens(tokenC));
    }

    // ============ History Tests ============

    function test_History_StoresEntries() public {
        vm.startPrank(operator);
        
        oracle.updateSentiment(tokenA, 1e17, 100, 8000);
        vm.warp(block.timestamp + 5 minutes);
        
        oracle.updateSentiment(tokenA, 2e17, 200, 8500);
        vm.warp(block.timestamp + 5 minutes);
        
        oracle.updateSentiment(tokenA, 3e17, 300, 9000);
        
        vm.stopPrank();

        ISentimentOracle.SentimentData[] memory history = oracle.getSentimentHistory(tokenA, 3);
        
        assertEq(history.length, 3);
        // Newest first
        assertEq(history[0].score, 3e17);
        assertEq(history[1].score, 2e17);
        assertEq(history[2].score, 1e17);
    }

    function test_History_CircularBufferOverwrite() public {
        // Fill buffer beyond MAX_HISTORY_SIZE
        vm.startPrank(operator);

        for (uint256 i = 0; i < 300; i++) {
            oracle.updateSentiment(tokenA, int128(int256(i * 1e15)), uint32(i + 1), 8000);
            vm.warp(block.timestamp + 5 minutes);
        }

        vm.stopPrank();

        // Should only have MAX_HISTORY_SIZE entries
        assertEq(oracle.getHistoryCount(tokenA), oracle.MAX_HISTORY_SIZE());

        // Oldest entries should be overwritten
        ISentimentOracle.SentimentData[] memory history = oracle.getSentimentHistory(tokenA, 10);
        
        // Most recent should be the last update (index 299)
        assertEq(history[0].score, int128(299 * 1e15));
    }

    function test_History_ReturnsRequestedCount() public {
        vm.startPrank(operator);
        
        for (uint256 i = 0; i < 10; i++) {
            oracle.updateSentiment(tokenA, int128(int256(i * 1e17)), uint32(i + 1), 8000);
            vm.warp(block.timestamp + 5 minutes);
        }
        
        vm.stopPrank();

        // Request less than available
        ISentimentOracle.SentimentData[] memory history = oracle.getSentimentHistory(tokenA, 5);
        assertEq(history.length, 5);

        // Request more than available
        history = oracle.getSentimentHistory(tokenA, 20);
        assertEq(history.length, 10);
    }

    function test_History_RevertsForExcessiveCount() public {
        vm.expectRevert(
            abi.encodeWithSelector(
                SentimentOracleV1.InvalidHistoryCount.selector,
                289,
                oracle.MAX_HISTORY_SIZE()
            )
        );
        oracle.getSentimentHistory(tokenA, 289);
    }

    // ============ Batch Update Tests ============

    function test_BatchUpdate_Success() public {
        address[] memory tokens = new address[](3);
        tokens[0] = tokenA;
        tokens[1] = tokenB;
        tokens[2] = tokenC;

        int128[] memory scores = new int128[](3);
        scores[0] = 5e17;
        scores[1] = 3e17;
        scores[2] = -2e17;

        uint32[] memory sampleSizes = new uint32[](3);
        sampleSizes[0] = 1000;
        sampleSizes[1] = 500;
        sampleSizes[2] = 2000;

        uint16[] memory confidences = new uint16[](3);
        confidences[0] = 8500;
        confidences[1] = 7500;
        confidences[2] = 9000;

        vm.prank(operator);
        oracle.batchUpdateSentiment(tokens, scores, sampleSizes, confidences);

        assertEq(oracle.getSentiment(tokenA).score, 5e17);
        assertEq(oracle.getSentiment(tokenB).score, 3e17);
        assertEq(oracle.getSentiment(tokenC).score, -2e17);
    }

    function test_BatchUpdate_SkipsInvalidTokens() public {
        address[] memory tokens = new address[](3);
        tokens[0] = tokenA;
        tokens[1] = address(0); // Invalid
        tokens[2] = tokenC;

        int128[] memory scores = new int128[](3);
        scores[0] = 5e17;
        scores[1] = 3e17;
        scores[2] = -2e17;

        uint32[] memory sampleSizes = new uint32[](3);
        sampleSizes[0] = 1000;
        sampleSizes[1] = 500;
        sampleSizes[2] = 2000;

        uint16[] memory confidences = new uint16[](3);
        confidences[0] = 8500;
        confidences[1] = 7500;
        confidences[2] = 9000;

        vm.prank(operator);
        oracle.batchUpdateSentiment(tokens, scores, sampleSizes, confidences);

        // Valid tokens updated, invalid skipped
        assertEq(oracle.getSentiment(tokenA).score, 5e17);
        assertEq(oracle.getSentiment(address(0)).score, 0); // Not updated
        assertEq(oracle.getSentiment(tokenC).score, -2e17);
    }

    function test_BatchUpdate_RevertsForTooLargeBatch() public {
        address[] memory tokens = new address[](51);
        int128[] memory scores = new int128[](51);
        uint32[] memory sampleSizes = new uint32[](51);
        uint16[] memory confidences = new uint16[](51);

        for (uint256 i = 0; i < 51; i++) {
            tokens[i] = address(uint160(i + 1));
            scores[i] = 5e17;
            sampleSizes[i] = 1000;
            confidences[i] = 8500;
        }

        vm.prank(operator);
        vm.expectRevert(
            abi.encodeWithSelector(SentimentOracleV1.BatchSizeTooLarge.selector, 51, 50)
        );
        oracle.batchUpdateSentiment(tokens, scores, sampleSizes, confidences);
    }

    function test_BatchUpdate_RevertsForArrayMismatch() public {
        address[] memory tokens = new address[](3);
        int128[] memory scores = new int128[](2); // Mismatch
        uint32[] memory sampleSizes = new uint32[](3);
        uint16[] memory confidences = new uint16[](3);

        vm.prank(operator);
        vm.expectRevert(SentimentOracleV1.ArrayLengthMismatch.selector);
        oracle.batchUpdateSentiment(tokens, scores, sampleSizes, confidences);
    }

    // ============ Pause Tests ============

    function test_Pause_BlocksUpdates() public {
        vm.prank(admin);
        oracle.pause();

        vm.prank(operator);
        vm.expectRevert();
        oracle.updateSentiment(tokenA, 5e17, 1000, 8500);
    }

    function test_Pause_AllowsReads() public {
        // First update
        vm.prank(operator);
        oracle.updateSentiment(tokenA, 5e17, 1000, 8500);

        // Pause
        vm.prank(admin);
        oracle.pause();

        // Reads should still work
        ISentimentOracle.SentimentData memory data = oracle.getSentiment(tokenA);
        assertEq(data.score, 5e17);
    }

    function test_Unpause_AllowsUpdates() public {
        vm.prank(admin);
        oracle.pause();

        vm.prank(admin);
        oracle.unpause();

        vm.prank(operator);
        oracle.updateSentiment(tokenA, 5e17, 1000, 8500);

        assertEq(oracle.getSentiment(tokenA).score, 5e17);
    }

    function test_Pause_OnlyAdmin() public {
        vm.prank(user);
        vm.expectRevert();
        oracle.pause();
    }

    // ============ Data Freshness Tests ============

    function test_IsDataFresh_ReturnsTrue() public {
        vm.prank(operator);
        oracle.updateSentiment(tokenA, 5e17, 1000, 8500);

        assertTrue(oracle.isDataFresh(tokenA, 10 minutes));
    }

    function test_IsDataFresh_ReturnsFalseWhenStale() public {
        vm.prank(operator);
        oracle.updateSentiment(tokenA, 5e17, 1000, 8500);

        vm.warp(block.timestamp + 15 minutes);

        assertFalse(oracle.isDataFresh(tokenA, 10 minutes));
    }

    function test_IsDataFresh_ReturnsFalseWhenNoData() public {
        assertFalse(oracle.isDataFresh(tokenA, 10 minutes));
    }

    // ============ Admin Configuration Tests ============

    function test_SetMaxScoreChange() public {
        int128 newMax = 3e17; // 30%

        vm.prank(admin);
        oracle.setMaxScoreChange(newMax);

        assertEq(oracle.maxScoreChange(), newMax);
    }

    function test_SetMaxScoreChange_OnlyAdmin() public {
        vm.prank(user);
        vm.expectRevert();
        oracle.setMaxScoreChange(3e17);
    }

    function test_SetMaxScoreChange_RevertsForInvalidValue() public {
        vm.prank(admin);
        vm.expectRevert("Invalid max change");
        oracle.setMaxScoreChange(0);

        vm.prank(admin);
        vm.expectRevert("Invalid max change");
        oracle.setMaxScoreChange(2e18); // > MAX_SCORE
    }

    // ============ Upgrade Tests ============

    function test_Upgrade_OnlyUpgrader() public {
        SentimentOracleV1 newImpl = new SentimentOracleV1();

        vm.prank(user);
        vm.expectRevert();
        oracle.upgradeToAndCall(address(newImpl), "");
    }

    function test_Upgrade_Success() public {
        // First, store some data
        vm.prank(operator);
        oracle.updateSentiment(tokenA, 5e17, 1000, 8500);

        // Deploy new implementation
        SentimentOracleV1 newImpl = new SentimentOracleV1();

        // Upgrade
        vm.prank(upgrader);
        oracle.upgradeToAndCall(address(newImpl), "");

        // Data should persist
        assertEq(oracle.getSentiment(tokenA).score, 5e17);
    }

    // ============ Edge Case Tests ============

    function test_ExtremeScores() public {
        vm.startPrank(operator);

        // Maximum positive
        oracle.updateSentiment(tokenA, 1e18, 1000, 8500);
        assertEq(oracle.getSentiment(tokenA).score, 1e18);

        // Reset for next test
        vm.warp(block.timestamp + 5 minutes);

        // Disable circuit breaker for extreme test
        vm.stopPrank();
        vm.prank(admin);
        oracle.setCircuitBreakerEnabled(false);
        vm.startPrank(operator);

        // Maximum negative
        oracle.updateSentiment(tokenB, -1e18, 1000, 8500);
        assertEq(oracle.getSentiment(tokenB).score, -1e18);

        // Neutral
        oracle.updateSentiment(tokenC, 0, 1000, 8500);
        assertEq(oracle.getSentiment(tokenC).score, 0);

        vm.stopPrank();
    }

    function test_ExtremeConfidence() public {
        vm.startPrank(operator);

        // Minimum confidence
        oracle.updateSentiment(tokenA, 5e17, 1000, 0);
        assertEq(oracle.getSentiment(tokenA).confidence, 0);

        // Maximum confidence
        oracle.updateSentiment(tokenB, 5e17, 1000, 10000);
        assertEq(oracle.getSentiment(tokenB).confidence, 10000);

        vm.stopPrank();
    }
}
