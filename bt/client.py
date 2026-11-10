"""Bounded BLE service inspection/read session, executed on the Pi."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import sys
import time
from datetime import datetime, timezone
from bt.trace import read_trace

REPORT_PATH = Path(__file__).resolve().parent.parent/'reports'/'ble-report.json'

TARGET_SERVICE = '4fafc201-1fb5-459e-8fcc-c5c9c331914b'


DEVICE_NAME = '00002a00-0000-1000-8000-00805f9b34fb'
GENERIC_ACCESS = '00001800-0000-1000-8000-00805f9b34fb'


async def inspect_device(address, service_uuid, characteristic, pair, report, client_factory=None,
                         state_reader=None, checkpoint=None, target_only=False):
    client_pair = pair
    if client_factory is None:
        from bleak import BleakClient
        from bt.pairing import device_state
        client_factory = BleakClient
        state_reader = state_reader or device_state
        if pair:
            from bt.pairing import pair_device
            await pair_device(address, report)
            client_pair = False
    started = time.monotonic()
    phase = 'connecting'
    expected_disconnect = False
    result = {'address': address, 'target_service': service_uuid, 'pair_requested': pair,
              'encryption_verified': False, 'services': [], 'diagnostics': {
                  'started_at': datetime.now(timezone.utc).isoformat(),
                  'state_samples': [], 'disconnect_events': []}}
    diagnostics = result['diagnostics']

    def elapsed():
        return round((time.monotonic()-started)*1000)

    def persist():
        if checkpoint:
            checkpoint(result)

    def disconnected(client):
        diagnostics['disconnect_events'].append({'elapsed_ms': elapsed(), 'phase': phase,
                                                  'expected': expected_disconnect})
        report('Disconnected / session cleanup' if expected_disconnect else 'Connection dropped / recording phase')
        persist()

    async def snapshot(label):
        sample = {'phase': label, 'elapsed_ms': elapsed()}
        if state_reader:
            try:
                sample.update(await asyncio.wait_for(state_reader(address), timeout=3))
            except Exception as error:
                sample['unavailable'] = error_details(error)
        else:
            sample['unavailable'] = 'No BlueZ state reader'
        diagnostics['state_samples'].append(sample)
        persist()
        return sample

    async def read(client, candidate, label):
        nonlocal phase
        phase = label
        began = time.monotonic()
        probe = {'uuid': candidate.uuid, 'started_ms': elapsed(),
                 'connected_before': getattr(client, 'is_connected', None)}
        report('Reading Device Name / control' if label == 'control_read' else 'Reading target characteristic')
        with read_trace() as trace:
            try:
                data = await asyncio.wait_for(client.read_gatt_char(candidate), timeout=20)
                probe.update(value_details(data))
                report(f'{"Control" if label == "control_read" else "Target"} read OK / {len(data)} bytes')
            except Exception as error:
                probe.update(error_details(error))
                if isinstance(error, TimeoutError):
                    probe['timeout_evidence'] = ('BlueZ returned InProgress repeatedly'
                        if trace['in_progress_retries'] else
                        'No completed read or InProgress retry logged before timeout')
                    report(f'{"Control" if label == "control_read" else "Target"} read timed out'
                           + (' / BlueZ busy' if trace['in_progress_retries'] else ' / awaiting reply'))
                else:
                    report(f'{"Control" if label == "control_read" else "Target"} read failed')
            finally:
                probe['elapsed_ms'] = round((time.monotonic()-began)*1000)
                probe['connected_after'] = getattr(client, 'is_connected', None)
                probe['transport_trace'] = trace
        return probe

    report('Pair/connect requested' if pair else 'Connecting to selected device')
    async with client_factory(address, pair=client_pair, timeout=45,
                              disconnected_callback=disconnected) as client:
        try:
            report('Connected / checking service')
            phase = 'service_discovery'
            services = list(client.services)
            result['services'] = [
                {'uuid': s.uuid, 'characteristics': [
                    {'uuid': c.uuid, 'properties': list(c.properties)} for c in s.characteristics]}
                for s in services]
            persist()
            initial = await snapshot('before_target' if target_only else 'before_control')
            def flag(name):
                return str(initial[name]).lower() if name in initial else 'unknown'
            report(f'BlueZ paired={flag("Paired")} bonded={flag("Bonded")}')
            if target_only:
                diagnostics['control_read'] = {'skipped': 'Target-only capture mode'}
                report('Target-only mode / no control read')
            else:
                control = next((c for s in services if s.uuid.lower() == GENERIC_ACCESS
                                for c in s.characteristics if c.uuid.lower() == DEVICE_NAME
                                and 'read' in c.properties), None)
                if control:
                    diagnostics['control_read'] = await read(client, control, 'control_read')
                else:
                    diagnostics['control_read'] = {'skipped': 'Readable Device Name not advertised'}
                    report('Device Name control unavailable')
                persist()
                await snapshot('after_control')
            target = next((s for s in services if s.uuid.lower() == service_uuid.lower()), None)
            if target is None:
                raise ValueError('Target service absent on selected device')
            report('Target service found')
            candidates = [c for c in target.characteristics if 'read' in c.properties]
            if characteristic:
                candidates = [c for c in candidates if c.uuid.lower() == characteristic.lower()]
                if len(candidates) != 1:
                    raise ValueError('Read characteristic absent, ambiguous or not readable')
            result['probes'] = []
            result['readable_total'] = len(candidates)
            for candidate in candidates[:16]:
                if getattr(client, 'is_connected', None) is False:
                    report('Target read skipped / disconnected')
                    diagnostics['target_skipped'] = 'Connection already dropped'
                    break
                probe = await read(client, candidate, 'target_read')
                result['probes'].append(probe)
                if characteristic:
                    result['read'] = probe
                persist()
                await snapshot('after_target_read')
                if 'error' in probe:
                    # Do not queue more GATT requests behind a potentially stuck read.
                    break
            diagnostics['assessment'] = assess_diagnostics(result)
            report(diagnostics['assessment'])
            persist()
        finally:
            expected_disconnect = True
            phase = 'cleanup'
    report('Disconnected')
    persist()
    return result


def assess_diagnostics(result):
    diag = result['diagnostics']
    if any(not event['expected'] for event in diag['disconnect_events']):
        return 'Connection dropped / inspect timing'
    if diag.get('target_skipped'):
        return 'Connection lost before target read'
    probes = result.get('probes', [])
    control = diag.get('control_read', {})
    if probes and all('error' not in item for item in probes):
        return 'Target data read / encryption unverified'
    if probes and 'bytes' in control:
        return 'Control OK / target read failed'
    if probes and 'error' in control:
        return 'Both reads failed / cause unresolved'
    return 'Insufficient read evidence / see report'


def value_details(data):
    raw = bytes(data)
    preview = raw[:256]
    result = {'bytes': len(raw), 'hex': preview.hex(), 'truncated': len(raw) > 256}
    try:
        result['text'] = preview.decode('utf-8')
    except UnicodeDecodeError:
        pass
    return result


def save_report(path, result):
    """Atomic project report, including bounded values read from the target service."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        os.fchmod(stream.fileno(), 0o644)
        json.dump(result, stream, indent=2)
        stream.write('\n')
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def error_details(error):
    def clean(value):
        return ''.join(char if char.isprintable() else ' ' for char in str(value))[:500]
    result = {'error': type(error).__name__, 'message': clean(error)}
    for field, alternate in (('dbus_error', 'type'), ('dbus_error_details', 'text')):
        value = getattr(error, field, None) or getattr(error, alternate, None)
        if value:
            result[field] = clean(value)
    return result


