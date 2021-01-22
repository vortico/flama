import asyncio
import inspect
import marshmallow
from functools import wraps

from flama import exceptions
from flama.utils import is_marshmallow_dataclass, is_marshmallow_schema

__all__ = ["get_output_schema", "output_validation"]


def get_output_schema(func):
    """
    Get output schema annotated as function's return. If there is no schema, return None.

    :param func: Annotated function.
    :returns: Output schema.
    """
    response_schema = getattr(func, '_response_schema', None)
    return_annotation = response_schema if response_schema else inspect.signature(func).return_annotation
    if is_marshmallow_schema(return_annotation):
        return return_annotation()
    elif is_marshmallow_dataclass(return_annotation):
        return return_annotation.Schema()
    elif isinstance(return_annotation, marshmallow.Schema):
        return return_annotation

    return None


def output_validation(error_cls=exceptions.ValidationError, error_status_code=500):
    """
    Validate view output using schema annotated as function's return.

    :param error_cls: Error class to be raised when validation fails. Errors dict will be passed through 'detail' param.
    :param error_status_code: HTTP status code assigned to response when it fails to validate output, default 500.
    :raises exceptions.ValidationError: if output validation fails.
    """

    def outer_decorator(func):
        schema = get_output_schema(func)
        assert schema is not None, "Return annotation must be a valid marshmallow schema"

        @wraps(func)
        async def inner_decorator(*args, **kwargs):
            response = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

            try:
                # Use output schema to validate the data
                errors = schema.validate(schema.dump(response))
            except Exception as e:
                raise error_cls(
                    detail=f"Error serializing response before validation: {str(e)}", status_code=error_status_code
                )

            if errors:
                raise error_cls(detail=errors, status_code=error_status_code)

            return response

        return inner_decorator

    return outer_decorator
