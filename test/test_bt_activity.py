import tempfile
import unittest
from pathlib import Path
from bt.activity import read_activity, publish_event, event_status


class ActivityTests(unittest.TestCase):
    def test_shared_bluetooth_feed_is_bounded_and_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'activity.json'
            path.write_text('broken')
            self.assertEqual(read_activity(path), {})
            publish_event('Scanning nearby devices', path)
            self.assertEqual(read_activity(path)['status'], 'SCANNING')
            for index in range(25):
                publish_event(f'Bluetooth event {index}', path)
            state = publish_event('Done / report saved', path)
            self.assertEqual(state['status'], 'DONE')
            self.assertEqual(len(state['activity']), 20)
            self.assertTrue(state['activity'][-1].endswith('Done / report saved'))
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_status_transitions_do_not_claim_connection_on_read_failure(self):
        self.assertEqual(event_status('Pairing failed / try normal connect'), 'CONNECTING')
        self.assertEqual(event_status('Read rejected / recording details'), 'ERROR')
        self.assertEqual(event_status('Done / 0 reads, 1 rejected'), 'ERROR')
        self.assertEqual(event_status('Trying readable characteristic'), 'READING')
