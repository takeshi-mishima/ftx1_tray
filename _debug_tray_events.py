#
# _debug_tray_events.py : log the raw tray mouse messages (diagnostic)
# Run:  python _debug_tray_events.py   (Shift+right click -> menu -> 終了)
#
import time
from ftx1common import (TrayApp, make_icon, rgb, key_down, VK_SHIFT,
                        WM_LBUTTONDOWN, WM_LBUTTONUP, WM_LBUTTONDBLCLK,
                        WM_RBUTTONDOWN, WM_RBUTTONUP, WM_RBUTTONDBLCLK,
                        WM_MBUTTONDOWN, WM_MBUTTONUP, WM_MBUTTONDBLCLK)

NAMES = {WM_LBUTTONDOWN: 'L down', WM_LBUTTONUP: 'L up', WM_LBUTTONDBLCLK: 'L DBLCLK',
         WM_RBUTTONDOWN: 'R down', WM_RBUTTONUP: 'R up', WM_RBUTTONDBLCLK: 'R DBLCLK',
         WM_MBUTTONDOWN: 'C down', WM_MBUTTONUP: 'C up', WM_MBUTTONDBLCLK: 'C DBLCLK'}


class EventLog(TrayApp):
    APP_NAME = 'TrayEventLog'

    def on_start(self):
        self.t0 = time.perf_counter()
        self.set_icon(make_icon([('?', rgb(0xC0, 0x40, 0x00), rgb(0xFF, 0xFF, 0xFF))]),
                      'TrayEventLog')

    def on_tray_event(self, event):
        if event == 0x0200:                     # WM_MOUSEMOVE
            return
        ms = (time.perf_counter() - self.t0) * 1000
        print(f'{ms:9.0f} ms  {NAMES.get(event, hex(event))}', flush=True)
        if event == WM_RBUTTONUP and key_down(VK_SHIFT):
            self.show_menu()

    def on_menu(self, cmd):
        self.quit()


if __name__ == '__main__':
    EventLog().run()
