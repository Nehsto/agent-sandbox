"""Project-local Bluetooth interaction feed shared by dashboard and CLI."""
import json
import os
from pathlib import Path
import tempfile
import time

PATH = Path(__file__).resolve().parent.parent/'bluetooth-activity.json'


def read_activity(path=PATH):
    try:
        if path.stat().st_size > 32768:
            return {}
        value = json.loads(path.read_text())
        if (not isinstance(value, dict) or not isinstance(value.get('status'), str)
                or not isinstance(value.get('activity'), list)
                or not all(isinstance(item, str) for item in value['activity'])):
            return {}
        return value
    except (OSError, ValueError):
        return {}


def event_status(message, previous='IDLE'):
    lower = message.lower()
    if lower.startswith('bluetooth work stopped'):
        return 'IDLE'
    if lower.startswith('pairing failed / try normal connect'):
        return 'CONNECTING'
    if any(word in lower for word in ('failed', 'rejected', 'unavailable', 'timed out',
                                      'requires', 'missing', 'canceled', 'dropped', 'lost')):
        return 'ERROR'
    if lower.startswith('done'):
        return 'DONE'
    if lower.startswith('nearby devices:'):
        return 'READY'
    if lower.startswith('scanning'):
        return 'SCANNING'
    if lower.startswith(('connecting', 'starting selected', 'pairing failed / try')):
        return 'CONNECTING'
    if lower.startswith(('pair', 'authorizing')):
        return 'PAIRING'
    if lower.startswith(('trying readable', 'reading')):
        return 'READING'
    if lower.startswith(('connected', 'target service', 'read succeeded', 'service inspected')):
        return 'CONNECTED'
    if lower.startswith(('disconnected', 'idle')):
        return 'IDLE'
    return previous


def publish_event(message, path=PATH):
    state = read_activity(path)
    message = ''.join(c if c.isprintable() else ' ' for c in str(message))[:500]
    state['status'] = event_status(message, state.get('status', 'IDLE'))
    state['activity'] = (*state.get('activity', []), f'{time.strftime("%H:%M:%S")} {message}')[-20:]
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        os.fchmod(stream.fileno(), 0o644)
        json.dump(state, stream)
        stream.write('\n')
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return state
