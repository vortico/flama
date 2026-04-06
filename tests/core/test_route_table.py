import pytest

from flama._core.route_table import RouteTable
from flama._core.url import PathMatcher
from flama.routing.routes.base import ScopeType


def _table(*entries):
    """Build a RouteTable from (path_pattern, scope_type_mask, accept_partial, methods) tuples."""
    rt = RouteTable()
    for path, mask, partial, methods in entries:
        has_start = path.startswith("/")
        has_trail = path.endswith("/") and len(path) > 1
        raw = path.strip("/")
        segments = [(False, s, "") for s in raw.split("/") if s] if raw else [(False, "", "")]
        matcher = PathMatcher(has_start, has_trail, segments)
        rt.add_entry(matcher, mask, partial, methods)
    return rt


def _param_table(*entries):
    """Build a RouteTable with parametrized paths."""
    rt = RouteTable()
    for segments_spec, has_start, has_trail, mask, partial, methods in entries:
        matcher = PathMatcher(has_start, has_trail, segments_spec)
        rt.add_entry(matcher, mask, partial, methods)
    return rt


class TestCaseRouteTable:
    @pytest.mark.parametrize(
        ["table", "path", "scope_type_mask", "method", "expected"],
        (
            # --- Full match (result_type=0) ---
            pytest.param(
                _table(("/foo/", ScopeType.http, False, ["GET", "HEAD"])),
                "/foo/",
                ScopeType.http,
                "GET",
                (0, 0, (), "/foo/", None),
                id="full_match_first_route",
            ),
            pytest.param(
                _table(
                    ("/foo/", ScopeType.http, False, ["GET", "HEAD"]),
                    ("/bar/", ScopeType.http, False, ["POST"]),
                ),
                "/bar/",
                ScopeType.http,
                "POST",
                (0, 1, (), "/bar/", None),
                id="full_match_second_route",
            ),
            pytest.param(
                _table(("/ws/", ScopeType.websocket, False, None)),
                "/ws/",
                ScopeType.websocket,
                "",
                (0, 0, (), "/ws/", None),
                id="full_match_websocket",
            ),
            pytest.param(
                _table(("/any/", ScopeType.all, False, None)),
                "/any/",
                ScopeType.http,
                "GET",
                (0, 0, (), "/any/", None),
                id="full_match_both_types_http",
            ),
            pytest.param(
                _table(("/any/", ScopeType.all, False, None)),
                "/any/",
                ScopeType.websocket,
                "",
                (0, 0, (), "/any/", None),
                id="full_match_both_types_websocket",
            ),
            # --- Mount match (result_type=1) ---
            pytest.param(
                _table(("/sub", ScopeType.all, True, None)),
                "/sub/leaf/",
                ScopeType.http,
                "GET",
                (1, 0, (), "/sub", "/leaf/"),
                id="mount_match_http",
            ),
            pytest.param(
                _table(("/sub", ScopeType.all, True, None)),
                "/sub/leaf/",
                ScopeType.websocket,
                "",
                (1, 0, (), "/sub", "/leaf/"),
                id="mount_match_websocket",
            ),
            pytest.param(
                _table(
                    ("/foo/", ScopeType.http, False, ["GET"]),
                    ("/api", ScopeType.all, True, None),
                ),
                "/api/v1/users/",
                ScopeType.http,
                "GET",
                (1, 1, (), "/api", "/v1/users/"),
                id="mount_match_after_route",
            ),
            # --- MethodNotAllowed (result_type=2) ---
            pytest.param(
                _table(("/foo/", ScopeType.http, False, ["GET", "HEAD"])),
                "/foo/",
                ScopeType.http,
                "DELETE",
                (2, 0, ["GET", "HEAD"]),
                id="method_not_allowed_single",
            ),
            pytest.param(
                _table(
                    ("/foo/", ScopeType.http, False, ["GET", "HEAD"]),
                    ("/foo/", ScopeType.http, False, ["POST"]),
                ),
                "/foo/",
                ScopeType.http,
                "DELETE",
                (2, 0, ["GET", "HEAD", "POST"]),
                id="method_not_allowed_accumulated",
            ),
            # --- NotFound (None) ---
            pytest.param(
                _table(("/foo/", ScopeType.http, False, ["GET"])),
                "/bar/",
                ScopeType.http,
                "GET",
                None,
                id="not_found_no_path_match",
            ),
            pytest.param(
                _table(("/foo/", ScopeType.http, False, ["GET"])),
                "/foo/",
                ScopeType.websocket,
                "",
                None,
                id="not_found_wrong_scope_type",
            ),
            pytest.param(
                _table(),
                "/anything/",
                ScopeType.http,
                "GET",
                None,
                id="not_found_empty_table",
            ),
            pytest.param(
                _table(("/foo/", ScopeType.http, False, ["GET"])),
                "/foo/",
                0,
                "",
                None,
                id="not_found_zero_mask",
            ),
            # --- Parametrized paths ---
            pytest.param(
                _param_table(
                    ([(False, "users", ""), (True, "id", "int")], True, True, ScopeType.http, False, ["GET"]),
                ),
                "/users/42/",
                ScopeType.http,
                "GET",
                (0, 0, ("42",), "/users/42/", None),
                id="param_int_match",
            ),
            pytest.param(
                _param_table(
                    ([(False, "items", ""), (True, "slug", "str")], True, True, ScopeType.http, False, ["GET"]),
                ),
                "/items/hello-world/",
                ScopeType.http,
                "GET",
                (0, 0, ("hello-world",), "/items/hello-world/", None),
                id="param_str_match",
            ),
            pytest.param(
                _param_table(
                    (
                        [
                            (False, "items", ""),
                            (True, "id", "uuid"),
                        ],
                        True,
                        True,
                        ScopeType.http,
                        False,
                        ["GET"],
                    ),
                ),
                "/items/550e8400-e29b-41d4-a716-446655440000/",
                ScopeType.http,
                "GET",
                (0, 0, ("550e8400-e29b-41d4-a716-446655440000",), "/items/550e8400-e29b-41d4-a716-446655440000/", None),
                id="param_uuid_match",
            ),
            # --- Partial path on non-mount is skipped ---
            pytest.param(
                _table(("/foo", ScopeType.http, False, ["GET"])),
                "/foo/extra",
                ScopeType.http,
                "GET",
                None,
                id="partial_path_non_mount_skipped",
            ),
            # --- Mount with exact path ---
            pytest.param(
                _table(("/sub", ScopeType.all, True, None)),
                "/sub",
                ScopeType.http,
                "GET",
                (1, 0, (), "/sub", None),
                id="mount_exact_path",
            ),
        ),
    )
    def test_resolve(self, table, path, scope_type_mask, method, expected):
        result = table.resolve(path, scope_type_mask, method)

        if expected is None:
            assert result is None
        else:
            assert result is not None
            assert result[0] == expected[0]
            assert result[1] == expected[1]

            if expected[0] == 2:
                assert sorted(result[2]) == sorted(expected[2])
            else:
                assert tuple(result[2]) == expected[2]
                assert result[3] == expected[3]
                assert result[4] == expected[4]
