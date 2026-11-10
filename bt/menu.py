"""Bounded nearby Bluetooth discovery using the host's bluetoothctl."""
import subprocess
import re
import threading
import time
import sys
from PIL import Image, ImageDraw, ImageFont
from ui.controls import shortcuts
from bt.client import run_session, TARGET_SERVICE, REPORT_PATH
from bt.activity import publish_event, read_activity, event_status


def read_bluetooth():
    """Discover nearby radios for eight seconds; do not pair or change power."""
    try:
        result = subprocess.run(['bluetoothctl', '--timeout', '8', 'scan', 'on'],
                                capture_output=True, text=True, timeout=11, check=False)
        output = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', result.stdout)
        if result.returncode or any(message in output for message in
                ('Failed to start discovery', 'No default controller', 'NotReady', 'NotAuthorized')):
            return ['Bluetooth scan unavailable', 'Check adapter power / permissions', 'Press R to retry']
        seen = {}
        names = {}
        for line in output.splitlines():
            match = re.search(r'\[(NEW|CHG)\] Device ([0-9A-Fa-f:]{17}) (.+)', line)
            if not match:
                continue
            kind, address, detail = match.groups()
            address = address.upper()
            if kind == 'NEW' or detail.startswith('RSSI:'):
                seen.setdefault(address, address)
                if kind == 'NEW' and detail not in (address, address.replace(':', '-')):
                    names[address] = detail
            if detail.startswith(('Name:', 'Alias:')):
                names[address] = detail.split(':', 1)[1].strip()
        if any(address not in names for address in seen):
            try:
                cached = subprocess.run(['bluetoothctl', 'devices'], capture_output=True,
                                        text=True, timeout=2, check=False)
                if cached.returncode == 0:
                    for line in cached.stdout.splitlines():
                        match = re.match(r'Device ([0-9A-Fa-f:]{17}) (.+)', line)
                        if match:
                            address, name = match.groups()
                            address = address.upper()
                            if name not in (address, address.replace(':', '-')):
                                names.setdefault(address, name)
            except (OSError, subprocess.TimeoutExpired):
                pass  # Keep successful discovery results if name lookup fails.
        lines = [f'Nearby devices: {len(seen)}']
        for address in seen:
            lines.extend([names.get(address) or 'Unknown', address])
        if not seen:
            lines.extend(['No devices found', 'Put devices in discovery mode'])
        return lines
    except FileNotFoundError:
        return ['bluetoothctl is unavailable', 'Run this menu on the Pi']
    except subprocess.TimeoutExpired:
        return ['Bluetooth scan timed out', 'Press R to retry']
    except OSError:
        return ['Bluetooth scan failed', 'Press R to retry']


