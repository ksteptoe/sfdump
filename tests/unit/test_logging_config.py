import logging

from sfdump.logging_config import configure_logging


def test_configure_logging_none_ok():
    # should not crash and should return a logger configured
    configure_logging(None)
    assert logging.getLogger().getEffectiveLevel() in (logging.WARNING, logging.INFO, logging.DEBUG)


def test_configure_logging_info():
    configure_logging(logging.INFO)
    assert logging.getLogger().getEffectiveLevel() == logging.INFO
