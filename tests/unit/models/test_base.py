from flama.models.base import BaseModel


class TestCaseBaseModel:
    def test_predict_is_abstract(self):
        assert getattr(BaseModel.predict, "__isabstractmethod__", False)

    def test_stream_is_abstract(self):
        assert getattr(BaseModel.stream, "__isabstractmethod__", False)
