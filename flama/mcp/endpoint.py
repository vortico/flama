import asyncio
import logging
import typing as t

from flama import _concurrency, exceptions, http, types
from flama._core.json_encoder import encode_json
from flama.endpoints.jsonrpc import JSONRPCEndpoint
from flama.http import JSONRPCStatus
from flama.mcp.data_structures import (
    Elicit,
    Elicitation,
    Extensions,
    Prompt,
    RequestHeaders,
    RequestState,
    Resource,
    Tool,
)
from flama.mcp.http import MCPResponse
from flama.mcp.server import MCPServer
from flama.mcp.tasks import Task, TaskStatus
from flama.schemas.exceptions import SchemaValidationError

__all__ = ["MCPEndpoint"]

logger = logging.getLogger(__name__)


class MCPEndpoint(JSONRPCEndpoint):
    """MCP endpoint implementing the stateless Model Context Protocol (``2026-07-28``) over JSON-RPC.

    The ``initialize``/``initialized`` handshake and protocol-level sessions are gone (SEP-2575/2567): every request is
    self-contained, carrying its protocol version, client identity, and capabilities in ``_meta`` and its routing data
    in the ``Mcp-Method``/``Mcp-Name`` headers (SEP-2243). Clients fetch server capabilities on demand via
    ``server/discover``.
    """

    server: t.ClassVar[MCPServer]
    handlers: t.ClassVar[dict[str, str]] = {
        "server/discover": "server_discover",
        "ping": "ping",
        "tools/list": "tools_list",
        "tools/call": "tools_call",
        "resources/list": "resources_list",
        "resources/read": "resources_read",
        "resources/templates/list": "resources_templates_list",
        "prompts/list": "prompts_list",
        "prompts/get": "prompts_get",
        "tasks/get": "tasks_get",
        "tasks/update": "tasks_update",
        "tasks/cancel": "tasks_cancel",
    }

    async def resolve_handler(self) -> t.Callable[..., t.Awaitable[t.Any] | t.Any]:
        """Enforce the routing headers and protocol version before resolving the JSON-RPC handler.

        :return: Handler.
        :raises JSONRPCException: If the routing headers disagree with the body, or the requested protocol version is
            not supported.
        """
        headers = await self.state.app.injector.value(RequestHeaders, self.state)

        if (
            headers.method != "server/discover"
            and headers.protocol_version is not None
            and headers.protocol_version not in MCPServer.SUPPORTED_VERSIONS
        ):
            raise exceptions.JSONRPCException(
                status_code=JSONRPCStatus.UNSUPPORTED_PROTOCOL_VERSION,
                data={"supported": list(MCPServer.SUPPORTED_VERSIONS), "requested": headers.protocol_version},
            )

        return await super().resolve_handler()

    async def dispatch(self) -> t.Any:
        response = await super().dispatch()
        if isinstance(response, http.JSONRPCResponse):
            response = MCPResponse(response.result, id=response.id)

        response.headers[RequestHeaders.PROTOCOL_VERSION_HEADER] = MCPServer.PROTOCOL_VERSION
        return response

    def server_discover(self) -> dict[str, t.Any]:
        capabilities: dict[str, dict[str, t.Any]] = {}
        if self.server._tools:
            capabilities["tools"] = {}
        if self.server._resources:
            capabilities["resources"] = {}
        if self.server._prompts:
            capabilities["prompts"] = {}
        if self.server.supported_extensions:
            capabilities["extensions"] = {extension: {} for extension in sorted(self.server.supported_extensions)}

        result: dict[str, t.Any] = {
            "resultType": "complete",
            "supportedVersions": list(MCPServer.SUPPORTED_VERSIONS),
            "capabilities": capabilities,
            "serverInfo": {"name": self.server.name, "version": self.server.version},
            **self._cache_metadata(),
        }

        if self.server.instructions:
            result["instructions"] = self.server.instructions

        return result

    def ping(self) -> dict[str, t.Any]:
        return {}

    def tools_list(self) -> dict[str, t.Any]:
        tools = []
        for entry in self.server._tools.values():
            tool: dict[str, t.Any] = {
                "name": entry.name,
                "description": entry.description,
                "inputSchema": entry.input_schema,
            }
            if entry.output_schema is not None:
                tool["outputSchema"] = entry.output_schema
            if entry.ui_template is not None:
                tool["uiTemplate"] = entry.ui_template
            tools.append(tool)

        return {"tools": tools, **self._cache_metadata()}

    async def tools_call(self, tool: Tool, params: types.JSONRPCParams, extensions: Extensions) -> dict[str, t.Any]:
        arguments = params.get("arguments") or {}
        responses = self._combined_responses(params)

        if tool.task and Extensions.TASKS in extensions:
            task = await self.server.task_store.create(
                ttl_ms=self.server.cache_ttl_ms, tool_name=tool.name, arguments=arguments
            )
            task.runner = asyncio.ensure_future(self._run_tool_task(task, tool, arguments, responses))
            await self.server.task_store.save(task)
            return {"resultType": "task", "task": task.to_dict(), **self._cache_metadata()}

        try:
            return await self._invoke_tool(tool, arguments, responses)
        except exceptions.JSONRPCException:
            raise
        except Exception as e:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INTERNAL_ERROR, detail=f"Tool '{tool.name}' raised: {e}"
            ) from e

    async def _invoke_tool(
        self, entry: Tool, arguments: dict[str, t.Any], responses: dict[str, t.Any]
    ) -> dict[str, t.Any]:
        """Run a tool handler, returning either an ``inputRequired`` result or the final tool result.

        Elicitation responses gathered so far are injected into the handler's declared parameter so it can branch; if
        the handler asks for more input (returns :class:`Elicit`), they are carried forward in ``requestState``.
        Invalid arguments are a failed tool call rather than a protocol error, so the model can read why and retry.
        """
        try:
            kwargs = entry.arguments.validate(arguments)
        except SchemaValidationError as e:
            return {"content": [{"type": "text", "text": f"Invalid arguments:\n{e}"}], "isError": True}

        if entry.elicitation_param is not None:
            kwargs[entry.elicitation_param] = Elicitation(responses)

        result = await _concurrency.run(entry.handler, **kwargs)

        if isinstance(result, Elicit):
            return {
                "resultType": "inputRequired",
                "inputRequests": result.input_requests,
                "requestState": RequestState.encode({"inputResponses": responses}),
            }

        return self._tool_content(entry, result)

    @staticmethod
    def _tool_content(entry: Tool, result: t.Any) -> dict[str, t.Any]:
        """Render a tool result as content blocks plus ``structuredContent`` when the tool declares an output schema.

        A schema result is serialised through it first, as REST serialises it, so both contents carry the same data.

        :param entry: Tool that produced the result.
        :param result: Value the tool returned.
        :return: The tool result.
        :raises JSONRPCException: If the result does not fit the tool's output schema.
        """
        if entry.result is not None:
            try:
                result = entry.result.dump(result)
            except SchemaValidationError as e:
                raise exceptions.JSONRPCException(
                    status_code=http.JSONRPCStatus.INTERNAL_ERROR,
                    detail=f"Tool '{entry.name}' returned a result not fitting its output schema:\n{e}",
                ) from e

        text = encode_json(result, compact=True).decode() if isinstance(result, (dict, list)) else str(result)
        response: dict[str, t.Any] = {"content": [{"type": "text", "text": text}]}

        if entry.output_schema is not None:
            response["structuredContent"] = result

        return response

    @staticmethod
    def _combined_responses(params: types.JSONRPCParams) -> dict[str, t.Any]:
        """Merge elicitation answers carried in ``requestState`` with the new ``inputResponses`` on this request."""
        state = RequestState.decode(params["requestState"]) if params.get("requestState") else {}
        return {**(state.get("inputResponses") or {}), **(params.get("inputResponses") or {})}

    async def _run_tool_task(
        self, task: Task, entry: Tool, arguments: dict[str, t.Any], responses: dict[str, t.Any]
    ) -> None:
        """Background runner that drives a task-augmented tool call to a terminal or ``input_required`` state."""
        try:
            outcome = await self._invoke_tool(entry, arguments, responses)
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            await self.server.task_store.save(task)
            raise
        except exceptions.JSONRPCException as e:
            task.status = TaskStatus.FAILED
            task.error = e.detail or "error"
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
        else:
            if outcome.get("resultType") == "inputRequired":
                task.status = TaskStatus.INPUT_REQUIRED
                task.input_requests = outcome["inputRequests"]
                task.request_state = outcome["requestState"]
            else:
                task.status = TaskStatus.COMPLETED
                task.result = outcome

        await self.server.task_store.save(task)

    def tasks_get(self, task: Task) -> dict[str, t.Any]:
        return {"task": task.to_dict(), **self._cache_metadata()}

    async def tasks_update(self, task: Task, params: types.JSONRPCParams) -> dict[str, t.Any]:
        if task.status != TaskStatus.INPUT_REQUIRED:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INVALID_PARAMS, detail=f"Task '{task.id}' is not awaiting input"
            )

        entry = self.server._tools.get(task.tool_name or "")
        if entry is None:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INVALID_PARAMS, detail=f"Tool '{task.tool_name}' not found"
            )

        prior = (RequestState.decode(task.request_state).get("inputResponses") or {}) if task.request_state else {}
        responses = {**prior, **(params.get("inputResponses") or {})}

        task.status = TaskStatus.WORKING
        task.input_requests = None
        task.request_state = None
        await self.server.task_store.save(task)
        task.runner = asyncio.ensure_future(self._run_tool_task(task, entry, task.arguments or {}, responses))

        return {"task": task.to_dict()}

    async def tasks_cancel(self, task: Task) -> dict[str, t.Any]:
        if task.runner is not None and not task.runner.done():
            task.runner.cancel()

        task.status = TaskStatus.CANCELLED
        await self.server.task_store.save(task)

        return {"task": task.to_dict()}

    def resources_list(self) -> dict[str, t.Any]:
        return {
            "resources": [
                {"uri": e.uri, "name": e.name, "description": e.description, "mimeType": e.mime_type}
                for e in self.server._resources.values()
            ],
            **self._cache_metadata(),
        }

    async def resources_read(self, resource: Resource) -> dict[str, t.Any]:
        try:
            result = await _concurrency.run(resource.handler)
        except exceptions.JSONRPCException:
            raise
        except Exception as e:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INTERNAL_ERROR, detail=f"Resource '{resource.uri}' raised: {e}"
            ) from e

        return {
            "contents": [{"uri": resource.uri, "mimeType": resource.mime_type, "text": str(result)}],
            **self._cache_metadata(),
        }

    def resources_templates_list(self) -> dict[str, t.Any]:
        """List the prefetchable MCP Apps UI templates this server declares (SEP-1865)."""
        return {
            "resourceTemplates": [
                {"uri": tpl.uri, "name": tpl.name, "description": tpl.description, "mimeType": tpl.mime_type}
                for tpl in self.server._app_templates.values()
            ],
            **self._cache_metadata(),
        }

    def prompts_list(self) -> dict[str, t.Any]:
        return {
            "prompts": [
                {"name": e.name, "description": e.description, "arguments": e.arguments}
                for e in self.server._prompts.values()
            ],
            **self._cache_metadata(),
        }

    async def prompts_get(self, prompt: Prompt, params: types.JSONRPCParams) -> dict[str, t.Any]:
        try:
            result = await _concurrency.run(prompt.handler, **(params.get("arguments") or {}))
        except exceptions.JSONRPCException:
            raise
        except Exception as e:
            raise exceptions.JSONRPCException(
                status_code=http.JSONRPCStatus.INTERNAL_ERROR, detail=f"Prompt '{prompt.name}' raised: {e}"
            ) from e

        if isinstance(result, str):
            messages = [{"role": "user", "content": {"type": "text", "text": result}}]
        elif isinstance(result, list):
            messages = result
        else:
            messages = [{"role": "user", "content": {"type": "text", "text": str(result)}}]

        return {"description": prompt.description, "messages": messages}

    def _cache_metadata(self) -> dict[str, t.Any]:
        """HTTP-style caching hints for list and read results (SEP-2549)."""
        return {"ttlMs": self.server.cache_ttl_ms, "cacheScope": self.server.cache_scope}
