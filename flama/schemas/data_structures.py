import dataclasses
import inspect
import typing as t

from flama import schemas
from flama.schemas.types import ParameterLocation

__all__ = ["Parameter", "Parameters"]


@dataclasses.dataclass(frozen=True)
class Parameter:
    name: str
    location: ParameterLocation
    schema_type: t.Optional[t.Union[t.Type[schemas.Field], t.Type[schemas.Schema], schemas.Field, schemas.Schema]]
    required: bool = False
    default: t.Any = None

    @property
    def schema(self) -> t.Optional[t.Union[schemas.Field, schemas.Schema]]:
        if self.schema_type is None:
            return None

        if inspect.isclass(self.schema_type) and issubclass(self.schema_type, schemas.Schema):
            return self.schema_type()

        if isinstance(self.schema_type, schemas.Schema) or isinstance(self.schema_type, schemas.Field):
            return self.schema_type

        return schemas.adapter.build_field(field_type=self.schema_type, required=self.required, default=self.default)


Parameters = t.Dict[str, Parameter]
