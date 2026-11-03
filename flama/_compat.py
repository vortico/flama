import sys

__all__ = ["Format", "TypedDict", "TypeForm", "evaluate_forward_ref", "get_annotations", "sentinel"]

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
