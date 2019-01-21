import asyncio
import inspect
from functools import wraps

import marshmallow
from starlette_api import exceptions


def get_output_schema(func):
    """
    Get output schema annotated as function's return. If there is no schema, return None.

    :param func: Annotated function.
    :returns: Output schema.
    """
    return_annotation = inspect.signature(func).return_annotation
    if inspect.isclass(return_annotation) and issubclass(return_annotation, marshmallow.Schema):
        return return_annotation()
    elif isinstance(return_annotation, marshmallow.Schema):
        return return_annotation

    return None


def output_validation(func, error_status_code=500):
    """
    Validate view output using schema annotated as function's return.

    :param func: Function to be decorated.
    :param error_status_code: HTTP status code assigned to response when it fails to validate output, default 500.
    :raises exceptions.ValidationError: if output validation fails.
    """
    schema = get_output_schema(func)
    assert schema is not None, "Return annotation must be a valid marshmallow schema"

    @wraps(func)
    async def inner(*args, **kwargs):
        response = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

        try:
            # Use output schema to validate and format data
            schema.dump(response)
        except marshmallow.ValidationError as e:
            raise exceptions.OutputValidationError(detail=e.messages, status_code=error_status_code)

        return response

    return inner
