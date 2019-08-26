import asyncio
import inspect
from functools import wraps

import marshmallow

from flama import exceptions

__all__ = ["get_output_schema", "output_validation"]


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
                if errors:
                    raise error_cls(detail=errors, status_code=error_status_code)
            except marshmallow.ValidationError as e:
                raise error_cls(detail=e.messages, status_code=error_status_code)
            except Exception:
                raise error_cls(detail="Error serializing response before validation", status_code=error_status_code)

            return response

        return inner_decorator

    return outer_decorator
