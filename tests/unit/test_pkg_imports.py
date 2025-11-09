def test_import_package_and_version_smoke():
    import sfdump

    # __version__ should be a string (may be dynamic via setuptools_scm)
    assert isinstance(sfdump.__version__, str)
    # importing _version shouldn't crash; attributes may vary
    import sfdump._version as _ver

    # tolerate missing attributes in some envs; just ensure module loads
    assert _ver is not None
