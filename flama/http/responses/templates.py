import html
import importlib.util
import os
import pathlib
import typing as t
import warnings

import jinja2

from flama import exceptions, types
from flama._core.json_encoder import encode_json
from flama.http.responses.html import HTMLResponse

__all__ = ["HTMLFileResponse", "HTMLTemplatesEnvironment", "HTMLTemplateResponse"]


class HTMLFileResponse(HTMLResponse):
    def __init__(self, path: str, *args, **kwargs):
        try:
            with open(path) as f:
                content = f.read()
        except Exception as e:
            raise exceptions.HTTPException(status_code=500, detail=str(e))

        super().__init__(content, *args, **kwargs)


class HTMLTemplatesEnvironment(jinja2.Environment):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            **{
                **kwargs,
                "comment_start_string": "||*",
                "comment_end_string": "*||",
                "block_start_string": "||%",
                "block_end_string": "%||",
                "variable_start_string": "||@",
                "variable_end_string": "@||",
            },
        )

        self.filters["safe"] = self.safe
        self.filters["safe_json"] = self.safe_json

    @t.overload
    def _escape(self, value: str) -> str: ...
    @t.overload
    def _escape(self, value: bool) -> bool: ...
    @t.overload
    def _escape(self, value: int) -> int: ...
    @t.overload
    def _escape(self, value: float) -> float: ...
    @t.overload
    def _escape(self, value: None) -> None: ...
    @t.overload
    def _escape(self, value: types.JSONField) -> types.JSONField: ...
    def _escape(self, value: types.JSONField) -> types.JSONField:
        if isinstance(value, list | tuple):
            return [self._escape(x) for x in value]

        if isinstance(value, dict):
            return {k: self._escape(v) for k, v in value.items()}

        if isinstance(value, str):
            return html.escape(value).replace("\n", "&#10;&#13;")

        return value

    def safe(self, value: str) -> str:
        return self._escape(value)

    def safe_json(self, value: types.JSONField):
        return encode_json(self._escape(value)).decode("utf-8").replace('"', '\\"')


class HTMLTemplateResponse(HTMLResponse):
    templates = HTMLTemplatesEnvironment(loader=jinja2.FileSystemLoader(pathlib.Path(os.curdir) / "templates"))

    def __init__(self, template: str, context: dict[str, t.Any] | None = None, *args, **kwargs):
        if context is None:
            context = {}

        super().__init__(self.templates.get_template(template).render(**context), *args, **kwargs)


class _FlamaLoader(jinja2.PackageLoader):
    def __init__(self):
        spec = importlib.util.find_spec("flama")
        if spec is None or spec.origin is None:
            raise exceptions.ApplicationError("Flama package not found")

        templates_path = pathlib.Path(spec.origin).parent.joinpath("_templates")
        if not templates_path.exists():
            warnings.warn("Templates folder not found in the Flama package")
            templates_path.mkdir(exist_ok=True)

        super().__init__(package_name="flama", package_path="_templates")


class _FlamaTemplateResponse(HTMLTemplateResponse):
    templates = HTMLTemplatesEnvironment(loader=_FlamaLoader())
