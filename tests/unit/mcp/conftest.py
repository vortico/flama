import pytest

from flama import schemas


@pytest.fixture(autouse=True)
def default_schema_library():
    """Pin the process-global schema library to the default for every MCP test.

    MCP schema generation reads the active :data:`flama.schemas.adapter`, so a library switched by another test on the
    same worker (e.g. via the parametrized ``app`` fixture) would leak in and change the generated JSON Schema shapes.
    Resetting to the default before each test keeps these adapter-dependent assertions deterministic regardless of
    worker ordering.
    """
    schemas._module.setup()
    yield
