import importlib.metadata
import io
import json
import logging
import os
import pathlib
import struct
import tempfile
import typing as t

from flama import exceptions, types
from flama._core.compression import tar
from flama.serialize.data_structures import LLMModelCapabilities
from flama.serialize.model_serializers._base import BaseModelSerializer

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

    _WEIGHT_INDEX: t.ClassVar[str] = "model.safetensors.index.json"
    _WEIGHT_FILE: t.ClassVar[str] = "model.safetensors"
    _VISION_TENSORS: t.ClassVar[frozenset[str]] = frozenset(
        {
            "vision_tower",
            "vision_model",
            "vision_embedder",
            "embed_vision",
            "visual",
            "multi_modal_projector",
            "mm_projector",
            "image_projector",
        }
    )
    _AUDIO_TENSORS: t.ClassVar[frozenset[str]] = frozenset(
        {"audio_tower", "audio_model", "audio_embedder", "embed_audio", "audio_projector"}
    )

    def detect_capabilities(self, model: t.Any, /) -> "LLMModelCapabilities | None":
        """Detect modal capabilities by inspecting the HuggingFace bundle on disk.

        Accepts either a directory path or an in-memory :class:`transformers.Pipeline` whose
        underlying model points at a local snapshot; both shapes resolve to a filesystem path
        that is probed for the canonical HuggingFace signal site: ``vision_config`` /
        ``audio_config`` blocks in ``config.json``, with the modality-specific processor types
        declared in ``preprocessor_config.json`` acting as a softer fallback when the config
        carries no modality block at all.

        A declared config block is treated as *necessary but not sufficient*: it advertises what
        the architecture can do, not what the checkpoint actually ships. Text-only derivatives
        routinely keep the upstream multimodal ``config.json`` while dropping the tower weights,
        which would strand the artifact on a runtime that strict-loads them. :meth:`_probe_weights`
        therefore corroborates each declared modality against the bundle's tensor names, and a
        modality is cleared when the tensor set is known and carries no matching tower. The
        corroboration is deliberately downgrade-only — when the weight layout cannot be read the
        config-derived answer stands — so an unfamiliar naming scheme degrades to the declared
        capabilities instead of silently dropping a real one.

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
            image, audio = self._probe_preprocessor(preprocessor_path)

        if (tensors := self._probe_weights(path)) is not None:
            architectures = config.get("architectures") if isinstance(config, dict) else None
            if image and not self._carries(tensors, self._VISION_TENSORS):
                logger.warning(
                    "Bundle at '%s' declares image support (architectures=%s) but ships no vision tensors; "
                    "reporting the model as image-incapable",
                    path,
                    architectures,
                )
                image = False
            if audio and not self._carries(tensors, self._AUDIO_TENSORS):
                logger.warning(
                    "Bundle at '%s' declares audio support (architectures=%s) but ships no audio tensors; "
                    "reporting the model as audio-incapable",
                    path,
                    architectures,
                )
                audio = False

        tools, reasoning = self._probe_chat_template(path, tokenizer_config_path)
        return LLMModelCapabilities(text=True, image=image, audio=audio, tools=tools, reasoning=reasoning)

    @staticmethod
    def _probe_preprocessor(preprocessor_path: pathlib.Path, /) -> tuple[bool, bool]:
        """Read the image / audio modalities declared by ``preprocessor_config.json``.

        Fallback for bundles whose ``config.json`` carries no modality block at all: a multimodal
        bundle has to ship a processor to preprocess its non-text inputs, and that processor names its
        own type. Keying off the declared ``image_processor_type`` / ``feature_extractor_type`` rather
        than the file's mere presence keeps text-only bundles that happen to carry a processor config
        from being reported as multimodal. ``feature_extractor_type`` is ambiguous on older vision
        bundles predating ``image_processor_type``; :meth:`_probe_weights` corroborates the result.

        :param preprocessor_path: Candidate ``preprocessor_config.json`` path (need not exist).
        :return: Tuple of ``(image, audio)``, both :data:`False` when the file is absent or unreadable.
        """
        try:
            preprocessor = json.loads(preprocessor_path.read_text())
        except (OSError, ValueError):
            return False, False
        if not isinstance(preprocessor, dict):
            return False, False
        return "image_processor_type" in preprocessor, "feature_extractor_type" in preprocessor

    def _probe_weights(self, path: pathlib.Path, /) -> frozenset[str] | None:
        """Enumerate the bundle's tensor names without reading any tensor data.

        Sharded bundles are read from ``model.safetensors.index.json``'s ``weight_map`` keys;
        single-file bundles from the safetensors header (a little-endian ``uint64`` header length
        followed by that many bytes of JSON, whose keys are the tensor names).

        :param path: Extracted HuggingFace bundle directory.
        :return: Tensor names, or :data:`None` when the layout cannot be read (legacy ``.bin``
            pickles, absent weights, truncated or malformed headers) so callers keep whatever the
            config declared.
        """
        if (index := path / self._WEIGHT_INDEX).is_file():
            try:
                names = json.loads(index.read_text())["weight_map"]
            except (OSError, ValueError, KeyError, TypeError):
                return None
        elif (single := path / self._WEIGHT_FILE).is_file():
            try:
                with single.open("rb") as f:
                    (header_size,) = struct.unpack("<Q", f.read(struct.calcsize("<Q")))
                    names = json.loads(f.read(header_size))
            except (OSError, ValueError, struct.error):
                return None
        else:
            return None

        # Both shapes are objects keyed by tensor name, so they normalise identically; ``__metadata__``
        # is the safetensors header's reserved non-tensor entry.
        if not isinstance(names, dict):
            return None
        return frozenset(name for name in names if isinstance(name, str) and name != "__metadata__")

    @staticmethod
    def _carries(tensors: frozenset[str], tokens: frozenset[str], /) -> bool:
        """Whether any tensor name carries one of *tokens* as a dotted segment.

        Segment-wise rather than substring matching so ``language_model.model.embed_tokens.weight``
        never trips the ``embed_vision`` / ``embed_audio`` tokens.
        """
        return any(not tokens.isdisjoint(name.split(".")) for name in tensors)

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
