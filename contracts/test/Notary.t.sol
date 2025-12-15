// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "forge-std/Test.sol";
import {Notary} from "../src/Notary.sol";

contract NotaryTest is Test {
    Notary notary;
    uint256 signerKey;
    address signer;

    function setUp() public {
        notary = new Notary();
        signerKey = 0xBEEF; // deterministic test key
        signer = vm.addr(signerKey);
    }

    function testNotarizeSucceeds() public {
        bytes32 dataHash = keccak256(abi.encodePacked("test-data"));

        // Build the Ethereum signed message hash equivalent to ECDSA.toEthSignedMessageHash
        bytes32 ethMessageHash = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", dataHash));

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerKey, ethMessageHash);
        bytes memory signature = abi.encodePacked(r, s, v);

        // Call notarize
        uint256 id = notary.notarize(dataHash, signer, signature, "test-metadata");

        assertEq(id, 0);
        // Verify stored attestation
        (bytes32 storedHash, address storedAttestor, uint256 ts, string memory meta) = notary.attestations(id);
        assertEq(storedHash, dataHash);
        assertEq(storedAttestor, signer);
        assertEq(ts > 0, true);
    }
}
