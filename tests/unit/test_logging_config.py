import logging

from sfdump.logging_config import configure_logging


def test_configure_logging_levels(caplog):
    # None: keep default WARNING (>=20)
    configure_logging(None)
    logger = logging.getLogger("sfdump.test")
    logger.warning("warn")
    assert any("warn" in rec.message for rec in caplog.records)

    # INFO lowers threshold
    caplog.clear()
    configure_logging(logging.INFO)
    logger.info("info-ok")
    assert any("info-ok" in rec.message for rec in caplog.records)

    # DEBUG includes debug
    caplog.clear()
    configure_logging(logging.DEBUG)
    logger.debug("dbg")
    assert any("dbg" in rec.message for rec in caplog.records)
