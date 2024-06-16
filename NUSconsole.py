import asyncio
from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout import HSplit, Layout
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.widgets import TextArea, Label
from prompt_toolkit.styles import Style
from prompt_toolkit.document import Document
from bleak import BleakClient
from consts import *

VERSION = "1.0"  # Assuming VERSION is defined in consts.py

class BLEConsoleApp:
    def __init__(self, loop, client, settings):
        self.settings = settings
        self.ble_client = client
        self.rx_characteristics = settings[2]
        self.tx_characteristics = settings[3]
        self.loop = loop
        style = Style(
            [
                ("output-field", "bg:"+black+" fg:"+text),#"bg:black fg:white"),
                ("title-field", "bg:"+text+" fg:"+black),
                ("input-field", "bg:"+blue)#"bg:#2472c8 fg:white")
            ]
        )
        self.title_area = Label(text=f"NUSig {VERSION} - Connected to {settings[0].name or settings[0].address}", style="class:title-field",)
        self.history_area = TextArea(style="class:output-field", text="")
        self.input_area = TextArea(
            height=1,
            prompt="T> ",
            style="class:input-field",
            multiline=False,
            wrap_lines=False,
            accept_handler=self.on_enter
        )

        container = HSplit(
            [
                self.title_area,
                self.history_area,
                self.input_area
            ]
        )

        self.layout = Layout(container, focused_element=self.input_area)

        self.kb = KeyBindings()
        @self.kb.add(ESC_KEY)
        def _(event):
            event.app.exit()

        self.app = Application(
            layout=self.layout,
            key_bindings=self.kb,
            full_screen=True,
            mouse_support=True,
            style=style
        )
        self.input_buffer = ""

    async def ensure_connected(self):
        client = self.ble_client
        if not client.is_connected:
            try:
                await client.connect()
            except Exception as e:
                raise Exception(f"Connection to device was lost and could not be reestablished: {e}")

    async def initialize_ble_client(self):
        await self.ensure_connected()
        client=self.ble_client
        for i,rx_char in enumerate(self.rx_characteristics):
            try:
                await client.stop_notify(rx_char.handle)
            except:
                pass
            try:
                await client.start_notify(rx_char.handle, self.ble_notification_handler)
            except Exception as err:
                self.append_history("Connection to Rx"+ str(i)+" failed: "+str(err))
            else:
                try:
                    msg = await client.read_gatt_char(rx_char.handle)
                except:
                    msg = ''
                charstr='"'+client.services[rx_char.handle].description + '" (uuid:'+client.services[rx_char.handle].uuid+')'
                if msg:
                    self.append_history("R"+ str(i)+": Connected to "+charstr+". Last Message: "+msg)
                else:
                    self.append_history("R"+ str(i)+": Connected to "+charstr)

    def ble_notification_handler(self, sender, data):
        msg = data.decode('utf-8')
        [self.append_history(f"R{i}> {msg}") for i,snd in enumerate(self.settings[2]) if snd.handle==sender.handle]

    def append_history(self, line):
        area=self.history_area
        bot=False
        bot=self.is_at_bottom(area)
        if area.buffer.text=='': #don't prepend a newline if this is the first line
            nl=''
        else:
            nl='\n'
        area.buffer.document = area.buffer.document.insert_after(nl+line)
        if bot:
            self.scroll_to_bottom(area)

    def is_at_bottom(self,area):
        try:
            lastline=area.window.render_info.window_height+area.window.vertical_scroll
            return (area.document.line_count==lastline)
        except:
            return False
    
    def scroll_to_bottom(self,area):
        #area.window.vertical_scroll=area.document.line_count-area.window.render_info.window_height
        area.buffer.cursor_position=len(area.buffer.text)

    async def handle_user_input(self, input_text):
        await self.ensure_connected()
        self.input_buffer = input_text
        self.append_history(f"Tx> {self.input_buffer}")
        for i,tx_characteristic in enumerate(self.tx_characteristics):
            try:
                await self.ble_client.write_gatt_char(tx_characteristic.handle, bytearray(self.input_buffer, "utf-8"))
            except Exception as err:
                self.append_history("Send failed on Tx"+str(i)+': '+str(err))
            await asyncio.sleep(0.1)
        self.input_area.buffer.document = Document()  # Clear the input field

    def on_enter(self, buff):
        input_text = buff.text
        self.loop.create_task(self.handle_user_input(input_text))

    def quit(self, event):
        asyncio.create_task(self.ble_client.disconnect())
        self.app.exit()

    async def run(self):
        try:
            async with BleakClient(self.settings[0].address) as client:
                self.ble_client = client
                await self.initialize_ble_client()
                await self.app.run_async()
        except:
            pass

def show_console(loop, client, settings):
    app = BLEConsoleApp(loop, client, settings)
    loop.run_until_complete(app.run())

if __name__ == "__main__":
    class dy:  # dummy
        def __init__(self, handle=None, address=None):
            self.handle = handle
            self.name = None
            self.address = address

    DEVICE_ADDRESS = "cb:fa:c2:07:9f:3e"
    SERVICE_HANDLE = 16
    RX_CHARACTERISTIC_HANDLE = 17
    TX_CHARACTERISTIC_HANDLE = 20

    settings = [
        dy(address=DEVICE_ADDRESS),
        [dy(SERVICE_HANDLE)],
        [dy(RX_CHARACTERISTIC_HANDLE)],
        [dy(TX_CHARACTERISTIC_HANDLE)]
    ]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    client = BleakClient(DEVICE_ADDRESS)
    show_console(loop, client, settings)
    loop.close()
    client.disconnect()
