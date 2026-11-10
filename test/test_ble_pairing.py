"""Exercise target scoping and cleanup without a host D-Bus connection."""
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from bt.pairing import pair_device


class FakeError(Exception):
    pass


class PairingTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, fail=False):
        address = '80:B5:4E:E8:B4:69'
        path = '/org/bluez/hci0/dev_80_B5_4E_E8_B4_69'
        registered = AsyncMock()
        unregistered = AsyncMock()
        agent = None
        events = []

        async def pair():
            agent.RequestAuthorization(path)
            with self.assertRaises(FakeError):
                agent.RequestAuthorization('/unrelated/device')
            with self.assertRaises(FakeError):
                agent.RequestPasskey(path)
            if fail:
                raise FakeError('org.bluez.Error.AuthenticationFailed', 'failed')

        manager = SimpleNamespace(call_register_agent=registered, call_unregister_agent=unregistered)
        objects = {'org.bluez.Device1': {'Address': SimpleNamespace(value=address),
                                         'Paired': SimpleNamespace(value=False)}}
        interfaces = {
            'org.freedesktop.DBus.ObjectManager': SimpleNamespace(
                call_get_managed_objects=AsyncMock(return_value={path: objects})),
            'org.bluez.AgentManager1': manager,
            'org.bluez.Device1': SimpleNamespace(call_pair=pair)}

        class Bus:
            disconnected = False
            unexported = False
            async def connect(self):
                return self
            async def introspect(self, *args):
                return ''
            def get_proxy_object(self, *args):
                return SimpleNamespace(get_interface=lambda name: interfaces[name])
            def export(self, path, value):
                nonlocal agent
                agent = value
            def unexport(self, path):
                self.unexported = True
            def disconnect(self):
                self.disconnected = True

        bus = Bus()
        class Interface:
            def __init__(self, name):
                pass
        modules = {
            'dbus_fast': SimpleNamespace(BusType=SimpleNamespace(SYSTEM=1), DBusError=FakeError),
            'dbus_fast.aio': SimpleNamespace(MessageBus=lambda **kwargs: bus),
            'dbus_fast.service': SimpleNamespace(ServiceInterface=Interface, method=lambda: lambda f: f)}
        with patch.dict(sys.modules, modules):
            if fail:
                with self.assertRaises(FakeError):
                    await pair_device(address, events.append)
            else:
                await pair_device(address, events.append)
        registered.assert_awaited_once_with('/org/agent_sandbox/pairing', 'NoInputNoOutput')
        unregistered.assert_awaited_once()
        self.assertTrue(bus.disconnected)
        self.assertTrue(bus.unexported)

    async def test_target_scope_and_cleanup_on_success(self):
        await self.exercise()

    async def test_cleanup_on_pairing_failure(self):
        await self.exercise(fail=True)
