import sys

__all__ = ["TypedDict", "TypeForm", "get_annotations", "sentinel"]

# PORT: Remove when stop supporting 3.13
# annotationlib.get_annotations was added in Python 3.14
# https://docs.python.org/3/library/annotationlib.html#annotationlib.get_annotations
if sys.version_info >= (3, 14):
    from annotationlib import get_annotations
else:
    from typing_extensions import get_annotations

# PORT: Remove when stop supporting 3.14
# TypeForm and the closed/extra_items TypedDict parameters were added in Python 3.15
# https://peps.python.org/pep-0747/
# https://peps.python.org/pep-0728/
if sys.version_info >= (3, 15):
    from typing import TypedDict, TypeForm
else:
    from typing_extensions import TypedDict, TypeForm

# PORT: Remove when stop supporting 3.14
# sentinel was added as a builtin in Python 3.15
# https://peps.python.org/pep-0661/
if sys.version_info >= (3, 15):
    from builtins import sentinel
else:
    from typing_extensions import sentinel
