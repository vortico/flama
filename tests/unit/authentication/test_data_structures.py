import pytest

from flama.authentication.data_structures import ProtectedResource


class TestCaseProtectedResource:
    @pytest.mark.parametrize(
        ["resource", "path", "url"],
        (
            pytest.param(
                "https://example.com/mcp",
                "/.well-known/oauth-protected-resource/mcp",
                "https://example.com/.well-known/oauth-protected-resource/mcp",
                id="path",
            ),
            pytest.param(
                "https://example.com/public/mcp/",
                "/.well-known/oauth-protected-resource/public/mcp/",
                "https://example.com/.well-known/oauth-protected-resource/public/mcp/",
                id="nested_path",
            ),
            # A slash right after the host is dropped before the well-known path is inserted (RFC 9728).
            pytest.param(
                "https://example.com/",
                "/.well-known/oauth-protected-resource",
                "https://example.com/.well-known/oauth-protected-resource",
                id="root_slash",
            ),
            pytest.param(
                "https://example.com:8443",
                "/.well-known/oauth-protected-resource",
                "https://example.com:8443/.well-known/oauth-protected-resource",
                id="root_with_port",
            ),
        ),
    )
    def test_metadata_location(self, resource, path, url):
        protected_resource = ProtectedResource(resource)

        assert protected_resource.metadata_path == path
        assert protected_resource.metadata_url == url

    @pytest.mark.parametrize(
        ["scopes", "expected"],
        (
            pytest.param(
                ("tools:read",),
                {
                    "resource": "https://example.com/mcp",
                    "authorization_servers": ["https://auth.example.com"],
                    "scopes_supported": ["tools:read"],
                    "bearer_methods_supported": ["header"],
                },
                id="scopes",
            ),
            pytest.param(
                None,
                {
                    "resource": "https://example.com/mcp",
                    "authorization_servers": ["https://auth.example.com"],
                    "bearer_methods_supported": ["header"],
                },
                id="no_scopes",
            ),
        ),
    )
    def test_to_dict(self, scopes, expected):
        protected_resource = ProtectedResource(
            "https://example.com/mcp", authorization_servers=("https://auth.example.com",), scopes_supported=scopes
        )

        assert protected_resource.to_dict() == expected
