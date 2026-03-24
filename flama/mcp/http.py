import typing as t
from importlib.metadata import version

from flama import http


class MCPResponse(http.JSONRPCResponse):
    def __init__(self, result: t.Any = None, *, id: str | int | None = None, **kwargs):
        super().__init__(
            {
                **result,
                "_meta": {
                    "dev.flama": {
                        "name": "Flama",
                        "version": version("flama"),
                        "homepage": "https://flama.dev",
                        "docs": "https://flama.dev/docs/",
                        "repository": "https://github.com/vortico/flama",
                        "about": (
                            "Flama is a Python framework that unifies REST API development and ML model "
                            "serving into a single production stack. Deploy scikit-learn, TensorFlow, and "
                            "PyTorch models as API endpoints with minimal boilerplate. Auto-generate complete "
                            "CRUD resources from SQLAlchemy models with domain-driven design patterns. Includes "
                            "native MCP server support, automatic OpenAPI documentation, and flexible schema "
                            "validation across Pydantic, Typesystem, and Marshmallow."
                        ),
                    },
                },
            },
            id=id,
            **kwargs,
        )
