import asyncio
import inspect
from functools import wraps

from flama import exceptions, schemas
from flama.schemas.utils import is_field_class, is_field_instance, is_schema_class, is_schema_instance

__all__ = ["get_output_schema", "output_validation"]


def get_output_schema(func):
    """
    Get output schema annotated as function's return. If there is no schema, return None.

    :param func: Annotated function.
    :returns: Output schema.
    """
    return_annotation = inspect.signature(func).return_annotation
    if is_schema_class(return_annotation) or is_field_class(return_annotation):
        return return_annotation()
    elif is_schema_instance(return_annotation) or is_field_instance(return_annotation):
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
        assert schema is not None, "Return annotation must be a valid schema"

        @wraps(func)
        async def inner_decorator(*args, **kwargs):
            response = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

            try:
                # Use output schema to validate the data
                schemas.validate(schema, schemas.dump(schema, response))
            except schemas.SchemaValidationError as e:
                raise error_cls(detail=e.errors, status_code=error_status_code)
            except Exception as e:
                raise error_cls(
                    detail=f"Error serializing response before validation: {str(e)}", status_code=error_status_code
                )

            return response

        return inner_decorator

    return outer_decorator
