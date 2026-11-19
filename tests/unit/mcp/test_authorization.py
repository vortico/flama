import asyncio
import uuid

import pytest

from flama import Flama
from flama.authentication import AccessTokenComponent, AuthenticationMiddleware
from flama.authentication.data_structures import ProtectedResource
from flama.authentication.jwt import JWT
from flama.client import Client
from flama.http import JSONRPCStatus
from flama.mcp.data_structures import Extensions, RequestHeaders, RequestMeta
from flama.mcp.server import MCPServer
from flama.mcp.tasks import TaskStatus

RESOURCE = "https://api.example.com/mcp/"
METADATA = "https://api.example.com/.well-known/oauth-protected-resource/mcp/"
SECRET = uuid.UUID(int=0).bytes
TASKS_META = {f"{RequestMeta.MCP_NAMESPACE}/clientCapabilities": {"extensions": {Extensions.TASKS: {}}}}


async def call(app, method, params=None, *, claims=None):
    """Send an MCP request with its routing headers, carrying a token with the given claims if any."""
    params = params or {}
    headers = {RequestHeaders.METHOD_HEADER: method, RequestHeaders.PROTOCOL_VERSION_HEADER: MCPServer.PROTOCOL_VERSION}
    if (name := params.get("uri" if method == "resources/read" else "name")) is not None:
        headers[RequestHeaders.NAME_HEADER] = name
    if claims is not None:
        headers["Authorization"] = f"Bearer {JWT({'alg': 'HS256', 'typ': 'JWT'}, claims).encode(SECRET).decode()}"

    async with Client(app=app) as client:
        return await client.post(
            "/mcp/", json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, headers=headers
        )


class TestCaseServerAuthorization:
    @pytest.fixture(scope="function")
    def app(self):
        app = Flama(schema=None, docs=None, components=[AccessTokenComponent(SECRET)])
        app.add_middleware(AuthenticationMiddleware())
        app.mcp.add_server(
            "/mcp/",
            "test",
            tags={"permissions": ["mcp:use"]},
            authorization=ProtectedResource(
                RESOURCE, authorization_servers=("https://auth.example.com",), scopes_supported=("mcp:use",)
            ),
        )
        return app

    @pytest.mark.parametrize(
        ["claims", "status_code", "challenge"],
        (
            pytest.param({"aud": RESOURCE, "scope": "mcp:use"}, 200, None, id="granted"),
            pytest.param(None, 401, f'Bearer scope="mcp:use", resource_metadata="{METADATA}"', id="no_token"),
            pytest.param(
                {"aud": RESOURCE},
                403,
                f'Bearer error="insufficient_scope", scope="mcp:use", resource_metadata="{METADATA}"',
                id="scope_missing",
            ),
            pytest.param(
                {"aud": "https://other.example.com", "scope": "mcp:use"},
                401,
                f'Bearer error="invalid_token", scope="mcp:use", resource_metadata="{METADATA}"',
                id="other_audience",
            ),
        ),
    )
    async def test_request(self, app, claims, status_code, challenge):
        response = await call(app, "ping", claims=claims)

        assert response.status_code == status_code
        assert response.headers.get("www-authenticate") == challenge

    async def test_protected_resource_metadata(self, app):
        async with Client(app=app) as client:
            response = await client.get("/.well-known/oauth-protected-resource/mcp/")

        assert response.status_code == 200
        assert response.json() == {
            "resource": RESOURCE,
            "authorization_servers": ["https://auth.example.com"],
            "scopes_supported": ["mcp:use"],
            "bearer_methods_supported": ["header"],
        }

    def test_authorization_names_an_authorization_server(self):
        app = Flama(schema=None, docs=None)

        with pytest.raises(ValueError, match="at least one authorization server"):
            app.mcp.add_server("/mcp/", "test", authorization=ProtectedResource(RESOURCE))


