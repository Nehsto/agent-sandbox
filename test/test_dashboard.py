import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from dashboard import push_changed, read_state, render, latest_update, UPDATE_FONT


class DashboardTests(unittest.TestCase):
    def test_update_fits_portrait_and_landscape_widths(self):
        state = {'updated_at': '2026-11-08T14:31:00-05:00',
                 'detail': 'Long update ' * 100}
        for width in (220, 300):
            line = latest_update(state, width)
            self.assertLessEqual(UPDATE_FONT.getlength(line), width)
            self.assertRegex(line, r'^\d{2}/\d{2}-\d{2}:\d{2}: ')
            self.assertTrue(line.endswith('…'))

    def test_no_subtitle_shows_only_timestamp(self):
        state = {'updated_at': '2026-11-08T14:31:00-05:00', 'task': 'Done'}
        self.assertRegex(latest_update(state), r'^\d{2}/\d{2}-\d{2}:\d{2}$')
        state['detail'] = '   '
        self.assertRegex(latest_update(state), r'^\d{2}/\d{2}-\d{2}:\d{2}$')

    def test_partial_update_reconstructs_rotated_frame(self):
        class Display:
            def __init__(self):
                self.canvas = Image.new('RGB', (240, 320))
                self.calls = []
            def image(self, image, x=0, y=0):
                self.calls.append((image.size, x, y))
                self.canvas.paste(image, (x, y))
        display = Display()
        image = Image.new('RGB', (320, 240), 'black')
        previous = push_changed(display, None, image)
        push_changed(display, previous, image)
        self.assertEqual(len(display.calls), 1)
        image.putpixel((30, 40), (255, 0, 0))
        push_changed(display, previous, image)
        self.assertEqual(display.calls[-1][0], (1, 1))
        self.assertEqual(display.canvas.tobytes(), image.rotate(90, expand=True).tobytes())

    def test_bad_state_is_visible_and_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'state.json'
            path.write_text('{')
            state, age, errors = read_state(path)
            self.assertTrue(errors)
            self.assertEqual(state['status'], 'unknown')
            path.write_text(json.dumps({'task': 'Recovered', 'activity': ['ok']}))
            state, age, errors = read_state(path)
            self.assertFalse(errors)
            self.assertEqual(state['task'], 'Recovered')
            self.assertIsNotNone(age)

    def test_missing_metrics_and_long_text_render(self):
        image = render(dict.fromkeys(('cpu', 'ram', 'temp', 'uptime')),
                       {'task': 'long task '*100, 'errors': ['failure '*100]}, None, [])
        self.assertEqual(image.size, (320, 240))


if __name__ == '__main__':
    unittest.main()
