"""
Logger module for evo-hl-library.

Thin wrapper around Python's stdlib ``logging`` module. Provides colored console
output, optional file rotation, a custom SUCCESS level, and per-module loggers.

Usage::

    from evo_hl.logger import setup_logger, get_logger

    setup_logger()                        # call once at startup
    log = get_logger("MyModule")
    log.info("Hello")
    log.success("Sensor initialized")     # custom level between INFO and WARNING
"""

import logging
import sys
from logging.handlers import TimedRotatingFileHandler

from colorama import Fore, Style

# ---------------------------------------------------------------------------
# Custom SUCCESS level (between INFO=20 and WARNING=30)
# ---------------------------------------------------------------------------

SUCCESS = 25
logging.addLevelName(SUCCESS, "SUCCESS")


def _success(self, message, *args, **kwargs):
    if self.isEnabledFor(SUCCESS):
        self._log(SUCCESS, message, args, **kwargs)


# Attach the convenience method to the Logger class so every logger gets it.
logging.Logger.success = _success

# ---------------------------------------------------------------------------
# Color map
# ---------------------------------------------------------------------------

_LEVEL_COLORS = {
    logging.DEBUG:    Style.DIM + Fore.WHITE,
    logging.INFO:     Fore.BLUE,
    SUCCESS:          Style.BRIGHT + Fore.GREEN,
    logging.WARNING:  Style.BRIGHT + Fore.YELLOW,
    logging.ERROR:    Style.BRIGHT + Fore.RED,
    logging.CRITICAL: Style.DIM + Fore.RED,
}

_LEVEL_LABELS = {
    logging.DEBUG:    "Debug",
    logging.INFO:     "Info",
    SUCCESS:          "Success",
    logging.WARNING:  "Warning",
    logging.ERROR:    "Error",
    logging.CRITICAL: "Fatal",
}

_BRACKET = Style.BRIGHT + Fore.BLACK
_TIME_COLOR = Fore.WHITE
_MODULE_COLOR = Fore.CYAN
_MSG_COLORS = {
    logging.DEBUG:    Style.DIM + Fore.WHITE,
    logging.INFO:     Fore.WHITE,
    SUCCESS:          Fore.GREEN,
    logging.WARNING:  Fore.YELLOW,
    logging.ERROR:    Fore.RED,
    logging.CRITICAL: Style.DIM + Fore.RED,
}

# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

class ColorFormatter(logging.Formatter):
    """Formatter that adds ANSI colors, matching Kolte's visual style."""

    def __init__(self, datefmt: str = "%d-%m-%Y %H:%M:%S"):
        super().__init__(datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        lvl = record.levelno
        label = _LEVEL_LABELS.get(lvl, record.levelname)
        lvl_color = _LEVEL_COLORS.get(lvl, "")
        msg_color = _MSG_COLORS.get(lvl, "")
        timestamp = self.formatTime(record, self.datefmt)

        # Build prefix: [timestamp] [Module] Level: message
        parts = [
            _BRACKET, "[", Style.RESET_ALL,
            _TIME_COLOR, timestamp,
            _BRACKET, "] ", Style.RESET_ALL,
        ]

        if record.name != "evo_hl" and record.name.startswith("evo_hl."):
            module_name = record.name.removeprefix("evo_hl.")
            parts += [
                _BRACKET, "[", Style.RESET_ALL,
                _MODULE_COLOR, module_name,
                _BRACKET, "] ",  Style.RESET_ALL,
            ]

        parts += [
            lvl_color, label, Style.RESET_ALL,
            Style.DIM + Fore.WHITE, ": ", Style.RESET_ALL,
            msg_color,
        ]

        prefix = "".join(parts)
        message = record.getMessage()

        # Multiline support: prefix each line
        if "\n" in message:
            lines = message.split("\n")
            formatted = "\n".join(
                prefix + line + Style.RESET_ALL if line else ""
                for line in lines
            )
        else:
            formatted = prefix + message + Style.RESET_ALL

        # Append exception info if present
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            formatted += "\n" + msg_color + record.exc_text + Style.RESET_ALL

        return formatted


class PlainFormatter(logging.Formatter):
    """Formatter without ANSI codes, for file output."""

    def __init__(self, datefmt: str = "%d-%m-%Y %H:%M:%S"):
        super().__init__(datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        lvl = record.levelno
        label = _LEVEL_LABELS.get(lvl, record.levelname)
        timestamp = self.formatTime(record, self.datefmt)

        parts = [f"[{timestamp}] "]

        if record.name != "evo_hl" and record.name.startswith("evo_hl."):
            module_name = record.name.removeprefix("evo_hl.")
            parts.append(f"[{module_name}] ")

        parts.append(f"{label}: ")

        prefix = "".join(parts)
        message = record.getMessage()

        if "\n" in message:
            lines = message.split("\n")
            formatted = "\n".join(
                prefix + line if line else ""
                for line in lines
            )
        else:
            formatted = prefix + message

        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            formatted += "\n" + record.exc_text

        return formatted


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_root_logger_name = "evo_hl"


def setup_logger(
    level: int = logging.DEBUG,
    console: bool = True,
    log_file: str | None = None,
    rotation_when: str = "midnight",
    rotation_interval: int = 1,
    rotation_backup_count: int = 30,
    datefmt: str = "%d-%m-%Y %H:%M:%S",
) -> logging.Logger:
    """
    Configure the root ``evo_hl`` logger. Call once at application startup.

    Args:
        level: Minimum log level.
        console: Whether to add a console (stderr) handler.
        log_file: Path to a log file. If set, adds a rotating file handler.
        rotation_when: Rotation interval unit ('S', 'M', 'H', 'D', 'midnight').
        rotation_interval: Number of units between rotations.
        rotation_backup_count: How many rotated files to keep.
        datefmt: strftime format for timestamps.

    Returns:
        The configured root logger.
    """
    logger = logging.getLogger(_root_logger_name)
    logger.setLevel(level)

    # Avoid adding duplicate handlers on repeated calls
    logger.handlers.clear()

    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(ColorFormatter(datefmt=datefmt))
        logger.addHandler(console_handler)

    if log_file:
        file_handler = TimedRotatingFileHandler(
            filename=log_file,
            when=rotation_when,
            interval=rotation_interval,
            backupCount=rotation_backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(PlainFormatter(datefmt=datefmt))
        logger.addHandler(file_handler)

    return logger


def get_logger(module_name: str) -> logging.Logger:
    """
    Get a child logger for a specific module.

    Args:
        module_name: Name of the module (e.g. "AX12", "PCA9685").

    Returns:
        A ``logging.Logger`` instance with a ``.success()`` method.
    """
    return logging.getLogger(f"{_root_logger_name}.{module_name}")


def setup_excepthook(logger: logging.Logger | None = None) -> None:
    """
    Install a ``sys.excepthook`` that logs uncaught exceptions as CRITICAL.

    This is opt-in: call it explicitly after ``setup_logger()``.
    No stdout/stderr replacement — only uncaught exceptions are captured.
    """
    log = logger or logging.getLogger(_root_logger_name)

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            # Let Ctrl+C behave normally
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        log.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))

    sys.excepthook = _hook
