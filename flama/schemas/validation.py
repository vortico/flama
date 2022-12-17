import asyncio
import inspect
from functools import wraps

from flama import exceptions, schemas

__all__ = ["output_validation"]


def output_validation(error_cls=exceptions.ValidationError, error_status_code=500):
    """
    Validate view output using schema annotated as function's return.

    :param error_cls: Error class to be raised when validation fails. Errors dict will be passed through 'detail' param.
    :param error_status_code: HTTP status code assigned to response when it fails to validate output, default 500.
    :raises exceptions.ValidationError: if output validation fails.
    """

    def outer_decorator(func):
        try:
            schema = schemas.Schema.from_type(inspect.signature(func).return_annotation)
        except Exception as e:
            raise TypeError(f"Invalid return signature for function '{func}'") from e

        @wraps(func)
        async def inner_decorator(*args, **kwargs):
            response = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

            try:
                # Use output schema to validate the data
                schema.validate(schema.dump(response))
            except schemas.SchemaValidationError as e:
                raise error_cls(detail=e.errors, status_code=error_status_code)
            except Exception as e:
                raise error_cls(
                    detail=f"Error serializing response before validation: {str(e)}", status_code=error_status_code
                )

            return response

        return inner_decorator

    return outer_decorator
