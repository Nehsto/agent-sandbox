"""Atomically publish agent task/status and append an activity entry."""
import argparse
import json
from pathlib import Path
import tempfile
import os
from datetime import datetime


def publish(path, status, task, detail, activity):
    try:
        state = json.loads(path.read_text()) if path.exists() else {}
    except PermissionError:
        # Preserve the unreadable feed before replacing it for shared use.
        archive = path.parent/'reports'
        archive.mkdir(exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%dT%H%M%S%f')
        path.rename(archive/f'{path.stem}-unreadable-{stamp}.json')
        state = {}
    state.update(status=status, task=task, detail=detail)
    state['updated_at'] = datetime.now().astimezone().isoformat()
    state['activity'] = (state.get('activity', []) + [activity])[-20:]
    state.setdefault('errors', [])
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        os.fchmod(stream.fileno(), 0o644)
        json.dump(state, stream, indent=2)
        stream.write('\n')
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('status', choices=('working', 'ready', 'blocked', 'error'))
    parser.add_argument('task')
    parser.add_argument('activity')
    parser.add_argument('--detail', default='')
    parser.add_argument('--state', type=Path, default=Path(__file__).resolve().parent/'agent-state.json')
    args = parser.parse_args()
    publish(args.state, args.status, args.task, args.detail, args.activity)
