from flama import http, types
from flama.injection import Component, Components

__all__ = ["JSONRPCEnvelopeComponent", "JSONRPCMethodComponent", "JSONRPCParamsComponent", "JSONRPC_COMPONENTS"]


class JSONRPCEnvelopeComponent(Component):
    async def resolve(self, request: http.Request) -> types.JSONRPCEnvelope:
        return types.JSONRPCEnvelope(await request.json())


class JSONRPCMethodComponent(Component):
    def resolve(self, envelope: types.JSONRPCEnvelope) -> types.JSONRPCMethod:
        return types.JSONRPCMethod(envelope.get("method") or "")


class JSONRPCParamsComponent(Component):
    def resolve(self, envelope: types.JSONRPCEnvelope) -> types.JSONRPCParams:
        return types.JSONRPCParams(envelope.get("params") or {})


JSONRPC_COMPONENTS = Components([JSONRPCEnvelopeComponent(), JSONRPCMethodComponent(), JSONRPCParamsComponent()])
