import dataclasses
import re
import typing

from flama.resources import types
from flama.resources.exceptions import ResourceAttributeError

if typing.TYPE_CHECKING:
    from flama.applications import Flama

__all__ = ["BaseResource", "ResourceType"]


class BaseResource:
    name: str
    verbose_name: str

    def __init__(self, app: typing.Optional["Flama"] = None, *args, **kwargs):
        if app is not None:
            self.app = app

    @property
    def app(self) -> "Flama":
        try:
            return self._app
        except AttributeError:
            raise AttributeError(f"{self.__class__.__name__} is not initialized")

    @app.setter
    def app(self, app: "Flama"):
        self._app = app

    @app.deleter
    def app(self):
        del self._app


class ResourceType(type):
    METHODS: typing.Sequence[str] = ()

    def __new__(mcs, name: str, bases: typing.Tuple[type], namespace: typing.Dict[str, typing.Any]):
        """Resource metaclass for defining basic behavior:
        * Create _meta attribute containing some metadata (name, verbose name...).
        * Adds methods related to resource (create, retrieve...) listed in METHODS class attribute.
        * Generate a Router with above methods.

        :param name: Class name.
        :param bases: List of superclasses.
        :param namespace: Variables namespace used to create the class.
        """
        try:
            # Define resource names
            resource_name, verbose_name = mcs._get_resource_name(name, namespace)
        except AttributeError as e:
            raise ResourceAttributeError(str(e), name)

        if "_meta" in namespace:
            namespace["_meta"].name = resource_name
            namespace["_meta"].verbose_name = verbose_name
        else:
            namespace["_meta"] = types.Metadata(name=resource_name, verbose_name=verbose_name)

        # Create methods and routes
        namespace.update(mcs._build_methods(namespace))
        namespace["routes"] = mcs._build_routes(namespace)

        return super().__new__(mcs, name, bases, namespace)

    @classmethod
    def _get_mro(mcs, *classes: type) -> typing.List[typing.Type]:
        """Generate the MRO list for given base class or list of base classes.

        :param classes: Base classes.
        :return: MRO list.
        """
        return list(
            dict.fromkeys(
                [y for x in [[cls.__mro__[0]] + mcs._get_mro(*cls.__mro__[1:]) for cls in classes] for y in x]
            )
        )

    @classmethod
    def _get_attribute(
        mcs, attribute: str, bases: typing.Sequence[typing.Any], namespace: typing.Dict[str, typing.Any]
    ) -> typing.Any:
        """Look for an attribute given his name on namespace or parent classes namespace.

        :param attribute: Attribute name.
        :param bases: List of superclasses.
        :param namespace: Variables namespace used to create the class.
        :return: Attribute.
        """
        try:
            return namespace.pop(attribute)
        except KeyError:
            for base in mcs._get_mro(*bases):
                if hasattr(base, "_meta") and hasattr(base._meta, attribute):
                    return getattr(base._meta, attribute)
                elif hasattr(base, attribute):
                    return getattr(base, attribute)

        raise AttributeError(ResourceAttributeError.ATTRIBUTE_NOT_FOUND.format(attribute=attribute))

    @classmethod
    def _get_resource_name(mcs, name: str, namespace: typing.Dict[str, typing.Any]) -> typing.Tuple[str, str]:
        """Look for a resource name in namespace and check it's a valid name.

        :param name: Class name.
        :param namespace: Variables namespace used to create the class.
        :return: Resource name.
        """
        resource_name = namespace.pop("name", name)

        # Check resource name validity
        if re.match("[a-zA-Z][-_a-zA-Z]", resource_name) is None:
            raise AttributeError(ResourceAttributeError.RESOURCE_NAME_INVALID.format(resource_name=resource_name))

        return resource_name, namespace.pop("verbose_name", resource_name)

    @classmethod
    def _build_routes(mcs, namespace: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Callable]:
        """Builds the routes' descriptor.

        :param namespace: Variables namespace used to create the class.
        """
        return {
            name: m
            for name, m in namespace.items()
            if hasattr(m, "_meta") and isinstance(m._meta, types.MethodMetadata) and not name.startswith("_")
        }

    @classmethod
    def _build_methods(mcs, namespace: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Callable]:
        """Builds a namespace containing all resource methods. Look for all methods listed in METHODS attribute and
        named '_add_[method]'.

        :param namespace: Variables namespace used to create the class.
        :return: Methods namespace.
        """
        # Get available methods
        methods = [getattr(mcs, f"_add_{method}") for method in mcs.METHODS if hasattr(mcs, f"_add_{method}")]

        # Generate methods
        methods_namespace = {
            func_name: func
            for method in methods
            for func_name, func in method(**namespace["_meta"].to_plain_dict()).items()
        }

        # Preserve already defined methods
        methods_namespace.update(
            {method: methods_namespace[f"_{method}"] for method in mcs.METHODS if method not in namespace}
        )

        return methods_namespace
