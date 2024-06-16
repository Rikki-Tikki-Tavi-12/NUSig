import asyncio
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window
from prompt_toolkit.widgets import Box, Frame, TextArea, Button, Label, Dialog
from prompt_toolkit.shortcuts import message_dialog, radiolist_dialog, yes_no_dialog, checkboxlist_dialog, button_dialog
from prompt_toolkit.styles import Style
from bleak import BleakScanner, BleakClient
from sys import argv
import NUSconsole

from consts import *

settings = [None, [], [], []]  # Device, Services, Rx Characteristic, Tx Characteristic
aux_settings = {'show_unnamed': False}
all_items = [[], [], [], []]  # Devices, Services, Characteristics Rx, Characteristics Tx
step_index = 0
breadcrumbs = ["Device", "Services", "Rx Characteristics", "Tx Characteristics"]

defaults = ["Nordic_UART_Service", "Nordic UART Service", "Nordic UART TX", "Nordic UART RX"]

def make_breadcrumb_strs():
    str_1 = f" NUSig {VERSION} "
    str_2 = ""
    for i in range(step_index + 1):
        str_1 += "> " + breadcrumbs[i] + " "
    for i in range(step_index + 1, len(breadcrumbs)):
        str_2 += "> " + breadcrumbs[i] + " "
    return str_1, str_2

def truncate_text(text, max_len):
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."

async def spinner():
    spinner_str = ['|', '/', '-', '\\']
    i = 0
    while True:
        yield spinner_str[i]
        await asyncio.sleep(0.1)
        i = (i + 1) % len(spinner_str)

async def get_bluetooth_devices():
    devices = await BleakScanner.discover()
    return devices

async def scan_devices():
    global all_items
    devices = []
    while not devices:
        devices = await get_bluetooth_devices()
        await asyncio.sleep(0.2)
    all_items[0] = devices

async def get_device_services():
    async with BleakClient(settings[0].address) as client:
        services = client.services
        service_dict = [service for service in client.services if hasattr(service, 'characteristics')]
        return service_dict

async def scan_services():
    global all_items
    services = []
    while not services:
        services = await get_device_services()
        await asyncio.sleep(0.2)
    all_items[1] = services

async def get_characteristics():
    global all_items
    selected_services = settings[1]
    all_items[2] = []
    all_items[3] = []
    for service in selected_services:
        for char in service.characteristics:
            if set(char.properties).intersection(READABLE):
                all_items[2].append(char)
            if set(char.properties).intersection(WRITEABLE):
                all_items[3].append(char)

def render_devices():
    if aux_settings['show_unnamed']:
        return ([(i,(device.name or device.address)) for i,device in enumerate(all_items[0])])
    else:
        device_menu = []
        for index, device in enumerate(all_items[0]):
            if device.name:
                device_menu.append((index,device.name))
        return device_menu

def render_services():
    return [(i,str(service)) for i,service in enumerate(all_items[1])]

def render_rx():
    return [(i,str(char)) for i,char in enumerate(all_items[2])]

def render_tx():
    return [(i,str(char)) for i,char in enumerate(all_items[3])]

def cb_dev_menu(key):
    global aux_settings
    if key in SHOW_UNNAMED:
        aux_settings['show_unnamed'] = not aux_settings['show_unnamed']
        return True  # refresh the menu
    return False

async def menu_interaction(make_items_cb, render_menu_cb, info_line, multi_select, key_cb, wait_line):
    msg=button_dialog(wait_line,buttons=[])

    msg_task=asyncio.create_task(msg.run_async())

    if make_items_cb:
        await make_items_cb()
    
    menu = render_menu_cb()

    str_bright, str_dark = make_breadcrumb_strs()

    if multi_select:
        dialog = checkboxlist_dialog(
            title=str_bright+ str_dark,
            text=info_line,
            values=menu,
            default_values=[i for i, s in menu if s.endswith(defaults[step_index])]
        )
        dialog_task = asyncio.create_task(dialog.run_async())
        return await dialog_task
        msg_task.cancel()
    else:
        match_default=[i for i, s in menu if s.endswith(defaults[step_index])] or None
        if match_default:
            match_default=match_default[0]
        dialog = radiolist_dialog(
            title=str_bright+ str_dark,
            text=info_line,
            values=menu,
            default=match_default
            # buttons=[
            #     ("OK", True),
            #     ("Cancel", False)
            # ]
        )
        dialog_task = asyncio.create_task(dialog.run_async())
        sel = await dialog_task
        msg_task.cancel()
        if sel:
            return [sel]
        else:
            return None
        

async def confirm_quit():
    return await yes_no_dialog(
        title="Quit",
        text="Do you really want to quit?"
    ).run_async()

def show_console(loop, client, settings):
    # Implement the function to show console using `prompt_toolkit`
    pass

def main():
    global step_index
    steps = [
        {
            'create_menu_items': scan_devices,
            'render_menu_items': render_devices,
            'keypress_callback': cb_dev_menu,
            'info_line': "Select the desired Bluetooth device",
            'wait_line': "Scanning for Bluetooth devices",
            'multi_select': False
        },
        {
            'create_menu_items': scan_services,
            'render_menu_items': render_services,
            'keypress_callback': None,
            'info_line': "Select the service or services with which to interact",
            'wait_line': "Scanning for services",
            'multi_select': True
        },
        {
            'create_menu_items': get_characteristics,
            'render_menu_items': render_rx,
            'keypress_callback': None,
            'info_line': "Select the characteristics to listen to",
            'wait_line': "Scanning for characteristics",
            'multi_select': True
        },
        {
            'create_menu_items': get_characteristics,
            'render_menu_items': render_tx,
            'keypress_callback': None,
            'info_line': "Select the characteristics to send to",
            'wait_line': "",
            'multi_select': True
        }
    ]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while step_index in range(-1, len(steps) + 1):
        if step_index == -1:
            if not loop.run_until_complete(confirm_quit()):
                step_index = 0
            else:
                break
        elif step_index == len(steps):
            client = BleakClient(settings[0].address)
            NUSconsole.show_console(loop, client, settings)
        else:
            step = steps[step_index]

            selection = loop.run_until_complete(menu_interaction(
                step['create_menu_items'],
                step['render_menu_items'],
                step['info_line'],
                step['multi_select'],
                step['keypress_callback'],
                step['wait_line']
            ))

            if selection:
                if step['multi_select']:
                    settings[step_index]=[all_items[step_index][i] for i in selection]
                else:
                    settings[step_index]=all_items[step_index][selection[0]]
                step_index += 1
            else:
                step_index -= 1

if __name__ == "__main__":
    main()
