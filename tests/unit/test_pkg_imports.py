def test_import_package_and_version_smoke():
    import sfdump

    assert isinstance(sfdump.__version__, str)
    import sfdump._version as _ver

    assert _ver is not None
