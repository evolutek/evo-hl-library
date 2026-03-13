"""
Logger module for Evo-HL library.

This module provides a flexible logging system with support for multiple sinks (console, file),
log rotation, colors, and module-specific logging contexts.
"""

import sys
import os
from datetime import datetime, timedelta
import threading
import re
from abc import ABC, abstractmethod
import atexit

# Here colorama is used to get a list of ANSI colors code
from colorama import Fore, Style

# Here colorama is used to pasively enable color support on Windows terminals
if sys.platform == "win32":
    from colorama import just_fix_windows_console
    just_fix_windows_console()


_logger_lock = threading.Lock()


def _are_ansi_color_supported():
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' # and (plat != 'win32' or 'ANSICON' in os.environ)
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


def _encode(s):
    return s.encode('utf-8', errors='ignore')


# Keep original sys.stdout and sys.stderr
_base_stdout = sys.stdout
_base_stderr = sys.stderr

# Currently no good way to fix encoding errors
_base_stdout._errors = "backslashreplace"
_base_stderr._errors = "backslashreplace"


ANSI_SEQUENCE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
def _remove_ansi_codes(sentence: str):
    return ANSI_SEQUENCE_RE.sub('', sentence)


class ModuleLogger:
    """
    Logger wrapper for a specific module.

    This class forwards log calls to the parent Logger instance, automatically
    attaching the module name to the log record.
    """

    def __init__(self, logger: Logger, name: str) -> None:
        self.logger = logger
        self.name = name

    def debug(self, *args, sep: str = ' ', end: str = '\n', flush: bool = False) -> None:
        """Log a debug message."""
        self.logger.debug(*args, sep=sep, end=end, flush=flush, module=self.name)

    def info(self, *args, sep: str = ' ', end: str = '\n', flush: bool = False) -> None:
        """Log an info message."""
        self.logger.info(*args, sep=sep, end=end, flush=flush, module=self.name)

    def success(self, *args, sep: str = ' ', end: str = '\n', flush: bool = False) -> None:
        """Log a success message."""
        self.logger.success(*args, sep=sep, end=end, flush=flush, module=self.name)

    def warning(self, *args, sep: str = ' ', end: str = '\n', flush: bool = False) -> None:
        """Log a warning message."""
        self.logger.warning(*args, sep=sep, end=end, flush=flush, module=self.name)

    def error(self, *args, sep: str = ' ', end: str = '\n', flush: bool = False) -> None:
        """Log an error message."""
        self.logger.error(*args, sep=sep, end=end, flush=flush, module=self.name)

    def fatal(self, *args, sep: str = ' ', end: str = '\n', flush: bool = False) -> None:
        """Log a fatal message."""
        self.logger.fatal(*args, sep=sep, end=end, flush=flush, module=self.name)


class LoggerLevel:
    """
    Represents a logging level configuration.

    Attributes:
        colored_prefix: The prefix string with ANSI colors.
        prefix: The prefix string without ANSI colors.
        colored_module_fmt: The module format string with ANSI colors.
        module_fmt: The module format string without ANSI colors.
        pipe: The IO stream (stdout or stderr) for this level.
    """

    def __init__(self, pipe, module_fmt: str, colored_prefix: str) -> None:
        self.colored_prefix = colored_prefix
        self.prefix = _remove_ansi_codes(colored_prefix)
        self.colored_module_fmt = module_fmt
        self.module_fmt = _remove_ansi_codes(module_fmt)
        self.pipe = pipe


_COMMON_PREFIX = Style.BRIGHT + Fore.BLACK + "[" + Style.RESET_ALL + Fore.WHITE + "%s" + Style.BRIGHT + Fore.BLACK + "] %s" + Style.RESET_ALL
_MODULE_FORMAT = Style.BRIGHT + Fore.BLACK + "[" + Style.RESET_ALL + Fore.CYAN + "%s" + Style.BRIGHT + Fore.BLACK + "] "

