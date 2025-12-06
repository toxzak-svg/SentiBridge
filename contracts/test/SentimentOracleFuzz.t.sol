// SPDX-License-Identifier: MIT
pragma solidity ^0.8.23;

import {Test, console2} from "forge-std/Test.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

import {SentimentOracleV1} from "../src/SentimentOracleV1.sol";
import {ISentimentOracle} from "../src/interfaces/ISentimentOracle.sol";
import {SentimentMath} from "../src/libraries/SentimentMath.sol";

/**
 * @title SentimentOracleFuzzTest
 * @notice Fuzz testing for the SentimentOracleV1 contract
 * @dev Run with: forge test --match-contract SentimentOracleFuzzTest -vvv
 */
contract SentimentOracleFuzzTest is Test {
    SentimentOracleV1 public oracle;

    address public admin = makeAddr("admin");
    address public operator = makeAddr("operator");

    function setUp() public {
        SentimentOracleV1 implementation = new SentimentOracleV1();
        bytes memory initData = abi.encodeWithSelector(
            SentimentOracleV1.initialize.selector,
            admin,
            operator
        );
        ERC1967Proxy proxy = new ERC1967Proxy(address(implementation), initData);
        oracle = SentimentOracleV1(address(proxy));

        // Disable circuit breaker for fuzz testing
        vm.prank(admin);
        oracle.setCircuitBreakerEnabled(false);
    }

    /**
     * @notice Fuzz test that valid scores are always accepted
     */
    function testFuzz_UpdateSentiment_ValidScores(
        address token,
        int128 score,
        uint32 sampleSize,
        uint16 confidence
    ) public {
        // Bound inputs to valid ranges
        vm.assume(token != address(0));
        score = int128(bound(int256(score), -1e18, 1e18));
        sampleSize = uint32(bound(sampleSize, 1, type(uint32).max));
        confidence = uint16(bound(confidence, 0, 10000));

        // Advance time to avoid rate limiting
        vm.warp(block.timestamp + 5 minutes);

        vm.prank(operator);
        oracle.updateSentiment(token, score, sampleSize, confidence);

        ISentimentOracle.SentimentData memory data = oracle.getSentiment(token);
        assertEq(data.score, score);
        assertEq(data.sampleSize, sampleSize);
        assertEq(data.confidence, confidence);
    }

    /**
     * @notice Fuzz test that invalid scores are always rejected
     */
    function testFuzz_UpdateSentiment_InvalidScores(
        address token,
        int128 score
    ) public {
        vm.assume(token != address(0));
        vm.assume(score < -1e18 || score > 1e18);

        vm.prank(operator);
        vm.expectRevert();
        oracle.updateSentiment(token, score, 1000, 8500);
    }

    /**
     * @notice Fuzz test that invalid confidence is always rejected
     */
    function testFuzz_UpdateSentiment_InvalidConfidence(
        address token,
        uint16 confidence
    ) public {
        vm.assume(token != address(0));
        vm.assume(confidence > 10000);

        vm.prank(operator);
        vm.expectRevert();
        oracle.updateSentiment(token, 5e17, 1000, confidence);
    }

    /**
     * @notice Fuzz test history always returns correct count
     */
    function testFuzz_GetSentimentHistory_Count(
        uint8 updateCount,
        uint8 requestCount
    ) public {
        address token = makeAddr("token");
        updateCount = uint8(bound(updateCount, 1, 50)); // Reasonable test range
        requestCount = uint8(bound(requestCount, 1, 100));

        // Advance time to start fresh
        vm.warp(block.timestamp + 5 minutes);

        // Perform updates
        vm.startPrank(operator);
        for (uint256 i = 0; i < updateCount; i++) {
            // forge-lint: disable-next-line(unsafe-typecast)
            oracle.updateSentiment(token, int128(int256(i * 1e16)), uint32(i + 1), 8000);
            vm.warp(block.timestamp + 5 minutes);
        }
        vm.stopPrank();

        // Request history
        uint256 expectedCount = requestCount > updateCount ? updateCount : requestCount;
        if (requestCount > 288) {
            vm.expectRevert();
            oracle.getSentimentHistory(token, requestCount);
        } else {
            ISentimentOracle.SentimentData[] memory history = oracle.getSentimentHistory(token, requestCount);
            assertEq(history.length, expectedCount);
        }
    }

    /**
     * @notice Fuzz test batch updates
     */
    function testFuzz_BatchUpdate(uint8 batchSize) public {
        batchSize = uint8(bound(batchSize, 1, 50));

        // Advance time to avoid rate limiting
        vm.warp(block.timestamp + 5 minutes);

        address[] memory tokens = new address[](batchSize);
        int128[] memory scores = new int128[](batchSize);
        uint32[] memory sampleSizes = new uint32[](batchSize);
        uint16[] memory confidences = new uint16[](batchSize);

        for (uint256 i = 0; i < batchSize; i++) {
            // forge-lint: disable-next-line(unsafe-typecast)
            tokens[i] = address(uint160(i + 1));
            // Calculate score within bounds
            // forge-lint: disable-next-line(unsafe-typecast)
            scores[i] = int128(int256((i % 100) * 1e16)); // 0 to 0.99e18
            // forge-lint: disable-next-line(unsafe-typecast)
            sampleSizes[i] = uint32(i + 1);
            confidences[i] = 8500;
        }

        vm.prank(operator);
        oracle.batchUpdateSentiment(tokens, scores, sampleSizes, confidences);

        // Verify all updates
        for (uint256 i = 0; i < batchSize; i++) {
            assertEq(oracle.getSentiment(tokens[i]).score, scores[i]);
        }
    }

    /**
     * @notice Fuzz test that circular buffer works correctly
     */
    function testFuzz_CircularBuffer_Integrity(uint16 totalUpdates) public {
        address token = makeAddr("token");
        totalUpdates = uint16(bound(totalUpdates, 1, 500));

        // Advance time to start fresh
        vm.warp(block.timestamp + 5 minutes);

        vm.startPrank(operator);
        for (uint256 i = 0; i < totalUpdates; i++) {
            // forge-lint: disable-next-line(unsafe-typecast)
            int128 score = int128(int256((i % 200) * 5e15)); // Stay within bounds
            // forge-lint: disable-next-line(unsafe-typecast)
            oracle.updateSentiment(token, score, uint32(i + 1), 8000);
            vm.warp(block.timestamp + 5 minutes);
        }
        vm.stopPrank();

        // Buffer should never exceed MAX_HISTORY_SIZE
        uint256 historyCount = oracle.getHistoryCount(token);
        assertTrue(historyCount <= oracle.MAX_HISTORY_SIZE());

        // If we updated more than MAX_HISTORY_SIZE, count should be exactly MAX_HISTORY_SIZE
        if (totalUpdates >= oracle.MAX_HISTORY_SIZE()) {
            assertEq(historyCount, oracle.MAX_HISTORY_SIZE());
        } else {
            assertEq(historyCount, totalUpdates);
        }

        // Latest should always be the last update
        ISentimentOracle.SentimentData memory latest = oracle.getSentiment(token);
        assertEq(latest.sampleSize, uint32(totalUpdates));
    }

    /**
     * @notice Fuzz test rate limiting
     */
    function testFuzz_RateLimiting(uint32 timeDelta) public {
        address token = makeAddr("token");
        timeDelta = uint32(bound(timeDelta, 0, 10 minutes));

        // First advance time to ensure we can do initial update
        vm.warp(block.timestamp + 5 minutes);
        uint256 initialTime = block.timestamp;

        vm.prank(operator);
        oracle.updateSentiment(token, 5e17, 1000, 8500);

        vm.warp(initialTime + timeDelta);

        if (timeDelta < 4 minutes) {
            vm.prank(operator);
            vm.expectRevert();
            oracle.updateSentiment(token, 6e17, 1000, 8500);
        } else {
            vm.prank(operator);
            oracle.updateSentiment(token, 6e17, 1000, 8500);
            assertEq(oracle.getSentiment(token).score, 6e17);
        }
    }
}