async def probe_device(address, service_uuid, characteristic, pair, report, checkpoint=None, target_only=False):
    attempts = []
    for request_pair in ([True, False] if pair else [False]):
        partial = {}
        def capture(value):
            partial.update(value)
            if checkpoint:
                checkpoint(value)
        try:
            options = {'checkpoint': capture}
            if target_only:
                options['target_only'] = True
            result = await inspect_device(address, service_uuid, characteristic, request_pair, report, **options)
            read_errors = any('error' in item for item in result.get('probes', []))
            attempts.append({'pair_requested': request_pair,
                             'outcome': 'completed_with_read_errors' if read_errors else 'completed'})
            result['attempts'] = attempts
            return result
        except ImportError:
            raise
        except Exception as error:
            details = error_details(error)
            attempts.append({'pair_requested': request_pair, **details})
            if request_pair and details.get('dbus_error') in (
                    'org.bluez.Error.AuthenticationFailed', 'org.bluez.Error.AuthenticationRejected',
                    'org.bluez.Error.Rejected'):
                report('Pairing failed / try normal connect')
                continue
            return {**partial, 'address': address, 'target_service': service_uuid,
                    'pair_requested': request_pair, 'attempts': attempts, **details}
    return {'address': address, 'attempts': attempts, 'error': 'All attempts failed'}


