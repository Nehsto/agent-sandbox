import logging
import threading
import unittest
from bt.trace import LOGGER, read_trace


class ReadTraceTests(unittest.TestCase):
    def test_counts_busy_without_recording_payload_and_restores_logger(self):
        logger = logging.getLogger(LOGGER)
        previous_level = logger.level
        previous_handlers = list(logger.handlers)
        with read_trace() as evidence:
            logger.debug('retrying characteristic ReadValue due to InProgress')
            logger.debug('retrying characteristic ReadValue due to InProgress')
            logger.debug('Read Characteristic %s | %s: %r', 'UUID', '/path', b'private payload')
            record = logging.LogRecord(LOGGER, logging.DEBUG, '', 0,
                'retrying characteristic ReadValue due to InProgress', (), None)
            record.thread = threading.get_ident()+1
            logger.handle(record)
        self.assertEqual(evidence, {'in_progress_retries': 2, 'logged_read_completions': 1})
        self.assertNotIn('payload', str(evidence))
        self.assertEqual(logger.level, previous_level)
        self.assertEqual(logger.handlers, previous_handlers)

    def test_cleanup_on_exception(self):
        logger = logging.getLogger(LOGGER)
        previous = logger.level, list(logger.handlers)
        with self.assertRaises(RuntimeError):
            with read_trace():
                raise RuntimeError('failed')
        self.assertEqual((logger.level, logger.handlers), previous)
