from unittest.mock import MagicMock

import pytest

from flama import exceptions, types
from flama.injection.resolver import Parameter
from flama.validation import (
    CompositeParamComponent,
    PrimitiveParamComponent,
    ValidatedPathParams,
    ValidatedQueryParams,
    ValidatedRequestData,
    ValidatePathParamsComponent,
    ValidateRequestDataComponent,
    WebSocketMessageDataComponent,
)


class TestCaseValidatePathParamsComponent:
    @pytest.mark.parametrize(
        ["path_params", "validate_return", "expected", "exception"],
        [
            pytest.param(
                types.PathParams({"id": 1}),
                {"id": 1},
                ValidatedPathParams({"id": 1}),
                None,
                id="success",
            ),
            pytest.param(
                types.PathParams({"id": "bad"}),
                None,
                None,
                exceptions.ValidationError(detail=[{"error": "invalid"}]),
                id="validation_error",
            ),
        ],
        indirect=["exception"],
    )
    async def test_resolve(self, path_params, validate_return, expected, exception):
        component = ValidatePathParamsComponent()
        request = MagicMock()
        request.method = "GET"
        route = MagicMock()
        field = MagicMock()
        route.parameters.path.__getitem__ = MagicMock(return_value={"id": MagicMock(field=field)})

        mock_schema = MagicMock()
        if validate_return is not None:
            mock_schema.validate.return_value = validate_return
        else:
            from flama.schemas import SchemaValidationError

            mock_schema.validate.side_effect = SchemaValidationError(errors=[{"error": "invalid"}])

        with exception:
            from unittest.mock import patch

            with patch("flama.validation.Schema.build", return_value=mock_schema):
                result = await component.resolve(request, route, path_params)

            assert result == expected


class TestCaseValidateRequestDataComponent:
    @pytest.mark.parametrize(
        ["body_param", "data", "expected", "exception"],
        [
            pytest.param(
                None,
                types.RequestData({}),
                None,
                exceptions.ApplicationError("Body schema parameter not defined"),
                id="body_param_none",
            ),
            pytest.param(
                MagicMock(schema=MagicMock(validate=MagicMock(return_value={"key": "value"}))),
                types.RequestData({"key": "value"}),
                ValidatedRequestData({"key": "value"}),
                None,
                id="success",
            ),
        ],
        indirect=["exception"],
    )
    def test_resolve(self, body_param, data, expected, exception):
        component = ValidateRequestDataComponent()
        request = MagicMock()
        request.method = "POST"
        route = MagicMock()
        route.parameters.body.__getitem__ = MagicMock(return_value=body_param)

        with exception:
            result = component.resolve(request, route, data)

            assert isinstance(result, ValidatedRequestData)
            assert result == expected


class TestCasePrimitiveParamComponent:
    def test_resolve_from_path(self):
        component = PrimitiveParamComponent()
        parameter = Parameter(name="id", annotation=int, default=Parameter.empty)
        path_params = ValidatedPathParams({"id": 42})
        query_params = ValidatedQueryParams({})

        mock_schema = MagicMock()
        mock_schema.validate.return_value = {"id": 42}

        from unittest.mock import patch

        with patch("flama.validation.Schema.build", return_value=mock_schema):
            result = component.resolve(parameter, path_params, query_params)

        assert result == 42

    def test_resolve_from_query(self):
        component = PrimitiveParamComponent()
        parameter = Parameter(name="q", annotation=str, default="default")
        path_params = ValidatedPathParams({})
        query_params = ValidatedQueryParams({"q": "search"})

        mock_schema = MagicMock()
        mock_schema.validate.return_value = {"q": "search"}

        from unittest.mock import patch

        with patch("flama.validation.Schema.build", return_value=mock_schema):
            result = component.resolve(parameter, path_params, query_params)

        assert result == "search"

    def test_resolve_default(self):
        component = PrimitiveParamComponent()
        parameter = Parameter(name="missing", annotation=str, default="fallback")
        path_params = ValidatedPathParams({})
        query_params = ValidatedQueryParams({})

        mock_schema = MagicMock()
        mock_schema.validate.return_value = {}

        from unittest.mock import patch

        with patch("flama.validation.Schema.build", return_value=mock_schema):
            result = component.resolve(parameter, path_params, query_params)

        assert result == "fallback"


class TestCaseCompositeParamComponent:
    def test_resolve_body_param_none(self):
        component = CompositeParamComponent()
        parameter = MagicMock()
        parameter.annotation = str
        request = MagicMock()
        request.method = "POST"
        route = MagicMock()
        route.parameters.body.__getitem__ = MagicMock(return_value=None)
        data = types.RequestData({})

        with pytest.raises(exceptions.ApplicationError, match="Body schema parameter not defined"):
            component.resolve(parameter, request, route, data)


class TestCaseWebSocketMessageDataComponent:
    @pytest.mark.parametrize(
        ["message", "encoding", "exception"],
        [
            pytest.param(types.Message({"bytes": b"hello"}), "bytes", None, id="success"),
            pytest.param(types.Message({}), "unknown", exceptions.WebSocketException(1003), id="unsupported_encoding"),
            pytest.param(types.Message({}), "bytes", exceptions.WebSocketException(1003), id="decode_error"),
        ],
        indirect=["exception"],
    )
    async def test_resolve(self, message, encoding, exception):
        component = WebSocketMessageDataComponent()

        with exception:
            result = await component.resolve(message, encoding)

            assert result.data == b"hello"
