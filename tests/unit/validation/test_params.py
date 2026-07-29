import datetime
import decimal
import enum

import pytest

from flama.injection.exceptions import ComponentNotFound


class _Colour(enum.Enum):
    red = "red"
    blue = "blue"


class TestCaseParamsValidation:
    @pytest.fixture(scope="function", autouse=True)
    def add_path_endpoints(self, app):
        @app.route("/str-path-param/{param}/")
        def str_path_param(param: str):
            assert isinstance(param, str)
            return {"param": param}

        @app.route("/int-path-param/{param}/")
        def int_path_param(param: int):
            assert isinstance(param, int)
            return {"param": param}

        @app.route("/float-path-param/{param}/")
        def float_path_param(param: float):
            assert isinstance(param, float)
            return {"param": param}

        @app.route("/decimal-path-param/{param}/")
        def decimal_path_param(param: decimal.Decimal):
            assert isinstance(param, decimal.Decimal)
            return {"param": param}

        @app.route("/bool-path-param/{param}/")
        def bool_path_param(param: bool):
            assert isinstance(param, bool)
            return {"param": param}

        @app.route("/datetime-path-param/{param}/")
        def datetime_path_param(param: datetime.datetime):
            assert isinstance(param, datetime.datetime)
            return {"param": param}

        @app.route("/date-path-param/{param}/")
        def date_path_param(param: datetime.date):
            assert isinstance(param, datetime.date)
            return {"param": param}

        @app.route("/time-path-param/{param}/")
        def time_path_param(param: datetime.time):
            assert isinstance(param, datetime.time)
            return {"param": param}

    @pytest.fixture(scope="function", autouse=True)
    def add_query_endpoints(self, app):
        @app.route("/str-query-param/")
        def str_query_param(param: str):
            assert isinstance(param, str)
            return {"param": param}

        @app.route("/int-query-param/")
        def int_query_param(param: int):
            assert isinstance(param, int)
            return {"param": param}

        @app.route("/float-query-param/")
        def float_query_param(param: float):
            assert isinstance(param, float)
            return {"param": param}

        @app.route("/decimal-query-param/")
        def decimal_query_param(param: decimal.Decimal):
            assert isinstance(param, decimal.Decimal)
            return {"param": param}

        @app.route("/bool-query-param/")
        def bool_query_param(param: bool):
            assert isinstance(param, bool)
            return {"param": param}

        @app.route("/datetime-query-param/")
        def datetime_query_param(param: datetime.datetime):
            assert isinstance(param, datetime.datetime)
            return {"param": param}

        @app.route("/date-query-param/")
        def date_query_param(param: datetime.date):
            assert isinstance(param, datetime.date)
            return {"param": param}

        @app.route("/time-query-param/")
        def time_query_param(param: datetime.time):
            assert isinstance(param, datetime.time)
            return {"param": param}

    @pytest.fixture(scope="function", autouse=True)
    def add_query_with_default_endpoints(self, app):
        @app.route("/str-query-param-with_default/")
        def str_query_param_with_default(param: str = "Foo"):
            assert isinstance(param, str)
            return {"param": param}

        @app.route("/int-query-param-with_default/")
        def int_query_param_with_default(param: int = 0):
            assert isinstance(param, int)
            return {"param": param}

        @app.route("/float-query-param-with_default/")
        def float_query_param_with_default(param: float = 0.0):
            assert isinstance(param, float)
            return {"param": param}

        @app.route("/decimal-query-param-with_default/")
        def decimal_query_param_with_default(param: decimal.Decimal = decimal.Decimal("0.0")):
            assert isinstance(param, decimal.Decimal)
            return {"param": param}

        @app.route("/bool-query-param-with_default/")
        def bool_query_param_with_default(param: bool = False):
            assert isinstance(param, bool)
            return {"param": param}

        @app.route("/datetime-query-param-with_default/")
        def datetime_query_param_with_default(param: datetime.datetime = datetime.datetime(2018, 1, 1, 0, 0, 0)):
            assert isinstance(param, datetime.datetime)
            return {"param": param}

        @app.route("/date-query-param-with_default/")
        def date_query_param_with_default(param: datetime.date = datetime.date(2018, 1, 1)):
            assert isinstance(param, datetime.date)
            return {"param": param}

        @app.route("/time-query-param-with_default/")
        def time_query_param_with_default(param: datetime.time = datetime.time(0, 0, 0)):
            assert isinstance(param, datetime.time)
            return {"param": param}

    @pytest.fixture(scope="function", autouse=True)
    def add_query_optional_endpoints(self, app):
        @app.route("/str-query-param-optional/")
        def str_query_param_optional(param: str | None = None):
            assert param is None
            return {"param": param}

        @app.route("/int-query-param-optional/")
        def int_query_param_optional(param: int | None = None):
            assert param is None
            return {"param": param}

        @app.route("/float-query-param-optional/")
        def float_query_param_optional(param: float | None = None):
            assert param is None
            return {"param": param}

        @app.route("/decimal-query-param-optional/")
        def decimal_query_param_optional(param: decimal.Decimal | None = None):
            assert param is None
            return {"param": param}

        @app.route("/bool-query-param-optional/")
        def bool_query_param_optional(param: bool | None = None):
            assert param is None
            return {"param": param}

        @app.route("/datetime-query-param-optional/")
        def datetime_query_param_optional(param: datetime.datetime | None = None):
            assert param is None
            return {"param": param}

        @app.route("/date-query-param-optional/")
        def date_query_param_optional(param: datetime.date | None = None):
            assert param is None
            return {"param": param}

        @app.route("/time-query-param-optional/")
        def time_query_param_optional(param: datetime.time | None = None):
            assert param is None
            return {"param": param}

    @pytest.fixture(scope="function", autouse=True)
    def add_other_endpoints(self, app):
        @app.route("/empty/", methods=["POST"])
        def empty(foo):
            return {}

    @pytest.mark.parametrize(
        ["url", "value"],
        [
            pytest.param("/str-path-param/123/", "123", id="str-path-param"),
            pytest.param("/int-path-param/123/", 123, id="int-path-param"),
            pytest.param("/float-path-param/123.321/", 123.321, id="float-path-param"),
            pytest.param("/decimal-path-param/123.45/", 123.45, id="decimal-path-param"),
            pytest.param("/bool-path-param/true/", True, id="bool-path-param"),
            pytest.param(
                "/datetime-path-param/2018-01-01T00:00:00+00:00/", "2018-01-01T00:00:00+00:00", id="datetime-path-param"
            ),
            pytest.param("/date-path-param/2018-01-01/", "2018-01-01", id="date-path-param"),
            pytest.param("/time-path-param/00:00:00/", "00:00:00", id="time-path-param"),
        ],
    )
    async def test_path_param(self, url, value, client):
        response = await client.get(url)
        assert response.json() == {"param": value}

    @pytest.mark.parametrize(
        ["url", "value"],
        [
            pytest.param("/str-query-param/", "123", id="str-query-param"),
            pytest.param("/int-query-param/", 123, id="int-query-param"),
            pytest.param("/float-query-param/", 123.321, id="float-query-param"),
            pytest.param("/decimal-query-param/", 123.45, id="decimal-query-param"),
            pytest.param("/bool-query-param/", True, id="bool-query-param"),
            pytest.param("/datetime-query-param/", "2018-01-01T00:00:00", id="datetime-query-param"),
            pytest.param("/date-query-param/", "2018-01-01", id="date-query-param"),
            pytest.param("/time-query-param/", "00:00:00", id="time-query-param"),
        ],
    )
    async def test_query_param(self, url, value, client):
        response = await client.get(url, params={"param": value})
        assert response.json() == {"param": value}

    @pytest.mark.parametrize(
        ["url", "value"],
        [
            pytest.param("/str-query-param-with_default/", "Foo", id="str-query-param-with-default"),
            pytest.param("/int-query-param-with_default/", 0, id="int-query-param-with-default"),
            pytest.param("/float-query-param-with_default/", 0.0, id="float-query-param-with-default"),
            pytest.param("/decimal-query-param-with_default/", 0.0, id="decimal-query-param-with-default"),
            pytest.param("/bool-query-param-with_default/", False, id="bool-query-param-with-default"),
            pytest.param(
                "/datetime-query-param-with_default/", "2018-01-01T00:00:00", id="datetime-query-param-with-default"
            ),
            pytest.param("/date-query-param-with_default/", "2018-01-01", id="date-query-param-with-default"),
            pytest.param("/time-query-param-with_default/", "00:00:00", id="time-query-param-with-default"),
        ],
    )
    async def test_query_param_with_default(self, url, value, client):
        response = await client.get(url, params={"param": value})
        assert response.json() == {"param": value}

    @pytest.mark.parametrize(
        "url",
        [
            pytest.param("/str-query-param-optional/", id="str-query-param-optional"),
            pytest.param("/int-query-param-optional/", id="int-query-param-optional"),
            pytest.param("/float-query-param-optional/", id="float-query-param-optional"),
            pytest.param("/decimal-query-param-optional/", id="decimal-query-param-optional"),
            pytest.param("/bool-query-param-optional/", id="bool-query-param-optional"),
            pytest.param("/datetime-query-param-optional/", id="datetime-query-param-optional"),
            pytest.param("/date-query-param-optional/", id="date-query-param-optional"),
            pytest.param("/time-query-param-optional/", id="time-query-param-optional"),
        ],
    )
    async def test_query_param_optional(self, url, client):
        response = await client.get(url)
        assert response.json() == {"param": None}

    async def test_wrong_query_param(self, client):
        response = await client.get("/int-query-param/?param=foo")
        assert response.status_code == 400

    async def test_wrong_path_param(self, client):
        response = await client.get("/int-path-param/foo/")
        assert response.status_code == 400

    async def test_no_type_param(self, client):
        with pytest.raises(ComponentNotFound, match="No component able to handle parameter 'foo' for function 'empty'"):
            await client.post("/empty/")


