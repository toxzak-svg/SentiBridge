// SPDX-License-Identifier: MIT
pragma solidity ^0.8.23;

/**
 * @title ISentimentOracle
 * @author SentiBridge Team
 * @notice Interface for the SentiBridge Sentiment Oracle
 * @dev All sentiment scores use 18 decimal fixed-point representation
 *      Score range: -1e18 to +1e18 (-100% to +100%)
 *      Confidence range: 0 to 10000 (basis points, 0% to 100%)
 */
interface ISentimentOracle {
    // ============ Structs ============

    /**
     * @notice Sentiment data structure for a token
     * @param score Sentiment score (-1e18 to +1e18)
     * @param timestamp Block timestamp when data was recorded
     * @param sampleSize Number of social posts analyzed
     * @param confidence Confidence level in basis points (0-10000)
     */
    struct SentimentData {
        int128 score;
        uint64 timestamp;
        uint32 sampleSize;
        uint16 confidence;
    }

    // ============ Events ============

    /**
     * @notice Emitted when sentiment is updated for a token
     * @param token The token address
     * @param score The new sentiment score
     * @param timestamp When the update occurred
     * @param confidence Confidence level of the sentiment
     * @param sampleSize Number of posts analyzed
     */
    event SentimentUpdated(
        address indexed token,
        int128 score,
        uint64 timestamp,
        uint16 confidence,
        uint32 sampleSize
    );

    /**
     * @notice Emitted when a token is added/removed from whitelist
     * @param token The token address
     * @param status Whether the token is whitelisted
     */
    event TokenWhitelisted(address indexed token, bool status);

    /**
     * @notice Emitted when circuit breaker triggers
     * @param token The affected token
     * @param reason The reason code for the circuit break
     */
    event CircuitBreakerTriggered(address indexed token, uint8 reason);

    // ============ Read Functions ============

    /**
     * @notice Get the latest sentiment data for a token
     * @param token The token address to query
     * @return The latest SentimentData struct
     */
    function getSentiment(address token) external view returns (SentimentData memory);

    /**
     * @notice Get historical sentiment data for a token
     * @param token The token address to query
     * @param count Number of historical entries to retrieve (max 288)
     * @return Array of SentimentData structs, newest first
     */
    function getSentimentHistory(
        address token,
        uint256 count
    ) external view returns (SentimentData[] memory);

    /**
     * @notice Check if a token is supported by the oracle
     * @param token The token address to check
     * @return Whether the token is supported
     */
    function isTokenSupported(address token) external view returns (bool);

    /**
     * @notice Get the timestamp of the last update for a token
     * @param token The token address to query
     * @return The timestamp of the last update
     */
    function getLastUpdateTime(address token) external view returns (uint256);

    // ============ Write Functions ============

    /**
     * @notice Update sentiment data for a token (operator only)
     * @param token The token address
     * @param score Sentiment score (-1e18 to +1e18)
     * @param sampleSize Number of posts analyzed
     * @param confidence Confidence in basis points (0-10000)
     */
    function updateSentiment(
        address token,
        int128 score,
        uint32 sampleSize,
        uint16 confidence
    ) external;

    /**
     * @notice Batch update sentiment for multiple tokens (operator only)
     * @param tokens Array of token addresses
     * @param scores Array of sentiment scores
     * @param sampleSizes Array of sample sizes
     * @param confidences Array of confidence values
     */
    function batchUpdateSentiment(
        address[] calldata tokens,
        int128[] calldata scores,
        uint32[] calldata sampleSizes,
        uint16[] calldata confidences
    ) external;
}