/**
 * @title SentimentOracleInvariantTest
 * @notice Invariant testing for the SentimentOracleV1 contract
 */
contract SentimentOracleInvariantTest is Test {
    SentimentOracleV1 public oracle;
    InvariantHandler public handler;

    function setUp() public {
        SentimentOracleV1 implementation = new SentimentOracleV1();
        bytes memory initData = abi.encodeWithSelector(
            SentimentOracleV1.initialize.selector,
            address(this),
            address(this)
        );
        ERC1967Proxy proxy = new ERC1967Proxy(address(implementation), initData);
        oracle = SentimentOracleV1(address(proxy));

        // Disable circuit breaker for invariant testing
        oracle.setCircuitBreakerEnabled(false);

        handler = new InvariantHandler(oracle);
        targetContract(address(handler));
    }

    /**
     * @notice Invariant: scores are always within valid bounds
     */
    function invariant_ScoresWithinBounds() public view {
        address[] memory tokens = handler.getTokens();
        for (uint256 i = 0; i < tokens.length; i++) {
            ISentimentOracle.SentimentData memory data = oracle.getSentiment(tokens[i]);
            if (data.timestamp > 0) {
                assertTrue(data.score >= -1e18);
                assertTrue(data.score <= 1e18);
            }
        }
    }

    /**
     * @notice Invariant: confidence is always within valid bounds
     */
    function invariant_ConfidenceWithinBounds() public view {
        address[] memory tokens = handler.getTokens();
        for (uint256 i = 0; i < tokens.length; i++) {
            ISentimentOracle.SentimentData memory data = oracle.getSentiment(tokens[i]);
            if (data.timestamp > 0) {
                assertTrue(data.confidence <= 10000);
            }
        }
    }

    /**
     * @notice Invariant: history count never exceeds maximum
     */
    function invariant_HistoryBounded() public view {
        address[] memory tokens = handler.getTokens();
        for (uint256 i = 0; i < tokens.length; i++) {
            uint256 count = oracle.getHistoryCount(tokens[i]);
            assertTrue(count <= oracle.MAX_HISTORY_SIZE());
        }
    }

    /**
     * @notice Invariant: total updates always increases
     */
    function invariant_TotalUpdatesMonotonic() public view {
        assertTrue(oracle.totalUpdates() >= handler.expectedUpdates());
    }
}

