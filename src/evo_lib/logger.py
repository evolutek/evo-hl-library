"""
Logger module for Evo-HL library.

This module provides a flexible logging system with support for multiple sinks (console, file),
log rotation, colors, and module-specific logging contexts.
"""

import sys
import os
from datetime import datetime, timedelta
import re
from abc import ABC, abstractmethod
import logging
import logging.handlers
from enum import Enum
from typing import TextIO

# Here colorama is used to get a list of ANSI colors code
from colorama import Fore, Style


# Here colorama is used to passively enable color support on Windows terminals
if sys.platform == "win32":
    from colorama import just_fix_windows_console
    just_fix_windows_console()


# Custom level number INFO is 20
class LoggerLevel(Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    SUCCESS = logging.INFO + 1
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


def _are_ansi_color_supported():
    plat = sys.platform
    supported_platform = plat != 'Pocket PC'
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform and is_a_tty


class _CustomWriteIO:
    """Internal class to redirect stdout/stderr to the logger."""
    def __init__(self, write_func):
        self.write_func = write_func

    def write(self, data):
        """Write data to the logger."""
        self.write_func(data)
        return len(data)

    def flush(self):
        """Flush the stream (no-op)."""
        pass


# Keep original sys.stdout and sys.stderr
_base_stdout = sys.stdout
_base_stderr = sys.stderr


ANSI_SEQUENCE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
def _remove_ansi_codes(sentence: str):
    return ANSI_SEQUENCE_RE.sub('', sentence)


COLORED_MODULE_FMT = Style.BRIGHT + Fore.BLACK + "[" + Style.RESET_ALL + Fore.CYAN + "%s" + Style.BRIGHT + Fore.BLACK + "] "

_COMMON_PREFIX = Style.BRIGHT + Fore.BLACK + "[" + Style.RESET_ALL + Fore.WHITE + "%s" + Style.BRIGHT + Fore.BLACK + "] %s" + Style.RESET_ALL
COLORED_PREFIXES_FMT = {
    LoggerLevel.DEBUG.value: (_COMMON_PREFIX + Fore.BLACK + "Debug" + Style.DIM + Fore.WHITE + ": " + Style.RESET_ALL + Style.DIM + Fore.WHITE),
    LoggerLevel.INFO.value: (_COMMON_PREFIX + Fore.BLUE + "Info" + Style.DIM + Fore.WHITE + ": " + Style.RESET_ALL + Fore.WHITE),
    LoggerLevel.SUCCESS.value: (_COMMON_PREFIX + Style.BRIGHT + Fore.GREEN + "Success" + Style.RESET_ALL + Style.DIM + Fore.WHITE + ": " + Style.RESET_ALL + Fore.GREEN),
    LoggerLevel.WARNING.value: (_COMMON_PREFIX + Style.BRIGHT + Fore.YELLOW + "Warning" + Style.RESET_ALL + Style.DIM + Fore.WHITE + ": " + Style.RESET_ALL + Fore.YELLOW),
    LoggerLevel.ERROR.value: (_COMMON_PREFIX + Style.BRIGHT + Fore.RED + "Error" + Style.RESET_ALL + Style.DIM + Fore.WHITE + ": " + Style.RESET_ALL + Fore.RED),
    LoggerLevel.CRITICAL.value: (_COMMON_PREFIX + Style.BRIGHT + Style.DIM + Fore.RED + "Fatal" + Style.RESET_ALL + Style.DIM + Fore.WHITE + ": " + Style.DIM + Fore.RED),
}

# Pre-calculate plain styles
PLAIN_PREFIXES_FMT = {k: _remove_ansi_codes(v) for k, v in COLORED_PREFIXES_FMT.items()}
PLAIN_MODULE_FMT = _remove_ansi_codes(COLORED_MODULE_FMT)


_default_logger: Logger = None


class LoggerFormater(logging.Formatter):
    """
    Handles formatting of log messages.

    Manages timestamps, prefixes, module names, and indentation for multiline logs.
    """
    def __init__(self, colored: bool = False):
        super().__init__()
        self._strftime_format: str = "%d-%m-%Y %H:%M:%S"
        self._colored: bool = colored
        self._next_reset_color: bool = False

    def is_colored(self) -> bool:
        return self._colored

    def set_colored(self, colored: bool) -> None:
        if not colored:
            self._next_reset_color = True
        self._colored = colored

    def set_time_format(self, format: str) -> None:
        """Set the format string for timestamps (strftime format)."""
        self._strftime_format = format

    def format(self, record: logging.LogRecord) -> str:
        # Determine prefix and formatting based on level and color settings
        prefixes_fmt = COLORED_PREFIXES_FMT if self._colored else PLAIN_PREFIXES_FMT
        module_fmt = COLORED_MODULE_FMT if self._colored else PLAIN_MODULE_FMT

        # Get the format string for the current level (default to INFO if unknown)
        prefix_fmt = prefixes_fmt.get(record.levelno, prefixes_fmt[logging.INFO])

        # Format time part of the prefix
        strtime = datetime.fromtimestamp(record.created).strftime(self._strftime_format)

        # Format module part of the prefix
        module_name = record.name
        module_str = (module_fmt % module_name) if module_name else ""

        # Format prefix
        prefix = prefix_fmt % (strtime, module_str)

        # Add prefix in front of every non empty line
        lines = record.getMessage().split('\n')
        for i, line in enumerate(lines):
            line = line.rstrip()
            if line:
                line = prefix + line
            lines[i] = line

        output = '\n'.join(lines)

        if self._next_reset_color:
            self._next_reset_color = False
            output = Style.RESET_ALL + output

        return output


class LoggerSink(ABC):
    """
    Abstract base class for log sinks.
    """
    @abstractmethod
    def get_handler() -> logging.Handler:
        ...

    @abstractmethod
    def close(self) -> None:
        ...


class _LoggingFileHandler(logging.handlers.TimedRotatingFileHandler):
    def __init__(self, folder: str, latest_filename: str, filename_format: str, interval: int):
        super().__init__(self, latest_filename, "s", interval)

        # Add possibility to enable/disable rotation
        self._rotation_enable: bool = False

        # Settings reative to files name
        self._rotation_filename_format = filename_format # %i is a counter to avoid two files with the same name
        self._rotation_folder = folder

        # See: https://docs.python.org/3/library/logging.handlers.html#logging.handlers.BaseRotatingHandler.namer
        self.namer = self._get_next_rotation_filename

    # Override the super shouldRollover to disable rotation if needed
    def shouldRollover(self, record: logging.LogRecord) -> bool:
        if not self._rotation_enable:
            return False
        return super().shouldRollover(record)

    def set_rotation_enable(self, enable: bool) -> None:
        self._rotation_enable = enable

    def set_rotation_interval(self, seconds: int) -> None:
        """Set the time interval for log rotation."""
        self.interval = seconds

    def _get_next_rotation_filename(self, default) -> str:
        base_filename = datetime.now().strftime(self._rotation_filename_format)

        if not os.path.isdir(self._rotation_folder):
            return base_filename.replace("%i", "000")

        filenames = set()
        for filename in os.listdir(self._rotation_folder):
            if os.path.isfile(os.path.join(self._rotation_folder, filename)):
                filenames.add(filename)

        for count in range(0, 1000):
            filename = base_filename.replace("%i", "%03d" % count)
            if filename not in filenames:
                return filename

        # Can't find proper filename
        raise Exception("Failed to find a valid rotation file name")


class LoggerFileSink(LoggerSink):
    """
    Logger sink that writes to a file (wrapping logging.TimedRotatingFileHandler).

    Supports log rotation based on time intervals.
    """
    def __init__(self, folder: str, latest_filename: str = "latest.log", filename_format: str = "%Y-%m-%d-%i.log", interval = 24*3600):
        self.handler = _LoggingFileHandler(folder, latest_filename, filename_format, interval)

    def get_handler(self) -> logging.Handler:
        return self.handler

    def set_rotation_enable(self, enable: bool) -> None:
        """Enable or disable log rotation."""
        self.handler.set_rotation_enable(enable)

    def set_rotation_interval(self, interval: timedelta) -> None:
        """Set the time interval for log rotation."""
        self.handler.set_rotation_interval(interval.seconds)


class _LoggingConsoleHandler(logging.Handler):
    def __init__(self, stdout: TextIO, stderr: TextIO):
        super().__init__()
        self.stdout = stdout
        self.stderr = stderr

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            stream = self.stderr if record.levelno >= logging.ERROR else self.stdout
            stream.write(msg)
            stream.flush()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        """Flush console streams."""
        self.stdout.flush()
        self.stderr.flush()
        super().close()


class LoggerConsoleSink(LoggerSink):
    """
    Logger sink that writes to the console (stdout/stderr).
    """
    def __init__(self, stdout: TextIO | None = None, stderr: TextIO | None = None):
        if stdout is None:
            stdout = _base_stdout
        if stderr is None:
            stderr = _base_stderr

        self.formater = LoggerFormater(_are_ansi_color_supported())

        self.handler = _LoggingConsoleHandler(stdout, stderr)
        self.handler.setFormatter(self.formater)

    def get_handler(self) -> logging.Handler:
        return self.handler

    def close(self) -> None:
        self.handler.close()

    def set_colored(self, colored: bool) -> None:
        """Enable or disable ANSI color output."""
        self.formater.set_colored(colored)


class Logger:
    """
    Main logger class.

    Manages multiple sinks and module-specific loggers.
    """
    def __init__(self, name: str, *, parent: Logger = None) -> None:
        if parent is None:
            self._logger = logging.getLogger(name)
            self._logger.setLevel(logging.DEBUG)
            # Don't propagate to root logger to avoid double logging
            self._logger.propagate = False
        else:
            self._logger = parent._logger.getChild(name)
            self._logger.setLevel(parent._logger.level)

        self._parent = parent

        self._default_stdout_level = logging.DEBUG
        self._default_stderr_level = logging.ERROR

        self._sinks: list[LoggerSink] = []

    def __del__(self):
        self.close()

    def get_stdlib_logger(self) -> logging.Logger:
        return self._logger

    def set_level(self, level: LoggerLevel) -> None:
        self._logger.setLevel(level.value)

    def add_sink(self, sink: LoggerSink) -> None:
        """Add a sink to the logger."""
        self._sinks.append(sink)
        self._logger.addHandler(sink.get_handler())

    def use_as_default(self, default_stdout_level = logging.DEBUG, default_stderr_level = logging.ERROR):
        """
        Set this logger as the system default.

        Redirects sys.stdout and sys.stderr to this logger.

        Args:
            default_stdout_level: Log level for stdout.
            default_stderr_level: Log level for stderr.
        """
        global _default_logger
        _default_logger = self

        self._default_stdout_level = default_stdout_level
        self._default_stderr_level = default_stderr_level

        # Replace Python default sys.stdout and sys.stderr with our custom function
        # so every call to ``print`` will be redirected to the logger
        sys.stdout = _CustomWriteIO(self._io_info)
        sys.stderr = _CustomWriteIO(self._io_error)

        # Currently no good way to fix encoding errors
        _base_stdout._errors = "backslashreplace"
        _base_stderr._errors = "backslashreplace"

    def _io_info(self, data):
        self.info(data, end='', module=self._default_module)

    def _io_error(self, data):
        self.error(data, end='', module=self._default_module)

    def close(self):
        """Close all sinks."""
        for sink in self._sinks:
            self._logger.removeHandler(sink)
            sink.close()
        self._sinks.clear()

    def _merge_args(self, args: list, sep=' ') -> str:
        return sep.join(str(a) for a in args)

    def _log(self, lvl: LoggerLevel, *args, sep: str, end: str, flush: bool | None) -> None:
        msg = self._merge_args(args, sep) + end
        self._logger.log(lvl.value, msg)

    def debug(self, *args, sep: str = ' ', end: str = '\n', flush: bool | None = None) -> None:
        """Log a debug message."""
        self._log(LoggerLevel.DEBUG, *args, sep=sep, end=end, flush=flush)

    def info(self, *args, sep: str = ' ', end: str = '\n', flush: bool | None = None) -> None:
        """Log an info message."""
        self._log(LoggerLevel.INFO, *args, sep=sep, end=end, flush=flush)

    def success(self, *args, sep: str = ' ', end: str = '\n', flush: bool | None = None) -> None:
        """Log a success message."""
        self._log(LoggerLevel.SUCCESS, *args, sep=sep, end=end, flush=flush)

    def warning(self, *args, sep: str = ' ', end: str = '\n', flush: bool | None = None) -> None:
        """Log a warning message."""
        self._log(LoggerLevel.WARNING, *args, sep=sep, end=end, flush=flush)

    def error(self, *args, sep: str = ' ', end: str = '\n', flush: bool | None = None) -> None:
        """Log an error message."""
        self._log(LoggerLevel.ERROR, *args, sep=sep, end=end, flush=flush)

    def fatal(self, *args, sep: str = ' ', end: str = '\n', flush: bool | None = None) -> None:
        """Log a fatal message."""
        self._log(LoggerLevel.CRITICAL, *args, sep=sep, end=end, flush=flush)

    def get_sublogger(self, name: str) -> Logger:
        """
        Get a logger instance for a specific module.

        Args:
            name: The name of the module.

        Returns:
            A ModuleLogger instance.
        """
        return Logger(name, parent=self)


def get_default_logger() -> Logger:
    """Get or create the global default logger instance."""
    global _default_logger
    if _default_logger is None:
        _default_logger = Logger()
    return _default_logger
