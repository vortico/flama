import typing as t

from flama.ddd.repositories import AbstractRepository

__all__ = ["Repositories"]

Repositories = t.NewType("Repositories", t.Dict[str, t.Type[AbstractRepository]])
