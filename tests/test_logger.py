import sys

from evo_lib.logger import Logger, LoggerConsoleSink, LoggerLevel, LoggerSink


def _get_test_sink() -> LoggerSink:
    return LoggerConsoleSink(sys.stdout, sys.stderr)


def test_logger_levels(capsys):
    logger = Logger("Robot")
    logger.add_sink(_get_test_sink())
    logger.debug("dbg msg")
    logger.info("info msg")
    logger.success("success msg")
    logger.warning("warn msg")
    logger.error("err msg")
    logger.critical("fatal msg")
    captured = capsys.readouterr()
    assert "dbg msg" in captured.out
    assert "info msg" in captured.out
    assert "success msg" in captured.out
    assert "warn msg" in captured.out
    assert "err msg" in captured.err
    assert "fatal msg" in captured.err


def test_multiline(capsys):
    logger = Logger("Robot")
    logger.add_sink(_get_test_sink())
    logger.info("line1\nline2\nline3")
    captured = capsys.readouterr()
    assert "line1" in captured.out
    assert "line2" in captured.out
    assert "line3" in captured.out


def test_sublogger(capsys):
    logger = Logger("Robot")
    logger.add_sink(_get_test_sink())
    sublogger = logger.get_sublogger("MyModule")
    sublogger.info("hello from a sublogger")
    captured = capsys.readouterr()
    assert "hello from a sublogger" in captured.out
    assert "MyModule" in captured.out


def test_set_level(capsys):
    logger = Logger("Robot")
    logger.add_sink(_get_test_sink())
    logger.set_level(LoggerLevel.WARNING)
    logger.debug("should not appear")
    logger.info("should not appear")
    logger.success("should not appear")
    logger.warning("visible warning")
    logger.error("visible error")
    captured = capsys.readouterr()
    assert "should not appear" not in captured.out
    assert "should not appear" not in captured.err
    assert "visible warning" in captured.out
    assert "visible error" in captured.err
