import pytest

from flama.config import fields


class TestCaseSecret:
    def test_secret(self):
        secret = fields.Secret("foo")

        assert secret._value == "foo"
        assert repr(secret) == "Secret('*****')"
        assert str(secret) == "foo"
        assert secret == "foo"
        assert secret


class TestCaseURL:
    @pytest.mark.parametrize(
        ["url", "components"],
        (
            pytest.param(
                "",
                {"scheme": "", "netloc": "", "path": "", "params": "", "query": "", "fragment": ""},
                id="empty",
            ),
            pytest.param(
                "https://www.foo.bar/foobar?foo=bar",
                {
                    "scheme": "https",
                    "netloc": "www.foo.bar",
                    "path": "/foobar",
                    "params": "",
                    "query": "foo=bar",
                    "fragment": "",
                },
                id="basic",
            ),
            pytest.param(
                "https://user:pass@www.foo.bar:8000/foobar?foo=bar#barfoo",
                {
                    "scheme": "https",
                    "netloc": "user:pass@www.foo.bar:8000",
                    "path": "/foobar",
                    "params": "",
                    "query": "foo=bar",
                    "fragment": "barfoo",
                },
                id="full",
            ),
        ),
    )
    def test_url(self, url, components):
        url_obj = fields.URL(url)

        assert url_obj.components == components
        assert str(url_obj) == url
        assert repr(url_obj) == f"URL('{url}')"
        assert url_obj == url
        assert url_obj == fields.URL(url)