LVL_DEBUG   = LoggerLevel(_base_stdout, _MODULE_FORMAT, _COMMON_PREFIX + Fore.BLACK                          + "Debug"   + Style.DIM + Fore.WHITE                   + ": " + Style.RESET_ALL + Style.DIM + Fore.WHITE)
LVL_INFO    = LoggerLevel(_base_stdout, _MODULE_FORMAT, _COMMON_PREFIX + Fore.BLUE                           + "Info"    + Style.DIM + Fore.WHITE                   + ": " + Style.RESET_ALL + Fore.WHITE)
LVL_SUCCESS = LoggerLevel(_base_stdout, _MODULE_FORMAT, _COMMON_PREFIX + Style.BRIGHT + Fore.GREEN           + "Success" + Style.RESET_ALL + Style.DIM + Fore.WHITE + ": " + Style.RESET_ALL + Fore.GREEN)
LVL_WARNING = LoggerLevel(_base_stdout, _MODULE_FORMAT, _COMMON_PREFIX + Style.BRIGHT + Fore.YELLOW          + "Warning" + Style.RESET_ALL + Style.DIM + Fore.WHITE + ": " + Style.RESET_ALL + Fore.YELLOW)
LVL_ERROR   = LoggerLevel(_base_stderr, _MODULE_FORMAT, _COMMON_PREFIX + Style.BRIGHT + Fore.RED             + "Error"   + Style.RESET_ALL + Style.DIM + Fore.WHITE + ": " + Style.RESET_ALL + Fore.RED)
LVL_FATAL   = LoggerLevel(_base_stderr, _MODULE_FORMAT, _COMMON_PREFIX + Style.BRIGHT + Style.DIM + Fore.RED + "Fatal"   + Style.RESET_ALL + Style.DIM + Fore.WHITE + ": " + Style.DIM + Fore.RED)


_default_logger: "Logger" = None
_loggers: list["Logger"] = []


# Be sure to close all logger instances before exit
def _close_loggers():
    for logger in _loggers:
        logger.close()

atexit.register(_close_loggers)


class LoggerFormater:
    """
    Handles formatting of log messages.

    Manages timestamps, prefixes, module names, and indentation for multiline logs.
    """
    def __init__(self):
        self._last_line_level = None
        self._last_is_newline = True
        self._last_trailing_spaces = ""

        self._strftime_format = "%d-%m-%Y %H:%M:%S"

    def set_time_format(self, format: str) -> None:
        """Set the format string for timestamps (strftime format)."""
        self._strftime_format = format

    def format(self, lvl: LoggerLevel, module: str, s: str, colored: bool) -> str:
        """
        Format a log message.

        Args:
            lvl: The logging level.
            module: The module name.
            s: The message string.
            colored: Whether to include ANSI colors.

        Returns:
            The formatted log string.
        """
        strtime = datetime.now().strftime(self._strftime_format)
        module_str = (lvl.colored_module_fmt if colored else lvl.module_fmt) % module if module else ""
        prefix = (lvl.colored_prefix if colored else lvl.prefix) % (strtime, module_str)

        out = ""
        trailing_spaces = self._last_trailing_spaces
        last_is_newline = self._last_is_newline

        if self._last_line_level != lvl and not last_is_newline:
            out += "\n"
            last_is_newline = True

        for i in range(len(s)):
            c = s[i]
            if c == '\r' or c == '\n':
                last_is_newline = True
                out += trailing_spaces
                trailing_spaces = ""
                out += c
            elif last_is_newline and c.isspace():
                trailing_spaces += c
            else:
                if last_is_newline:
                    out += prefix
                    out += trailing_spaces
                    trailing_spaces = ""
                    last_is_newline = False
                out += c

        self._last_is_newline = last_is_newline
        self._last_trailing_spaces = trailing_spaces
        self._last_line_level = lvl

        return out


class LoggerSink(ABC):
    """
    Abstract base class for log sinks.

    A sink is a destination for log messages (e.g., console, file).
    """
    def __init__(self):
        super().__init__()
        self.formater = LoggerFormater()

    @abstractmethod
    def write(self, lvl: LoggerLevel, module: str, s: str, flush: bool) -> None:
        """
        Write a log message to the sink.

        Args:
            lvl: The logging level.
            module: The module name.
            s: The message content.
            flush: Whether to flush the stream.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the sink and release resources."""
        pass

    def get_formater(self) -> LoggerFormater:
        """Get the formatter used by this sink."""
        return self.formater


