from evo_hl.logger import Logger, LoggerSink, LoggerConsoleSink
import sys


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
      logger.fatal("fatal msg")
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
