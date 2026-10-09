#
# ftx1common.py : FTX-1 tray tool common module
#
# - Config path / rigctld settings
# - rigctld TCP client
# - Minimal Win32 system tray base (ctypes only, no extra libs)
# - Icon drawing
#
# (c) 2026 Takeshi Mishima JK1VUZ
#

import configparser
import ctypes
import ctypes.wintypes as wt
import os
import socket
import sys

# ============================================================
# Config
# ============================================================

def base_dir():
    """Folder of the exe (PyInstaller) or of this script."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


INI_PATH = os.path.join(base_dir(), 'ftx1_tools.ini')


def read_ini():
    cp = configparser.ConfigParser()
    cp.optionxform = str            # keep key case (SWAP, M145, ...)
    cp.read(INI_PATH, encoding='utf-8-sig')
    return cp


class Config:
    def __init__(self):
        cp = read_ini()
        self.host = cp.get('rigctld', 'host', fallback='127.0.0.1')
        self.port = cp.getint('rigctld', 'port', fallback=4534)
        self.timeout = cp.getfloat('rigctld', 'timeout', fallback=3.0)


# ============================================================
# rigctld client
# ============================================================

class RigctldError(Exception):
    pass


def rigctld(cfg, commands):
    """
    Send commands to rigctld over one TCP connection and return the reply
    line of each command.
    Set commands reply "RPRT 0" on success; get commands (e.g. "v") reply
    the value. Any "RPRT <non-zero>" raises RigctldError.
    """
    replies = []
    try:
        with socket.create_connection((cfg.host, cfg.port), timeout=cfg.timeout) as s:
            f = s.makefile('rw', encoding='ascii', newline='\n')
            for cmd in commands:
                f.write(cmd + '\n')
                f.flush()
                line = f.readline()
                if not line:
                    raise RigctldError(f'{cmd}: rigctldが応答せずに切断しました')
                line = line.strip()
                if line.startswith('RPRT'):
                    parts = line.split()
                    if len(parts) < 2 or parts[1] != '0':
                        raise RigctldError(f'{cmd}: {line}')
                replies.append(line)
    except socket.timeout:
        raise RigctldError(f'rigctldの応答がタイムアウトしました（{cfg.timeout}秒）')
    except OSError as e:
        raise RigctldError(f'rigctld ({cfg.host}:{cfg.port}) に接続できません: {e}')
    return replies


def normalize_vfo(reply):
    """rigctld 'v' reply -> 'MAIN' / 'SUB'"""
    r = reply.strip().lower()
    if r in ('main', 'maina', 'vfoa'):
        return 'MAIN'
    if r in ('sub', 'suba', 'vfob'):
        return 'SUB'
    raise RigctldError(f'想定外のVFO応答: {reply}')


# ============================================================
# Win32 API definitions
# ============================================================

user32 = ctypes.WinDLL('user32', use_last_error=True)
shell32 = ctypes.WinDLL('shell32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

WM_NULL = 0x0000
WM_DESTROY = 0x0002
WM_TIMER = 0x0113
WM_LBUTTONDOWN, WM_LBUTTONUP, WM_LBUTTONDBLCLK = 0x0201, 0x0202, 0x0203
WM_RBUTTONDOWN, WM_RBUTTONUP, WM_RBUTTONDBLCLK = 0x0204, 0x0205, 0x0206
WM_MBUTTONDOWN, WM_MBUTTONUP, WM_MBUTTONDBLCLK = 0x0207, 0x0208, 0x0209
WM_APP = 0x8000
WM_TRAY = WM_APP + 1

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x01, 0x02, 0x04, 0x10
NIIF_INFO, NIIF_ERROR = 0x01, 0x03

MF_STRING, MF_GRAYED, MF_SEPARATOR = 0x0000, 0x0001, 0x0800
TPM_RIGHTBUTTON, TPM_RETURNCMD = 0x0002, 0x0100
VK_SHIFT, VK_CONTROL = 0x10, 0x11
SM_CXSMICON = 49
ERROR_ALREADY_EXISTS = 183
MB_ICONWARNING = 0x30

DT_CENTER, DT_VCENTER, DT_SINGLELINE = 0x01, 0x04, 0x20
TRANSPARENT = 1
FW_BOLD = 700
DEFAULT_CHARSET = 1
ANTIALIASED_QUALITY = 4
DIB_RGB_COLORS = 0
BI_RGB = 0


class WNDCLASSW(ctypes.Structure):
    _fields_ = [('style', wt.UINT), ('lpfnWndProc', WNDPROC),
                ('cbClsExtra', ctypes.c_int), ('cbWndExtra', ctypes.c_int),
                ('hInstance', wt.HINSTANCE), ('hIcon', wt.HICON),
                ('hCursor', wt.HANDLE), ('hbrBackground', wt.HBRUSH),
                ('lpszMenuName', wt.LPCWSTR), ('lpszClassName', wt.LPCWSTR)]


class GUID(ctypes.Structure):
    _fields_ = [('Data1', wt.DWORD), ('Data2', wt.WORD), ('Data3', wt.WORD),
                ('Data4', wt.BYTE * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [('cbSize', wt.DWORD), ('hWnd', wt.HWND), ('uID', wt.UINT),
                ('uFlags', wt.UINT), ('uCallbackMessage', wt.UINT),
                ('hIcon', wt.HICON), ('szTip', wt.WCHAR * 128),
                ('dwState', wt.DWORD), ('dwStateMask', wt.DWORD),
                ('szInfo', wt.WCHAR * 256), ('uVersion', wt.UINT),
                ('szInfoTitle', wt.WCHAR * 64), ('dwInfoFlags', wt.DWORD),
                ('guidItem', GUID), ('hBalloonIcon', wt.HICON)]


class ICONINFO(ctypes.Structure):
    _fields_ = [('fIcon', wt.BOOL), ('xHotspot', wt.DWORD), ('yHotspot', wt.DWORD),
                ('hbmMask', wt.HBITMAP), ('hbmColor', wt.HBITMAP)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wt.DWORD), ('biWidth', wt.LONG), ('biHeight', wt.LONG),
                ('biPlanes', wt.WORD), ('biBitCount', wt.WORD),
                ('biCompression', wt.DWORD), ('biSizeImage', wt.DWORD),
                ('biXPelsPerMeter', wt.LONG), ('biYPelsPerMeter', wt.LONG),
                ('biClrUsed', wt.DWORD), ('biClrImportant', wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [('bmiHeader', BITMAPINFOHEADER), ('bmiColors', wt.DWORD * 3)]


def _proto(func, restype, argtypes):
    func.restype = restype
    func.argtypes = argtypes


_proto(user32.RegisterClassW, wt.ATOM, [ctypes.POINTER(WNDCLASSW)])
_proto(user32.CreateWindowExW, wt.HWND,
       [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID])
_proto(user32.DefWindowProcW, LRESULT, [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM])
_proto(user32.DestroyWindow, wt.BOOL, [wt.HWND])
_proto(user32.GetMessageW, wt.BOOL, [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT])
_proto(user32.TranslateMessage, wt.BOOL, [ctypes.POINTER(wt.MSG)])
_proto(user32.DispatchMessageW, LRESULT, [ctypes.POINTER(wt.MSG)])
_proto(user32.PostQuitMessage, None, [ctypes.c_int])
_proto(user32.PostMessageW, wt.BOOL, [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM])
_proto(user32.RegisterWindowMessageW, wt.UINT, [wt.LPCWSTR])
_proto(user32.SetTimer, wt.WPARAM, [wt.HWND, wt.WPARAM, wt.UINT, wt.LPVOID])
_proto(user32.KillTimer, wt.BOOL, [wt.HWND, wt.WPARAM])
_proto(user32.GetDoubleClickTime, wt.UINT, [])
_proto(user32.GetKeyState, wt.SHORT, [ctypes.c_int])
_proto(user32.CreatePopupMenu, wt.HMENU, [])
_proto(user32.AppendMenuW, wt.BOOL, [wt.HMENU, wt.UINT, wt.WPARAM, wt.LPCWSTR])
_proto(user32.TrackPopupMenu, ctypes.c_int,
       [wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.LPVOID])
_proto(user32.DestroyMenu, wt.BOOL, [wt.HMENU])
_proto(user32.GetCursorPos, wt.BOOL, [ctypes.POINTER(wt.POINT)])
_proto(user32.SetForegroundWindow, wt.BOOL, [wt.HWND])
_proto(user32.GetSystemMetrics, ctypes.c_int, [ctypes.c_int])
_proto(user32.FillRect, ctypes.c_int, [wt.HDC, ctypes.POINTER(wt.RECT), wt.HBRUSH])
_proto(user32.DrawTextW, ctypes.c_int,
       [wt.HDC, wt.LPCWSTR, ctypes.c_int, ctypes.POINTER(wt.RECT), wt.UINT])
_proto(user32.CreateIconIndirect, wt.HICON, [ctypes.POINTER(ICONINFO)])
_proto(user32.DestroyIcon, wt.BOOL, [wt.HICON])
_proto(user32.MessageBoxW, ctypes.c_int, [wt.HWND, wt.LPCWSTR, wt.LPCWSTR, wt.UINT])
_proto(user32.SetProcessDPIAware, wt.BOOL, [])
_proto(shell32.Shell_NotifyIconW, wt.BOOL, [wt.DWORD, ctypes.POINTER(NOTIFYICONDATAW)])
_proto(gdi32.CreateCompatibleDC, wt.HDC, [wt.HDC])
_proto(gdi32.DeleteDC, wt.BOOL, [wt.HDC])
_proto(gdi32.CreateDIBSection, wt.HBITMAP,
       [wt.HDC, ctypes.POINTER(BITMAPINFO), wt.UINT, ctypes.POINTER(ctypes.c_void_p),
        wt.HANDLE, wt.DWORD])
_proto(gdi32.CreateBitmap, wt.HBITMAP,
       [ctypes.c_int, ctypes.c_int, wt.UINT, wt.UINT, wt.LPVOID])
_proto(gdi32.SelectObject, wt.HGDIOBJ, [wt.HDC, wt.HGDIOBJ])
_proto(gdi32.DeleteObject, wt.BOOL, [wt.HGDIOBJ])
_proto(gdi32.CreateSolidBrush, wt.HBRUSH, [wt.DWORD])
_proto(gdi32.SetBkMode, ctypes.c_int, [wt.HDC, ctypes.c_int])
_proto(gdi32.SetTextColor, wt.DWORD, [wt.HDC, wt.DWORD])
_proto(gdi32.CreateFontW, wt.HFONT,
       [ctypes.c_int] * 5 + [wt.DWORD] * 8 + [wt.LPCWSTR])
_proto(gdi32.GdiFlush, wt.BOOL, [])
_proto(kernel32.GetModuleHandleW, wt.HMODULE, [wt.LPCWSTR])
_proto(kernel32.CreateMutexW, wt.HANDLE, [wt.LPVOID, wt.BOOL, wt.LPCWSTR])


def rgb(r, g, b):
    return r | (g << 8) | (b << 16)


def key_down(vk):
    return bool(user32.GetKeyState(vk) & 0x8000)


def double_click_ms():
    return user32.GetDoubleClickTime()


# ============================================================
# Icon drawing
# ============================================================

def make_icon(parts, font_ratio=0.8):
    """
    Draw an icon split horizontally into len(parts) cells.
    parts: list of (text, bg_colorref, fg_colorref)
    Returns HICON sized to the system small-icon metric.
    """
    size = user32.GetSystemMetrics(SM_CXSMICON) or 16

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = size
    bmi.bmiHeader.biHeight = -size          # top-down
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB

    bits = ctypes.c_void_p()
    hdc = gdi32.CreateCompatibleDC(None)
    hbm = gdi32.CreateDIBSection(hdc, ctypes.byref(bmi), DIB_RGB_COLORS,
                                 ctypes.byref(bits), None, 0)
    old_bm = gdi32.SelectObject(hdc, hbm)

    font = gdi32.CreateFontW(-int(size * font_ratio), 0, 0, 0, FW_BOLD, 0, 0, 0,
                             DEFAULT_CHARSET, 0, 0, ANTIALIASED_QUALITY, 0, 'Segoe UI')
    old_font = gdi32.SelectObject(hdc, font)
    gdi32.SetBkMode(hdc, TRANSPARENT)

    n = len(parts)
    for i, (text, bg, fg) in enumerate(parts):
        rc = wt.RECT(i * size // n, 0, (i + 1) * size // n, size)
        brush = gdi32.CreateSolidBrush(bg)
        user32.FillRect(hdc, ctypes.byref(rc), brush)
        gdi32.DeleteObject(brush)
        gdi32.SetTextColor(hdc, fg)
        user32.DrawTextW(hdc, text, -1, ctypes.byref(rc),
                         DT_CENTER | DT_VCENTER | DT_SINGLELINE)
    gdi32.GdiFlush()

    # GDI leaves alpha = 0; make every pixel opaque
    pixels = (ctypes.c_uint32 * (size * size)).from_address(bits.value)
    for i in range(size * size):
        pixels[i] |= 0xFF000000

    gdi32.SelectObject(hdc, old_font)
    gdi32.SelectObject(hdc, old_bm)
    gdi32.DeleteObject(font)

    mask_bytes = ctypes.create_string_buffer(((size + 15) // 16) * 2 * size)
    hmask = gdi32.CreateBitmap(size, size, 1, 1, mask_bytes)

    ii = ICONINFO(True, 0, 0, hmask, hbm)
    hicon = user32.CreateIconIndirect(ctypes.byref(ii))

    gdi32.DeleteObject(hmask)
    gdi32.DeleteObject(hbm)
    gdi32.DeleteDC(hdc)
    return hicon


# ============================================================
# Tray application base
# ============================================================

class TrayApp:
    """
    Thin tray base. Subclass and override the hooks:
      on_start()             : set initial icon/tip (before the icon is added)
      on_tray_event(event)   : raw mouse message (WM_LBUTTONDOWN, ...)
      on_timer(tid)          : WM_TIMER
      menu_items()           : list of (id, text) / None for separator
      on_menu(cmd)           : selected menu id
      on_idle()              : called after each dispatched message
    """
    APP_NAME = 'FTX1Tray'

    def __init__(self):
        self.cfg = Config()
        self._mutex = None
        self._hicon = None
        self._tip = ''
        self._wndproc = WNDPROC(self._wnd_proc)   # keep reference
        self.hwnd = None
        self.WM_TASKBARCREATED = user32.RegisterWindowMessageW('TaskbarCreated')

    # ---------- hooks ----------
    def on_start(self):
        pass

    def on_tray_event(self, event):
        pass

    def on_timer(self, tid):
        pass

    def menu_items(self):
        return [(0, '終了')]

    def on_menu(self, cmd):
        pass

    def on_idle(self):
        pass

    # ---------- icon / tooltip / balloon ----------
    def _nid(self, flags):
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = flags
        return nid

    def _add_icon(self):
        nid = self._nid(NIF_MESSAGE | NIF_ICON | NIF_TIP)
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = self._hicon
        nid.szTip = self._tip[:127]
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

    def set_icon(self, hicon, tip=None):
        old = self._hicon
        self._hicon = hicon
        if tip is not None:
            self._tip = tip
        if self.hwnd:
            nid = self._nid(NIF_ICON | NIF_TIP)
            nid.hIcon = self._hicon
            nid.szTip = self._tip[:127]
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
        if old and old != hicon:
            user32.DestroyIcon(old)

    def balloon(self, title, text, error=True):
        nid = self._nid(NIF_INFO)
        nid.szInfoTitle = title[:63]
        nid.szInfo = text[:255]
        nid.dwInfoFlags = NIIF_ERROR if error else NIIF_INFO
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    # ---------- timers / menu / quit ----------
    def set_timer(self, tid, ms):
        user32.SetTimer(self.hwnd, tid, ms, None)

    def kill_timer(self, tid):
        user32.KillTimer(self.hwnd, tid)

    def show_menu(self):
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING | MF_GRAYED, 0, self.APP_NAME)
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        for item in self.menu_items():
            if item is None:
                user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
            else:
                user32.AppendMenuW(menu, MF_STRING, item[0], item[1])
        pt = wt.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self.hwnd)
        cmd = user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_RETURNCMD,
                                    pt.x, pt.y, 0, self.hwnd, None)
        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(menu)
        if cmd:
            self.on_menu(cmd)

    def quit(self):
        user32.DestroyWindow(self.hwnd)

    # ---------- window procedure ----------
    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TRAY:
                self.on_tray_event(lparam & 0xFFFF)
                return 0
            if msg == WM_TIMER:
                self.on_timer(wparam)
                return 0
            if msg == self.WM_TASKBARCREATED:       # Explorer restarted
                self._add_icon()
                return 0
            if msg == WM_DESTROY:
                nid = self._nid(0)
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
                if self._hicon:
                    user32.DestroyIcon(self._hicon)
                user32.PostQuitMessage(0)
                return 0
        except Exception as e:
            self.balloon(self.APP_NAME, f'内部エラー: {e!r}')
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    # ---------- main ----------
    def run(self):
        self._mutex = kernel32.CreateMutexW(None, False, 'Local\\' + self.APP_NAME)
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            user32.MessageBoxW(None, f'{self.APP_NAME} は既に起動しています。',
                               self.APP_NAME, MB_ICONWARNING)
            return

        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = self.APP_NAME
        user32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = user32.CreateWindowExW(0, self.APP_NAME, self.APP_NAME, 0,
                                           0, 0, 0, 0, None, None, hinst, None)

        self.on_start()
        self._add_icon()

        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
            try:
                self.on_idle()
            except Exception as e:
                self.balloon(self.APP_NAME, f'内部エラー: {e!r}')