class LoggerFileSink(LoggerSink):
    """
    Logger sink that writes to a file.

    Supports log rotation based on time intervals.
    """
    def __init__(self):
        super().__init__()

        # The opened file
        self._file = None

        # Rotation filename is: FILENAME_PREFIX + FILENAME_FORMAT + FILENAME_SUFFIX
        self._rotation_enable = False
        self._rotation_interval = timedelta(days = 1) # Default to 1 day interval
        self._rotation_format = "%Y-%m-%d-%i.log" # %i is a counter to avoid two files with the same name
        self._rotation_folder = "logs/"
        self._rotation_latest = "latest.log"
        self._rotation_next = None # Datetime of the next rotation

    def write(self, lvl: LoggerLevel, module: str, s: str, flush: bool) -> None:
        """Write a log message to the file."""
        self.check_rotation()
        raw = self.formater.format(lvl, module, s, False)
        self._file.write(_encode(raw))
        if flush:
            self._file.flush()

    def open(self, filename: str, append: bool =True) -> None:
        """
        Open the log file.

        Args:
            filename: Path to the log file.
            append: Whether to append to existing file or overwrite.
        """
        pdir = os.path.dirname(filename)
        if pdir and not os.path.isdir(pdir):
            os.makedirs(pdir)
        self._file = open(filename, 'ab' if append else 'wb')

    def close(self) -> None:
        """Close the log file."""
        if self._file is not None:
            if not self._file.closed:
                self._file.close()
            self._file = None

    def enable_rotation(self, enable: bool) -> None:
        """Enable or disable log rotation."""
        self._rotation_enable = enable

    def _get_next_rotation_filename(self) -> None:
        base_filename = datetime.now().strftime(self._rotation_format)

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
        return None

    def set_rotation_interval(self, interval: timedelta) -> None:
        """Set the time interval for log rotation."""
        self._rotation_interval = interval

    def set_rotation_filename(self, format: str) -> None:
        """Set the filename format for rotated logs."""
        self._rotation_format = format.replace("%i", "%%i")

    def set_rotation_folder(self, folder: str) -> None:
        """Set the folder where rotated logs will be stored."""
        self._rotation_folder = folder

    def set_rotation_latest_filename(self, filename: str) -> None:
        """Set the filename for the 'latest' log file."""
        self._rotation_latest = filename

    def create_rotation_latest_file(self) -> None:
        """Create or reset the 'latest' log file."""
        self.close()
        self.open(self._rotation_latest, False)

    def do_rotation(self) -> None:
        """Perform the log rotation process."""
        self._rotation_next = datetime.now() + self._rotation_interval
        if os.path.isfile(self._rotation_latest):
            filename = self._get_next_rotation_filename()
            if filename is None:
                self.close()
                return
            if not os.path.isdir(self._rotation_folder):
                os.makedirs(self._rotation_folder)
            os.rename(self._rotation_latest, os.path.join(self._rotation_folder, filename))
        self.create_rotation_latest_file()

    def check_rotation(self) -> None:
        """Check if rotation is needed and perform it if necessary."""
        if self._rotation_enable:
            if self._rotation_next is None or datetime.now() >= self._rotation_next:
                self.do_rotation()


class LoggerConsoleSink(LoggerSink):
    """
    Logger sink that writes to the console (stdout/stderr).
    """
    def __init__(self):
        super().__init__()
        self._allow_color = _are_ansi_color_supported()

    def write(self, lvl: LoggerLevel, module: str, s: str, flush: bool) -> None:
        """Write a log message to the console."""
        raw = self.formater.format(lvl, module, s, self._allow_color)
        lvl.pipe.write(raw)
        if flush:
            lvl.pipe.flush()

    def close(self) -> None:
        """Flush console streams."""
        _base_stdout.flush()
        _base_stderr.flush()

    def set_allow_color(self, allow: bool) -> None:
        """Enable or disable ANSI color output."""
        if allow != self._allow_color:
            self._allow_color = allow
            if not allow:
                # Reset color in terminal
                _base_stderr.write(Style.RESET_ALL)
                _base_stdout.write(Style.RESET_ALL)
                _base_stderr.flush()
                _base_stdout.flush()


