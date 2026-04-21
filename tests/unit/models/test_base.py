from unittest.mock import MagicMock

from flama.models.base import BaseLLMModel, BaseMLModel, BaseModel


class TestCaseBaseModel:
    def test_inspect_exists(self):
        assert hasattr(BaseModel, "inspect")
        assert not getattr(BaseModel.inspect, "__isabstractmethod__", False)


class TestCaseBaseMLModel:
    def test_predict_is_abstract(self):
        assert getattr(BaseMLModel.predict, "__isabstractmethod__", False)

    def test_stream_is_abstract(self):
        assert getattr(BaseMLModel.stream, "__isabstractmethod__", False)

    def test_inherits_base_model(self):
        assert issubclass(BaseMLModel, BaseModel)


class TestCaseBaseLLMModel:
    def test_query_is_abstract(self):
        assert getattr(BaseLLMModel.query, "__isabstractmethod__", False)

    def test_stream_is_abstract(self):
        assert getattr(BaseLLMModel.stream, "__isabstractmethod__", False)

    def test_inherits_base_model(self):
        assert issubclass(BaseLLMModel, BaseModel)

    def test_configure(self):
        meta = MagicMock()
        meta.to_dict.return_value = {}

        class ConcreteLLM(BaseLLMModel):
            def query(self, prompt, /, **params):
                return ""

            async def stream(self, prompt, /, **params):
                yield ""

        model = ConcreteLLM(None, meta, None)
        assert model.params == {}

        model.configure({"temperature": 0.7, "max_tokens": 100})
        assert model.params == {"temperature": 0.7, "max_tokens": 100}

        model.configure({"temperature": 0.9})
        assert model.params == {"temperature": 0.9, "max_tokens": 100}
