// SPDX-License-Identifier: MIT
pragma solidity ^0.8.23;

import {Initializable} from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import {AccessControlUpgradeable} from "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import {PausableUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import {ReentrancyGuardUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";

import {ISentimentOracle} from "./interfaces/ISentimentOracle.sol";
import {SentimentMath} from "./libraries/SentimentMath.sol";

/**
 * @title SentimentOracleV1
 * @author SentiBridge Team
 * @notice Production-ready sentiment oracle for DeFi integrations
 * @dev Implements UUPS upgradeable pattern with role-based access control
 *
 * Security features:
 * - Role-based access control (Admin, Operator, Upgrader)
 * - Pausable for emergency situations
 * - Reentrancy protection
 * - Circuit breaker for anomalous updates
 * - Circular buffer to prevent unbounded storage growth
 * - Minimum update interval to prevent spam
 * - Optional token whitelist
 *
 * Storage layout (for upgrades):
 * - Slot 0-50: OpenZeppelin upgradeable contracts
 * - Slot 51+: SentiBridge-specific storage
 */
contract SentimentOracleV1 is
    Initializable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    ReentrancyGuardUpgradeable,
    UUPSUpgradeable,
    ISentimentOracle
{
    using SentimentMath for int128;
    using SentimentMath for uint16;
    using SentimentMath for uint32;

    // ============ Constants ============

    /// @notice Role for oracle operators who can update sentiment
    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");

    /// @notice Role for administrators who can configure the oracle
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");

    /// @notice Role for addresses that can upgrade the contract
    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");

    /// @notice Maximum entries in the circular buffer (24h at 5-min intervals)
    uint256 public constant MAX_HISTORY_SIZE = 288;

    /// @notice Minimum time between updates for the same token (4 minutes)
    uint256 public constant MIN_UPDATE_INTERVAL = 4 minutes;

    /// @notice Maximum tokens that can be updated in a single batch
    uint256 public constant MAX_BATCH_SIZE = 50;

    /// @notice Contract version for upgrade tracking
    string public constant VERSION = "1.0.0";

    // ============ Structs ============

    /**
     * @notice Circular buffer for storing sentiment history
     * @param entries Fixed-size array of sentiment data
     * @param head Index of the next write position
     * @param count Number of entries currently stored
     */
    struct CircularBuffer {
        SentimentData[288] entries;
        uint256 head;
        uint256 count;
    }

    // ============ State Variables ============

    /// @notice Latest sentiment for each token
    mapping(address => SentimentData) public latestSentiment;

    /// @notice Historical sentiment data in circular buffer
    mapping(address => CircularBuffer) internal _history;

    /// @notice Last update timestamp per token (for rate limiting)
    mapping(address => uint256) public lastUpdateTime;

    /// @notice Whitelist of supported tokens
    mapping(address => bool) public supportedTokens;

    /// @notice Whether token whitelist is enforced
    bool public tokenWhitelistEnabled;

    /// @notice Maximum allowed score change per update (circuit breaker)
    int128 public maxScoreChange;

    /// @notice Whether circuit breaker is enabled
    bool public circuitBreakerEnabled;

    /// @notice Total number of updates performed
    uint256 public totalUpdates;

    /// @notice Gap for future storage variables (upgradeable pattern)
    uint256[44] private __gap;

    // ============ Errors ============

    error InvalidToken();
    error TokenNotWhitelisted(address token);
    error UpdateTooFrequent(address token, uint256 nextAllowedTime);
    error CircuitBreakerTripped(address token, int128 change, int128 maxAllowed);
    error BatchSizeTooLarge(uint256 size, uint256 maxSize);
    error ArrayLengthMismatch();
    error InvalidHistoryCount(uint256 requested, uint256 max);

    // ============ Modifiers ============

    /**
     * @notice Ensures token address is valid and optionally whitelisted
     * @param token The token address to validate
     */
    modifier validToken(address token) {
        if (token == address(0)) {
            revert InvalidToken();
        }
        if (tokenWhitelistEnabled && !supportedTokens[token]) {
            revert TokenNotWhitelisted(token);
        }
        _;
    }

    // ============ Constructor ============

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    // ============ Initializer ============

    /**
     * @notice Initialize the oracle contract
     * @param admin Address to receive admin role
     * @param operator Address to receive operator role
     * @dev Can only be called once during proxy deployment
     */
    function initialize(address admin, address operator) public initializer {
        require(admin != address(0), "Invalid admin address");
        require(operator != address(0), "Invalid operator address");

        __AccessControl_init();
        __Pausable_init();
        __ReentrancyGuard_init();
        __UUPSUpgradeable_init();

        // Set up roles
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ADMIN_ROLE, admin);
        _grantRole(OPERATOR_ROLE, operator);
        _grantRole(UPGRADER_ROLE, admin);

        // Initialize default settings
        maxScoreChange = SentimentMath.DEFAULT_MAX_CHANGE; // 20%
        circuitBreakerEnabled = true;
        tokenWhitelistEnabled = false;
    }

    // ============ External Write Functions ============

    /**
     * @inheritdoc ISentimentOracle
     */
    function updateSentiment(
        address token,
        int128 score,
        uint32 sampleSize,
        uint16 confidence
    ) external override onlyRole(OPERATOR_ROLE) whenNotPaused nonReentrant validToken(token) {
        _updateSentiment(token, score, sampleSize, confidence);
    }

    /**
     * @inheritdoc ISentimentOracle
     */
    function batchUpdateSentiment(
        address[] calldata tokens,
        int128[] calldata scores,
        uint32[] calldata sampleSizes,
        uint16[] calldata confidences
    ) external override onlyRole(OPERATOR_ROLE) whenNotPaused nonReentrant {
        uint256 length = tokens.length;

        if (length > MAX_BATCH_SIZE) {
            revert BatchSizeTooLarge(length, MAX_BATCH_SIZE);
        }
        if (length != scores.length || length != sampleSizes.length || length != confidences.length)
        {
            revert ArrayLengthMismatch();
        }

        for (uint256 i = 0; i < length;) {
            address token = tokens[i];

            // Skip invalid or non-whitelisted tokens in batch (don't revert whole batch)
            if (token != address(0) && (!tokenWhitelistEnabled || supportedTokens[token])) {
                // Skip if update too recent (don't revert whole batch)
                // Allow first update (lastUpdateTime == 0) or if enough time has passed
                uint256 lastUpdate = lastUpdateTime[token];
                if (lastUpdate == 0 || block.timestamp >= lastUpdate + MIN_UPDATE_INTERVAL) {
                    _updateSentimentUnchecked(token, scores[i], sampleSizes[i], confidences[i]);
                }
            }

            unchecked {
                ++i;
            }
        }
    }

    // ============ External Read Functions ============

    /**
     * @inheritdoc ISentimentOracle
     */
    function getSentiment(address token) external view override returns (SentimentData memory) {
        return latestSentiment[token];
    }

    /**
     * @inheritdoc ISentimentOracle
     */
    function getSentimentHistory(
        address token,
        uint256 count
    ) external view override returns (SentimentData[] memory) {
        if (count > MAX_HISTORY_SIZE) {
            revert InvalidHistoryCount(count, MAX_HISTORY_SIZE);
        }

        CircularBuffer storage buf = _history[token];
        uint256 actualCount = count > buf.count ? buf.count : count;

        SentimentData[] memory result = new SentimentData[](actualCount);

        for (uint256 i = 0; i < actualCount;) {
            // Read from newest to oldest
            uint256 idx = (buf.head + MAX_HISTORY_SIZE - 1 - i) % MAX_HISTORY_SIZE;
            result[i] = buf.entries[idx];

            unchecked {
                ++i;
            }
        }

        return result;
    }

    /**
     * @inheritdoc ISentimentOracle
     */
    function isTokenSupported(address token) external view override returns (bool) {
        if (!tokenWhitelistEnabled) {
            return true; // All tokens supported when whitelist disabled
        }
        return supportedTokens[token];
    }

    /**
     * @inheritdoc ISentimentOracle
     */
    function getLastUpdateTime(address token) external view override returns (uint256) {
        return lastUpdateTime[token];
    }

    /**
     * @notice Get the number of historical entries for a token
     * @param token The token address
     * @return The number of entries in the history buffer
     */
    function getHistoryCount(address token) external view returns (uint256) {
        return _history[token].count;
    }

    /**
     * @notice Check if the oracle is healthy (recent updates)
     * @param token The token to check
     * @param maxStaleness Maximum age in seconds for data to be considered fresh
     * @return Whether the data is fresh
     */
    function isDataFresh(address token, uint256 maxStaleness) external view returns (bool) {
        uint256 lastUpdate = lastUpdateTime[token];
        if (lastUpdate == 0) {
            return false;
        }
        return block.timestamp - lastUpdate <= maxStaleness;
    }

    // ============ Admin Functions ============

    /**
     * @notice Add or remove a token from the whitelist
     * @param token The token address
     * @param status Whether to whitelist (true) or remove (false)
     */
    function setTokenWhitelist(address token, bool status) external onlyRole(ADMIN_ROLE) {
        require(token != address(0), "Invalid token");
        supportedTokens[token] = status;
        emit TokenWhitelisted(token, status);
    }

    /**
     * @notice Batch whitelist multiple tokens
     * @param tokens Array of token addresses
     * @param statuses Array of whitelist statuses
     */
    function batchSetTokenWhitelist(
        address[] calldata tokens,
        bool[] calldata statuses
    ) external onlyRole(ADMIN_ROLE) {
        require(tokens.length == statuses.length, "Array length mismatch");

        for (uint256 i = 0; i < tokens.length;) {
            if (tokens[i] != address(0)) {
                supportedTokens[tokens[i]] = statuses[i];
                emit TokenWhitelisted(tokens[i], statuses[i]);
            }
            unchecked {
                ++i;
            }
        }
    }

    /**
     * @notice Enable or disable the token whitelist
     * @param enabled Whether to enable the whitelist
     */
    function setTokenWhitelistEnabled(bool enabled) external onlyRole(ADMIN_ROLE) {
        tokenWhitelistEnabled = enabled;
    }

    /**
     * @notice Set the maximum allowed score change (circuit breaker threshold)
     * @param newMaxChange New maximum change value
     */
    function setMaxScoreChange(int128 newMaxChange) external onlyRole(ADMIN_ROLE) {
        require(newMaxChange > 0 && newMaxChange <= SentimentMath.MAX_SCORE, "Invalid max change");
        maxScoreChange = newMaxChange;
    }

    /**
     * @notice Enable or disable the circuit breaker
     * @param enabled Whether to enable the circuit breaker
     */
    function setCircuitBreakerEnabled(bool enabled) external onlyRole(ADMIN_ROLE) {
        circuitBreakerEnabled = enabled;
    }

    /**
     * @notice Pause the oracle (emergency stop)
     */
    function pause() external onlyRole(ADMIN_ROLE) {
        _pause();
    }

    /**
     * @notice Unpause the oracle
     */
    function unpause() external onlyRole(ADMIN_ROLE) {
        _unpause();
    }

    // ============ Internal Functions ============

    /**
     * @notice Internal function to update sentiment with all checks
     */
    function _updateSentiment(
        address token,
        int128 score,
        uint32 sampleSize,
        uint16 confidence
    ) internal {
        // Rate limiting check (skip for first update when lastUpdateTime is 0)
        uint256 lastUpdate = lastUpdateTime[token];
        if (lastUpdate > 0) {
            uint256 nextAllowed = lastUpdate + MIN_UPDATE_INTERVAL;
            if (block.timestamp < nextAllowed) {
                revert UpdateTooFrequent(token, nextAllowed);
            }
        }

        _updateSentimentUnchecked(token, score, sampleSize, confidence);
    }

    /**
     * @notice Internal function to update sentiment without rate limit check
     * @dev Used by batch updates where we skip rather than revert
     */
    function _updateSentimentUnchecked(
        address token,
        int128 score,
        uint32 sampleSize,
        uint16 confidence
    ) internal {
        // Validate inputs
        score.validateScore();
        confidence.validateConfidence();
        sampleSize.validateSampleSize();

        // Circuit breaker check
        if (circuitBreakerEnabled) {
            int128 previousScore = latestSentiment[token].score;
            if (
                previousScore != 0
                    && !SentimentMath.isChangeWithinBounds(score, previousScore, maxScoreChange)
            ) {
                int128 change = SentimentMath.absDiff(score, previousScore);
                emit CircuitBreakerTriggered(token, 1); // Reason: excessive change
                revert CircuitBreakerTripped(token, change, maxScoreChange);
            }
        }

        // Create sentiment data
        uint64 timestamp = uint64(block.timestamp);
        SentimentData memory data =
            SentimentData({score: score, timestamp: timestamp, sampleSize: sampleSize, confidence: confidence});

        // Update latest sentiment
        latestSentiment[token] = data;
        lastUpdateTime[token] = block.timestamp;

        // Add to circular buffer
        CircularBuffer storage buf = _history[token];
        buf.entries[buf.head] = data;
        buf.head = (buf.head + 1) % MAX_HISTORY_SIZE;
        if (buf.count < MAX_HISTORY_SIZE) {
            buf.count++;
        }

        // Increment counter
        unchecked {
            totalUpdates++;
        }

        // Emit event
        emit SentimentUpdated(token, score, timestamp, confidence, sampleSize);
    }

    /**
     * @notice Authorize upgrade (UUPS pattern)
     * @param newImplementation Address of the new implementation
     */
    function _authorizeUpgrade(address newImplementation) internal override onlyRole(UPGRADER_ROLE) {
        // Additional checks can be added here
        require(newImplementation != address(0), "Invalid implementation");
    }
}
