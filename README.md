<p align="center">
    <a href="https://flama.dev"><img src="https://raw.githubusercontent.com/vortico/flama/master/.github/logo.png" alt='Flama'></a>
</p>
<p align="center">
    <em>Light up your models</em> &#128293;
</p>
<p align="center">
    <a href="https://github.com/vortico/flama/actions/workflows/ci_production.yaml">
        <img src="https://github.com/vortico/flama/actions/workflows/ci_production.yaml/badge.svg" alt="Production workflow status">
    </a>
    <a href="https://pypi.org/project/flama/">
        <img src="https://img.shields.io/pypi/v/flama?logo=PyPI&logoColor=white" alt="Package version">
    </a>
    <a href="https://pypi.org/project/flama/">
        <img src="https://img.shields.io/pypi/pyversions/flama?logo=Python&logoColor=white" alt="PyPI - Python Version">
    </a>
    <a href="https://pepy.tech/project/flama">
        <img src="https://img.shields.io/pepy/dt/flama?logo=python&logoColor=white&label=downloads" alt="Downloads">
    </a>
    <a href="https://flama.dev/docs/">
        <img src="https://img.shields.io/badge/docs-flama.dev-E25822" alt="Documentation">
    </a>
    <a href="https://github.com/vortico/flama/discussions">
        <img src="https://img.shields.io/github/discussions/vortico/flama?logo=github&logoColor=white" alt="GitHub Discussions">
    </a>
</p>

---

# Flama

**The production framework for Predictive and Generative AI.**

Turn any model into a production API in a single line of code. Serve predictive and
generative models on a Rust-powered core, and expose your tools to AI agents over the
Model Context Protocol (MCP).

Flama is the **F**ramework for **L**ightweight **A**pplications, artificial intelligence
**M**odels, and **A**utomation. It packages a model from any of the mainstream frameworks
into a single portable format (the `.flm` file), so every model looks the same to your API
no matter where it came from, and serves it over HTTP in seconds.

<p align="center">
    <img src="https://raw.githubusercontent.com/vortico/flama/master/.github/assets/chat.gif" alt="The streaming chat UI that ships with every model served by Flama" width="100%">
</p>

- 📦 **Any framework, one format.** Package scikit-learn, TensorFlow, PyTorch, or an LLM into a single portable `.flm` artifact.
- ⬇️ **Models on demand.** Download and package any model from the HuggingFace Hub with one command.
- 🤖 **Generative AI serving.** Serve LLMs with OpenAI-, Anthropic-, and Ollama-compatible endpoints, side by side.
- 💬 **Chatbot out of the box.** Every served model ships a polished streaming chat UI at `/chat/`, with Markdown, LaTeX, and Mermaid.
- 🔌 **Native MCP.** Expose tools, resources, and prompts to AI agents with a single decorator, schemas derived from your type hints.
- ⚡ **Rust-powered core.** Routing, JSON encoding, request parsing, and compression compiled to native code, shipped as plain wheels.
- 🚀 **Production-ready first.** Go from a packaged model to a running service over the CLI, in Python, with a spec file, or inside a container.

## Installation

Flama is published on PyPI and ships native wheels for every supported Python version
(3.10 to 3.14) on Linux, macOS, and Windows. No Rust toolchain required.

```commandline
pip install flama
```

Schema, database, and LLM support are optional extras, so you install only what you need:

```commandline
pip install "flama[pydantic]"      # schema validation (also: typesystem, marshmallow)
pip install "flama[database]"      # SQLAlchemy-backed resources
pip install "flama[llm]"           # generative AI serving (vLLM on Linux, MLX on Apple Silicon)
pip install "flama[full]"          # everything
```

