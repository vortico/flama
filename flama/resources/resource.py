import re
import typing as t

from flama.resources import data_structures
from flama.resources.exceptions import ResourceAttributeNotFound, ResourceNameInvalid

__all__ = ["Resource", "ResourceType"]


class ResourceType(type):
    METHODS: t.Sequence[str] = ()

    def __new__(mcs, name: str, bases: tuple[type], namespace: dict[str, t.Any]):
        """Resource metaclass for defining basic behavior:
        * Create _meta attribute containing some metadata (name, verbose name...).
        * Adds methods related to resource (create, retrieve...) listed in METHODS class attribute.
        * Generate a Router with above methods.

        :param name: Class name.
        :param bases: List of superclasses.
        :param namespace: Variables namespace used to create the class.
        """
        if not mcs._is_abstract(namespace):
            resource_name, verbose_name = mcs._get_resource_name(name, namespace)

            namespace.setdefault("_meta", data_structures.Metadata()).name = resource_name
            namespace["_meta"].verbose_name = verbose_name

            # Create methods and routes
            namespace.update(mcs._build_methods(namespace))
            namespace.update(mcs._build_routes(namespace))

        return super().__new__(mcs, name, bases, namespace)

    @staticmethod
    def _is_abstract(namespace: dict[str, t.Any]) -> bool:
        return namespace.get("__module__") == "flama.resources.resource" and namespace.get("__qualname__") == "Resource"

    @classmethod
    def _get_mro(cls, *classes: type) -> list[type]:
        """Generate the MRO list for given base class or list of base classes.

        :param classes: Base classes.
        :return: MRO list.
        """
        return list(
            dict.fromkeys([y for x in [[c.__mro__[0]] + cls._get_mro(*c.__mro__[1:]) for c in classes] for y in x])
        )

    @classmethod
    def _get_attribute(
        cls,
        name: str,
        attribute: str,
        bases: t.Sequence[t.Any],
        namespace: dict[str, t.Any],
        metadata_namespace: str | None = None,
    ) -> t.Any:
        """Look for an attribute given his name on namespace or parent classes namespace.

        :param name: Resource class name (used to qualify error messages).
        :param attribute: Attribute name.
        :param bases: List of superclasses.
        :param namespace: Variables namespace used to create the class.
        :return: Attribute.
        :raises ResourceAttributeNotFound: If the attribute is not present on the namespace nor any
            base class — callers that treat the absence as a fallback signal should ``except`` this
            specific subclass.
        """
        try:
            return namespace.pop(attribute)
        except KeyError:
            for base in cls._get_mro(*bases):
                if hasattr(base, "_meta"):
                    if attribute in base._meta.namespaces.get(metadata_namespace, {}):  # ty: ignore[unresolved-attribute]
                        return base._meta.namespaces[metadata_namespace][attribute]  # ty: ignore[unresolved-attribute]

                    if hasattr(base._meta, attribute):
                        return getattr(base._meta, attribute)

                if hasattr(base, attribute):
                    return getattr(base, attribute)

        raise ResourceAttributeNotFound(name=name, attribute=attribute)

    @classmethod
    def _get_resource_name(cls, name: str, namespace: dict[str, t.Any]) -> tuple[str, str]:
        """Look for a resource name in namespace and check it's a valid name.

        :param name: Class name.
        :param namespace: Variables namespace used to create the class.
        :return: Resource name.
        :raises ResourceNameInvalid: If the declared ``name`` does not match the expected identifier
            shape (a letter followed by letters, dashes or underscores).
        """
        resource_name = namespace.pop("name", name)

        if re.match("[a-zA-Z][-_a-zA-Z]", resource_name) is None:
            raise ResourceNameInvalid(name=name, resource_name=resource_name)

        return resource_name, namespace.pop("verbose_name", resource_name)

    @classmethod
    def _build_routes(cls, namespace: dict[str, t.Any]) -> dict[str, t.Any]:
        """Builds the routes' descriptor.

        :param namespace: Variables namespace used to create the class.
        :return: Routes namespace.
        """
        return {
            "_methods": {
                name: m
                for name, m in namespace.items()
                if isinstance(m, data_structures.ResourceMethod) and not name.startswith("_")
            },
            **{name: m.func.method for name, m in namespace.items() if isinstance(m, data_structures.ResourceMethod)},
        }

    @classmethod
    def _build_methods(
        cls, namespace: dict[str, t.Any], methods: t.Sequence[str] | None = None
    ) -> dict[str, t.Callable]:
        """Builds a namespace containing the requested resource methods.

        Looks for ``_add_<method>`` factories on *cls* for each name in *methods* (or
        :attr:`METHODS` when *methods* is ``None``) and assembles their results into a single
        namespace dict. Subclass metaclasses can pass *methods* explicitly to drive registration
        from a per-resource source (e.g. a ``serving`` selector) rather than the class-level
        attribute.

        :param namespace: Variables namespace used to create the class.
        :param methods: Optional explicit list of method names to register. Falls back to
            :attr:`METHODS` when ``None``.
        :return: Methods namespace.
        """
        resolved = methods if methods is not None else cls.METHODS
        adders = [getattr(cls, f"_add_{method}") for method in resolved if hasattr(cls, f"_add_{method}")]

        methods_namespace = {
            func_name: func
            for adder in adders
            for func_name, func in adder(**namespace["_meta"].to_plain_dict()).items()
        }

        methods_namespace.update(
            {
                method: methods_namespace[f"_{method}"]
                for method in resolved
                if method not in namespace and f"_{method}" in methods_namespace
            }
        )

        return methods_namespace


class Resource(metaclass=ResourceType):
    name: str
    verbose_name: str

    _methods: dict[str, data_structures.ResourceMethod]
    _meta: data_structures.Metadata
