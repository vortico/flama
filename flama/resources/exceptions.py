from flama.exceptions import ApplicationError

__all__ = [
    "ResourceError",
    "ResourceAttributeNotFound",
    "ResourceNameInvalid",
    "ResourceSchemaNotFound",
    "ResourceModelNotFound",
    "ResourceModelInvalid",
    "ResourcePrimaryKeyNotFound",
    "ResourcePrimaryKeyInvalid",
    "ResourceServingLayerUnknown",
    "ResourceServingMethodInvalidPrefix",
]


class ResourceError(ApplicationError):
    """Base class for resource-declaration validation failures.

    Inherits :class:`~flama.exceptions.ApplicationError` so resource errors participate in the
    framework-wide error hierarchy alongside :class:`~flama.exceptions.DependencyNotInstalled`,
    :class:`~flama.exceptions.SQLAlchemyError`, etc.
    """

    def __init__(self, name: str, msg: str = "is invalid") -> None:
        self.name = name
        super().__init__(f"{name} {msg}")


class ResourceAttributeNotFound(ResourceError):
    """Resource declaration is missing a required attribute."""

    def __init__(self, name: str, attribute: str) -> None:
        super().__init__(name, f"needs to define attribute '{attribute}'")


class ResourceNameInvalid(ResourceError):
    """Resource ``name`` attribute does not match the expected identifier shape."""

    def __init__(self, name: str, resource_name: str) -> None:
        super().__init__(name, f"invalid resource name '{resource_name}'")


class ResourceSchemaNotFound(ResourceError):
    """REST resource is missing the ``schema`` or the ``input_schema``/``output_schema`` pair."""

    def __init__(self, name: str) -> None:
        super().__init__(name, "needs to define attribute 'schema' or the pair 'input_schema' and 'output_schema'")


class ResourceModelNotFound(ResourceError):
    """Model resource is missing both ``model_path`` and ``component`` declarations."""

    def __init__(self, name: str) -> None:
        super().__init__(name, "needs to define attribute 'model_path' or 'component'")


class ResourceModelInvalid(ResourceError):
    """REST resource's model is not a SQLAlchemy ``Table`` nor a :class:`data_structures.Model`."""

    def __init__(self, name: str) -> None:
        super().__init__(name, "model must be a valid SQLAlchemy Table instance or a Model instance")


class ResourcePrimaryKeyNotFound(ResourceError):
    """REST resource's model does not expose a single-column primary key."""

    def __init__(self, name: str) -> None:
        super().__init__(name, "model must define a single-column primary key")


class ResourcePrimaryKeyInvalid(ResourceError):
    """REST resource's model primary key column type is not a supported scalar type."""

    def __init__(self, name: str) -> None:
        super().__init__(name, "model primary key wrong type")


class ResourceServingLayerUnknown(ResourceError):
    """LLM resource selects one or more serving layers that are not registered."""

    def __init__(self, name: str, layers: str, known: str) -> None:
        super().__init__(name, f"declares unknown serving layer(s) {layers} (known: {known})")


class ResourceServingMethodInvalidPrefix(ResourceError):
    """LLM serving layer declares method names without the required ``<NAME>_`` prefix."""

    def __init__(self, name: str, methods: str) -> None:
        super().__init__(name, f"declares serving layer method(s) without the required prefix: {methods}")