class TestCaseEntryAuthorization:
    @pytest.fixture(scope="function")
    def app(self):
        app = Flama(schema=None, docs=None, components=[AccessTokenComponent(SECRET)])
        app.add_middleware(AuthenticationMiddleware())
        app.mcp.add_server("/mcp/", "test")

        @app.mcp.tool("public")
        def public() -> str:
            return "public"

        @app.mcp.tool("admin", permissions=["tools:admin"])
        def admin() -> str:
            return "admin"

        @app.mcp.tool("slow", task=True, permissions=["tools:slow"])
        async def slow() -> str:
            await asyncio.sleep(10)
            return "slow"

        @app.mcp.resource("res://public")
        def public_resource():
            return "public"

        @app.mcp.resource("res://secret", roles=["admin"])
        def secret_resource():
            return "secret"

        @app.mcp.resource("res://secrets/{id}", roles=["admin"], completions={"id": lambda value, arguments: ["1"]})
        def secret_resources(id: int):
            return f"secret {id}"

        @app.mcp.prompt("public_prompt")
        def public_prompt():
            return "public"

        @app.mcp.prompt("secret_prompt", permissions=["prompts:secret"])
        def secret_prompt():
            return "secret"

        @app.mcp.ui_resource("ui://secret", permissions=["ui:secret"])
        def secret_ui():
            return "<html></html>"

        return app

    @pytest.mark.parametrize(
        ["method", "params", "claims", "status_code", "challenge"],
        (
            pytest.param("tools/call", {"name": "public"}, None, 200, None, id="tool_without_requirements"),
            pytest.param("tools/call", {"name": "admin"}, {"scope": "tools:admin"}, 200, None, id="tool_granted"),
            pytest.param("tools/call", {"name": "admin"}, None, 401, 'Bearer scope="tools:admin"', id="tool_no_token"),
            pytest.param(
                "tools/call",
                {"name": "admin"},
                {"scope": "other"},
                403,
                'Bearer error="insufficient_scope", scope="tools:admin"',
                id="tool_scope_missing",
            ),
            pytest.param("resources/read", {"uri": "res://secret"}, {"roles": ["admin"]}, 200, None, id="resource"),
            pytest.param(
                "resources/read", {"uri": "res://secret"}, {"roles": ["guest"]}, 403, None, id="resource_role_missing"
            ),
            pytest.param(
                "resources/read", {"uri": "res://secrets/1"}, {"roles": ["admin"]}, 200, None, id="resource_template"
            ),
            pytest.param(
                "resources/read",
                {"uri": "res://secrets/1"},
                {"roles": ["guest"]},
                403,
                None,
                id="resource_template_role_missing",
            ),
            pytest.param(
                "prompts/get", {"name": "secret_prompt"}, {"scope": "prompts:secret"}, 200, None, id="prompt_granted"
            ),
            # An entry the server does not know adds nothing, and is answered as not found by the endpoint.
            pytest.param("tools/call", {"name": "unknown"}, None, 200, None, id="unknown_entry"),
        ),
    )
    async def test_request(self, app, method, params, claims, status_code, challenge):
        response = await call(app, method, params, claims=claims)

        assert response.status_code == status_code
        assert response.headers.get("www-authenticate") == challenge

    @pytest.mark.parametrize(
        ["authorization", "status_code", "challenge"],
        (
            pytest.param("Bearer not.a.token", 401, 'Bearer error="invalid_token"', id="invalid_token"),
            pytest.param("token", 400, 'Bearer error="invalid_request"', id="malformed_header"),
        ),
    )
    async def test_invalid_credentials(self, app, authorization, status_code, challenge):
        # A public server lists without a token, but refuses one it cannot accept as HTTP does, not as a failed call.
        headers = {
            RequestHeaders.METHOD_HEADER: "tools/list",
            RequestHeaders.PROTOCOL_VERSION_HEADER: MCPServer.PROTOCOL_VERSION,
            "Authorization": authorization,
        }
        async with Client(app=app) as client:
            response = await client.post(
                "/mcp/", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, headers=headers
            )

        assert response.status_code == status_code
        assert response.headers["www-authenticate"] == challenge

    @pytest.mark.parametrize(
        ["claims", "tools", "resources", "prompts"],
        (
            pytest.param(None, ["public"], ["res://public"], ["public_prompt"], id="anonymous"),
            pytest.param(
                {"scope": "tools:admin tools:slow prompts:secret ui:secret", "roles": ["admin"]},
                ["public", "admin", "slow"],
                ["res://public", "res://secret", "ui://secret"],
                ["public_prompt", "secret_prompt"],
                id="granted",
            ),
        ),
    )
    async def test_lists(self, app, claims, tools, resources, prompts):
        tools_response = await call(app, "tools/list", claims=claims)
        resources_response = await call(app, "resources/list", claims=claims)
        prompts_response = await call(app, "prompts/list", claims=claims)

        assert [x["name"] for x in tools_response.json()["result"]["tools"]] == tools
        assert [x["uri"] for x in resources_response.json()["result"]["resources"]] == resources
        assert [x["name"] for x in prompts_response.json()["result"]["prompts"]] == prompts

    @pytest.mark.parametrize(
        ["creator", "caller", "found"],
        (
            pytest.param("alice", "alice", True, id="owner"),
            pytest.param("alice", "bob", False, id="another_principal"),
            pytest.param(None, "bob", True, id="created_without_subject"),
        ),
    )
    async def test_task_ownership(self, app, creator, caller, found):
        created = await call(
            app,
            "tools/call",
            {"name": "slow", "_meta": TASKS_META},
            claims={"sub": creator, "scope": "tools:slow"},
        )
        task_id = created.json()["result"]["task"]["taskId"]

        for method in ("tasks/get", "tasks/cancel"):
            response = await call(app, method, {"taskId": task_id}, claims={"sub": caller, "scope": "tools:slow"})

            if found:
                assert response.json()["result"]["task"]["taskId"] == task_id
            else:
                assert response.json()["error"]["code"] == JSONRPCStatus.INVALID_PARAMS
                assert response.json()["error"]["message"] == f"Task '{task_id}' not found"

    @pytest.mark.parametrize(
        ["claims", "resumed"],
        (
            pytest.param({"scope": "tools:admin"}, True, id="granted"),
            pytest.param({"scope": "other"}, False, id="scope_missing"),
        ),
    )
    async def test_task_resume(self, app, claims, resumed):
        server = app.mcp._servers["test"]
        task, _ = await server.task_store.create(tool_name="admin")
        task.status = TaskStatus.INPUT_REQUIRED
        await server.task_store.save(task)

        response = await call(app, "tasks/update", {"taskId": task.id, "inputResponses": {}}, claims=claims)

        if resumed:
            assert response.json()["result"]["task"]["status"] == "working"
        else:
            assert response.json()["error"]["message"] == f"Insufficient permissions for task '{task.id}'"

    @pytest.mark.parametrize(
        ["claims", "templates", "completion"],
        (
            pytest.param(None, [], None, id="anonymous"),
            pytest.param({"roles": ["admin"]}, ["res://secrets/{id}"], ["1"], id="granted"),
        ),
    )
    async def test_resource_templates(self, app, claims, templates, completion):
        listed = await call(app, "resources/templates/list", claims=claims)
        completed = await call(
            app,
            "completion/complete",
            {"ref": {"type": "ref/resource", "uri": "res://secrets/{id}"}, "argument": {"name": "id", "value": ""}},
            claims=claims,
        )

        assert [x["uriTemplate"] for x in listed.json()["result"]["resourceTemplates"]] == templates
        if completion is None:
            assert completed.json()["error"]["message"] == "Resource template 'res://secrets/{id}' not found"
        else:
            assert completed.json()["result"]["completion"]["values"] == completion
