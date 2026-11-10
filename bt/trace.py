"""Bounded, thread-scoped observation of Bleak's BlueZ read diagnostics."""
from contextlib import contextmanager
import logging
import threading

LOGGER = 'bleak.backends.bluezdbus.client'


@contextmanager
def read_trace():
    """Count busy replies/completions without recording payloads or credentials."""
    evidence = {'in_progress_retries': 0, 'logged_read_completions': 0}
    owner = threading.get_ident()

    class Handler(logging.Handler):
        def emit(self, record):
            if record.thread != owner:
                return
            template = str(record.msg)
            if 'retrying characteristic ReadValue due to InProgress' in template:
                evidence['in_progress_retries'] += 1
            elif template.startswith('Read Characteristic '):
                evidence['logged_read_completions'] += 1

    logger = logging.getLogger(LOGGER)
    previous = logger.level
    handler = Handler(level=logging.DEBUG)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        yield evidence
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)
