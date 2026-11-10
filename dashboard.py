"""Headless agent dashboard, 320x240 logical canvas / orientation 2."""
import argparse
from contextlib import ExitStack
import json
import math
from pathlib import Path
import sys
import time
from datetime import datetime

from PIL import Image, ImageChops, ImageDraw, ImageFont
from ui.face import Companion, Keyboard, render_face
from ui.controls import shortcuts
from bt.menu import BluetoothScanner, render_bluetooth
from bt.client import TARGET_SERVICE

ROOT = Path(__file__).resolve().parent
BG = '#0b1220'
MUTED = '#8c9bb4'
WHITE = '#edf3ff'
CYAN = '#53dcca'
FONT = ImageFont.load_default(size=12)
TITLE = ImageFont.load_default(size=17)
try:
    TITLE = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 16)
except OSError:
    pass
try:
    UPDATE_FONT = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 11)
except OSError:
    UPDATE_FONT = FONT


def latest_update(state, width=300):
    """Fit the entire timestamp, label and latest message to a pixel budget."""
    try:
        stamp = datetime.fromisoformat(state.get('updated_at', '')).astimezone().strftime('%m/%d-%H:%M')
    except (ValueError, TypeError):
        stamp = '--/-----:--'
    message = state.get('detail', '').strip()
    value = (f'{stamp}: {message}' if message else stamp).replace('\n', ' ')
    if UPDATE_FONT.getlength(value) <= width:
        return value
    low, high = 0, len(value)
    while low < high:
        middle = (low + high + 1) // 2
        if UPDATE_FONT.getlength(value[:middle] + '…') <= width:
            low = middle
        else:
            high = middle - 1
    return value[:low] + '…' if UPDATE_FONT.getlength('…') <= width else ''


class Metrics:
    def __init__(self):
        self.previous = None

    def sample(self):
        result = {'cpu': None, 'ram': None, 'temp': None, 'uptime': None}
        errors = []
        try:
            values = list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))
            total, idle = sum(values), values[3] + values[4]
            if self.previous:
                delta = total - self.previous[0]
                if delta > 0:
                    result['cpu'] = max(0, min(100, 100 * (1 - (idle-self.previous[1])/delta)))
            self.previous = total, idle
        except (OSError, ValueError, IndexError) as error:
            errors.append(f'CPU: {error}')
        try:
            memory = {line.split(':')[0]: int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()}
            result['ram'] = 100 * (1 - memory['MemAvailable']/memory['MemTotal'])
        except (OSError, ValueError, KeyError, ZeroDivisionError) as error:
            errors.append(f'RAM: {error}')
        try:
            result['temp'] = float(Path('/sys/class/thermal/thermal_zone0/temp').read_text()) / 1000
        except (OSError, ValueError):
            pass
        try:
            result['uptime'] = float(Path('/proc/uptime').read_text().split()[0])
        except (OSError, ValueError, IndexError) as error:
            errors.append(f'Uptime: {error}')
        return result, errors


def read_state(path):
    try:
        if path.stat().st_size > 65536:
            raise ValueError('state file exceeds 64 KiB')
        state = json.loads(path.read_text())
        if not isinstance(state, dict):
            raise ValueError('expected JSON object')
        for key in ('task', 'status', 'detail'):
            if not isinstance(state.get(key, ''), str):
                raise ValueError(f'{key} must be text')
        for key in ('activity', 'errors'):
            if not isinstance(state.get(key, []), list) or not all(isinstance(item, str) for item in state.get(key, [])):
                raise ValueError(f'{key} must be a list of text')
        age = max(0, time.time() - path.stat().st_mtime)
        return state, age, []
    except (OSError, ValueError) as error:
        return {'task': 'Waiting for agent state', 'status': 'unknown'}, None, [f'State: {error}']


