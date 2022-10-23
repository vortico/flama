import codecs
import io
import typing

from flama.serialize.base import Serializer

try:
    import torch
except Exception:  # pragma: no cover
    torch = None  # type: ignore[misc, assignment]


class PyTorchSerializer(Serializer):
    def dump(self, obj: typing.Any, **kwargs) -> bytes:
        assert torch is not None, "`pytorch` must be installed to use PyTorchSerializer."
        buffer = io.BytesIO()
        torch.jit.save(torch.jit.script(obj), buffer, **kwargs)
        buffer.seek(0)
        return codecs.encode(buffer.read(), "base64")

    def load(self, model: bytes, **kwargs) -> typing.Any:
        assert torch is not None, "`pytorch` must be installed to use PyTorchSerializer."
        return torch.jit.load(io.BytesIO(codecs.decode(model, "base64")), **kwargs)
