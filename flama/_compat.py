import base64
import sys

__all__ = [
    "Format",
    "TypeAliasType",
    "TypedDict",
    "TypeForm",
    "evaluate_forward_ref",
    "get_annotations",
    "sentinel",
    "urlsafe_b64decode",
    "urlsafe_b64encode",
]

# PORT: Remove when stop supporting 3.11
# typing.TypeAliasType was added in Python 3.12
# https://docs.python.org/3/library/typing.html#typing.TypeAliasType
if sys.version_info >= (3, 12):
    from typing import TypeAliasType
else:
    from typing_extensions import TypeAliasType

# PORT: Remove when stop supporting 3.13
# annotationlib.get_annotations was added in Python 3.14
# https://docs.python.org/3/library/annotationlib.html#annotationlib.get_annotations
if sys.version_info >= (3, 14):
    from annotationlib import get_annotations
else:
    from typing_extensions import get_annotations

# PORT: Remove when stop supporting 3.13
# annotationlib.Format was added in Python 3.14
# https://docs.python.org/3/library/annotationlib.html#annotationlib.Format
if sys.version_info >= (3, 14):
    from annotationlib import Format
else:
    from typing_extensions import Format

# PORT: Remove when stop supporting 3.13
# typing.evaluate_forward_ref was added in Python 3.14
# https://docs.python.org/3/library/typing.html#typing.evaluate_forward_ref
if sys.version_info >= (3, 14):
    from typing import evaluate_forward_ref
else:
    from typing_extensions import evaluate_forward_ref

# PORT: Remove when stop supporting 3.14
# The closed/extra_items TypedDict parameters were added in Python 3.15
# https://peps.python.org/pep-0728/
if sys.version_info >= (3, 15):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict

# PORT: Remove when stop supporting 3.14
# TypeForm was added in Python 3.15
# https://peps.python.org/pep-0747/
if sys.version_info >= (3, 15):
    from typing import TypeForm
else:
    from typing_extensions import TypeForm

# PORT: Remove when stop supporting 3.14
# sentinel was added as a builtin in Python 3.15
# https://peps.python.org/pep-0661/
if sys.version_info >= (3, 15):
    from builtins import sentinel
else:
    from typing_extensions import sentinel

# PORT: Remove when stop supporting 3.14
# The padded parameter of base64.urlsafe_b64encode was added in Python 3.15
# https://docs.python.org/3.15/library/base64.html#base64.urlsafe_b64encode
if sys.version_info >= (3, 15):
    from base64 import urlsafe_b64encode
else:

    def urlsafe_b64encode(s: bytes, *, padded: bool = True) -> bytes:
        encoded = base64.urlsafe_b64encode(s)
        return encoded if padded else encoded.rstrip(b"=")


# PORT: Remove when stop supporting 3.14
# The padded parameter of base64.urlsafe_b64decode was added in Python 3.15
# https://docs.python.org/3.15/library/base64.html#base64.urlsafe_b64decode
if sys.version_info >= (3, 15):
    from base64 import urlsafe_b64decode
else:

    def urlsafe_b64decode(s: bytes | str, *, padded: bool = False) -> bytes:
        if isinstance(s, str):
            s = s.encode("ascii")
        return base64.urlsafe_b64decode(s if padded else s + b"=" * (-len(s) % 4))