/**
 * @title InvariantHandler
 * @notice Handler contract for invariant testing
 */
contract InvariantHandler is Test {
    SentimentOracleV1 public oracle;
    address[] public tokens;
    uint256 public expectedUpdates;

    constructor(SentimentOracleV1 _oracle) {
        oracle = _oracle;
    }

    function updateSentiment(
        uint256 tokenSeed,
        int128 score,
        uint32 sampleSize,
        uint16 confidence
    ) external {
        // Generate token address from seed
        address token = address(uint160(bound(tokenSeed, 1, 1000)));
        
        // Add to tokens list if new
        bool found = false;
        for (uint256 i = 0; i < tokens.length; i++) {
            if (tokens[i] == token) {
                found = true;
                break;
            }
        }
        if (!found) {
            tokens.push(token);
        }

        // Bound inputs
        score = int128(bound(int256(score), -1e18, 1e18));
        sampleSize = uint32(bound(sampleSize, 1, type(uint32).max));
        confidence = uint16(bound(confidence, 0, 10000));

        // Advance time to avoid rate limiting
        vm.warp(block.timestamp + 5 minutes);

        // Update sentiment
        oracle.updateSentiment(token, score, sampleSize, confidence);
        expectedUpdates++;
    }

    function getTokens() external view returns (address[] memory) {
        return tokens;
    }
}
