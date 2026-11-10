import asyncio
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from bt.client import cancellable_probe, inspect_device, TARGET_SERVICE
from bt.menu import BluetoothScanner


class CancelTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_during_read_awaits_client_context_cleanup(self):
        entered = asyncio.Event()
        cleaned = asyncio.Event()
        stop = threading.Event()
        async def read(candidate):
            entered.set()
            await asyncio.Event().wait()
        async def exit_context(*args):
            await asyncio.sleep(0)
            cleaned.set()
        client = SimpleNamespace(is_connected=True, services=[SimpleNamespace(uuid=TARGET_SERVICE,
            characteristics=[SimpleNamespace(uuid='read', properties=['read'])])], read_gatt_char=read)
        context = AsyncMock()
        context.__aenter__.return_value = client
        context.__aexit__.side_effect = exit_context
        session = asyncio.create_task(cancellable_probe(inspect_device('AA', TARGET_SERVICE, None,
            False, lambda message: None, client_factory=lambda *a, **kw: context), stop))
        await asyncio.wait_for(entered.wait(), timeout=1)
        stop.set()
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(session, timeout=2)
        self.assertTrue(cleaned.is_set())
        context.__aexit__.assert_awaited_once()


class QuitTests(unittest.TestCase):
    def test_close_cancels_joins_and_disconnects_only_owned_address(self):
        scanner = BluetoothScanner()
        scanner.active_address = '80:B5:4E:E8:B4:69'
        scanner.worker = Mock()
        scanner.worker.is_alive.return_value = False
        with patch('bt.menu.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='', stderr='')) as run, \
             patch('bt.menu.publish_event'):
            scanner.close()
            scanner.close()
        self.assertTrue(scanner.stop_event.is_set())
        scanner.worker.join.assert_called_once_with(timeout=12)
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], ['bluetoothctl', 'disconnect', '80:B5:4E:E8:B4:69'])
        self.assertEqual(scanner.status, 'IDLE')
        scanner.start()
        self.assertTrue(scanner.closing)

    def test_close_does_not_disconnect_unowned_devices(self):
        with patch('bt.menu.subprocess.run') as run, patch('bt.menu.publish_event'):
            BluetoothScanner().close()
        run.assert_not_called()

    def test_disconnect_failure_remains_visible(self):
        scanner = BluetoothScanner()
        scanner.active_address = 'AA'
        with patch('bt.menu.subprocess.run', return_value=SimpleNamespace(returncode=1, stdout='Failed', stderr='')), \
             patch('bt.menu.publish_event'), patch('sys.stderr'):
            scanner.close()
        self.assertEqual(scanner.status, 'ERROR')
        self.assertIn('disconnect unconfirmed', scanner.activity[-1])
