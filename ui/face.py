"""Pillow companion face and terminal controls; no additional GPIO claims."""
import math
import os
import select
import sys
import termios
import tty
from PIL import Image, ImageDraw, ImageFont
from ui.controls import shortcuts


class Keyboard:
    def __enter__(self):
        self.saved = None
        self.buffer = ''
        if sys.stdin.isatty():
            self.fd = sys.stdin.fileno()
            self.saved = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        return self

    def read(self):
        if self.saved is not None and select.select([self.fd], [], [], 0)[0]:
            self.buffer += os.read(self.fd, 64).decode('ascii', errors='ignore')
        if not self.buffer:
            return ''
        if self.buffer.startswith('\x1b'):
            if len(self.buffer) < 3:
                return ''
            sequence, self.buffer = self.buffer[:3], self.buffer[3:]
            return {'\x1b[A': 'up', '\x1b[B': 'down',
                    '\x1bOA': 'up', '\x1bOB': 'down'}.get(sequence, '')
        key, self.buffer = self.buffer[0], self.buffer[1:]
        return key.lower()

    def __exit__(self, *args):
        if self.saved is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)


class Companion:
    def __init__(self, view='face'):
        self.view = view
        self.reaction = None
        self.until = 0

    def key(self, key, now):
        if key == 'm':
            self.view = 'menu'
        elif key == 'f':
            self.view = 'face'
        elif key == 'b':
            self.view = 'bluetooth'
        elif key in ('h', 'n'):
            self.view = 'face'
            self.reaction = {'h': 'happy', 'n': 'sleep'}[key]
            self.until = now + (8 if key == 'n' else 2)
        return key != 'q'

    def expression(self, state, errors, now):
        if self.reaction and now < self.until:
            return self.reaction
        if errors or state.get('errors') or state.get('status', '').lower() in ('error', 'failed', 'blocked'):
            return 'concerned'
        if state.get('status', '').lower() in ('working', 'running', 'busy'):
            return 'thinking'
        if state.get('status', '').lower() in ('unknown', 'offline'):
            return 'waiting'
        return 'ready'


def render_face(expression, now):
    image = Image.new('RGB', (320, 240), '#080e18')
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=11)
    color = '#ffb586' if expression == 'concerned' else '#61ead4'
    draw.rounded_rectangle((25, 34, 295, 193), radius=35, outline='#1b3c46', width=2)
    blink = now % 4.8 < .16 or expression in ('blink', 'sleep')
    gaze = round(math.sin(now * .7) * 5) if expression != 'sleep' else 0
    for x in (94, 224):
        x += gaze
        if blink:
            draw.rounded_rectangle((x-21, 101, x+21, 106), radius=2, fill=color)
        elif expression == 'happy':
            draw.arc((x-22, 83, x+22, 124), 185, 355, fill=color, width=7)
        else:
            draw.rounded_rectangle((x-17, 78, x+17, 125), radius=12, fill=color)
            draw.rectangle((x-8, 85, x-3, 96), fill='#d7fff6')
            if expression == 'concerned':
                draw.line((x-23, 65, x+20, 72), fill=color, width=4)
    if expression == 'concerned':
        draw.arc((139, 151, 181, 175), 190, 350, fill=color, width=3)
    elif expression == 'thinking':
        for i in range(3):
            draw.ellipse((145+i*12, 152, 149+i*12, 156), fill=color if int(now*3)%3 == i else '#254c52')
    elif expression == 'sleep':
        draw.text((250, 48), 'z Z', font=font, fill=color)
        draw.line((146, 155, 174, 155), fill=color, width=3)
    else:
        draw.arc((139, 135, 181, 164), 5, 175, fill=color, width=3)
    label = 'CODEX / ' + expression.upper()
    draw.text((12, 10), label, font=font, fill='#8c9bb4')
    shortcuts(draw, 218, [('m', 'menu'), ('h', 'hello'), ('b', 'BT'), ('n', 'nap'), ('q', 'quit')])
    return image
