import typing as t

__all__ = ["Serving"]


class Serving:
    """Base class for protocol serving layers attached to a model resource.

    Subclasses bundle protocol-specific route mixins and declare the methods the layer
    enables (used by the resource metaclass to drive ``_add_<method>`` registration) and the
    URL prefix the layer's routes hang from. Layers are package-internal: end users select
    them by name through the ``serving`` attribute on resource classes (or the ``serving``
    kwarg on :meth:`flama.models.modules.ModelsModule.add_model`).
    """

    METHODS: t.ClassVar[tuple[str, ...]]
    PREFIX: t.ClassVar[str]
