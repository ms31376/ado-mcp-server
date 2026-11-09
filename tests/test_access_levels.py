import importlib
import sys

import pytest


def load(monkeypatch, level):
    monkeypatch.setenv("ADO_URL", "https://example/Coll")
    monkeypatch.setenv("ADO_PAT", "x")
    monkeypatch.setenv("ADO_ACCESS_LEVEL", level)
    for name in list(sys.modules):
        if name.startswith("ado_mcp"):
            del sys.modules[name]
    importlib.import_module("ado_mcp.server")
    return importlib.import_module("ado_mcp.app").REGISTERED


@pytest.mark.parametrize("level,writes,deletes", [
    ("read", False, False), ("write", True, False), ("full", True, True), ("nonsense", False, False)])
def test_levels(monkeypatch, level, writes, deletes):
    registered = load(monkeypatch, level)
    assert ("update_work_item" in registered) is writes
    assert ("delete_test_case" in registered) is deletes
    assert "search_work_items" in registered
