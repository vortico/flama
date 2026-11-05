import pytest

from flama import _compat


class TestCaseUrlsafeB64:
    @pytest.mark.parametrize(
        ["data", "padded", "result"],
        (
            pytest.param(b"abc", True, b"YWJj", id="no_padding_needed"),
            pytest.param(b"ab", True, b"YWI=", id="padded"),
            pytest.param(b"ab", False, b"YWI", id="unpadded"),
            pytest.param(b"a", False, b"YQ", id="unpadded_twice"),
        ),
    )
    def test_encode(self, data, padded, result):
        assert _compat.urlsafe_b64encode(data, padded=padded) == result

    def test_encode_pads_by_default(self):
        assert _compat.urlsafe_b64encode(b"a") == b"YQ=="

    @pytest.mark.parametrize(
        ["data", "result"],
        (
            pytest.param(b"YWI=", b"ab", id="padded"),
            pytest.param(b"YWI", b"ab", id="unpadded"),
            pytest.param(b"YQ", b"a", id="unpadded_twice"),
            pytest.param("YWI", b"ab", id="text"),
            pytest.param(b"-_8", b"\xfb\xff", id="urlsafe_alphabet"),
        ),
    )
    def test_decode(self, data, result):
        assert _compat.urlsafe_b64decode(data) == result

    @pytest.mark.parametrize("exception", [ValueError], indirect=["exception"])
    def test_decode_padding_required(self, exception):
        with exception:
            _compat.urlsafe_b64decode(b"YWI", padded=True)
