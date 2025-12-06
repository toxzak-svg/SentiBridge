// SPDX-License-Identifier: MIT
pragma solidity ^0.8.23;

import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";

/**
 * @title SentiBridgeTimelock
 * @notice Timelock controller for SentiBridge admin operations
 * @dev Wraps OpenZeppelin TimelockController with sensible defaults
 *
 * All critical admin operations should go through this timelock:
 * - Upgrading the oracle contract
 * - Changing circuit breaker parameters
 * - Adding/removing operators
 * - Emergency pause (can be immediate via CANCELLER_ROLE)
 *
 * Recommended delays:
 * - Testnet: 1 hour (for testing)
 * - Mainnet: 24-48 hours
 */
contract SentiBridgeTimelock is TimelockController {
    /**
     * @notice Initialize the timelock
     * @param minDelay Minimum delay for operations (in seconds)
     * @param proposers Addresses that can propose operations
     * @param executors Addresses that can execute operations (use address(0) for anyone)
     * @param admin Optional admin address (use address(0) to renounce)
     */
    constructor(
        uint256 minDelay,
        address[] memory proposers,
        address[] memory executors,
        address admin
    ) TimelockController(minDelay, proposers, executors, admin) {}
}
