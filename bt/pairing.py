"""Temporary, target-scoped BlueZ agent for headless Just Works pairing."""
import asyncio


async def pair_device(address, report):
    from dbus_fast import BusType, DBusError
    from dbus_fast.aio import MessageBus
    from dbus_fast.service import ServiceInterface, method

    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    path = '/org/agent_sandbox/pairing'
    manager = None
    registered = False
    target_path = None
    device = None

    class Agent(ServiceInterface):
        def __init__(self):
            super().__init__('org.bluez.Agent1')

        def check(self, device):
            if device != target_path:
                raise DBusError('org.bluez.Error.Rejected', 'Unexpected pairing target')

        @method()
        def Release(self):
            pass

        @method()
        def Cancel(self):
            report('Pairing canceled by BlueZ')

        @method()
        def RequestAuthorization(self, device: 'o'):
            self.check(device)
            report('Authorizing selected ESP32 pairing')

        @method()
        def RequestPinCode(self, device: 'o') -> 's':
            self.check(device)
            report('ESP32 requires a PIN')
            raise DBusError('org.bluez.Error.Rejected', 'PIN required; no PIN configured')

        @method()
        def RequestPasskey(self, device: 'o') -> 'u':
            self.check(device)
            report('ESP32 requires a passkey')
            raise DBusError('org.bluez.Error.Rejected', 'Passkey required; no passkey configured')

        @method()
        def RequestConfirmation(self, device: 'o', passkey: 'u'):
            self.check(device)
            report('ESP32 requires numeric confirmation')
            raise DBusError('org.bluez.Error.Rejected', 'Numeric comparison requires confirmation')

        @method()
        def AuthorizeService(self, device: 'o', uuid: 's'):
            self.check(device)
            raise DBusError('org.bluez.Error.Rejected', 'Unsolicited service authorization')

    try:
        root_xml = await bus.introspect('org.bluez', '/')
        root = bus.get_proxy_object('org.bluez', '/', root_xml)
        objects = await root.get_interface('org.freedesktop.DBus.ObjectManager').call_get_managed_objects()
        for device_path, interfaces in objects.items():
            props = interfaces.get('org.bluez.Device1', {})
            if props.get('Address') and props['Address'].value.upper() == address.upper():
                target_path = device_path
                if props.get('Paired') and props['Paired'].value:
                    report('Existing paired device / connecting')
                    return
                break
        if target_path is None:
            raise ValueError('ESP32 absent from BlueZ; rescan first')
        xml = await bus.introspect('org.bluez', '/org/bluez')
        manager = bus.get_proxy_object('org.bluez', '/org/bluez', xml).get_interface('org.bluez.AgentManager1')
        bus.export(path, Agent())
        await manager.call_register_agent(path, 'NoInputNoOutput')
        registered = True
        # Pair on this same D-Bus connection so BlueZ uses this application's agent.
        xml = await bus.introspect('org.bluez', target_path)
        device = bus.get_proxy_object('org.bluez', target_path, xml).get_interface('org.bluez.Device1')
        report('Pairing with temporary headless agent')
        await asyncio.wait_for(device.call_pair(), timeout=35)
        report('Pairing completed / encryption unverified')
    except asyncio.CancelledError:
        if device is not None:
            for method in (device.call_cancel_pairing, device.call_disconnect):
                try:
                    await asyncio.wait_for(method(), timeout=2)
                except Exception:
                    pass
        raise
    finally:
        if registered:
            try:
                await asyncio.wait_for(manager.call_unregister_agent(path), timeout=2)
            except Exception:
                pass
        bus.unexport(path)
        bus.disconnect()


async def device_state(address):
    """Read BlueZ's public device properties without changing host configuration."""
    from dbus_fast import BusType
    from dbus_fast.aio import MessageBus
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    try:
        xml = await bus.introspect('org.bluez', '/')
        root = bus.get_proxy_object('org.bluez', '/', xml)
        objects = await root.get_interface('org.freedesktop.DBus.ObjectManager').call_get_managed_objects()
        for path, interfaces in objects.items():
            props = interfaces.get('org.bluez.Device1', {})
            if props.get('Address') and props['Address'].value.upper() == address.upper():
                return {key: props[key].value for key in
                        ('Paired', 'Bonded', 'Connected', 'ServicesResolved') if key in props}
        return {'unavailable': 'Device not present in BlueZ'}
    finally:
        bus.disconnect()
