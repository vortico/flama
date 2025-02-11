import typing as t

from flama import compat
from flama.pagination.mixins import LimitOffsetMixin, PageNumberMixin
from flama.pagination.types import PaginationType

__all__ = ["paginator"]

P = compat.ParamSpec("P")  # PORT: Replace compat when stop supporting 3.9
R = t.TypeVar("R", covariant=True)


class Paginator(LimitOffsetMixin, PageNumberMixin):
    def __init__(self):
        self.schemas = {}

    def paginate(self, pagination: t.Union[str, PaginationType], func: t.Callable[P, R]) -> t.Callable[P, R]:
        return {
            PaginationType.limit_offset: self._paginate_limit_offset,
            PaginationType.page_number: self._paginate_page_number,
        }[PaginationType[pagination]](func)


paginator = Paginator()
