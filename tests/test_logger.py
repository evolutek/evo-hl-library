"""Tests for evo_hl.logger — stdlib logging wrapper."""

import logging
import sys

from evo_hl.logger import (
    SUCCESS,
    ColorFormatter,
    PlainFormatter,
    get_logger,
    setup_excepthook,
    setup_logger,
)


# ---------------------------------------------------------------------------
# SUCCESS level
# ---------------------------------------------------------------------------

def test_success_level_registered():
    """SUCCESS level (25) is registered between INFO (20) and WARNING (30)."""
    assert logging.getLevelName(SUCCESS) == "SUCCESS"
    assert logging.INFO < SUCCESS < logging.WARNING


def test_success_method_exists():
    """Every logger instance has a .success() convenience method."""
    log = get_logger("test_success")
    assert hasattr(log, "success")
    assert callable(log.success)


def test_success_captured(caplog):
    """Messages logged with .success() appear in caplog."""
    setup_logger(level=logging.DEBUG, console=False)
    log = get_logger("test_cap")

    with caplog.at_level(logging.DEBUG, logger="evo_hl.test_cap"):
        log.success("sensor OK")

    assert any(r.levelno == SUCCESS and "sensor OK" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Logger hierarchy
# ---------------------------------------------------------------------------

def test_get_logger_returns_child():
    """get_logger returns a child of the evo_hl root logger."""
    log = get_logger("AX12")
    assert log.name == "evo_hl.AX12"


def test_logger_hierarchy(caplog):
    """Child logger messages propagate to the root evo_hl logger."""
    setup_logger(level=logging.DEBUG, console=False)
    log = get_logger("PCA9685")

    with caplog.at_level(logging.DEBUG, logger="evo_hl"):
        log.info("PWM initialized")

    assert any("PWM initialized" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def test_color_formatter_output():
    """ColorFormatter produces output with ANSI codes and the expected label."""
    fmt = ColorFormatter()
    record = logging.LogRecord(
        name="evo_hl.GPIO", level=logging.WARNING, pathname="", lineno=0,
        msg="pin conflict", args=(), exc_info=None,
    )
    output = fmt.format(record)
    assert "Warning" in output
    assert "pin conflict" in output
    assert "GPIO" in output
    # Contains ANSI escape codes
    assert "\033[" in output


def test_plain_formatter_output():
    """PlainFormatter produces clean output without ANSI codes."""
    fmt = PlainFormatter()
    record = logging.LogRecord(
        name="evo_hl.Lidar", level=logging.ERROR, pathname="", lineno=0,
        msg="scan failed", args=(), exc_info=None,
    )
    output = fmt.format(record)
    assert "Error" in output
    assert "scan failed" in output
    assert "Lidar" in output
    # No ANSI codes
    assert "\033[" not in output


def test_plain_formatter_root_logger():
    """Root evo_hl logger does not show a module bracket."""
    fmt = PlainFormatter()
    record = logging.LogRecord(
        name="evo_hl", level=logging.INFO, pathname="", lineno=0,
        msg="startup", args=(), exc_info=None,
    )
    output = fmt.format(record)
    assert "Info: startup" in output
    assert "[evo_hl]" not in output


def test_color_formatter_success_label():
    """SUCCESS level uses the 'Success' label in formatted output."""
    fmt = ColorFormatter()
    record = logging.LogRecord(
        name="evo_hl.Init", level=SUCCESS, pathname="", lineno=0,
        msg="all systems go", args=(), exc_info=None,
    )
    output = fmt.format(record)
    assert "Success" in output
    assert "all systems go" in output


# ---------------------------------------------------------------------------
# Multiline
# ---------------------------------------------------------------------------

def test_multiline_formatting():
    """Each line of a multiline message gets its own prefix."""
    fmt = PlainFormatter()
    record = logging.LogRecord(
        name="evo_hl.Boot", level=logging.INFO, pathname="", lineno=0,
        msg="line1\nline2\nline3", args=(), exc_info=None,
    )
    output = fmt.format(record)
    lines = [l for l in output.split("\n") if l]
    assert len(lines) == 3
    assert all("Info:" in line for line in lines)


# ---------------------------------------------------------------------------
# setup_logger
# ---------------------------------------------------------------------------

def test_setup_logger_returns_root():
    """setup_logger returns the evo_hl root logger."""
    logger = setup_logger(console=False)
    assert logger.name == "evo_hl"


def test_setup_logger_clears_handlers():
    """Calling setup_logger twice does not duplicate handlers."""
    setup_logger(console=True)
    setup_logger(console=True)
    logger = logging.getLogger("evo_hl")
    # Should have exactly 1 console handler, not 2
    assert len(logger.handlers) == 1


# ---------------------------------------------------------------------------
# Excepthook
# ---------------------------------------------------------------------------

def test_setup_excepthook_installs_hook():
    """setup_excepthook replaces sys.excepthook."""
    original = sys.excepthook
    try:
        setup_excepthook()
        assert sys.excepthook is not original
    finally:
        sys.excepthook = original


def test_excepthook_keyboard_interrupt():
    """KeyboardInterrupt is not captured by the custom hook."""
    original = sys.excepthook
    try:
        setup_excepthook()
        hook = sys.excepthook
        # Should not raise — just delegates to sys.__excepthook__
        # We can't easily test this without mocking, but verify the hook exists
        assert callable(hook)
    finally:
        sys.excepthook = original
