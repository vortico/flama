"""Flama 2.0 example: model serialization (protocol v2) and serving.

Demonstrates the 2.0 ``.flm`` serialization protocol v2: a multi-artifact container with a typed metadata header,
explicit model ``family``, per-archive compression, side-artifact bundling, and cheap header-only introspection
(``flama.manifest`` / ``flama.meta``). The packaged model is then served through ``app.models``.

Run it:
    flama run examples.2_0.serialization:app
"""

import json
import pathlib
import tempfile

import numpy as np
import sklearn.linear_model

import flama
from flama import Flama

_X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
_y = np.array([0, 0, 0, 1])  # AND gate
_model = sklearn.linear_model.LogisticRegression().fit(_X, _y)

# Protocol v2 packs several artifacts into one container; bundle a side file alongside the model.
_workdir = pathlib.Path(tempfile.mkdtemp(prefix="flama2_serialization_"))
_labels = _workdir / "labels.json"
_labels.write_text(json.dumps({"0": "false", "1": "true"}))

MODEL_PATH = _workdir / "and_model.flm"
flama.dump(
    _model,
    path=MODEL_PATH,
    family="ml",
    compression="zstd",
    model_id="and-classifier",
    params={"penalty": "l2"},
    metrics={"train_accuracy": 1.0},
    extra={"task": "AND gate"},
    artifacts={"labels.json": _labels},
)

app = Flama(
    openapi={
        "info": {
            "title": "Flama 2.0 - Serialization",
            "version": "2.0.0",
            "description": ".flm protocol v2 packaging and serving",
        }
    },
)

app.models.add_model(path="/model", model=str(MODEL_PATH), name="and-classifier")


@app.route("/introspect/", name="introspect")
def introspect():
    """Cheap header-only introspection of the packaged model: manifest + metadata, no model load."""
    return {
        "manifest": list(flama.manifest(path=str(MODEL_PATH))),
        "meta": flama.meta(path=str(MODEL_PATH)).to_dict(),
    }


if __name__ == "__main__":
    flama.run(flama_app=app, server_host="0.0.0.0", server_port=8080)
