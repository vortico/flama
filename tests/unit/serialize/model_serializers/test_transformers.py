import importlib.metadata
import json
import pathlib
import types as py_types
import typing as t
from contextlib import ExitStack
from unittest.mock import MagicMock, call, patch

import pytest

from flama import exceptions
from flama.serialize.data_structures import LLMModelCapabilities
from flama.serialize.model_serializers.transformers import ModelSerializer as TransformersModelSerializer
from tests.unit.serialize.model_serializers.conftest import (
    SPECS,
    dump_assert,
    dump_setup,
    info_model,
    load_assert,
    load_setup,
)

_FRAMEWORK = "transformers"
# Sentinel objects used by the parametrised filesystem setup in :meth:`test_detect_capabilities` and
# :meth:`test_probe_with_heuristic` so each ``pytest.param`` can declare "write malformed JSON" or
# "leave the file out entirely" without inventing a parallel marker namespace inside the test body.
_INVALID_JSON_SENTINEL = object()
_FILE_MISSING_SENTINEL = object()


class TestCaseTransformersModelSerializer:
    """Cover the transformers slice of :class:`flama.serialize.model_serializers.transformers.ModelSerializer`."""

    @staticmethod
    def _build_capability_source(
        tmp_path: pathlib.Path,
        files: dict[str, t.Any],
        source_kind: str,
    ) -> t.Any:
        """Materialise the *files* under *tmp_path* and return the input shape *source_kind* dictates.

        Centralises the matrix expansion for :meth:`test_detect_capabilities` so each ``pytest.param``
        only describes its inputs declaratively (config payload + source shape) instead of repeating
        the filesystem-write / pipeline-build boilerplate per case.
        """
        for name, content in files.items():
            path = tmp_path / name
            if content is _INVALID_JSON_SENTINEL:
                path.write_text("not json{")
            else:
                # ``json.dumps`` even for str payloads so a ``"not-a-dict"`` case writes a JSON-encoded
                # string rather than raw text — matching what the production reader handles when the
                # config root deserialises to a non-mapping.
                path.write_text(json.dumps(content))
        sources = {
            "directory_path": tmp_path,
            "directory_path_str": str(tmp_path),
            "pipeline_local": py_types.SimpleNamespace(
                model=py_types.SimpleNamespace(name_or_path=str(tmp_path))
            ),
            "pipeline_remote": py_types.SimpleNamespace(
                model=py_types.SimpleNamespace(name_or_path="google/gemma-2-2b")
            ),
            "pipeline_no_path": py_types.SimpleNamespace(model=None),
            "opaque": py_types.SimpleNamespace(),
        }
        return sources[source_kind]

    @staticmethod
    def _build_probe_tokenizer(
        *,
        with_tools: t.Any,
        thinking_on: t.Any,
        thinking_off: t.Any,
    ) -> MagicMock:
        """Stub ``transformers.AutoTokenizer`` whose ``apply_chat_template`` returns hand-crafted strings
        (or raises) for the three sentinel calls the probe makes: tools-pass, thinking-on, thinking-off.

        Each axis accepts either a string (returned verbatim) or an :class:`Exception` subclass
        (raised). The tokenizer always advertises a populated ``chat_template`` so the probe doesn't
        short-circuit on the missing-template branch.
        """
        tokenizer = MagicMock()
        tokenizer.chat_template = "irrelevant"

        def apply(messages, tokenize=False, tools=None, enable_thinking=None):
            if tools is not None:
                if isinstance(with_tools, type) and issubclass(with_tools, BaseException):
                    raise with_tools()
                return with_tools
            if enable_thinking is True:
                if isinstance(thinking_on, type) and issubclass(thinking_on, BaseException):
                    raise thinking_on()
                return thinking_on
            if enable_thinking is False:
                if isinstance(thinking_off, type) and issubclass(thinking_off, BaseException):
                    raise thinking_off()
                return thinking_off
            return ""

        tokenizer.apply_chat_template = MagicMock(side_effect=apply)
        return tokenizer

    def test_lib(self) -> None:
        spec = SPECS[_FRAMEWORK]

        assert spec.serializer_cls.lib == spec.lib

    @pytest.mark.parametrize(
        ["scenario", "exception"],
        [
            pytest.param("path", None, id="path"),
            pytest.param("pipeline", None, id="pipeline"),
        ],
        indirect=["exception"],
    )
    def test_dump(self, scenario: str, exception, tmp_path: pathlib.Path) -> None:
        spec = SPECS[_FRAMEWORK]

        with ExitStack() as stack:
            obj, kwargs, mocks = dump_setup(_FRAMEWORK, scenario, stack, tmp_path)
            with exception:
                result = spec.serializer_cls().dump(obj, **kwargs)

            if not exception:
                assert isinstance(result, bytes)
                dump_assert(_FRAMEWORK, scenario, mocks, obj)

    @pytest.mark.parametrize(
        ["scenario", "exception"],
        [
            pytest.param("default", None, id="default"),
            pytest.param("extra", None, id="extra"),
            pytest.param("wrong-source", TypeError, id="wrong_source"),
            pytest.param("not-installed", exceptions.FrameworkNotInstalled, id="not_installed"),
        ],
        indirect=["exception"],
    )
    def test_load(self, scenario: str, exception) -> None:
        spec = SPECS[_FRAMEWORK]

        with ExitStack() as stack:
            source, kwargs, mocks = load_setup(_FRAMEWORK, scenario, stack)
            with exception:
                result = spec.serializer_cls().load(source, **kwargs)

            if not exception:
                load_assert(_FRAMEWORK, mocks, kwargs, source, result)

    @pytest.mark.parametrize(
        ["model_attrs", "expected"],
        [
            pytest.param(
                {"task": "text-generation", "config": {"hidden_size": 768}, "name": "google/gemma-2-2b"},
                {"config", "task", "model_name"},
                id="full",
            ),
            pytest.param({"config": {"hidden_size": 768}}, {"config"}, id="config_only"),
            pytest.param({"task": "text-generation"}, {"task"}, id="task_only"),
            pytest.param({}, None, id="empty"),
            pytest.param({"_raise": True}, None, id="exception"),
        ],
    )
    def test_info(self, model_attrs: dict, expected: set | None) -> None:
        spec = SPECS[_FRAMEWORK]
        model = info_model(_FRAMEWORK, model_attrs)

        result = spec.serializer_cls().info(model)

        if expected is None:
            assert result is None
        else:
            assert set(result.keys()) == expected

    @pytest.mark.parametrize(
        ["scenario", "exception"],
        [
            pytest.param("ok", None, id="success"),
            pytest.param("not-installed", exceptions.FrameworkNotInstalled, id="not_installed"),
        ],
        indirect=["exception"],
    )
    def test_version(self, scenario: str, exception) -> None:
        spec = SPECS[_FRAMEWORK]
        version_value = "1.2.3"
        side_effect = importlib.metadata.PackageNotFoundError() if scenario == "not-installed" else None
        return_value = None if scenario == "not-installed" else version_value

        with patch(spec.version_patch, return_value=return_value, side_effect=side_effect) as mock_ver:
            with exception:
                result = spec.serializer_cls().version()

        if not exception:
            assert result == version_value
            assert mock_ver.call_args == call(spec.version_key)

    @pytest.mark.parametrize(
        ["files", "source_kind", "expected"],
        [
            pytest.param(
                {"config.json": {"architectures": ["LlamaForCausalLM"]}},
                "directory_path",
                LLMModelCapabilities(text=True),
                id="text_only",
            ),
            pytest.param(
                {"config.json": {"vision_config": {"model_type": "siglip"}}},
                "directory_path",
                LLMModelCapabilities(text=True, image=True),
                id="image_only_via_vision_config",
            ),
            pytest.param(
                {"config.json": {"audio_config": {"model_type": "whisper"}}},
                "directory_path",
                LLMModelCapabilities(text=True, audio=True),
                id="audio_only_via_audio_config",
            ),
            pytest.param(
                {"config.json": {"vision_config": {}, "audio_config": {}}},
                "directory_path",
                LLMModelCapabilities(text=True, image=True, audio=True),
                id="image_and_audio",
            ),
            pytest.param(
                {"config.json": {"vision_config": "not-a-dict", "audio_config": 0}},
                "directory_path",
                LLMModelCapabilities(text=True),
                id="non_dict_blocks_ignored",
            ),
            pytest.param(
                {"config.json": "not-a-dict"},
                "directory_path",
                LLMModelCapabilities(text=True),
                id="root_not_a_dict",
            ),
            pytest.param(
                {"config.json": {"audio_config": {}}},
                "directory_path_str",
                LLMModelCapabilities(text=True, audio=True),
                id="directory_path_str",
            ),
            pytest.param(
                {"config.json": _INVALID_JSON_SENTINEL},
                "directory_path",
                None,
                id="invalid_json",
            ),
            pytest.param(
                {"preprocessor_config.json": {}},
                "directory_path",
                LLMModelCapabilities(text=True, image=True),
                id="preprocessor_fallback",
            ),
            pytest.param(
                {"config.json": {"vision_config": {}}, "preprocessor_config.json": {}},
                "directory_path",
                LLMModelCapabilities(text=True, image=True),
                id="preprocessor_skipped_when_config_advertises",
            ),
            pytest.param({}, "directory_path", None, id="empty_directory_returns_none"),
            pytest.param(
                {"config.json": {"vision_config": {}}},
                "pipeline_local",
                LLMModelCapabilities(text=True, image=True),
                id="pipeline_with_local_snapshot",
            ),
            pytest.param({}, "pipeline_remote", None, id="pipeline_with_remote_id_returns_none"),
            pytest.param({}, "pipeline_no_path", None, id="pipeline_without_name_or_path_returns_none"),
            pytest.param({}, "opaque", None, id="object_without_pipeline_attrs_returns_none"),
        ],
    )
    def test_detect_capabilities(
        self,
        files: dict[str, t.Any],
        source_kind: str,
        expected: LLMModelCapabilities | None,
        tmp_path: pathlib.Path,
    ) -> None:
        source = self._build_capability_source(tmp_path, files, source_kind)

        assert TransformersModelSerializer().detect_capabilities(source) == expected

    @pytest.mark.parametrize(
        ["scenario", "expected"],
        [
            pytest.param(
                {"with_tools": "<|tool|>__flama_probe_tool__</|tool|>", "thinking_on": "<think>", "thinking_off": ""},
                (True, True),
                id="tools_and_reasoning_supported",
            ),
            pytest.param(
                {"with_tools": "only-user-text", "thinking_on": "same", "thinking_off": "same"},
                (False, False),
                id="neither_supported",
            ),
            pytest.param(
                {"with_tools": "only-user-text", "thinking_on": "<think>", "thinking_off": ""},
                (False, True),
                id="reasoning_only",
            ),
            pytest.param(
                {"with_tools": "<|tool|>__flama_probe_tool__</|tool|>", "thinking_on": "same", "thinking_off": "same"},
                (True, False),
                id="tools_only",
            ),
            pytest.param(
                {
                    "with_tools": "<|tool|>__flama_probe_tool__</|tool|>",
                    "thinking_on": Exception,
                    "thinking_off": "ignored",
                },
                (True, False),
                id="thinking_call_raises_falls_through_to_false",
            ),
            pytest.param(
                {"with_tools": Exception, "thinking_on": "<think>", "thinking_off": ""},
                (False, True),
                id="tools_call_raises_then_thinking_still_evaluated",
            ),
            pytest.param(None, None, id="tokenizer_fails_to_load"),
            pytest.param("missing_template", None, id="template_missing_returns_none"),
        ],
    )
    def test_probe_with_tokenizer(
        self,
        scenario: dict[str, t.Any] | str | None,
        expected: tuple[bool, bool] | None,
        tmp_path: pathlib.Path,
    ) -> None:
        target = "flama.serialize.model_serializers.transformers.transformers.AutoTokenizer.from_pretrained"
        if scenario is None:
            patcher = patch(target, side_effect=OSError("missing tokenizer"))
        elif scenario == "missing_template":
            tokenizer = MagicMock()
            tokenizer.chat_template = None
            patcher = patch(target, return_value=tokenizer)
        else:
            tokenizer = self._build_probe_tokenizer(**scenario)
            patcher = patch(target, return_value=tokenizer)
        with patcher:
            assert TransformersModelSerializer()._probe_with_tokenizer(tmp_path) == expected

    @pytest.mark.parametrize(
        ["payload", "expected"],
        [
            pytest.param({"chat_template": "plain {{ messages }}"}, (False, False), id="no_markers"),
            pytest.param({"chat_template": "{{ tools }}"}, (True, False), id="tools_jinja_var"),
            pytest.param(
                {"chat_template": "{%- if tools %}call{% endif %}"},
                (True, False),
                id="tools_jinja_if_dash",
            ),
            pytest.param(
                {"chat_template": "{% if tools %}call{% endif %}"},
                (True, False),
                id="tools_jinja_if",
            ),
            pytest.param({"chat_template": "{{ enable_thinking }}"}, (False, True), id="reasoning_enable_thinking"),
            pytest.param(
                {"chat_template": "<think>{{ messages }}</think>"},
                (False, True),
                id="reasoning_think_tag",
            ),
            pytest.param(
                {"chat_template": "{{ message.reasoning_content }}"},
                (False, True),
                id="reasoning_content_field",
            ),
            pytest.param({"chat_template": "{{ tools }} {{ enable_thinking }}"}, (True, True), id="both_supported"),
            pytest.param(
                {"chat_template": "'tools' is great but unused"},
                (False, False),
                id="bare_substring_does_not_trip",
            ),
            pytest.param(
                {
                    "chat_template": [
                        {"name": "default", "template": "{{ tools }}"},
                        {"name": "tool", "template": "{{ enable_thinking }}"},
                    ]
                },
                (True, True),
                id="list_template_merges_blocks",
            ),
            pytest.param(_FILE_MISSING_SENTINEL, (False, False), id="file_missing_returns_false"),
            pytest.param(_INVALID_JSON_SENTINEL, (False, False), id="invalid_json_returns_false"),
        ],
    )
    def test_probe_with_heuristic(
        self,
        payload: dict[str, t.Any] | object,
        expected: tuple[bool, bool],
        tmp_path: pathlib.Path,
    ) -> None:
        target = tmp_path / "tokenizer_config.json"
        if payload is _FILE_MISSING_SENTINEL:
            pass
        elif payload is _INVALID_JSON_SENTINEL:
            target.write_text("not json{")
        else:
            target.write_text(json.dumps(payload))

        assert TransformersModelSerializer._probe_with_heuristic(target) == expected
