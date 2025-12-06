// SPDX-License-Identifier: MIT
pragma solidity ^0.8.23;

/**
 * @title SentimentMath
 * @author SentiBridge Team
 * @notice Library for sentiment score calculations and validation
 * @dev Uses 18 decimal fixed-point math for precision
 */
library SentimentMath {
    // ============ Constants ============

    /// @notice Maximum positive sentiment score (1.0)
    int128 public constant MAX_SCORE = 1e18;

    /// @notice Minimum negative sentiment score (-1.0)
    int128 public constant MIN_SCORE = -1e18;

    /// @notice Maximum confidence value (100% in basis points)
    uint16 public constant MAX_CONFIDENCE = 10000;

    /// @notice Default maximum score change per update (20%)
    int128 public constant DEFAULT_MAX_CHANGE = 2e17;

    // ============ Errors ============

    error ScoreOutOfBounds(int128 score);
    error ConfidenceOutOfBounds(uint16 confidence);
    error ExcessiveScoreChange(int128 change, int128 maxAllowed);
    error InvalidSampleSize();

    // ============ Functions ============

    /**
     * @notice Validate that a sentiment score is within bounds
     * @param score The score to validate
     * @return The validated score
     */
    function validateScore(int128 score) internal pure returns (int128) {
        if (score < MIN_SCORE || score > MAX_SCORE) {
            revert ScoreOutOfBounds(score);
        }
        return score;
    }

    /**
     * @notice Validate that confidence is within bounds
     * @param confidence The confidence value to validate
     * @return The validated confidence
     */
    function validateConfidence(uint16 confidence) internal pure returns (uint16) {
        if (confidence > MAX_CONFIDENCE) {
            revert ConfidenceOutOfBounds(confidence);
        }
        return confidence;
    }

    /**
     * @notice Validate sample size is positive
     * @param sampleSize The sample size to validate
     * @return The validated sample size
     */
    function validateSampleSize(uint32 sampleSize) internal pure returns (uint32) {
        if (sampleSize == 0) {
            revert InvalidSampleSize();
        }
        return sampleSize;
    }

    /**
     * @notice Calculate the absolute difference between two scores
     * @param a First score
     * @param b Second score
     * @return The absolute difference
     */
    function absDiff(int128 a, int128 b) internal pure returns (int128) {
        int128 diff = a - b;
        return diff >= 0 ? diff : -diff;
    }

    /**
     * @notice Check if score change is within allowed bounds
     * @param newScore The new score
     * @param oldScore The previous score
     * @param maxChange Maximum allowed change
     * @return Whether the change is within bounds
     */
    function isChangeWithinBounds(
        int128 newScore,
        int128 oldScore,
        int128 maxChange
    ) internal pure returns (bool) {
        // Allow any change if this is the first update (oldScore == 0)
        if (oldScore == 0) {
            return true;
        }
        return absDiff(newScore, oldScore) <= maxChange;
    }

    /**
     * @notice Calculate weighted average of two scores
     * @param score1 First score
     * @param weight1 Weight of first score (basis points)
     * @param score2 Second score
     * @param weight2 Weight of second score (basis points)
     * @return The weighted average score
     */
    function weightedAverage(
        int128 score1,
        uint256 weight1,
        int128 score2,
        uint256 weight2
    ) internal pure returns (int128) {
        require(weight1 + weight2 > 0, "Total weight must be positive");

        // Use int256 for intermediate calculations to prevent overflow
        int256 weighted1 = int256(score1) * int256(weight1);
        int256 weighted2 = int256(score2) * int256(weight2);
        int256 totalWeight = int256(weight1 + weight2);

        return int128((weighted1 + weighted2) / totalWeight);
    }

    /**
     * @notice Convert basis points to 18 decimal representation
     * @param basisPoints Value in basis points (0-10000)
     * @return Value in 18 decimal fixed-point
     */
    function basisPointsToFixed(uint16 basisPoints) internal pure returns (uint256) {
        return uint256(basisPoints) * 1e14; // 10000 bp = 1e18
    }

    /**
     * @notice Convert 18 decimal value to basis points
     * @param fixedValue Value in 18 decimal fixed-point
     * @return Value in basis points (capped at 10000)
     */
    function fixedToBasisPoints(uint256 fixedValue) internal pure returns (uint16) {
        uint256 bp = fixedValue / 1e14;
        return bp > MAX_CONFIDENCE ? MAX_CONFIDENCE : uint16(bp);
    }
}
