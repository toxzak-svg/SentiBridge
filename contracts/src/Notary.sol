// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

/**
 * @title Notary
 * @notice Minimal on-chain notary to store attestations of data hashes.
 *         This contract is a prototype placeholder: for full zk-TLS / TEE
 *         integration you'd replace or augment this with a verifier
 *         contract that validates zk proofs or trusted-attestation receipts.
 */
contract Notary {
    using ECDSA for bytes32;

    event Notarized(bytes32 indexed dataHash, address indexed attestor, uint256 timestamp, string metadata);

    struct Attestation {
        bytes32 dataHash;
        address attestor;
        uint256 timestamp;
        string metadata;
    }

    // Simple storage of attestations by an incrementing id
    Attestation[] public attestations;

    /**
     * @notice Notarize a data hash with a signer-provided signature.
     * @param dataHash keccak256 hash of the data being notarized
     * @param signerAddress address of the signer who attests the data
     * @param signature signature over the dataHash by the signer
     * @param metadata optional metadata (e.g., pointer to off-chain evidence)
     */
    function notarize(bytes32 dataHash, address signerAddress, bytes calldata signature, string calldata metadata) external returns (uint256) {
        // Recreate the Ethereum signed message hash and recover signer
        bytes32 ethMessageHash = ECDSA.toEthSignedMessageHash(dataHash);
        address recovered = ECDSA.recover(ethMessageHash, signature);

        require(recovered == signerAddress, "Notary: invalid signature");

        Attestation memory a = Attestation({
            dataHash: dataHash,
            attestor: signerAddress,
            timestamp: block.timestamp,
            metadata: metadata
        });

        attestations.push(a);
        uint256 id = attestations.length - 1;

        emit Notarized(dataHash, signerAddress, block.timestamp, metadata);

        return id;
    }

    /**
     * @notice Read-only helper to get the number of attestations stored.
     */
    function attestationsCount() external view returns (uint256) {
        return attestations.length;
    }
}