class TestCaseListQueryParamsValidation:
    """A query string expresses a collection by repeating a name."""

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/list-query-param/")
        def list_query_param(param: list[int]):
            assert isinstance(param, list)
            return {"param": param}

        @app.route("/scalar-query-param/")
        def scalar_query_param(param: str = "default"):
            assert isinstance(param, str)
            return {"param": param}

        @app.route("/list-query-param-default/")
        def list_query_param_default(param: list[int] = []):  # noqa: B006
            assert isinstance(param, list)
            return {"param": param}

        @app.route("/optional-list-query-param/")
        def optional_list_query_param(param: list[int] | None = None):
            assert param is None or isinstance(param, list)
            return {"param": param}

    @pytest.mark.parametrize(
        ["query", "expected"],
        [
            pytest.param("?param=1&param=2&param=3", [1, 2, 3], id="repeated"),
            # A one-element collection is indistinguishable from a scalar in a query string.
            pytest.param("?param=7", [7], id="single_occurrence"),
        ],
    )
    async def test_list_query_param(self, client, query, expected):
        response = await client.get(f"/list-query-param/{query}")

        assert response.status_code == 200, response.text
        assert response.json() == {"param": expected}

    @pytest.mark.parametrize(
        ["query", "expected"],
        [
            pytest.param("?param=a", "a", id="single"),
            # Repeating a scalar is not an error; the last value wins as it always has.
            pytest.param("?param=a&param=b", "b", id="repeated_keeps_last"),
            pytest.param("", "default", id="absent"),
        ],
    )
    async def test_scalar_query_param_is_unaffected(self, client, query, expected):
        response = await client.get(f"/scalar-query-param/{query}")

        assert response.status_code == 200, response.text
        assert response.json() == {"param": expected}

    @pytest.mark.parametrize(
        ["query", "expected"],
        [
            # A mutable default must not make the parameter unhashable when it is used as a cache key.
            pytest.param("", [], id="absent"),
            pytest.param("?param=1", [1], id="single_occurrence"),
            pytest.param("?param=1&param=2", [1, 2], id="repeated"),
        ],
    )
    async def test_list_query_param_with_mutable_default(self, client, query, expected):
        response = await client.get(f"/list-query-param-default/{query}")

        assert response.status_code == 200, response.text
        assert response.json() == {"param": expected}

    @pytest.mark.parametrize(
        ["query", "expected"],
        [
            # Making a list optional must not turn it back into a scalar.
            pytest.param("?param=1&param=2", [1, 2], id="repeated"),
            pytest.param("?param=7", [7], id="single_occurrence"),
            pytest.param("", None, id="absent"),
        ],
    )
    async def test_optional_list_query_param(self, client, query, expected):
        response = await client.get(f"/optional-list-query-param/{query}")

        assert response.status_code == 200, response.text
        assert response.json() == {"param": expected}


