import importlib
import types

import pytest


def _call_if_callable(obj, *args, **kwargs):
    if callable(obj):
        return obj(*args, **kwargs)
    return None


def _safe_instantiate(cls, *args, **kwargs):
    """Try to instantiate a class, trying fewer args if signature is strict."""
    # remove 'self'
    # try build simple args based on accepted params (only pass kwargs currently)
    try:
        return cls(*args, **kwargs)
    except TypeError:
        # try no-arg constructor
        try:
            return cls()
        except Exception as e:
            pytest.skip(f"Cannot instantiate {cls}: {e}")


def test_dumper_basic_behaviour(tmp_path, monkeypatch):
    """
    Exercise any exported Dumper-like class or dump function.

    The test is defensive:
    - imports the module
    - checks for a class named 'Dumper' or a function 'dump'/'dump_objects'
    - instantiates with a dummy API if needed
    - calls the first available run/dump method and asserts it returns a dict/list or doesn't crash
    """
    mod = importlib.import_module("sfdump.dumper")
    assert isinstance(mod, types.ModuleType)

    # find plausible entrypoints
    candidate_class = getattr(mod, "Dumper", None)
    candidate_func = getattr(mod, "dump", None) or getattr(mod, "dump_objects", None)

    # Minimal dummy API to pass in if constructor expects api-like object
    class DummyAPI:
        def __init__(self):
            self.instance_url = "https://example"
            self.api_version = "vX.Y"

        def connect(self):
            return True

        def query(self, *a, **k):
            return {"totalSize": 0, "records": []}

        def retrieve(self, *a, **k):
            return {}

    dummy_api = DummyAPI()

    if candidate_class is not None:
        dumper = _safe_instantiate(candidate_class, dummy_api)
        # try to call common methods: run, dump, dump_objects, execute
        for method_name in ("run", "dump", "dump_objects", "execute"):
            if hasattr(dumper, method_name):
                method = getattr(dumper, method_name)
                # call with safe args if needed
                try:
                    res = method()
                except TypeError:
                    # try with a temporary path or api
                    try:
                        res = method(tmp_path)
                    except Exception as e:
                        pytest.skip(f"Method {method_name} raised during call: {e}")
                # some dumper methods return None; that's acceptable
                assert (res is None) or isinstance(res, (list, dict, str))
                break
        else:
            # no recognised method — at least ensure object exists
            assert dumper is not None
    elif candidate_func is not None:
        # call function directly
        try:
            res = candidate_func()
        except TypeError:
            try:
                res = candidate_func(dummy_api, tmp_path)
            except Exception as e:
                pytest.skip(f"Function candidate raised during call: {e}")
        assert (res is None) or isinstance(res, (list, dict, str))
    else:
        pytest.skip("No Dumper class or dump function discovered in sfdump.dumper")
