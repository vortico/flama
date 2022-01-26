from flama.pagination.limit_offset import LimitOffsetMixin
from flama.pagination.page_number import PageNumberMixin


class Paginator(LimitOffsetMixin, PageNumberMixin):
    def __init__(self):
        self.schemas = {}
