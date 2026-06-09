"""Flama 2.0 example: stateless Model Context Protocol server (2026-07-28).

Demonstrates the 2.0 stateless MCP: no ``initialize`` handshake (every request is self-contained, carrying its
protocol version and capabilities in ``_meta`` and its routing data in ``Mcp-Method``/``Mcp-Name`` headers), with
tools (sync/async/typed), background Tasks, Elicitation round-trips, prompts, resources, MCP Apps UI templates,
and multiple servers mounted on one application.

Run it:
    flama run examples.2_0.mcp:app

Then POST JSON-RPC to ``/mcp/tools/`` or ``/mcp/math/`` with the SEP-2243 routing headers.
"""

import json

import flama
from flama import Flama
from flama.mcp.data_structures import Elicit, Elicitation
from flama.mcp.server import MCPServer

tools_server = MCPServer("tools", version="2.0.0", instructions="Flama 2.0 demo MCP tools server")


@tools_server.tool("add", description="Add two integers")
def add(a: int, b: int) -> int:
    return a + b


@tools_server.tool(description="Greet someone by name")
async def greet(name: str) -> str:
    return f"Hello, {name}!"


@tools_server.tool("square", task=True, description="Square a number as a background task")
async def square(x: int) -> int:
    return x * x


@tools_server.tool("confirm", description="Confirm an action through an elicitation round-trip")
def confirm(elicitation: Elicitation) -> str:
    if "confirm" not in elicitation:
        return Elicit.require("Are you sure?", {"type": "boolean"}, name="confirm")
    return f"confirmed={elicitation['confirm']}"


@tools_server.resource(
    "config://app",
    name="config",
    description="Application configuration",
    mime_type="application/json",
)
def config():
    return json.dumps({"debug": True, "name": "flama2-mcp"})


@tools_server.prompt("summarise", description="Summarise the given text")
def summarise(text: str):
    return f"Summarise the following:\n\n{text}"


@tools_server.app_template("ui://widget", name="widget", description="A small UI widget")
def widget():
    return "<html><body><h1>Flama widget</h1></body></html>"


@tools_server.tool("with_ui", description="A tool that declares a prefetchable UI template", ui_template="ui://widget")
def with_ui() -> str:
    return "rendered"


math_server = MCPServer("math", version="2.0.0")


@math_server.tool("multiply", description="Multiply two integers")
def multiply(a: int, b: int) -> int:
    return a * b


app = Flama(
    openapi={
        "info": {
            "title": "Flama 2.0 - MCP",
            "version": "2.0.0",
            "description": "Stateless Model Context Protocol servers",
        }
    },
)

app.mcp.add_server("/mcp/tools/", "tools", server=tools_server)
app.mcp.add_server("/mcp/math/", "math", server=math_server)


if __name__ == "__main__":
    flama.run(flama_app=app, server_host="0.0.0.0", server_port=8080)
