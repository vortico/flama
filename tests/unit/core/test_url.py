import pytest

from flama._core.url import PathMatcher


class TestCasePathMatcher:
    @pytest.mark.parametrize(
        ["matcher", "input", "result"],
        (
            # -- No-match cases --
            pytest.param(
                PathMatcher(True, False, [(False, "foo", "")]),
                "",
                None,
                id="no_match_empty_input",
            ),
            pytest.param(
                PathMatcher(True, True, [(True, "x", "int")]),
                "/foo/",
                None,
                id="no_match_int_alpha",
            ),
            pytest.param(
                PathMatcher(True, True, [(True, "x", "int")]),
                "/1.5/",
                None,
                id="no_match_int_float",
            ),
            pytest.param(
                PathMatcher(True, True, [(True, "x", "int")]),
                "//",
                None,
                id="no_match_int_empty_segment",
            ),
            pytest.param(
                PathMatcher(True, True, [(True, "x", "float")]),
                "/foo/",
                None,
                id="no_match_float_alpha",
            ),
            pytest.param(
                PathMatcher(True, True, [(True, "x", "float")]),
                "/1./",
                None,
                id="no_match_float_no_fraction",
            ),
            pytest.param(
                PathMatcher(True, True, [(True, "x", "float")]),
                "/1.2.3/",
                None,
                id="no_match_float_double_dot",
            ),
            pytest.param(
                PathMatcher(True, True, [(True, "x", "uuid")]),
                "/83a8e611/",
                None,
                id="no_match_uuid_short",
            ),
            pytest.param(
                PathMatcher(True, True, [(True, "x", "uuid")]),
                "/83A8E611-525C-4D30-9BBF-F2C142606A3D/",
                None,
                id="no_match_uuid_uppercase",
            ),
            pytest.param(
                PathMatcher(True, False, [(False, "foo", "")]),
                "/wrong",
                None,
                id="no_match_constant",
            ),
            # -- Exact match cases --
            pytest.param(
                PathMatcher(True, False, []),
                "/",
                (1, (), "/", None),
                id="exact_root",
            ),
            pytest.param(
                PathMatcher(False, False, [(False, "", "")]),
                "",
                (1, (), None, None),
                id="exact_empty",
            ),
            pytest.param(
                PathMatcher(True, True, [(True, "x", "str")]),
                "/bar/",
                (1, ("bar",), "/bar/", None),
                id="exact_str",
            ),
            pytest.param(
                PathMatcher(True, True, [(True, "x", "int")]),
                "/1/",
                (1, ("1",), "/1/", None),
                id="exact_int",
            ),
            pytest.param(
                PathMatcher(True, True, [(True, "x", "int")]),
                "/0/",
                (1, ("0",), "/0/", None),
                id="exact_int_zero",
            ),
            pytest.param(
                PathMatcher(True, True, [(True, "x", "int")]),
                "/-42/",
                (1, ("-42",), "/-42/", None),
                id="exact_int_negative",
            ),
            pytest.param(
                PathMatcher(True, True, [(True, "x", "float")]),
                "/3.14/",
                (1, ("3.14",), "/3.14/", None),
                id="exact_float",
            ),
            pytest.param(
                PathMatcher(True, True, [(True, "x", "float")]),
                "/42/",
                (1, ("42",), "/42/", None),
                id="exact_float_integer_form",
            ),
            pytest.param(
                PathMatcher(True, True, [(True, "x", "float")]),
                "/-3.14/",
                (1, ("-3.14",), "/-3.14/", None),
                id="exact_float_negative",
            ),
            pytest.param(
                PathMatcher(True, True, [(True, "x", "uuid")]),
                "/83a8e611-525c-4d30-9bbf-f2c142606a3d/",
                (1, ("83a8e611-525c-4d30-9bbf-f2c142606a3d",), "/83a8e611-525c-4d30-9bbf-f2c142606a3d/", None),
                id="exact_uuid",
            ),
            # -- Partial match cases --
            pytest.param(
                PathMatcher(True, False, []),
                "/foo",
                (2, (), "/", "foo"),
                id="partial_root",
            ),
            pytest.param(
                PathMatcher(True, False, [(True, "x", "str")]),
                "/foo/bar/baz",
                (2, ("foo",), "/foo", "/bar/baz"),
                id="partial_param",
            ),
            pytest.param(
                PathMatcher(True, False, []),
                "/unused/path",
                (2, (), "/", "unused/path"),
                id="partial_constant",
            ),
            # -- Multi-parameter cases --
            pytest.param(
                PathMatcher(True, True, [(True, "id", "int"), (False, "posts", ""), (True, "pid", "int")]),
                "/1/posts/42/",
                (1, ("1", "42"), "/1/posts/42/", None),
                id="multi_param",
            ),
            pytest.param(
                PathMatcher(True, False, [(False, "api", ""), (True, "version", "str"), (False, "users", "")]),
                "/api/v2/users",
                (1, ("v2",), "/api/v2/users", None),
                id="constant_param_interleave",
            ),
        ),
    )
    def test_match_path(self, matcher, input, result):
        assert matcher.match_path(input) == result
