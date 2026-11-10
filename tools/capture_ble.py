"""Capture one native target-only ESP32 BLE probe with btmon, without sudo."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
CHARACTERISTIC = 'beb5483e-36e1-4688-b7f5-ea07361b26a8'


def stop_monitor(process):
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--address', default='80:B5:4E:E8:B4:69')
    parser.add_argument('--index', type=int, default=0, help='Bluetooth controller index')
    args = parser.parse_args()
    if not shutil.which('btmon'):
        print('btmon unavailable; run on the native Pi with BlueZ tools installed.', file=sys.stderr)
        return 1
    reports = ROOT/'reports'
    reports.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-')
    directory = Path(tempfile.mkdtemp(prefix='ble-'+stamp, dir=reports))
    directory.chmod(0o755)
    print(f'Capture directory: {directory}', flush=True)
    with (directory/'btmon.log').open('w') as monitor_log:
        try:
            monitor = subprocess.Popen(['btmon', '-i', str(args.index), '-w',
                str(directory/'capture.btsnoop')], stdout=monitor_log, stderr=subprocess.STDOUT, cwd=ROOT)
        except OSError as error:
            print(f'Could not start btmon: {error}', file=sys.stderr)
            return 1
        try:
            try:
                monitor.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
            if monitor.poll() is not None:
                print('btmon exited before the probe; inspect btmon.log for permissions/controller errors.', file=sys.stderr)
                return 1
            report_path = reports/'ble-report.json'
            before = report_path.stat() if report_path.exists() else None
            with (directory/'probe.log').open('w') as probe_log:
                result = subprocess.run([sys.executable, '-m', 'bt.client', '--pair', '--target-only',
                    '--read', CHARACTERISTIC, '--address', args.address], cwd=ROOT,
                    stdout=probe_log, stderr=subprocess.STDOUT, timeout=170, check=False)
            after = report_path.stat() if report_path.exists() else None
            if after and (before is None or (after.st_ino, after.st_mtime_ns) !=
                          (before.st_ino, before.st_mtime_ns)):
                shutil.copy2(report_path, directory/'ble-report.json')
            else:
                print('No fresh report was produced; inspect probe.log.', file=sys.stderr)
            if monitor.poll() is not None:
                print('btmon stopped during the probe; capture may be incomplete.', file=sys.stderr)
                return 1
            print('Capture complete. Inspect the saved report for read success or failure.', flush=True)
            return result.returncode
        except subprocess.TimeoutExpired:
            print('Probe process timed out; partial capture retained.', file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print('Capture interrupted; partial files retained.', file=sys.stderr)
            return 130
        finally:
            stop_monitor(monitor)
            # The native Pi user and container user may have different mapped UIDs.
            for artifact in directory.iterdir():
                if artifact.is_file():
                    artifact.chmod(0o644)


if __name__ == '__main__':
    raise SystemExit(main())
