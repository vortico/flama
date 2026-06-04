import importlib.metadata
import io
import json
import logging
import os
import pathlib
import tempfile
import typing as t

from flama import exceptions, types
from flama._core.compression import tar
from flama.serialize.data_structures import LLMModelCapabilities
from flama.serialize.model_serializers.base import BaseModelSerializer

try:
    import transformers
    import transformers.utils.logging

    transformers.utils.logging.set_verbosity_error()
    transformers.utils.logging.disable_progress_bar()
except Exception:  # pragma: no cover
    transformers = None

if t.TYPE_CHECKING:
    from flama.types import JSONSchema

logger = logging.getLogger(__name__)

__all__ = ["ModelSerializer"]


class ModelSerializer(BaseModelSerializer):
    lib: t.ClassVar[types.ModelLib] = "transformers"

    @staticmethod
    def _tar_directory(directory: pathlib.Path) -> bytes:
        """Pack a directory into an uncompressed tar archive in memory.

        :param directory: Path to the directory to archive.
        :return: Tar archive bytes.
        """
        buf = io.BytesIO()
        tar(str(directory), buf)
        return buf.getvalue()

    def dump(self, obj: t.Any, /, **kwargs) -> bytes:
        """Serialize a transformers model into tar bytes.

        :param obj: A directory path (:class:`~pathlib.Path`, :class:`str`, or :class:`os.PathLike`) containing
            pretrained model files, or a :class:`transformers.Pipeline` whose weights are saved and archived.
        :return: Tar archive bytes containing the model directory.
        """
        if transformers is None:  # noqa
            raise exceptions.FrameworkNotInstalled("transformers")

        if isinstance(obj, str | os.PathLike | pathlib.Path):
            return self._tar_directory(pathlib.Path(obj))

        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir)
            obj.save_pretrained(path)
            return self._tar_directory(path)

    def load(
        self,
        source: bytes | pathlib.Path,
        /,
        *,
        task: str | None = None,
        framework: str | None = None,
        capabilities: "LLMModelCapabilities | None" = None,
        **kwargs,
    ) -> t.Any:
        """Deserialize an extracted bundle directory into a :class:`transformers.Pipeline`.

        :param source: :class:`pathlib.Path` to an extracted model bundle (the wire-level model
            section was a ``bundle`` kind). Raw bytes are rejected because Transformers consumes the
            on-disk snapshot directly.
        :param task: Pipeline task name (e.g. ``"text-generation"``).
        :param framework: DL framework to use (``"pt"`` or ``"tf"``).
        :param capabilities: Capabilities forwarded by the load protocol; unused at this layer
            (a Transformers pipeline does not act on them) but absorbed here so they do not bleed
            into ``model_kwargs`` of :func:`transformers.pipeline`.
        :return: A ready-to-use :class:`transformers.Pipeline`.
        """
        if transformers is None:  # noqa
            raise exceptions.FrameworkNotInstalled("transformers")

        if not isinstance(source, pathlib.Path):
            raise TypeError("transformers serializer expects an extracted model directory, not raw bytes")

        return t.cast(t.Callable[..., t.Any], transformers.pipeline)(task=task, model=str(source), **kwargs)

    _PROBE_TOOL_NAME: t.ClassVar[str] = "__flama_probe_tool__"
    _PROBE_TOOL_DESCRIPTION: t.ClassVar[str] = "__flama_probe_tool_description__"
    _PROBE_USER_MESSAGE: t.ClassVar[str] = "__flama_probe_user_message__"

    def detect_capabilities(self, model: t.Any, /) -> "LLMModelCapabilities | None":
        """Detect modal capabilities by inspecting the HuggingFace bundle on disk.

        Accepts either a directory path or an in-memory :class:`transformers.Pipeline` whose
        underlying model points at a local snapshot; both shapes resolve to a filesystem path
        that is probed for the canonical HuggingFace signal site: ``vision_config`` /
        ``audio_config`` blocks in ``config.json``, with ``preprocessor_config.json``'s
        presence acting as a softer image-only fallback.

        Tool and reasoning support are derived from the chat template at serialize time. The
        primary path loads the tokenizer and renders the template against sentinel inputs:

        * **Tools** — render a one-turn conversation with a single sentinel tool whose name
          is :data:`_PROBE_TOOL_NAME`; if the rendered output contains the sentinel verbatim,
          the template wires tools through. Templates that ignore the ``tools`` argument leave
          the sentinel out and are reported as tool-less.
        * **Reasoning** — render the same conversation twice with ``enable_thinking=True`` and
          ``enable_thinking=False``; if the outputs differ, the template observes the flag and
          the model is considered reasoning-capable.

        When the tokenizer cannot be loaded (e.g. ``trust_remote_code`` requirements, missing
        files, or sandboxed environments), falls back to a tightened textual heuristic that
        only fires on fully-qualified Jinja references (``{{ tools }}`` / ``{% if tools %}`` /
        ``{{ enable_thinking }}``…) so the false-positive rate stays close to the probe's.
        Returns :data:`None` when the bundle has no recognisable capability markers at all so
        callers can refuse to load rather than guess.

        :param model: Directory path or :class:`transformers.Pipeline` referencing a local snapshot.
        :return: Detected :class:`~flama.serialize.data_structures.LLMModelCapabilities`, or
            :data:`None` when the bundle has no capability markers.
        """
        model_path = getattr(getattr(model, "model", None), "name_or_path", model)
        if not isinstance(model_path, str | os.PathLike | pathlib.Path):
            return None

        path = pathlib.Path(model_path)
        config_path = path / "config.json"
        preprocessor_path = path / "preprocessor_config.json"
        tokenizer_config_path = path / "tokenizer_config.json"

        config: t.Any = None
        if config_path.is_file():
            try:
                config = json.loads(config_path.read_text())
            except (OSError, ValueError):
                pass

        has_preprocessor = preprocessor_path.is_file()
        if config is None and not has_preprocessor:
            return None

        image = isinstance(config, dict) and isinstance(config.get("vision_config"), dict)
        audio = isinstance(config, dict) and isinstance(config.get("audio_config"), dict)
        if not (image or audio):
            image = has_preprocessor

        tools, reasoning = self._probe_chat_template(path, tokenizer_config_path)
        return LLMModelCapabilities(text=True, image=image, audio=audio, tools=tools, reasoning=reasoning)

    def _probe_chat_template(self, path: pathlib.Path, tokenizer_config_path: pathlib.Path) -> tuple[bool, bool]:
        """Probe the bundle's chat template for tool and reasoning support.

        Tries the tokenizer-based probe first (rendering the template with sentinel inputs and
        observing whether the tokens flow through); on any failure (no tokenizer, parser error,
        Jinja raised) falls back to a Jinja-aware textual heuristic against
        ``tokenizer_config.json``.
        """
        if (probed := self._probe_with_tokenizer(path)) is not None:
            return probed
        return self._probe_with_heuristic(tokenizer_config_path)

    def _probe_with_tokenizer(self, path: pathlib.Path) -> tuple[bool, bool] | None:
        """Render the chat template against sentinel inputs and read the capabilities back.

        Returns :data:`None` when the tokenizer can't be loaded or the template can't be rendered;
        the caller falls back to the heuristic in that case.
        """
        if transformers is None:  # pragma: no cover
            return None

        try:
            tokenizer = transformers.AutoTokenizer.from_pretrained(str(path), trust_remote_code=False)
        except Exception:
            return None

        if not getattr(tokenizer, "chat_template", None):
            return None

        messages = [{"role": "user", "content": self._PROBE_USER_MESSAGE}]
        tool_schema = {
            "type": "function",
            "function": {
                "name": self._PROBE_TOOL_NAME,
                "description": self._PROBE_TOOL_DESCRIPTION,
                "parameters": {"type": "object", "properties": {}},
            },
        }

        try:
            with_tools = tokenizer.apply_chat_template(messages, tools=[tool_schema], tokenize=False)
        except Exception:
            with_tools = None
        tools_supported = isinstance(with_tools, str) and self._PROBE_TOOL_NAME in with_tools

        try:
            thinking_on = tokenizer.apply_chat_template(messages, tokenize=False, enable_thinking=True)
            thinking_off = tokenizer.apply_chat_template(messages, tokenize=False, enable_thinking=False)
        except Exception:
            return tools_supported, False
        reasoning_supported = (
            isinstance(thinking_on, str) and isinstance(thinking_off, str) and thinking_on != thinking_off
        )

        return tools_supported, reasoning_supported

    @staticmethod
    def _probe_with_heuristic(tokenizer_config_path: pathlib.Path) -> tuple[bool, bool]:
        """Detect tools/reasoning by inspecting Jinja references in the chat template source.

        Tighter than the legacy ``"tools" in template`` substring check: requires a full Jinja
        reference (``{{ tools ...}}`` or ``{% ... tools ...%}``) so that templates which merely
        document tools in a comment or string literal don't trip the heuristic. Reasoning is
        gated on a similar reference to ``enable_thinking`` plus the historical channel markers.
        """
        if not tokenizer_config_path.is_file():
            return False, False

        try:
            tok_config = json.loads(tokenizer_config_path.read_text())
        except (OSError, ValueError):
            return False, False

        chat_template = tok_config.get("chat_template", "")
        if isinstance(chat_template, list):
            chat_template = " ".join(entry.get("template", "") for entry in chat_template if isinstance(entry, dict))
        if not isinstance(chat_template, str) or not chat_template:
            return False, False

        tools = "{{ tools" in chat_template or "{%- if tools" in chat_template or "{% if tools" in chat_template
        reasoning = (
            "enable_thinking" in chat_template or "<think>" in chat_template or "reasoning_content" in chat_template
        )
        return tools, reasoning

    def info(self, model: t.Any, /) -> "JSONSchema | None":
        try:
            info: dict[str, t.Any] = {}
            if hasattr(model, "model") and hasattr(model.model, "config"):
                info["config"] = model.model.config.to_dict()
            if hasattr(model, "task"):
                info["task"] = model.task
            if hasattr(model, "model") and hasattr(model.model, "name_or_path"):
                info["model_name"] = model.model.name_or_path
            return info or None
        except Exception:  # noqa
            logger.exception("Cannot collect info from model")
            return None

    def version(self) -> str:
        try:
            return importlib.metadata.version("transformers")
        except Exception:  # noqa
            raise exceptions.FrameworkNotInstalled("transformers")
