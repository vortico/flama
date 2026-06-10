import pathlib

import pytest

import flama

__all__ = ["TEMPLATES_AVAILABLE", "requires_templates"]

_TEMPLATES_DIR = pathlib.Path(flama.__file__).parent / "_templates"

# The private @vortico/ui HTML templates are only built when GCP/Workload Identity credentials are
# available (internal pushes). Credential-less runs (Dependabot PRs, fork PRs, community installs)
# fall back to the public path, which leaves ``flama/_templates`` empty. Detect their presence so
# template-rendering tests skip cleanly instead of failing with a 500 from a missing Jinja template.
TEMPLATES_AVAILABLE = _TEMPLATES_DIR.is_dir() and any(_TEMPLATES_DIR.iterdir())

requires_templates = pytest.mark.skipif(not TEMPLATES_AVAILABLE, reason="Flama HTML templates not bundled.")
