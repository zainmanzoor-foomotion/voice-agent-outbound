"""
utils/logger.py
---------------
Tiny logging helper.

Centralizing logger creation means we keep the same formatting
across every service and route in the app.
"""

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger with timestamped, leveled output."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

    return logger
