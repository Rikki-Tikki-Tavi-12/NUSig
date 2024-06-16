import curses

VERSION = "0.1"
NUS_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"  # Default selection
READABLE = ['notify', 'read']
WRITEABLE = ['write', 'write-without-response']
ESC_KEY = 'escape' # Esc
CONTINUE_KEY = [curses.KEY_ENTER, 13, 10]
REFRESH_KEY = [114]
SHOW_UNNAMED = [115]

text='#cccccc'
white='#ffffff'
black='#181818'
blue='#2472c8'