class BluetoothScanner:
    """Keep terminal controls and drawing responsive during discovery."""
    def __init__(self):
        self.lines = ['Press B or R to scan nearby devices']
        self.worker = None
        self.selected = 0
        self.activity = ()
        self.activity = ('Idle / waiting for scan',)
        self.status = 'IDLE'
        self.monitor_updated = 0
        self.monitor_state = {}
        self.stop_event = threading.Event()
        self.closing = False
        self.active_address = None

    def record(self, message):
        entry = f'{time.strftime("%H:%M:%S")} {message}'
        self.activity = (*self.activity, entry)[-20:]
        self.status = event_status(message, self.status)
        try:
            publish_event(message)
        except OSError:
            pass  # Keep local feedback if the shared feed cannot be written.

    def monitor(self):
        if time.monotonic() - self.monitor_updated >= .5:
            self.monitor_state = read_activity()
            self.monitor_updated = time.monotonic()
        return (self.monitor_state.get('status', self.status),
                self.monitor_state.get('activity', self.activity))

    def start(self):
        if self.closing or (self.worker is not None and self.worker.is_alive()):
            return
        self.selected = 0
        self.lines = ['Scanning nearby devices...', 'Please wait about 8 seconds',
                      'Devices must be discoverable']
        self.record('Scanning nearby devices')
        self.worker = threading.Thread(target=self._scan, daemon=True)
        self.worker.start()

    def connect(self, service=TARGET_SERVICE, characteristic=None, pair=False):
        if self.closing or (self.worker is not None and self.worker.is_alive()):
            return
        if not device_count(self.lines):
            self.record('Select a discovered ESP32 first')
            return
        address = self.lines[2+self.selected*2]
        self.active_address = address
        self.record('Starting selected BLE session')
        self.worker = threading.Thread(target=run_session,
            args=(address, service, characteristic, pair, self.record,
                  REPORT_PATH), kwargs={'stop_event': self.stop_event}, daemon=True)
        self.worker.start()

    def close(self):
        """Cancel owned work, await context cleanup and disconnect the owned target."""
        if self.closing:
            return
        self.closing = True
        self.stop_event.set()
        cleanup_ok = True
        if self.worker is not None:
            self.worker.join(timeout=12)
        if self.active_address:
            try:
                result = subprocess.run(['bluetoothctl', 'disconnect', self.active_address],
                    capture_output=True, text=True, timeout=3, check=False)
                output = (result.stdout + result.stderr).lower()
                if result.returncode and not any(text in output for text in
                        ('not connected', 'notconnected', 'not available', 'does not exist')):
                    cleanup_ok = False
                    self.record('Bluetooth disconnect failed / inspect terminal')
                    print('Bluetooth disconnect failed: ' + output[:300], file=sys.stderr)
            except (OSError, subprocess.TimeoutExpired) as error:
                cleanup_ok = False
                self.record('Bluetooth disconnect could not be confirmed')
                print(f'Bluetooth quit cleanup: {type(error).__name__}', file=sys.stderr)
        if self.worker is not None and self.worker.is_alive():
            self.worker.join(timeout=3)
        if self.worker is not None and self.worker.is_alive():
            self.record('Bluetooth worker did not stop before exit')
            print('Bluetooth worker did not stop before exit.', file=sys.stderr)
        elif cleanup_ok:
            self.record('Bluetooth work stopped on quit')
        else:
            self.record('Bluetooth quit cleanup failed / disconnect unconfirmed')

    def move(self, key):
        count = device_count(self.lines)
        step = {'up': -1, 'down': 1}.get(key, 0)
        self.selected = max(0, min(max(0, count-1), self.selected + step))

    def _scan(self):
        try:
            self.lines = read_bluetooth()
        except Exception:
            self.lines = ['Bluetooth scan failed', 'Press R to retry']
        self.record(self.lines[0])


def device_count(lines):
    if lines and lines[0].startswith('Nearby devices: '):
        return min(int(lines[0].split(': ')[1]), (len(lines)-1)//2)
    return 0


def render_bluetooth(lines, selected=0, activity=(), status='IDLE'):
    image = Image.new('RGB', (320, 240), '#0b1220')
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=12)
    terminal_font = ImageFont.load_default(size=11)
    try:
        title = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 16)
    except OSError:
        title = ImageFont.load_default(size=17)

    def text(x, y, line, color='#edf3ff', width=None, font=font):
        line = str(line).replace('\n', ' ')
        width = 310-x if width is None else width
        if draw.textlength(line, font=font) > width:
            while line and draw.textlength(line + '…', font=font) > width:
                line = line[:-1]
            line += '…'
        draw.text((x, y), line, font=font, fill=color)

    draw.rectangle((0, 0, 319, 30), fill='#152238')
    text(10, 6, 'Bluetooth Menu', font=title, width=190)
    text(214, 9, status, '#ff9ca8' if status == 'ERROR' else '#53dcca', width=96)
    count = device_count(lines)
    if count:
        selected = max(0, min(count-1, selected))
        draw.rounded_rectangle((7, 37, 312, 81), radius=5, fill='#1c304a')
        draw.polygon([(12, 48), (20, 54), (12, 60)], fill='#96baff')
        text(27, 40, lines[1+selected*2])
        text(27, 59, lines[2+selected*2], '#8c9bb4')
        text(10, 86, f'Up/Down select   {selected+1}/{count}', '#96baff')
    else:
        for index, line in enumerate(lines[:3]):
            text(10, 38+index*19, line)

    draw.rounded_rectangle((7, 104, 312, 212), radius=6, fill='#101d30', outline='#24334b')
    text(14, 108, 'BT TERMINAL', '#53dcca', font=terminal_font)
    wrapped = []
    for entry in activity[-20:]:
        line = ''
        for char in str(entry):
            if draw.textlength(line + char, font=terminal_font) > 288:
                wrapped.append(line)
                line = '  '
            line += char if char.isprintable() else ' '
        wrapped.append(line)
    for index, line in enumerate(wrapped[-6:]):
        text(14, 124+index*14, line, '#b9c9df', width=288, font=terminal_font)
    if not wrapped:
        text(14, 124, 'Waiting for Bluetooth activity', '#8c9bb4', font=terminal_font)
    shortcuts(draw, 218, [('c', 'connect'), ('r', 'scan'), ('m', 'menu'), ('f', 'face'), ('q', 'quit')])
    return image