class Logger:
    """
    Main logger class.

    Manages multiple sinks and module-specific loggers.
    """
    def __init__(self) -> None:
        self._default_stdout_level = LVL_DEBUG
        self._default_stderr_level = LVL_ERROR

        self._default_module = ""
        self._modules: dict[str, ModuleLogger] = {}

        self._sinks: list[LoggerSink] = []

        """
        # Shortcuts
        self.dbg  = self.debug
        self.inf  = se>lf.info
        self.succ = self.success
        self.warn = self.warning
        self.err  = self.error
        self.crit = self.fatal
        """

        _loggers.append(self)

    def __del__(self):
        self.close_file()
        self.allow_color(False)

    def add_sink(self, sink: LoggerSink) -> None:
        """Add a sink to the logger."""
        self._sinks.append(sink)

    def use_as_default(self, default_stdout_level = LVL_DEBUG, default_stderr_level = LVL_ERROR):
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
        # Replace Python default sys.stdout and sys.stderr with ou custom function
        # so every call to ``print`` will be redirected to the logger
        sys.stdout = _CustomWriteIO(self._io_info)
        sys.stderr = _CustomWriteIO(self._io_error)

    def _io_info(self, data):
        self._write(self._default_stdout_level, data, None, self._default_module)

    def _io_error(self, data):
        self._write(self._default_stderr_level, data, None, self._default_module)

    def set_default_module_name(self, name: str) -> None:
        """Set the default module name for logs without a specific module."""
        self._default_module = name

    def close(self):
        """Close all sinks."""
        for sink in self._sinks:
            sink.close()
        self._sinks = []

    def _merge_args(self, args: list, sep=' ') -> str:
        out = ""
        first = True
        for a in args:
            if first:
                first = False
            else:
                out += sep
            out += str(a)
        return out

    def _write(self, lvl: LoggerLevel, s: str, flush: bool | None, module: str) -> None:
        if flush is None:
            flush = s.find('\n') != -1

        with _logger_lock:
            for sink in self._sinks:
                sink.write(lvl, module, s, flush)

    def _log(self, lvl: LoggerLevel, *args, sep: str, end: str, flush: bool | None, module: str) -> None:
        if module is None:
            module = self._default_module
        self._write(lvl, self._merge_args(args, sep) + end, flush, module)

    def debug(self, *args, sep: str = ' ', end: str = '\n', flush: bool | None = None, module: str = None) -> None:
        """Log a debug message."""
        self._log(LVL_DEBUG, *args, sep=sep, end=end, flush=flush, module=module)

    def info(self, *args, sep: str = ' ', end: str = '\n', flush: bool | None = None, module: str = None) -> None:
        """Log an info message."""
        self._log(LVL_INFO, *args, sep=sep, end=end, flush=flush, module=module)

    def success(self, *args, sep: str = ' ', end: str = '\n', flush: bool | None = None, module: str = None) -> None:
        """Log a success message."""
        self._log(LVL_SUCCESS, *args, sep=sep, end=end, flush=flush, module=module)

    def warning(self, *args, sep: str = ' ', end: str = '\n', flush: bool | None = None, module: str = None) -> None:
        """Log a warning message."""
        self._log(LVL_WARNING, *args, sep=sep, end=end, flush=flush, module=module)

    def error(self, *args, sep: str = ' ', end: str = '\n', flush: bool | None = None, module: str = None) -> None:
        """Log an error message."""
        self._log(LVL_ERROR, *args, sep=sep, end=end, flush=flush, module=module)

    def fatal(self, *args, sep: str = ' ', end: str = '\n', flush: bool | None = None, module: str = None) -> None:
        """Log a fatal message."""
        self._log(LVL_FATAL, *args, sep=sep, end=end, flush=flush, module=module)

    def get_module_logger(self, name: str) -> ModuleLogger:
        """
        Get a logger instance for a specific module.

        Args:
            name: The name of the module.

        Returns:
            A ModuleLogger instance.
        """
        if name not in self._modules:
            self._modules[name] = ModuleLogger(self, name)
        return self._modules[name]


def get_default_logger() -> Logger:
    """Get or create the global default logger instance."""
    global _default_logger
    _default_logger = None
    if _default_logger is None:
        _default_logger = Logger()
    return _default_logger


def get_default_module_logger(name: str) -> ModuleLogger:
    """Get a ModuleLogger from the default global logger."""
    return get_default_logger().get_module_logger(name)
