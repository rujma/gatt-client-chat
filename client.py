import dbus
try:
  from gi.repository import GObject
except ImportError:
  import gobject as GObject
import sys

from dbus.mainloop.glib import DBusGMainLoop

bus = None
mainloop = None

BLUEZ_SERVICE_NAME = 'org.bluez'
DBUS_OM_IFACE =      'org.freedesktop.DBus.ObjectManager'
DBUS_PROP_IFACE =    'org.freedesktop.DBus.Properties'

GATT_SERVICE_IFACE = 'org.bluez.GattService1'
GATT_CHRC_IFACE =    'org.bluez.GattCharacteristic1'

CHAT_SVC_UUID = '0000180d-0000-1000-8000-00805f9b34fb'
CHAT_NOTIFY_UUID = '00002a37-0000-1000-8000-00805f9b34fb'
CHAT_WRITE_UUID = '00002a39-0000-1000-8000-00805f9b34fb'
CHAT_VRS_UUID = '00002a38-0000-1000-8000-00805f9b34fb'

# The objects that we interact with.
chat_service = None
chat_rd_chrc = None
chat_wr_chrc = None

def generic_error_cb(error):
    print('D-Bus call failed: ' + str(error))
    mainloop.quit()

def chat_rd_cb(value):
    print(value)
    chat_wr_chrc[0].WriteValue(value, {}, error_handler=generic_error_cb,dbus_interface=GATT_CHRC_IFACE)

def start_client():
    chat_rd_chrc[0].ReadValue({}, reply_handler=chat_rd_cb, error_handler=generic_error_cb, dbus_interface=GATT_CHRC_IFACE)
    chat_rd_prop_iface = dbus.Interface(chat_rd_chrc[0], DBUS_PROP_IFACE)
    chat_rd_prop_iface.connect_to_signal("PropertiesChanged", chat_rd_cb)
    chat_rd_chrc[0].StartNotify(reply_handler=chat_rd_cb, error_handler=generic_error_cb, dbus_interface=GATT_CHRC_IFACE)

def process_chrc(chrc_path):
    chrc = bus.get_object(BLUEZ_SERVICE_NAME, chrc_path)
    chrc_props = chrc.GetAll(GATT_CHRC_IFACE,
                             dbus_interface=DBUS_PROP_IFACE)

    uuid = chrc_props['UUID']

    if uuid == CHAT_NOTIFY_UUID:
        global chat_rd_chrc
        chat_rd_chrc = (chrc, chrc_props)
    elif uuid == CHAT_WRITE_UUID:
        global chat_wr_chrc
        chat_wr_chrc = (chrc, chrc_props)
    else:
        print('Unrecognized characteristic: ' + uuid)

    return True


def process_chat_service(service_path, chrc_paths):
    service = bus.get_object(BLUEZ_SERVICE_NAME, service_path)
    service_props = service.GetAll(GATT_SERVICE_IFACE,
                                   dbus_interface=DBUS_PROP_IFACE)

    uuid = service_props['UUID']

    if uuid != CHAT_SVC_UUID:
        return False

    print('Chat Service found: ' + service_path)

    # Process the characteristics.
    for chrc_path in chrc_paths:
        process_chrc(chrc_path)

    global hr_service
    hr_service = (service, service_props, service_path)

    return True



def interfaces_removed_cb(object_path, interfaces):
    if not chat_service:
        return

    if object_path == chat_service[2]:
        print('Service was removed')
        mainloop.quit()


def main():
    # Set up the main loop.
    DBusGMainLoop(set_as_default=True)
    global bus
    bus = dbus.SystemBus()
    global mainloop
    mainloop = GObject.MainLoop()

    om = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, '/'), DBUS_OM_IFACE)
    om.connect_to_signal('InterfacesRemoved', interfaces_removed_cb)

    print('Getting objects...')
    objects = om.GetManagedObjects()
    chrcs = []

    # List characteristics found
    for path, interfaces in objects.items():
        if GATT_CHRC_IFACE not in interfaces.keys():
            continue
        chrcs.append(path)

    # List sevices found
    for path, interfaces in objects.items():
        if GATT_SERVICE_IFACE not in interfaces.keys():
            continue

        chrc_paths = [d for d in chrcs if d.startswith(path + "/")]

        print("Found in path: ", path)

        if process_chat_service(path, chrc_paths):
            break

    if not chat_service:
        print('No Chat Service found')
        sys.exit(1)

    start_client()

    mainloop.run()


if __name__ == '__main__':
    main()
