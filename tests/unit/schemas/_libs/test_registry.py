from flama.schemas._libs.marshmallow.schemas import SCHEMAS as MARSHMALLOW_SCHEMAS
from flama.schemas._libs.marshmallow.schemas.core import SCHEMAS as MARSHMALLOW_CORE
from flama.schemas._libs.pydantic.schemas import SCHEMAS as PYDANTIC_SCHEMAS
from flama.schemas._libs.pydantic.schemas.core import SCHEMAS as PYDANTIC_CORE
from flama.schemas._libs.typesystem.schemas import SCHEMAS as TYPESYSTEM_SCHEMAS
from flama.schemas._libs.typesystem.schemas.core import SCHEMAS as TYPESYSTEM_CORE


class TestCasePydanticSchemasRegistryAssembly:
    def test_singleton_is_shared_with_core(self):
        assert PYDANTIC_SCHEMAS is PYDANTIC_CORE

    def test_registry_contains_classes(self):
        for name in (
            "flama.core.APIError",
            "flama.core.DropCollection",
            "flama.pagination.LimitOffset",
            "flama.ml.PredictInput",
            "flama.llm_native.Message",
            "flama.llm_openai.ChatCompletionsInput",
            "flama.llm_ollama.ChatInput",
        ):
            assert name in PYDANTIC_SCHEMAS


class TestCaseMarshmallowSchemasRegistryAssembly:
    def test_singleton_is_shared_with_core(self):
        assert MARSHMALLOW_SCHEMAS is MARSHMALLOW_CORE

    def test_registry_contains_classes(self):
        for name in (
            "flama.core.APIError",
            "flama.core.DropCollection",
            "flama.pagination.LimitOffset",
            "flama.ml.PredictInput",
            "flama.llm_native.Message",
            "flama.llm_openai.ChatCompletionsInput",
            "flama.llm_ollama.ChatInput",
        ):
            assert name in MARSHMALLOW_SCHEMAS


class TestCaseTypesystemSchemasRegistryAssembly:
    def test_singleton_is_shared_with_core(self):
        assert TYPESYSTEM_SCHEMAS is TYPESYSTEM_CORE

    def test_registry_contains_classes(self):
        for name in (
            "flama.core.APIError",
            "flama.core.DropCollection",
            "flama.pagination.LimitOffset",
            "flama.ml.PredictInput",
            "flama.llm_native.Message",
            "flama.llm_openai.ChatCompletionsInput",
            "flama.llm_ollama.ChatInput",
        ):
            assert name in TYPESYSTEM_SCHEMAS
