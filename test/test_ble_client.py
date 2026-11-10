import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from bt.client import inspect_device, TARGET_SERVICE, value_details


class BLETests(unittest.IsolatedAsyncioTestCase):
    def client(self, service=TARGET_SERVICE):
        characteristic = SimpleNamespace(uuid='read-uuid', properties=['read'])
        client = SimpleNamespace(services=[SimpleNamespace(uuid=service, characteristics=[characteristic])],
                                 read_gatt_char=AsyncMock(return_value=b'value'))
        context = AsyncMock()
        context.__aenter__.return_value = client
        return context, client

    async def test_automatic_read_and_disconnect(self):
        context, client = self.client()
        events = []
        result = await inspect_device('AA', TARGET_SERVICE, None, False, events.append,
                                      client_factory=lambda *a, **k: context)
        client.read_gatt_char.assert_awaited_once()
        self.assertEqual(result['probes'][0]['text'], 'value')
        self.assertGreaterEqual(result['probes'][0]['elapsed_ms'], 0)
        context.__aexit__.assert_awaited_once()
        self.assertFalse(result['encryption_verified'])
        self.assertEqual(events[-1], 'Disconnected')

    async def test_read_only_explicit_target_characteristic(self):
        context, client = self.client()
        options = {}
        def factory(address, **kwargs):
            options.update(kwargs)
            return context
        result = await inspect_device('AA', TARGET_SERVICE, 'read-uuid', True, lambda x: None, factory)
        self.assertTrue(options['pair'])
        client.read_gatt_char.assert_awaited_once()
        self.assertEqual(result['read']['uuid'], 'read-uuid')
        self.assertEqual(result['read']['bytes'], 5)
        self.assertEqual(result['read']['text'], 'value')

    async def test_wrong_device_and_characteristic_disconnect(self):
        for service, characteristic in [('wrong-service', None), (TARGET_SERVICE, 'wrong-char')]:
            context, client = self.client(service)
            with self.assertRaises(ValueError):
                await inspect_device('AA', TARGET_SERVICE, characteristic, False, lambda x: None,
                                     client_factory=lambda *a, **k: context)
            client.read_gatt_char.assert_not_called()
            context.__aexit__.assert_awaited_once()


