import json

from flama.http.responses.ndjson import NDJSONResponse


class TestCaseNDJSONResponse:
    """Cover the NDJSON streaming response wrapper."""

    def test_media_type(self) -> None:
        """The class advertises the ``application/x-ndjson`` content type."""
        assert NDJSONResponse.media_type == "application/x-ndjson"

    def test_encode_appends_newline(self) -> None:
        """A single chunk is encoded as compact JSON followed by ``\\n``."""

        async def _empty():
            if False:
                yield {}

        response = NDJSONResponse(_empty())

        encoded = response.encode({"foo": "bar"})

        assert encoded.endswith(b"\n")
        assert json.loads(encoded.rstrip(b"\n")) == {"foo": "bar"}

    def test_encode_round_trip(self) -> None:
        """Encoded frames are individually parseable and preserve their payload."""

        async def _empty():
            if False:
                yield {}

        response = NDJSONResponse(_empty())
        frames = [
            {"done": False, "response": "hello"},
            {"done": True, "done_reason": "stop", "eval_count": 5},
        ]

        encoded = b"".join(response.encode(frame) for frame in frames)
        lines = encoded.splitlines()

        assert len(lines) == 2
        assert [json.loads(line) for line in lines] == frames

    def test_encode_compact_output(self) -> None:
        """The encoder produces compact JSON (no whitespace separators)."""

        async def _empty():
            if False:
                yield {}

        response = NDJSONResponse(_empty())

        encoded = response.encode({"a": 1, "b": 2})

        assert b", " not in encoded
        assert b": " not in encoded
