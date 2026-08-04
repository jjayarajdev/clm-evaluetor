"""Import every module under app/ — no syntax error may hide behind a lazy import.

Regression guard for the governance-bridge outage: a SyntaxError introduced in
a refactor lived in app/services/governance_bridge.py for weeks because the
module is only imported lazily inside a pipeline stage whose failure is
swallowed per contract. The app booted, all tests passed, and every upload
silently lost its org/relationship auto-creation. Importing everything at test
time makes that class of bug fail loudly.
"""

import importlib
import pkgutil

import pytest

import app


def _walk(package):
    for module_info in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        yield module_info.name


MODULES = sorted(_walk(app))


@pytest.mark.parametrize("module_name", MODULES)
def test_module_imports(module_name):
    importlib.import_module(module_name)
