import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from tools.capture_ble import main, stop_monitor


class CaptureTests(unittest.TestCase):
    def test_missing_btmon_never_starts_probe(self):
        with patch('sys.argv', ['capture_ble']), patch('tools.capture_ble.shutil.which', return_value=None), \
             patch('tools.capture_ble.subprocess.Popen') as popen, patch('sys.stderr'):
            self.assertEqual(main(), 1)
            popen.assert_not_called()

    def test_btmon_permission_failure_prevents_probe(self):
        monitor = Mock()
        monitor.poll.return_value = 1
        with tempfile.TemporaryDirectory() as directory:
            with patch('sys.argv', ['capture_ble']), patch('tools.capture_ble.ROOT', Path(directory)), \
                 patch('tools.capture_ble.shutil.which', return_value='/usr/bin/btmon'), \
                 patch('tools.capture_ble.subprocess.Popen', return_value=monitor), \
                 patch('tools.capture_ble.subprocess.run') as run, patch('sys.stderr'), patch('sys.stdout'):
                self.assertEqual(main(), 1)
                run.assert_not_called()
                capture_dir = next((Path(directory)/'reports').iterdir())
                self.assertEqual(capture_dir.stat().st_mode & 0o777, 0o755)
                self.assertEqual((capture_dir/'btmon.log').stat().st_mode & 0o777, 0o644)
        monitor.send_signal.assert_not_called()

    def test_stop_only_signals_owned_live_monitor(self):
        monitor = Mock()
        monitor.poll.return_value = None
        stop_monitor(monitor)
        monitor.send_signal.assert_called_once()
        monitor.wait.assert_called_once_with(timeout=5)