class TestCaseEnumParamsValidation:
    """An enum travels as the plain text of its value, in a query string as much as in a path."""

    @pytest.fixture(scope="function", autouse=True)
    def add_endpoints(self, app):
        @app.route("/enum-query-param/")
        def enum_query_param(param: _Colour):
            assert isinstance(param, _Colour)
            return {"param": param.value}

        @app.route("/optional-enum-query-param/")
        def optional_enum_query_param(param: _Colour | None = None):
            assert param is None or isinstance(param, _Colour)
            return {"param": param.value if param else None}

        @app.route("/enum-path-param/{param}/")
        def enum_path_param(param: _Colour):
            assert isinstance(param, _Colour)
            return {"param": param.value}

    @pytest.mark.parametrize(
        ["path", "query", "status_code", "expected"],
        [
            pytest.param("/enum-query-param/", "?param=red", 200, {"param": "red"}, id="query_by_value"),
            # A member is addressed by its value, so its name is not a second way to name it.
            pytest.param("/enum-query-param/", "?param=RED", 400, None, id="query_by_name_is_rejected"),
            pytest.param("/enum-query-param/", "?param=green", 400, None, id="query_outside_the_value_set"),
            pytest.param("/enum-query-param/", "", 400, None, id="query_missing"),
            pytest.param("/optional-enum-query-param/", "?param=blue", 200, {"param": "blue"}, id="optional_given"),
            pytest.param("/optional-enum-query-param/", "", 200, {"param": None}, id="optional_absent"),
            pytest.param("/enum-path-param/red/", "", 200, {"param": "red"}, id="path_by_value"),
            pytest.param("/enum-path-param/green/", "", 400, None, id="path_outside_the_value_set"),
        ],
    )
    async def test_enum_param(self, client, path, query, status_code, expected):
        response = await client.get(f"{path}{query}")

        assert response.status_code == status_code, response.text

        if expected is not None:
            assert response.json() == expected
