import pytest

from flama.crypto.algorithms.eddsa import EdDSAAlgorithm

# The order of the base point, as given in RFC 8032, section 5.1.
GROUP_ORDER = 2**252 + 27742317777372353535851937790883648493


class TestCaseEdDSAAlgorithm:
    @pytest.fixture(scope="function")
    def algorithm(self) -> EdDSAAlgorithm:
        return EdDSAAlgorithm()

    @pytest.fixture(scope="function")
    def keys(self, algorithm: EdDSAAlgorithm) -> tuple[bytes, bytes]:
        return algorithm.generate()

    @pytest.mark.parametrize(
        ["key", "public", "message", "signature"],
        (
            pytest.param(
                "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
                "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
                "",
                "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46"
                "bd25bf5f0595bbe24655141438e7a100b",
                id="empty_message",
            ),
            pytest.param(
                "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
                "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
                "72",
                "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c"
                "387b2eaeb4302aeeb00d291612bb0c00",
                id="one_byte_message",
            ),
            pytest.param(
                "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
                "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
                "af82",
                "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc659"
                "4a7c15e9716ed28dc027beceea1ec40a",
                id="two_byte_message",
            ),
        ),
    )
    def test_rfc_8032_vectors(self, algorithm: EdDSAAlgorithm, key, public, message, signature) -> None:
        # The vectors published in RFC 8032, section 7.1.
        key, public, message, signature = (bytes.fromhex(value) for value in (key, public, message, signature))

        assert algorithm.public_key(key) == public
        assert algorithm.sign(message, key) == signature
        assert algorithm.verify(message, signature, public) is True

    def test_sign(self, algorithm: EdDSAAlgorithm, keys: tuple[bytes, bytes]) -> None:
        signature = algorithm.sign(b"hello", keys[0])

        assert isinstance(signature, bytes)
        assert len(signature) == 64
        assert signature == algorithm.sign(b"hello", keys[0])

    @pytest.mark.parametrize(
        ["message", "key", "expected"],
        [
            pytest.param(b"hello", "public", True, id="valid"),
            pytest.param(b"tampered", "public", False, id="tampered_message"),
            pytest.param(b"hello", "other", False, id="wrong_key"),
            pytest.param(b"hello", "private", False, id="private_key"),
        ],
    )
    def test_verify(self, algorithm: EdDSAAlgorithm, keys: tuple[bytes, bytes], message, key, expected: bool) -> None:
        private, public = keys
        keyring = {"private": private, "public": public, "other": algorithm.generate()[1]}

        assert algorithm.verify(message, algorithm.sign(b"hello", private), keyring[key]) is expected

    @pytest.mark.parametrize(
        ["signature", "key"],
        [
            pytest.param(b"", None, id="empty_signature"),
            pytest.param(b"\x00" * 63, None, id="short_signature"),
            pytest.param(b"\x00" * 65, None, id="long_signature"),
            pytest.param(b"\x00" * 64, None, id="unusable_signature"),
            pytest.param("unreduced", None, id="unreduced_scalar"),
            pytest.param(None, b"\x00" * 31, id="short_key"),
            pytest.param(None, b"\xff" * 32, id="unusable_key"),
            # The identity, which is a point but never one a signature was made under.
            pytest.param(None, b"\x01" + b"\x00" * 31, id="identity_key"),
            # The identity with its sign bit set, which names no point at all.
            pytest.param(None, b"\x01" + b"\x00" * 30 + b"\x80", id="unusable_identity_key"),
            # A y in range, but one the curve equation has no x for.
            pytest.param(None, b"\x02" + b"\x00" * 31, id="off_curve_key"),
        ],
    )
    def test_verify_malformed(self, algorithm: EdDSAAlgorithm, keys: tuple[bytes, bytes], signature, key) -> None:
        private, public = keys
        valid = algorithm.sign(b"hello", private)

        if signature == "unreduced":
            # A scalar at or above the group order would let one signature be written more than one way.
            signature = valid[:32] + int.to_bytes(GROUP_ORDER, 32, "little")

        assert (
            algorithm.verify(b"hello", valid if signature is None else signature, public if key is None else key)
            is False
        )

    def test_generate(self, algorithm: EdDSAAlgorithm) -> None:
        private, public = algorithm.generate()

        assert len(private) == 32
        assert len(public) == 32
        assert algorithm.public_key(private) == public
        assert algorithm.generate()[0] != private