See the [installation docs](https://flama.dev/docs/getting-started/installation/) for details.

## Quickstart: serve an LLM

From zero to a production API with a built-in chat UI in three commands, no Python code
required:

```commandline
pip install "flama[llm,pydantic]"

# 1. Download and package a model from HuggingFace into a portable .flm
flama get --family llm --source huggingface mlx-community/gemma-4-E2B-it-qat-4bit

# 2. Try it straight from your terminal
echo "What is Flama?" | flama model mlx-community_gemma-4-E2B-it-qat-4bit.flm stream --system "Be concise."

# 3. Serve it over HTTP
flama serve --model file=mlx-community_gemma-4-E2B-it-qat-4bit.flm,url=/,name=gemma
```

That is it: a full HTTP API, a streaming chat interface at
[http://127.0.0.1:8000/chat/](http://127.0.0.1:8000/chat/), and multi-dialect endpoints.
The same `.flm` file runs on **vLLM** (Linux with CUDA) or **MLX** (Apple Silicon), with
Flama selecting the backend at load time.

<p align="center">
    <img src="https://raw.githubusercontent.com/vortico/flama/master/.github/assets/serve.gif" alt="A single flama serve command booting a packaged model into a live API" width="100%">
</p>

### Chat from your terminal

You do not even need a server to try a model. Pipe a prompt into `flama model ... stream`
and the response streams straight into your shell:

<p align="center">
    <img src="https://raw.githubusercontent.com/vortico/flama/master/.github/assets/stream.gif" alt="Chatting with a model straight from the terminal using flama model stream" width="100%">
</p>

### Speak the protocols your clients already use

A single model can serve multiple wire protocols simultaneously, so existing OpenAI,
Anthropic, and Ollama clients work without code changes, just point them at your server.

| Dialect   | Prefix       | Representative routes                                                |
|-----------|--------------|----------------------------------------------------------------------|
| Native    | (none)       | `/query/`, `/stream/`, `/chat/`                                      |
| OpenAI    | `/openai`    | `/v1/chat/completions`, `/v1/completions`, `/v1/responses`, `/v1/models` |
| Anthropic | `/anthropic` | `/v1/messages`, `/v1/models`                                        |
| Ollama    | `/ollama`    | `/api/chat`, `/api/generate`, `/api/tags`                           |

Learn more in the [Generative AI docs](https://flama.dev/docs/generative-ai/serving-llms/).

## Quickstart: serve a predictive model

The same workflow serves classic ML models. Package a model trained in any mainstream
framework:

```python
import flama
from sklearn.neural_network import MLPClassifier

model = MLPClassifier(activation="tanh", hidden_layer_sizes=(10,))
# ... training ...
flama.dump(model, "model.flm")
```

Or fetch one straight from the Hub, then serve it:

```commandline
flama get --family ml --source huggingface scikit-learn/Fish-Weight
flama serve --model file=scikit-learn_Fish-Weight.flm,url=/model,name=fish
```

Learn more in the [Predictive AI docs](https://flama.dev/docs/predictive-ai/packaging-models/).

## Expose tools to AI agents with MCP

Flama ships native, first-class support for the Model Context Protocol. Declare a
capability with a single decorator, mount the server, and Flama derives the JSON Schema
from your type hints and serves it over a stateless protocol:

```python
from flama import Flama

app = Flama()
app.mcp.add_server("/mcp/tools/", "tools")


@app.mcp.tool("add", description="Add two integers", mcp="tools")
def add(a: int, b: int) -> int:
    return a + b
```

Any MCP-capable client (Claude, Cursor, VS Code Copilot, or a custom agent) can discover
and invoke it. Tasks, Elicitation, and MCP Apps are included. Learn more in the
[MCP docs](https://flama.dev/docs/generative-ai/model-context-protocol/).

## And a full-featured API framework

Flama is also a complete toolkit for building production APIs:

- **Resources** with standard CRUD methods over SQLAlchemy tables.
- **Dependency injection** via `Component`s, the base of the plugin ecosystem.
- **Adaptable schemas** with Pydantic, Typesystem, or Marshmallow, all optional extras.
- **Auto-generated OpenAPI** schema plus Swagger UI and ReDoc.
- **Pagination**, background tasks, lifespan events, and JWT authentication.
- **Streaming-first HTTP** with Server-Sent Events and NDJSON responses.
- **[Domain-Driven Design](https://flama.dev/docs/domain-driven-design/introduction/)** patterns: repositories, workers, and domain models.
- **`flama upgrade`** codemods that rewrite imports and renamed symbols across major versions.

## Examples

A curated, documentation-aligned set of runnable examples lives in
[vortico/flama-examples](https://github.com/vortico/flama-examples), covering fundamentals,
the CLI, advanced topics, predictive AI, generative AI, and domain-driven design.

## Documentation

Visit [https://flama.dev/docs/](https://flama.dev/docs/) for the full documentation,
including the [quickstart](https://flama.dev/docs/getting-started/quickstart/) and the
[CLI guide](https://flama.dev/docs/flama-cli/serve/).

## Use Flama with your AI assistant

Drop [`skill.md`](https://flama.dev/skill.md) into your AI coding assistant and let it
build Flama apps with full framework knowledge.

## Authors

- José Antonio Perdiguero López ([@perdy](https://github.com/perdy/))
- Miguel Durán-Olivencia ([@migduroli](https://github.com/migduroli/))

## Contributing

This project is absolutely open to contributions, so if you have a nice idea, please read
our [contributing docs](.github/CONTRIBUTING.md) **before submitting** a pull request.
Questions and ideas are welcome in [GitHub Discussions](https://github.com/vortico/flama/discussions).

## Support

If you find Flama useful for building robust Machine Learning and Generative AI APIs, the
best way to support our work is to **give us a ⭐ on GitHub**, it is the best fuel for our
development efforts. You can also follow [Vortico](https://vortico.tech) for updates.

## Star History

<a href="https://github.com/vortico/flama">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=vortico/flama&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=vortico/flama&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=vortico/flama&type=Date" />
  </picture>
</a>

## License

Flama is released under the [Apache 2.0](https://github.com/vortico/flama/blob/master/LICENSE) license.
