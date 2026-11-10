import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from agent_status import publish
from bt.activity import publish_event


class PermissionTests(unittest.TestCase):
    def test_runtime_feeds_are_shared_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, write in [('agent-state.json', lambda p: publish(p, 'working', 'Task', '', 'Activity')),
                                ('bluetooth-activity.json', lambda p: publish_event('Scanning nearby devices', p))]:
                path = Path(directory)/name
                write(path)
                self.assertEqual(path.stat().st_mode & 0o777, 0o644)
                self.assertIsInstance(json.loads(path.read_text()), dict)

    def test_unreadable_agent_state_is_preserved_before_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'agent-state.json'
            path.write_text('{"task": "old"}')
            with patch.object(Path, 'read_text', side_effect=PermissionError):
                publish(path, 'ready', 'New task', '', 'Refreshed')
            archives = list((Path(directory)/'reports').glob('agent-state-unreadable-*.json'))
            self.assertEqual(len(archives), 1)
            self.assertEqual(json.loads(archives[0].read_text()), {'task': 'old'})
            self.assertEqual(json.loads(path.read_text())['status'], 'ready')

    def test_ble_report_is_shared_readable(self):
        from bt.client import save_report
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'report.json'
            save_report(path, {'probes': []})
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)