def render(metrics, state, age, errors):
    image = Image.new('RGB', (320, 240), BG)
    draw = ImageDraw.Draw(image)

    def text(x, y, value, color=WHITE, font=FONT, width=296):
        value = str(value).replace('\n', ' ')
        if draw.textlength(value, font=font) > width:
            low, high = 0, len(value)
            while low < high:
                middle = (low + high + 1) // 2
                if draw.textlength(value[:middle] + '…', font=font) <= width:
                    low = middle
                else:
                    high = middle - 1
            value = value[:low] + '…'
        draw.text((x, y), value, font=font, fill=color)

    draw.rectangle((0, 0, 319, 30), fill='#152238')
    text(10, 6, 'Codex @ Pi', font=TITLE, width=170)
    status = state.get('status', 'unknown').upper()
    text(194, 9, status, CYAN, width=116)
    text(10, 38, state.get('task', 'Waiting for task'), font=TITLE)
    text(10, 61, latest_update(state, image.width - 20), MUTED,
         font=UPDATE_FONT, width=image.width - 20)
    for x, key, label in ((10, 'cpu', 'CPU'), (166, 'ram', 'RAM')):
        value = metrics[key]
        text(x, 85, f'{label}  {value:.0f}%' if value is not None else f'{label}  --', width=140)
    uptime = metrics['uptime']
    hours = int(uptime // 3600) if uptime is not None else None
    temp = metrics['temp']
    text(10, 104, f'UP {hours}h {int(uptime//60)%60:02d}m' if hours is not None else 'UP --', MUTED, width=145)
    text(166, 104, f'TEMP {temp:.1f} C' if temp is not None else 'TEMP --', MUTED, width=145)
    draw.rounded_rectangle((7, 126, 312, 200), radius=6, fill='#101d30', outline='#24334b')
    text(14, 131, 'RECENT ACTIVITY', CYAN)
    for index, entry in enumerate(state.get('activity', [])[-3:]):
        text(14, 150 + index*15, entry, MUTED, width=288)
    diagnostics = errors + state.get('errors', [])
    draw.rectangle((0, 221, 319, 239), fill='#321b26' if diagnostics else '#152238')
    text(8, 223, diagnostics[-1] if diagnostics else
         (f'State updated {int(age)}s ago' if age is not None else 'No agent state'),
         '#ffad9f' if diagnostics else MUTED, width=304)
    shortcuts(draw, 204, [('f', 'face'), ('h', 'hello'), ('b', 'BT'), ('n', 'nap'), ('q', 'quit')])
    return image


def push_changed(display, previous, image):
    """Rotate to native coordinates before computing the changed rectangle."""
    native = image.rotate(90, expand=True)
    box = ImageChops.difference(previous, native).getbbox() if previous is not None else (0, 0, 240, 320)
    if box:
        display.image(native.crop(box), x=box[0], y=box[1])
    return native


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, default=ROOT/'agent-state.json')
    parser.add_argument('--preview', type=Path)
    parser.add_argument('--view', choices=('face', 'menu', 'bluetooth'), default='face')
    parser.add_argument('--baudrate', type=int, default=83_333_333)
    parser.add_argument('--interval', type=float, default=1)
    parser.add_argument('--ble-service', default=TARGET_SERVICE)
    parser.add_argument('--ble-read', help='Readable characteristic UUID in the target service')
    parser.add_argument('--ble-pair', action='store_true', help='Request BLE pairing before connection')
    args = parser.parse_args()
    if args.baudrate <= 0 or not math.isfinite(args.interval) or args.interval < .1:
        parser.error('baudrate must be positive and interval must be finite and >=0.1 seconds')
    metrics = Metrics()
    companion = Companion(args.view)
    bluetooth = BluetoothScanner()

    def snapshot():
        values, errors = metrics.sample()
        state, age, state_errors = read_state(args.state)
        return values, state, age, errors + state_errors

    def frame(data, now):
        if companion.view == 'face':
            return render_face(companion.expression(data[1], data[3], now), now)
        if companion.view == 'bluetooth':
            bt_status, bt_activity = bluetooth.monitor()
            return render_bluetooth(bluetooth.lines, bluetooth.selected,
                                    bt_activity, bt_status)
        return render(*data)

    if args.preview:
        frame(snapshot(), time.monotonic()).save(args.preview)
        print(f'Saved {args.preview} (landscape preview)')
        return 0
    try:
        if not Path('/dev/spidev0.0').exists():
            raise OSError('/dev/spidev0.0 unavailable; run from the host SSH shell')
        import board
        import digitalio
        if digitalio.Pin is None:
            raise RuntimeError(
                'Blinka GPIO backend is unset. On this Raspberry Pi 4B, rerun with '
                'BLINKA_FORCEBOARD=RASPBERRY_PI_4B BLINKA_FORCECHIP=BCM2XXX '
                'before the Python command.'
            )
        from adafruit_rgb_display import ili9341
        with ExitStack() as stack:
            dc = stack.enter_context(digitalio.DigitalInOut(board.D25))
            reset = stack.enter_context(digitalio.DigitalInOut(board.D24))
            spi = stack.enter_context(board.SPI())
            display = ili9341.ILI9341(spi, cs=None, dc=dc, rst=reset,
                                    baudrate=args.baudrate, width=240, height=320, rotation=0)
            print(f'Dashboard: orientation 2, requested SPI {args.baudrate:,} Hz. Ctrl-C to stop.', flush=True)
            print('Keys: m menu | f face | h hello | b Bluetooth | c connect selected | r refresh Bluetooth | n nap | q quit', flush=True)
            previous = None
            next_sample = 0
            data = None
            stack.callback(bluetooth.close)
            with Keyboard() as keyboard:
                while True:
                    started = time.monotonic()
                    key = keyboard.read()
                    if not companion.key(key, started):
                        display.image(Image.new('RGB', (240, 320), 'black'))
                        break
                    if companion.view == 'bluetooth' and (key in ('b', 'r') or data is None):
                        bluetooth.start()
                    if companion.view == 'bluetooth' and key in ('up', 'down'):
                        bluetooth.move(key)
                    if companion.view == 'bluetooth' and key == 'c':
                        bluetooth.connect(args.ble_service, args.ble_read, args.ble_pair)
                    if started >= next_sample:
                        data = snapshot()
                        next_sample = started + args.interval
                    previous = push_changed(display, previous, frame(data, started))
                    time.sleep(max(0, .1 - (time.monotonic()-started)))
    except KeyboardInterrupt:
        print('\nDashboard stopped.')
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        print(f'Dashboard failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
