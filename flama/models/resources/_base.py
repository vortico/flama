import typing as t

from flama.resources.routing import ResourceRoute

if t.TYPE_CHECKING:
    from flama.models import BaseModel

__all__ = ["InspectMixin"]


class InspectMixin:
    """Adds a ``GET /`` route returning the model's introspection payload.

    Both :class:`MLModel` and :class:`LLMModel` inherit :meth:`BaseModel.inspect` unchanged, so
    this mixin lives at the resources package root and is reused by every resource family
    (currently :class:`MLResourceType` and the native LLM serving layer). The signature stays
    the same as for any other ``_add_<method>`` factory; the ``model_model_type`` runtime
    parameter is the concrete model subclass and is used as a dependency-injection annotation
    on the inner handler.
    """

    @classmethod
    def _add_inspect(
        cls, name: str, verbose_name: str, model_model_type: type["BaseModel"], **kwargs
    ) -> dict[str, t.Any]:
        @ResourceRoute.method("/", methods=["GET"], name="inspect")
        async def inspect(self, model: model_model_type):  # ty: ignore[invalid-type-form]
            return model.inspect()

        inspect.__doc__ = f"""
            tags:
                - {verbose_name}
            summary:
                Retrieve the model
            description:
                Retrieve the model from this resource.
            responses:
                200:
                    description:
                        The model.
        """

        return {"_inspect": inspect}
