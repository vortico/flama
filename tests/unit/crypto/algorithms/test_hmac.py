import pytest

from flama.crypto.algorithms.hmac import HMACAlgorithm

ALGORITHMS = ("HS256", "HS384", "HS512")


class TestCaseHMACAlgorithm:
    @pytest.fixture(scope="function")
    def algorithm(self) -> HMACAlgorithm:
        return HMACAlgorithm("HS256")

    @pytest.fixture(scope="function")
    def key(self) -> bytes:
        return b"secret-key"

    @pytest.mark.parametrize(
        ["name", "exception"],
        [
            pytest.param("HS256", None, id="hs256"),
            pytest.param("HS384", None, id="hs384"),
            pytest.param("HS512", None, id="hs512"),
            pytest.param("HS128", ValueError("Unknown symmetric algorithm 'HS128'"), id="unknown_name"),
            pytest.param("EdDSA", ValueError("Unknown symmetric algorithm 'EdDSA'"), id="asymmetric_name"),
        ],
        indirect=["exception"],
    )
    def test_init(self, name, exception) -> None:
        with exception:
            assert HMACAlgorithm(name) is not None

    @pytest.mark.parametrize(
        ["name", "expected"],
        [
            pytest.param("HS256", "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7", id="hs256"),
            pytest.param(
                "HS384",
                "afd03944d84895626b0825f4ab46907f15f9dadbe4101ec682aa034c7cebc59cfaea9ea9076ede7f4af152e8b2fa9cb6",
                id="hs384",
            ),
            pytest.param(
                "HS512",
                "87aa7cdea5ef619d4ff0b4241a1d6cb02379f4e2ce4ec2787ad0b30545e17cdedaa833b7d6b8a702038b274eaea3f4e4"
                "be9d914eeb61f1702e696c203a126854",
                id="hs512",
            ),
        ],
    )
    def test_sign(self, name, expected: str) -> None:
        # The first test case published in RFC 4231.
        message, key = b"Hi There", b"\x0b" * 20

        signature = HMACAlgorithm(name).sign(message, key)

        assert signature == bytes.fromhex(expected)
        assert all(signature != HMACAlgorithm(o).sign(message, key) for o in ALGORITHMS if o != name)

    @pytest.mark.parametrize(
        ["message", "signature", "key_", "expected"],
        [
            pytest.param(b"hello", None, None, True, id="valid"),
            pytest.param(b"tampered", None, None, False, id="tampered_message"),
            pytest.param(b"hello", None, b"wrong-key", False, id="wrong_key"),
            pytest.param(b"hello", b"", None, False, id="empty_signature"),
            pytest.param(b"hello", b"\x00" * 32, None, False, id="wrong_signature"),
        ],
    )
    def test_verify(self, algorithm: HMACAlgorithm, key: bytes, message, signature, key_, expected: bool) -> None:
        valid = algorithm.sign(b"hello", key)

        assert algorithm.verify(message, valid if signature is None else signature, key_ or key) is expected
