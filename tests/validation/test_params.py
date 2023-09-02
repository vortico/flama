import datetime
import typing

import pytest

from flama.injection.exceptions import ComponentNotFound


class TestCaseParamsValidation:
    @pytest.fixture(scope="function", autouse=True)
    def add_path_endpoints(self, app):
        @app.route("/str_path_param/{param}/")
        def str_path_param(param: str):
            assert isinstance(param, str)
            return {"param": param}

        @app.route("/int_path_param/{param}/")
        def int_path_param(param: int):
            assert isinstance(param, int)
            return {"param": param}

        @app.route("/float_path_param/{param}/")
        def float_path_param(param: float):
            assert isinstance(param, float)
            return {"param": param}

        @app.route("/bool_path_param/{param}/")
        def bool_path_param(param: bool):
            assert isinstance(param, bool)
            return {"param": param}

        @app.route("/datetime_path_param/{param}/")
        def datetime_path_param(param: datetime.datetime):
            assert isinstance(param, datetime.datetime)
            return {"param": param}

        @app.route("/date_path_param/{param}/")
        def date_path_param(param: datetime.date):
            assert isinstance(param, datetime.date)
            return {"param": param}

        @app.route("/time_path_param/{param}/")
        def time_path_param(param: datetime.time):
            assert isinstance(param, datetime.time)
            return {"param": param}

    @pytest.fixture(scope="function", autouse=True)
    def add_query_endpoints(self, app):
        @app.route("/str_query_param/")
        def str_query_param(param: str):
            assert isinstance(param, str)
            return {"param": param}

        @app.route("/int_query_param/")
        def int_query_param(param: int):
            assert isinstance(param, int)
            return {"param": param}

        @app.route("/float_query_param/")
        def float_query_param(param: float):
            assert isinstance(param, float)
            return {"param": param}

        @app.route("/bool_query_param/")
        def bool_query_param(param: bool):
            assert isinstance(param, bool)
            return {"param": param}

        @app.route("/datetime_query_param/")
        def datetime_query_param(param: datetime.datetime):
            assert isinstance(param, datetime.datetime)
            return {"param": param}

        @app.route("/date_query_param/")
        def date_query_param(param: datetime.date):
            assert isinstance(param, datetime.date)
            return {"param": param}

        @app.route("/time_query_param/")
        def time_query_param(param: datetime.time):
            assert isinstance(param, datetime.time)
            return {"param": param}

    @pytest.fixture(scope="function", autouse=True)
    def add_query_with_default_endpoints(self, app):
        @app.route("/str_query_param_with_default/")
        def str_query_param_with_default(param: str = "Foo"):
            assert isinstance(param, str)
            return {"param": param}

        @app.route("/int_query_param_with_default/")
        def int_query_param_with_default(param: int = 0):
            assert isinstance(param, int)
            return {"param": param}

        @app.route("/float_query_param_with_default/")
        def float_query_param_with_default(param: float = 0.0):
            assert isinstance(param, float)
            return {"param": param}

        @app.route("/bool_query_param_with_default/")
        def bool_query_param_with_default(param: bool = False):
            assert isinstance(param, bool)
            return {"param": param}

        @app.route("/datetime_query_param_with_default/")
        def datetime_query_param_with_default(param: datetime.datetime = datetime.datetime(2018, 1, 1, 0, 0, 0)):
            assert isinstance(param, datetime.datetime)
            return {"param": param}

        @app.route("/date_query_param_with_default/")
        def date_query_param_with_default(param: datetime.date = datetime.date(2018, 1, 1)):
            assert isinstance(param, datetime.date)
            return {"param": param}

        @app.route("/time_query_param_with_default/")
        def time_query_param_with_default(param: datetime.time = datetime.time(0, 0, 0)):
            assert isinstance(param, datetime.time)
            return {"param": param}

    @pytest.fixture(scope="function", autouse=True)
    def add_query_optional_endpoints(self, app):
        @app.route("/str_query_param_optional/")
        def str_query_param_optional(param: typing.Optional[str] = None):
            assert param is None
            return {"param": param}

        @app.route("/int_query_param_optional/")
        def int_query_param_optional(param: typing.Optional[int] = None):
            assert param is None
            return {"param": param}

        @app.route("/float_query_param_optional/")
        def float_query_param_optional(param: typing.Optional[float] = None):
            assert param is None
            return {"param": param}

        @app.route("/bool_query_param_optional/")
        def bool_query_param_optional(param: typing.Optional[bool] = None):
            assert param is None
            return {"param": param}

        @app.route("/datetime_query_param_optional/")
        def datetime_query_param_optional(param: typing.Optional[datetime.datetime] = None):
            assert param is None
            return {"param": param}

        @app.route("/date_query_param_optional/")
        def date_query_param_optional(param: typing.Optional[datetime.date] = None):
            assert param is None
            return {"param": param}

        @app.route("/time_query_param_optional/")
        def time_query_param_optional(param: typing.Optional[datetime.time] = None):
            assert param is None
            return {"param": param}

    @pytest.fixture(scope="function", autouse=True)
    def add_other_endpoints(self, app):
        @app.route("/empty/", methods=["POST"])
        def empty(foo):
            return {}

    @pytest.mark.parametrize(
        "url,value",
        [
            pytest.param("/str_path_param/123/", "123", id="str path param"),
            pytest.param("/int_path_param/123/", 123, id="int path param"),
            pytest.param("/float_path_param/123.321/", 123.321, id="float path param"),
            pytest.param("/bool_path_param/true/", True, id="float path param"),
            pytest.param(
                "/datetime_path_param/2018-01-01T00:00:00+00:00/", "2018-01-01T00:00:00+00:00", id="datetime path param"
            ),
            pytest.param("/date_path_param/2018-01-01/", "2018-01-01", id="date path param"),
            pytest.param("/time_path_param/00:00:00/", "00:00:00", id="time path param"),
        ],
    )
    async def test_path_param(self, url, value, client):
        response = await client.get(url)
        assert response.json() == {"param": value}

    @pytest.mark.parametrize(
        "url,value",
        [
            pytest.param("/str_query_param/", "123", id="str query param"),
            pytest.param("/int_query_param/", 123, id="int query param"),
            pytest.param("/float_query_param/", 123.321, id="float query param"),
            pytest.param("/bool_query_param/", True, id="bool query param"),
            pytest.param("/datetime_query_param/", "2018-01-01T00:00:00", id="datetime query param"),
            pytest.param("/date_query_param/", "2018-01-01", id="date query param"),
            pytest.param("/time_query_param/", "00:00:00", id="time query param"),
        ],
    )
    async def test_query_param(self, url, value, client):
        response = await client.get(url, params={"param": value})
        assert response.json() == {"param": value}

    @pytest.mark.parametrize(
        "url,value",
        [
            pytest.param("/str_query_param_with_default/", "Foo", id="str query param with default"),
            pytest.param("/int_query_param_with_default/", 0, id="int query param with default"),
            pytest.param("/float_query_param_with_default/", 0.0, id="float query param with default"),
            pytest.param("/bool_query_param_with_default/", False, id="bool query param with default"),
            pytest.param(
                "/datetime_query_param_with_default/", "2018-01-01T00:00:00", id="datetime query param with default"
            ),
            pytest.param("/date_query_param_with_default/", "2018-01-01", id="date query param with default"),
            pytest.param("/time_query_param_with_default/", "00:00:00", id="time query param with default"),
        ],
    )
    async def test_query_param_with_default(self, url, value, client):
        response = await client.get(url, params={"param": value})
        assert response.json() == {"param": value}

    @pytest.mark.parametrize(
        "url",
        [
            pytest.param("/str_query_param_optional/", id="str query param optional"),
            pytest.param("/int_query_param_optional/", id="int query param optional"),
            pytest.param("/float_query_param_optional/", id="float query param optional"),
            pytest.param("/bool_query_param_optional/", id="bool query param optional"),
            pytest.param("/datetime_query_param_optional/", id="datetime query param optional"),
            pytest.param("/date_query_param_optional/", id="date query param optional"),
            pytest.param("/time_query_param_optional/", id="time query param optional"),
        ],
    )
    async def test_query_param_optional(self, url, client):
        response = await client.get(url)
        assert response.json() == {"param": None}

    async def test_wrong_query_param(self, client):
        response = await client.get("/int_query_param/?param=foo")
        assert response.status_code == 400

    async def test_wrong_path_param(self, client):
        response = await client.get("/int_path_param/foo/")
        assert response.status_code == 400

    async def test_no_type_param(self, client):
        with pytest.raises(ComponentNotFound, match="No component able to handle parameter 'foo' for function 'empty'"):
            await client.post("/empty/")