class BLEDiagnosticTests(unittest.TestCase):
    def test_dbus_details_are_bounded_and_control_characters_removed(self):
        from bt.client import error_details
        error = Exception('pairing\nfailed\x1b')
        error.dbus_error = 'org.bluez.Error.AuthenticationFailed'
        error.dbus_error_details = 'x'*700
        details = error_details(error)
        self.assertEqual(details['dbus_error'], 'org.bluez.Error.AuthenticationFailed')
        self.assertEqual(details['message'], 'pairing failed ')
        self.assertEqual(len(details['dbus_error_details']), 500)

    def test_failed_session_saves_reason_and_monitor_hint(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from bt.client import run_session
        error = Exception('connection failed')
        error.dbus_error = 'org.bluez.Error.Failed'
        events = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'report.json'
            with patch('bt.client.inspect_device', new=AsyncMock(side_effect=error)), patch('sys.stderr'):
                run_session('AA', TARGET_SERVICE, None, True, events.append, path)
            result = json.loads(path.read_text())
        self.assertEqual(result['message'], 'connection failed')
        self.assertEqual(result['dbus_error'], 'org.bluez.Error.Failed')
        self.assertEqual(events[-1], 'Failed')


class BLEProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_auth_failure_gets_one_normal_connection_attempt(self):
        from unittest.mock import patch
        from bt.client import probe_device
        error = Exception('Authentication Failed')
        error.dbus_error = 'org.bluez.Error.AuthenticationFailed'
        mock = AsyncMock(side_effect=[error, {'services': []}])
        events = []
        with patch('bt.client.inspect_device', new=mock):
            result = await probe_device('AA', TARGET_SERVICE, None, True, events.append)
        self.assertEqual(mock.await_count, 2)
        self.assertTrue(mock.call_args_list[0].args[3])
        self.assertFalse(mock.call_args_list[1].args[3])
        self.assertEqual(result['attempts'][0]['dbus_error'], error.dbus_error)
        self.assertEqual(result['attempts'][1]['outcome'], 'completed')

    async def test_other_errors_do_not_trigger_retries(self):
        from unittest.mock import patch
        from bt.client import probe_device
        with patch('bt.client.inspect_device', new=AsyncMock(side_effect=RuntimeError('failed'))) as mock:
            result = await probe_device('AA', TARGET_SERVICE, None, True, lambda x: None)
        self.assertEqual(mock.await_count, 1)
        self.assertEqual(result['error'], 'RuntimeError')

    async def test_rejected_read_retains_service_metadata(self):
        context, client = BLETests().client()
        client.read_gatt_char.side_effect = RuntimeError('read needs authentication')
        result = await inspect_device('AA', TARGET_SERVICE, None, False, lambda x: None,
                                      client_factory=lambda *a, **k: context)
        self.assertEqual(result['services'][0]['uuid'], TARGET_SERVICE)
        self.assertEqual(result['probes'][0]['error'], 'RuntimeError')
        context.__aexit__.assert_awaited_once()


class BLEValueTests(unittest.TestCase):
    def test_response_capture_is_bounded_and_binary_safe(self):
        result = value_details(b'a'*300)
        self.assertEqual(result['bytes'], 300)
        self.assertEqual(len(result['hex']), 512)
        self.assertEqual(len(result['text']), 256)
        self.assertTrue(result['truncated'])
        self.assertNotIn('text', value_details(b'\xff'))

    def test_native_dbus_errors_are_recognized(self):
        from bt.client import error_details
        error = Exception('pair failed')
        error.type = 'org.bluez.Error.AuthenticationFailed'
        error.text = 'Authentication Failed'
        self.assertEqual(error_details(error)['dbus_error'], error.type)


class BLEControlTests(unittest.IsolatedAsyncioTestCase):
    async def diagnostic_client(self, control_error=None, target_error=None, drop=False, busy=False):
        from bt.client import DEVICE_NAME, GENERIC_ACCESS
        context, client = BLETests().client()
        client.is_connected = True
        control = SimpleNamespace(uuid=DEVICE_NAME, properties=['read'])
        client.services.append(SimpleNamespace(uuid=GENERIC_ACCESS, characteristics=[control]))
        factory_options = {}
        def factory(address, **kwargs):
            factory_options.update(kwargs)
            return context
        async def read(candidate):
            if candidate.uuid == DEVICE_NAME:
                if control_error:
                    raise control_error
                return b'ESP32'
            if drop:
                client.is_connected = False
                factory_options['disconnected_callback'](client)
            if busy:
                import logging
                logging.getLogger('bleak.backends.bluezdbus.client').debug(
                    'retrying characteristic ReadValue due to InProgress')
            if target_error:
                raise target_error
            return b'service information'
        client.read_gatt_char.side_effect = read
        state = AsyncMock(return_value={'Paired': True, 'Connected': True, 'ServicesResolved': True})
        events = []
        result = await inspect_device('AA', TARGET_SERVICE, None, False, events.append,
                                      client_factory=factory, state_reader=state)
        return result, events, client

    async def test_control_success_target_timeout_distinguishes_service_failure(self):
        result, events, client = await self.diagnostic_client(target_error=TimeoutError())
        diag = result['diagnostics']
        self.assertEqual(diag['control_read']['text'], 'ESP32')
        self.assertEqual(diag['assessment'], 'Control OK / target read failed')
        self.assertEqual(result['probes'][0]['error'], 'TimeoutError')
        self.assertTrue(result['probes'][0]['connected_after'])
        self.assertNotIn('Bonded', diag['state_samples'][0])
        self.assertIn('bonded=unknown', ' '.join(events))
        self.assertEqual(client.read_gatt_char.await_count, 2)

    async def test_busy_reply_evidence_is_attached_to_target_timeout(self):
        result, events, _ = await self.diagnostic_client(target_error=TimeoutError(), busy=True)
        probe = result['probes'][0]
        self.assertEqual(probe['transport_trace']['in_progress_retries'], 1)
        self.assertEqual(probe['timeout_evidence'], 'BlueZ returned InProgress repeatedly')
        self.assertTrue(any('BlueZ busy' in message for message in events))

    async def test_both_reads_fail_does_not_blame_target_firmware(self):
        result, _, _ = await self.diagnostic_client(control_error=TimeoutError(), target_error=TimeoutError())
        self.assertEqual(result['diagnostics']['assessment'], 'Both reads failed / cause unresolved')

    async def test_unexpected_disconnect_records_phase(self):
        result, events, _ = await self.diagnostic_client(target_error=RuntimeError('disconnected'), drop=True)
        event = result['diagnostics']['disconnect_events'][0]
        self.assertEqual(event['phase'], 'target_read')
        self.assertFalse(event['expected'])
        self.assertFalse(result['probes'][0]['connected_after'])
        self.assertEqual(result['diagnostics']['assessment'], 'Connection dropped / inspect timing')

    async def test_state_failure_does_not_prevent_gatt_reads(self):
        context, client = BLETests().client()
        result = await inspect_device('AA', TARGET_SERVICE, None, False, lambda x: None,
            client_factory=lambda *a, **k: context, state_reader=AsyncMock(side_effect=PermissionError()))
        self.assertIn('unavailable', result['diagnostics']['state_samples'][0])
        self.assertEqual(result['probes'][0]['bytes'], 5)

    async def test_control_disconnect_skips_target_read(self):
        from bt.client import DEVICE_NAME, GENERIC_ACCESS
        context, client = BLETests().client()
        client.is_connected = True
        client.services.append(SimpleNamespace(uuid=GENERIC_ACCESS, characteristics=[
            SimpleNamespace(uuid=DEVICE_NAME, properties=['read'])]))
        async def read(candidate):
            client.is_connected = False
            return b'ESP32'
        client.read_gatt_char.side_effect = read
        result = await inspect_device('AA', TARGET_SERVICE, None, False, lambda x: None,
                                     client_factory=lambda *a, **k: context)
        client.read_gatt_char.assert_awaited_once()
        self.assertEqual(result['probes'], [])
        self.assertEqual(result['diagnostics']['target_skipped'], 'Connection already dropped')


class BLECheckpointTests(unittest.TestCase):
    def test_session_timeout_keeps_partial_diagnostics(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from bt.client import run_session
        async def timeout(address, service, characteristic, pair, report, checkpoint):
            checkpoint({'services': [{'uuid': service}], 'diagnostics': {'control_read': {'text': 'ESP32'}}})
            raise TimeoutError()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'report.json'
            with patch('bt.client.probe_device', side_effect=timeout):
                run_session('AA', TARGET_SERVICE, None, False, lambda x: None, path)
            result = json.loads(path.read_text())
        self.assertEqual(result['diagnostics']['control_read']['text'], 'ESP32')
        self.assertEqual(result['error'], 'BLE session timed out')


class BLETargetOnlyTests(unittest.IsolatedAsyncioTestCase):
    async def test_target_only_skips_advertised_control(self):
        from bt.client import DEVICE_NAME, GENERIC_ACCESS
        context, client = BLETests().client()
        client.services.append(SimpleNamespace(uuid=GENERIC_ACCESS, characteristics=[
            SimpleNamespace(uuid=DEVICE_NAME, properties=['read'])]))
        result = await inspect_device('AA', TARGET_SERVICE, None, False, lambda x: None,
                                     client_factory=lambda *a, **k: context, target_only=True)
        client.read_gatt_char.assert_awaited_once()
        self.assertEqual(client.read_gatt_char.call_args.args[0].uuid, 'read-uuid')
        self.assertEqual(result['diagnostics']['control_read']['skipped'], 'Target-only capture mode')
