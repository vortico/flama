import typing as t

from flama import compat, types
from flama.pagination.mixins import LimitOffsetMixin, PageNumberMixin

__all__ = ["paginator"]

P = compat.ParamSpec("P")  # PORT: Replace compat when stop supporting 3.9
R = t.TypeVar("R", covariant=True)


class Paginator(LimitOffsetMixin, PageNumberMixin):
    def __init__(self):
        self.schemas: dict[str, t.Any] = {}

    def paginate(self, pagination: types.Pagination, func: t.Callable[P, R]) -> t.Callable[P, R]:
        return {
            "limit_offset": self._paginate_limit_offset,
            "page_number": self._paginate_page_number,
        }[pagination](func)


paginator = Paginator()
