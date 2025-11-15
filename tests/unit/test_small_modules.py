import importlib


def test_init_module_imports():
    """Ensure sfdump.init imports without side effects."""
    mod = importlib.import_module("sfdump.init")
    assert mod is not None
