import subprocess
import threading
import unittest
from unittest.mock import patch
from bt.menu import BluetoothScanner, read_bluetooth, render_bluetooth


class BluetoothTests(unittest.TestCase):
    def setUp(self):
        writer = patch('bt.menu.publish_event')
        writer.start()
        self.addCleanup(writer.stop)

    def test_only_observed_devices_and_names(self):
        output = ('Discovery started\n'
                  '\x1b[0;92m[NEW]\x1b[0m Device AA:BB:CC:DD:EE:FF Speaker\n'
                  '[CHG] Device 11:22:33:44:55:66 RSSI: -61\n'
                  '[CHG] Device 11:22:33:44:55:66 Name: Phone\n'
                  '[CHG] Device 00:00:00:00:00:00 Connected: no\n')
        with patch('bt.menu.subprocess.run', return_value=subprocess.CompletedProcess([], 0, output)) as run:
            lines = read_bluetooth()
        self.assertEqual(lines, ['Nearby devices: 2', 'Speaker', 'AA:BB:CC:DD:EE:FF',
                                 'Phone', '11:22:33:44:55:66'])
        self.assertEqual(run.call_args.kwargs['timeout'], 11)
        self.assertEqual(render_bluetooth(lines).size, (320, 240))

    def test_failures_and_empty_scan(self):
        for failure in (FileNotFoundError(), subprocess.TimeoutExpired('bluetoothctl', 11)):
            with patch('bt.menu.subprocess.run', side_effect=failure):
                self.assertTrue(read_bluetooth())
        for output, expected in [('Failed to start discovery: org.bluez.Error.NotReady', 'unavailable'),
                                 ('Discovery started', 'Nearby devices: 0')]:
            with patch('bt.menu.subprocess.run', return_value=subprocess.CompletedProcess([], 0, output)):
                self.assertIn(expected, read_bluetooth()[0])

    def test_scan_is_async_and_does_not_overlap(self):
        release = threading.Event()
        def scan():
            release.wait(2)
            return ['finished']
        with patch('bt.menu.read_bluetooth', side_effect=scan) as query:
            scanner = BluetoothScanner()
            try:
                scanner.start()
                worker = scanner.worker
                scanner.start()
                self.assertIs(scanner.worker, worker)
                self.assertIn('Scanning', scanner.lines[0])
                self.assertIn('Scanning nearby devices', scanner.activity[-1])
            finally:
                release.set()
                scanner.worker.join(2)
            self.assertEqual(scanner.lines, ['finished'])
            self.assertTrue(scanner.activity[-1].endswith('finished'))
            self.assertEqual(len(scanner.activity), 3)
            self.assertEqual(query.call_count, 1)

    def test_selection_scrolls_all_results_and_clamps(self):
        scanner = BluetoothScanner()
        scanner.lines = ['Nearby devices: 8']
        for index in range(8):
            scanner.lines.extend([f'Device {index}', f'AA:BB:CC:DD:EE:{index:02X}'])
        first = render_bluetooth(scanner.lines, scanner.selected)
        for _ in range(12):
            scanner.move('down')
        self.assertEqual(scanner.selected, 7)
        last = render_bluetooth(scanner.lines, scanner.selected)
        self.assertNotEqual(first.tobytes(), last.tobytes())
        for _ in range(12):
            scanner.move('up')
        self.assertEqual(scanner.selected, 0)
        scanner.lines = ['Nearby devices: 0', 'No devices found']
        scanner.move('down')
        self.assertEqual(scanner.selected, 0)

    def test_monitor_renders_bluetooth_updates(self):
        lines = ['Nearby devices: 0', 'No devices found']
        before = render_bluetooth(lines)
        after = render_bluetooth(lines, activity=('12:00:00 Scanning', '12:00:08 Nearby devices: 0'),
                                 status='READY')
        self.assertEqual(after.size, (320, 240))
        self.assertNotEqual(before.crop((7, 104, 313, 213)).tobytes(),
                            after.crop((7, 104, 313, 213)).tobytes())

    def test_header_single_device_and_wrapped_feedback(self):
        from PIL import ImageDraw
        original = ImageDraw.ImageDraw.text
        calls = []
        def capture(draw, xy, text, *args, **kwargs):
            calls.append((xy, text))
            return original(draw, xy, text, *args, **kwargs)
        lines = ['Nearby devices: 2', 'ESP32 one', 'AA:BB:CC:DD:EE:01',
                 'ESP32 two', 'AA:BB:CC:DD:EE:02']
        with patch.object(ImageDraw.ImageDraw, 'text', new=capture):
            render_bluetooth(lines, 1, ('12:00:00 ' + 'Long Bluetooth feedback '*5,), 'READING')
        texts = [value for xy, value in calls]
        self.assertIn('Bluetooth Menu', texts)
        self.assertIn('READING', texts)
        self.assertIn('ESP32 two', texts)
        self.assertNotIn('ESP32 one', texts)
        self.assertIn('Up/Down select   2/2', texts)
        feedback = [(xy, text) for xy, text in calls if 124 <= xy[1] <= 194]
        self.assertGreater(len(feedback), 1)
        self.assertTrue(all(not text.endswith('…') for xy, text in feedback))

    def test_names_before_rssi_and_cached_names(self):
        output = ('[CHG] Device 80:B5:4E:E8:B4:69 Name: ESP32 Server\n'
                  '[CHG] Device 80:B5:4E:E8:B4:69 RSSI: -50\n'
                  '[CHG] Device 11:22:33:44:55:66 RSSI: -60\n')
        cached = ('Device 11:22:33:44:55:66 Cached sensor\n'
                  'Device 00:00:00:00:00:00 Old offline device\n')
        with patch('bt.menu.subprocess.run', side_effect=[
                subprocess.CompletedProcess([], 0, output),
                subprocess.CompletedProcess([], 0, cached)]):
            lines = read_bluetooth()
        self.assertEqual(lines, ['Nearby devices: 2', 'ESP32 Server', '80:B5:4E:E8:B4:69',
                                 'Cached sensor', '11:22:33:44:55:66'])

    def test_cached_lookup_failure_keeps_discovered_device(self):
        with patch('bt.menu.subprocess.run', side_effect=[
                subprocess.CompletedProcess([], 0, '[CHG] Device 80:B5:4E:E8:B4:69 RSSI: -50'),
                subprocess.TimeoutExpired('bluetoothctl', 2)]):
            self.assertEqual(read_bluetooth(), ['Nearby devices: 1', 'Unknown',
                                               '80:B5:4E:E8:B4:69'])
