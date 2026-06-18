# Contributing

Thanks a lot for your interest in keeping alive the flame 🔥. We are very happy to integrate improvements suggested
and/or developed by GitHub's community. Please, have a look at the information below **before starting with your
development or request**.

## Contribution procedure

⚠️ **Please ask first before you start working on any significant new feature.**

The steps are quite standard in the GitHub community:

1. Submit an issue describing your proposed change or improvement to
   the [issue tracker](https://github.com/vortico/flama/issues) of this project.
2. Before submitting the issue where the new change is explained, please make sure this change is not being already
   developed (or listed). You can always ask team members in case of doubt.
3. Coordinate with team members that are listed on the issue in question. This will remove any potential redundancy,
   besides allowing for a better planning which should result in better code.
4. If your proposed change is accepted, fork the repo, develop and test your code changes. Ensure that your code has an
   appropriate set of unit tests which all pass. This is quite important to us, so please
   make your maximum effort in writing a 100% unit-tested code.
5. Submit a well documented pull request linked to the issue being addressed.

It's never a fun experience to have your pull request declined after investing a lot of time and effort into a new
feature, which is why we encourage you to follow the procedure depicted above as closely as possible.

## Development setup

To set up a local development environment, run:

```commandline
make install
```

This installs the Python dependencies, builds the Rust extension, and fetches the prebuilt frontend templates
(the debug pages, schema docs, and chatbot UI) from the latest published release. This is all you need to contribute
to Flama.

Building those templates from source is restricted to the core team, as it depends on a private package registry.
If you are a core team member with registry access, build them from source instead with:

```commandline
make install-from-source
```

## Coding standards

Our code formatting rules are implicitly defined by using multiple tools. You can check your code against these
standards by running:

### Code formatting

Flama uses Ruff for formatting the code ([PEP 8](https://peps.python.org/pep-0008/) compliant):

```commandline
make format
```

### Code quality checking

Ruff is used to determine if the code quality is high enough as required to be accepted:

```commandline
make lint
```

### Static type checking

Flama is completely static typed. To make sure your code fulfils this constraint, you can check it using pyright:

```commandline
make typecheck
```

This will automatically fix any style violations in your code.

## Running tests

You can run the test suite using the following commands:

```commandline
make test
```

Remember, for any pull request to be accepted, we need to know that all tests are being passed.
So, please ensure that all tests are passing when submitting a pull request.
Last, but not least, if you're adding new features to Flama, you need to include the tests required.

## Supporting a new Python version

When a new CPython (e.g. `3.X`) is released, **nothing happens automatically** — existing wheels keep
targeting the versions they were built for, and support for the new one is opt-in.

Flama's native extension (`flama._core`) is built against different Python versions, so every supported
Python needs its own wheel. The supported versions live in a **single source of truth**,
`.github/workflows/_python-versions.yaml`: every workflow (checks, tests, wheel builds, Docker matrices and
the default version) reads them from there. The wheel build derives its interpreter flags (`-i`) from that
list, so a version that is declared but unavailable makes the release **fail loudly** instead of silently
shipping fewer wheels.

### Prerequisites (upstream, must land before you start)

1. **PyO3 supports `3.X`.** A new CPython often needs a newer PyO3 — bump `pyo3` in `lib/core/Cargo.toml`
   if the build fails to compile against it.
2. **The manylinux/musllinux image ships `cp3X`.** Linux wheels build inside that container, so the
   interpreter must exist there. If the `auto` default lags behind, bump the `PyO3/maturin-action` pin
   (preferred) or set the `container:` input in `.github/workflows/ci_production.yaml`.
3. **`actions/setup-python` lists `3.X`** (used for macOS/Windows). Usually available within days of release.

Until each of these is ready, the corresponding step fails loudly — which is the intended safety net.

### Checklist

- **`.github/workflows/_python-versions.yaml`**: add (or remove) `3.X` in the `versions` array. This is the
  only CI edit needed — all workflow matrices and the default version are derived from it.
- **`pyproject.toml`**
  - Raise the `requires-python` upper bound.
  - Add the `Programming Language :: Python :: 3.X` classifier.
  - Raise the upper bounds in `[tool.uv]` `environments`.
  - Revisit dependency markers flagged with `# PORT:` and the ML extras gated on `python_version < '…'`
    (e.g. `vllm`, `mlx*`, `torch`, `tensorflow`) — extend them once those projects publish `3.X` wheels.

Dropping a version is the reverse of the same checklist.
