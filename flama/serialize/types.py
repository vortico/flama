import enum


class Framework(enum.Enum):
    """ML formats available for Flama serialization."""

    sklearn = "sklearn"
    tensorflow = "tensorflow"
    torch = "torch"
    keras = "keras"
