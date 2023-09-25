import typing as t

from flama.pagination import mixins, types

__all__ = ["paginator"]


class Paginator(mixins.LimitOffsetMixin, mixins.PageNumberMixin):
    def __init__(self):
        self.schemas = {}

    def paginate(self, pagination: t.Union[str, types.PaginationType], func: t.Callable) -> t.Callable:
        return {
            types.PaginationType.limit_offset: self._paginate_limit_offset,
            types.PaginationType.page_number: self._paginate_page_number,
        }[types.PaginationType[pagination]](func)


paginator = Paginator()