async def cancellable_probe(operation, stop_event):
    task = asyncio.create_task(operation)
    async def watch():
        while not stop_event.is_set():
            await asyncio.sleep(.05)
        task.cancel()
    watcher = asyncio.create_task(watch()) if stop_event is not None else None
    try:
        return await asyncio.wait_for(task, timeout=150)
    finally:
        if watcher is not None:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)


def run_session(address, service_uuid, characteristic, pair, report, path, target_only=False, stop_event=None):
    latest = {}
    def checkpoint(value):
        latest.update(value)
        save_report(path, latest)
    try:
        options = {'target_only': True} if target_only else {}
        result = asyncio.run(cancellable_probe(
            probe_device(address, service_uuid, characteristic, pair, report, checkpoint, **options), stop_event))
        save_report(path, result)
        if 'error' in result:
            print('BLE failure: ' + json.dumps(result), file=sys.stderr, flush=True)
            report('BLE failed / see reports/ble-report.json')
            reason = result.get('dbus_error', result.get('message') or result['error'])
            report(reason.removeprefix('org.bluez.Error.'))
        else:
            probes = result.get('probes', [])
            failures = sum('error' in item for item in probes)
            report(f'Done / {len(probes)-failures} reads, {failures} failed'
                   if probes else 'Done / report saved')
    except asyncio.CancelledError:
        save_report(path, {**latest, 'address': address, 'cancelled': True})
        report('BLE operation canceled / cleanup finished')
    except ImportError:
        save_report(path, {'address': address, 'error': 'Missing bleak'})
        report('Missing bleak / install requirements')
    except TimeoutError:
        save_report(path, {**latest, 'address': address, 'error': 'BLE session timed out'})
        report('BLE session timed out')
    except Exception as error:
        details = error_details(error)
        save_report(path, {**latest, 'address': address, 'target_service': service_uuid,
                           'pair_requested': pair, **details})
        report('BLE failed / see reports/ble-report.json')
        report(details['error'])


if __name__ == '__main__':
    import argparse
    from agent_status import publish
    from bt.activity import publish_event
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--address', default='80:B5:4E:E8:B4:69')
    parser.add_argument('--service', default=TARGET_SERVICE)
    parser.add_argument('--read', help='Read a specific characteristic instead of automatic probing')
    parser.add_argument('--pair', action='store_true')
    parser.add_argument('--target-only', action='store_true', help='Skip control read for a fresh target-only diagnostic')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent

    def progress(message):
        print(message, flush=True)
        publish_event(message)
        publish(root/'agent-state.json', 'working', message, 'ESP32 BLE investigation', message)

    run_session(args.address, args.service, args.read, args.pair, progress, REPORT_PATH, target_only=args.target_only)
    publish(root/'agent-state.json', 'ready', 'ESP32 BLE attempt finished',
            'See reports/ble-report.json for actual results', 'BLE attempt finished; report available')
