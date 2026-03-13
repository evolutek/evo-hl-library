import sys

from evo_hl.logger import Logger, LoggerConsoleSink


def test_logger():
    logger = Logger()
    logger.use_as_default()

    # Test console sink
    logger.add_sink(LoggerConsoleSink())
    #logger.open_file("test.log")

    # Test multiline logs
    logger.info("Multiline\nstring\nEOL")

    # Test different log leveld
    logger.debug("test")
    logger.info("test 1")
    logger.info("test 2")
    logger.info("test 3")
    logger.success("test")
    logger.warning("test")
    logger.error("test")
    logger.fatal("test")

    # Print to stdout
    print("test")

    # Print to stderr
    print("test", file=sys.stderr)

    # Create a division by zero exception
    _ = 42 / 0


# Test code
if __name__ == "__main__":
    test_logger()

