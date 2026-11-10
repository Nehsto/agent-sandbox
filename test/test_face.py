import os
import pty
import termios
import unittest
from unittest.mock import patch
from ui.face import Companion, Keyboard, render_face


class FaceTests(unittest.TestCase):
    def test_controls_and_reaction_expiry(self):
        face = Companion()
        face.key('m', 0)
        self.assertEqual(face.view, 'menu')
        face.key('b', .5)
        self.assertEqual(face.view, 'bluetooth')
        face.key('h', 1)
        self.assertEqual(face.view, 'face')
        self.assertEqual(face.expression({}, [], 2), 'happy')
        self.assertEqual(face.expression({'status': 'working'}, [], 4), 'thinking')
        self.assertEqual(face.expression({}, ['failure'], 4), 'concerned')
        self.assertFalse(face.key('q', 4))

    def test_terminal_restored_on_failure(self):
        master, slave = pty.openpty()
        try:
            with os.fdopen(slave, 'r') as stream, patch('sys.stdin', stream):
                before = termios.tcgetattr(stream.fileno())
                with self.assertRaises(RuntimeError):
                    with Keyboard() as keyboard:
                        os.write(master, b'm')
                        import select
                        self.assertTrue(select.select([stream], [], [], 1)[0])
                        self.assertEqual(keyboard.read(), 'm')
                        raise RuntimeError('simulated failure')
                self.assertEqual(termios.tcgetattr(stream.fileno()), before)
        finally:
            os.close(master)

    def test_arrow_sequences_across_reads_and_queued_keys(self):
        keyboard = Keyboard()
        keyboard.saved = True
        keyboard.fd = 123
        keyboard.buffer = ''
        with patch('ui.face.select.select', return_value=([123], [], [])), patch(
                'ui.face.os.read', side_effect=[b'\x1b', b'[A\x1b[Bf', b'', b'']):
            self.assertEqual(keyboard.read(), '')
            self.assertEqual(keyboard.read(), 'up')
            self.assertEqual(keyboard.read(), 'down')
            self.assertEqual(keyboard.read(), 'f')

    def test_every_expression_renders(self):
        for mood in ('ready', 'happy', 'blink', 'sleep', 'thinking', 'concerned', 'waiting'):
            image = render_face(mood, 2)
            self.assertEqual(image.size, (320, 240))


if __name__ == '__main__':
    unittest.main()
