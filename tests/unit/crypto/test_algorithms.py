import hashlib

import pytest

from flama.crypto.algorithms import HMACAlgorithm


class TestCaseHMACAlgorithm:
    @pytest.fixture
    def algorithm(self):
        return HMACAlgorithm(hashlib.sha256)

    @pytest.fixture
    def key(self):
        return b"secret-key"

    def test_sign_returns_bytes(self, algorithm, key):
        signature = algorithm.sign(b"hello", key)

        assert isinstance(signature, bytes)
        assert len(signature) == 32  # SHA-256 produces 32-byte digests

    def test_verify_valid(self, algorithm, key):
        message = b"hello"
        signature = algorithm.sign(message, key)

        assert algorithm.verify(message, signature, key) is True

    def test_verify_tampered_message(self, algorithm, key):
        signature = algorithm.sign(b"hello", key)

        assert algorithm.verify(b"tampered", signature, key) is False

    def test_verify_wrong_key(self, algorithm, key):
        signature = algorithm.sign(b"hello", key)

        assert algorithm.verify(b"hello", signature, b"wrong-key") is False

    def test_different_algorithms_produce_different_signatures(self, key):
        sha256 = HMACAlgorithm(hashlib.sha256)
        sha384 = HMACAlgorithm(hashlib.sha384)

        assert sha256.sign(b"hello", key) != sha384.sign(b"hello", key)
