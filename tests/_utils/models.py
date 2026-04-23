import tempfile
import typing as t
import warnings

from tests._utils.importlib import NotInstalled, installed

__all__ = ["model_factory"]

try:
    import numpy as np
except Exception:
    warnings.warn("Numpy not installed")
    np = None

try:
    import sklearn.compose
    import sklearn.impute
    import sklearn.neural_network
    import sklearn.pipeline
except Exception:
    warnings.warn("SKLearn not installed")
    sklearn = None

try:
    import tensorflow as tf
except Exception:
    warnings.warn("Tensorflow not installed")
    tf = None

try:
    import torch
except Exception:
    warnings.warn("Torch not installed")
    torch = None

try:
    import transformers
except Exception:
    warnings.warn("Transformers not installed")
    transformers = None

try:
    import huggingface_hub
except Exception:
    warnings.warn("huggingface_hub not installed")
    huggingface_hub = None


class ModelFactory:
    def __init__(self):
        self._libs = {
            "sklearn": ("sklearn", ["sklearn", "numpy"], self._sklearn),
            "sklearn-pipeline": ("sklearn", ["sklearn", "numpy"], self._sklearn_pipeline),
            "tensorflow": ("tensorflow", ["tensorflow", "numpy"], self._tensorflow),
            "torch": ("torch", ["torch", "numpy"], self._torch),
            "transformers": ("transformers", ["transformers"], self._transformers),
            "vllm": ("vllm", ["huggingface_hub", "vllm"], self._vllm),
        }

        self._models = {}
        self._models_cls = {}
        self._artifacts = {}
        self._tmpdirs: list[tempfile.TemporaryDirectory] = []

    def _build(self, x: str, /):
        try:
            _, dependencies, factory = self._libs[x]

            for dependency in dependencies:
                if not installed(dependency):
                    raise NotInstalled(dependency)
        except KeyError:
            raise ValueError(f"Wrong lib: '{x}'.")

        if x not in self._models:
            result = factory()
            self._models[x], self._models_cls[x] = result[0], result[1]
            self._artifacts[x] = result[2] if len(result) > 2 else None

    def lib(self, lib: str):
        self._build(lib)
        return self._libs[lib][0]

    def model(self, lib: str):
        self._build(lib)
        return self._models[lib]

    def model_cls(self, lib: str):
        self._build(lib)
        return self._models_cls[lib]

    def artifacts(self, lib: str):
        self._build(lib)
        return self._artifacts.get(lib)

    def config(self, lib: str) -> dict[str, t.Any] | None:
        self._build(lib)
        configs: dict[str, dict[str, t.Any]] = {
            "transformers": {"task": "text-generation", "framework": "pt"},
            "vllm": {"engine_params": {"max_model_len": 256}},
        }
        return configs.get(lib)

    def _sklearn(self):
        model = sklearn.neural_network.MLPClassifier(
            activation="tanh",
            max_iter=2000,
            hidden_layer_sizes=(10,),
            random_state=42,
            solver="adam",
        )
        model.fit(
            np.array([[0, 0], [0, 1], [1, 0], [1, 1]]),
            np.array([0, 1, 1, 0]),
        )
        return model, sklearn.neural_network.MLPClassifier

    def _sklearn_pipeline(self):
        model = sklearn.neural_network.MLPClassifier(
            activation="tanh",
            max_iter=2000,
            hidden_layer_sizes=(10,),
            random_state=42,
            solver="adam",
        )
        numerical_transformer = sklearn.pipeline.Pipeline(
            [
                ("imputer", sklearn.impute.SimpleImputer(strategy="constant", fill_value=0)),
            ]
        )
        preprocess = sklearn.compose.ColumnTransformer(
            [
                ("numerical", numerical_transformer, [0, 1]),
            ]
        )
        pipeline = sklearn.pipeline.Pipeline(
            [
                ("preprocess", preprocess),
                ("model", model),
            ]
        )

        pipeline.fit(
            np.array([[0, np.nan], [np.nan, 1], [1, 0], [1, 1]]),  # NaN will be replaced with 0
            np.array([0, 1, 1, 0]),
        )

        return pipeline, sklearn.pipeline.Pipeline

    def _tensorflow(self):
        tf.random.set_seed(42)

        model = tf.keras.models.Sequential(
            [
                tf.keras.Input((2,)),
                tf.keras.layers.Dense(10, activation="tanh"),
                tf.keras.layers.Dense(1, activation="sigmoid"),
            ]
        )

        model.compile(optimizer="adam", loss="binary_crossentropy")
        model.fit(
            np.array([[0, 0], [0, 1], [1, 0], [1, 1]]),
            np.array([[0], [1], [1], [0]]),
            epochs=1000,
            verbose=0,
        )

        return model, tf.keras.models.Sequential

    def _torch(self):
        class Model(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.l1 = torch.nn.Linear(2, 10)
                self.l2 = torch.nn.Linear(10, 1)

            def forward(self, x):
                x = torch.tanh(self.l1(x))
                x = torch.sigmoid(self.l2(x))
                return x

            def _train(self, X, Y, loss, optimizer):
                # Reset weights for consistent training start
                for m in self.modules():
                    if isinstance(m, torch.nn.Linear):
                        torch.nn.init.xavier_normal_(m.weight.data)
                        if m.bias is not None:
                            torch.nn.init.constant_(m.bias.data, 0)

                for _ in range(2000):
                    optimizer.zero_grad()
                    y_hat = self(X)  # Pass the entire 4-point batch
                    loss_result = loss(y_hat, Y)
                    loss_result.backward()
                    optimizer.step()

                return self

        X = torch.Tensor([[0, 0], [0, 1], [1, 0], [1, 1]])
        Y = torch.Tensor([0, 1, 1, 0]).view(-1, 1)
        model = Model()
        model._train(X, Y, loss=torch.nn.BCELoss(), optimizer=torch.optim.Adam(model.parameters()))

        return model, torch.nn.Module

    def _transformers(self):
        directory = tempfile.TemporaryDirectory()
        self._tmpdirs.append(directory)
        transformers.pipeline("text-generation", model="hf-internal-testing/tiny-random-gpt2").save_pretrained(
            directory.name
        )

        return directory.name, transformers.pipelines.base.Pipeline

    def _vllm(self):
        return huggingface_hub.snapshot_download(repo_id="facebook/opt-125m"), object


model_factory = ModelFactory()
