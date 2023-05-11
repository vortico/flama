import typing as t

from flama.types.asgi import *  # noqa
from flama.types.http import *  # noqa
from flama.types.schema import *  # noqa
from flama.types.websockets import *  # noqa

JSONField = t.Union[str, int, float, bool, None, t.List["JSONField"], t.Dict[str, "JSONField"]]
JSONSchema = t.Dict[str, JSONField]
Tag = t.Union[str, t.Sequence["Tag"], t.Dict[str, "Tag"]]
