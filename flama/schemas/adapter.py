import abc
import sys
import typing as t

from flama.types import JSONSchema
from flama.types.schema import _T_Field, _T_Schema

if sys.version_info < (3, 10):  # PORT: Remove when stop supporting 3.9 # pragma: no cover
    from typing_extensions import TypeGuard

    t.TypeGuard = TypeGuard  # type: ignore


class Adapter(t.Generic[_T_Schema, _T_Field], metaclass=abc.ABCMeta):
    DEFAULT_SCHEMA_NAME = "Schema"

    @abc.abstractmethod
    def build_field(
        self,
        name: str,
        type_: t.Type,
        nullable: bool = False,
        required: bool = True,
        default: t.Any = None,
        multiple: bool = False,
        **kwargs: t.Any,
    ) -> _T_Field:
        ...

    @t.overload
    @abc.abstractmethod
    def build_schema(
        self, *, name: t.Optional[str] = None, fields: t.Dict[str, _T_Field]
    ) -> t.Union[_T_Schema, t.Type[_T_Schema]]:
        ...

    @t.overload
    @abc.abstractmethod
    def build_schema(
        self, *, name: t.Optional[str] = None, schema: t.Union[_T_Schema, t.Type[_T_Schema]]
    ) -> t.Union[_T_Schema, t.Type[_T_Schema]]:
        ...

    @t.overload
    @abc.abstractmethod
    def build_schema(
        self,
        *,
        name: t.Optional[str] = None,
        schema: t.Union[_T_Schema, t.Type[_T_Schema]],
        fields: t.Optional[t.Dict[str, _T_Field]],
    ) -> t.Union[_T_Schema, t.Type[_T_Schema]]:
        ...

    @abc.abstractmethod
    def build_schema(
        self,
        *,
        name: t.Optional[str] = None,
        schema: t.Optional[t.Union[_T_Schema, t.Type[_T_Schema]]] = None,
        fields: t.Optional[t.Dict[str, _T_Field]] = None,
    ) -> t.Union[_T_Schema, t.Type[_T_Schema]]:
        ...

    @abc.abstractmethod
    def validate(self, schema: t.Union[_T_Schema, t.Type[_T_Schema]], values: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        ...

    @abc.abstractmethod
    def load(self, schema: t.Union[_T_Schema, t.Type[_T_Schema]], value: t.Dict[str, t.Any]) -> _T_Schema:
        ...

    @abc.abstractmethod
    def dump(self, schema: t.Union[_T_Schema, t.Type[_T_Schema]], value: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        ...

    @abc.abstractmethod
    def name(self, schema: t.Union[_T_Schema, t.Type[_T_Schema]]) -> str:
        ...

    @abc.abstractmethod
    def to_json_schema(self, schema: t.Union[_T_Schema, t.Type[_T_Schema], _T_Field]) -> JSONSchema:
        ...

    @abc.abstractmethod
    def unique_schema(self, schema: t.Union[_T_Schema, t.Type[_T_Schema]]) -> t.Union[_T_Schema, t.Type[_T_Schema]]:
        ...

    @abc.abstractmethod
    def schema_fields(
        self, schema: t.Union[_T_Schema, t.Type[_T_Schema]]
    ) -> t.Dict[
        str,
        t.Tuple[
            t.Union[
                t.Union[_T_Schema, t.Type], t.List[t.Union[_T_Schema, t.Type]], t.Dict[str, t.Union[_T_Schema, t.Type]]
            ],
            _T_Field,
        ],
    ]:
        ...

    @abc.abstractmethod
    def is_schema(
        self, obj: t.Any
    ) -> t.TypeGuard[  # type: ignore # PORT: Remove this comment when stop supporting 3.9
        t.Union[_T_Schema, t.Type[_T_Schema]]
    ]:
        ...

    @abc.abstractmethod
    def is_field(
        self, obj: t.Any
    ) -> t.TypeGuard[  # type: ignore # PORT: Remove this comment when stop supporting 3.9
        t.Union[_T_Field, t.Type[_T_Field]]
    ]:
        ...
