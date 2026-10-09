#
# ftx1_tray.py : FTX-1 tray tool (VS swap + 145/433 FM QSY)  Ver.1.1
#
# Functions:
#   SWAP : swap operating band MAIN <-> SUB
#   VFO  : put the operating band into VFO mode (from memory channel etc.)
#   M145 : MAIN 145.000 FM, operating band = MAIN
#   M433 : MAIN 433.000 FM, operating band = MAIN
#   S145 : SUB  145.000 FM, operating band = SUB
#   S433 : SUB  433.000 FM, operating band = SUB
#   (M/S145, M/S433 also put that side into VFO mode before setting the
#    frequency: the FTX-1 rejects frequency set in memory channel mode.)
#
# Each function is assigned to <BUTTON> <OPE> in the settings dialog
# (menu -> 設定...) and saved in ftx1_tools.ini.
#   BUTTON : L / C (wheel) / R / - (unassigned)
#   OPE    : SGL (single) / DBL (double) / TPL (triple) / CTL (Ctrl+click)
#   (Long press is not supported: the Windows 11 tray sends DOWN and UP
#    together on release, so the press duration cannot be measured.)
# Shift + right click always opens the menu.
#
# (c) 2026 Takeshi Mishima JK1VUZ
#

from ftx1common import (
    TrayApp, INI_PATH, read_ini, make_icon, rgb, rigctld, normalize_vfo,
    ensure_vfo, RigctldError, key_down, double_click_ms, VK_SHIFT, VK_CONTROL,
    WM_LBUTTONDOWN, WM_LBUTTONUP, WM_LBUTTONDBLCLK,
    WM_RBUTTONDOWN, WM_RBUTTONUP, WM_RBUTTONDBLCLK,
    WM_MBUTTONDOWN, WM_MBUTTONUP, WM_MBUTTONDBLCLK,
)

# ------------------------------------------------------------
# Constants
# ------------------------------------------------------------

VERSION = '1.1'

FREQ_145 = 145_000_000
FREQ_433 = 433_000_000
MODE = 'FM'

FUNCS = ['SWAP', 'VFO', 'M145', 'M433', 'S145', 'S433']
BUTTONS = ['L', 'C', 'R']
NONE_LABEL = '-'
OPS = ['SGL', 'DBL', 'TPL', 'CTL']
OP_BY_COUNT = {1: 'SGL', 2: 'DBL', 3: 'TPL'}
# old notation in ini (before v2) -> current
OP_ALIASES = {'SINGLE': 'SGL', 'DOUBLE': 'DBL', 'TRIPLE': 'TPL',
              'CTRL+': 'CTL', 'CTRL': 'CTL'}
# long press was removed -> treated as unassigned
OPS_REMOVED = ('LNG', 'LONG')

DEFAULT_FUNCS = {
    'SWAP': ('C', 'SGL'),
    'VFO': (None, 'SGL'),           # unassigned by default
    'M145': ('R', 'SGL'),
    'M433': ('R', 'DBL'),
    'S145': ('L', 'SGL'),
    'S433': ('L', 'DBL'),
}

TIMER_ID = {'L': 1, 'C': 2, 'R': 3}

EVENTS = {
    WM_LBUTTONDOWN: ('L', 'down'), WM_LBUTTONDBLCLK: ('L', 'down'), WM_LBUTTONUP: ('L', 'up'),
    WM_MBUTTONDOWN: ('C', 'down'), WM_MBUTTONDBLCLK: ('C', 'down'), WM_MBUTTONUP: ('C', 'up'),
    WM_RBUTTONDOWN: ('R', 'down'), WM_RBUTTONDBLCLK: ('R', 'down'), WM_RBUTTONUP: ('R', 'up'),
}

MENU_SETTINGS = 1
MENU_EXIT = 2

# Icon colors
MAIN_ON = rgb(0x1E, 0x5A, 0xC8)      # blue
SUB_ON = rgb(0x1E, 0x8C, 0x3C)       # green
OFF_BG = rgb(0x48, 0x48, 0x48)
OFF_FG = rgb(0xA0, 0xA0, 0xA0)
WHITE = rgb(0xFF, 0xFF, 0xFF)


# ------------------------------------------------------------
# Settings (ini) read / write
# ------------------------------------------------------------

def parse_assign(raw):
    """'L SGL' -> ('L', 'SGL'); '-' -> (None, 'SGL'); invalid -> None"""
    parts = raw.split()
    if not parts:
        return None
    b = parts[0].upper()
    o = parts[1].upper() if len(parts) > 1 else 'SGL'
    o = OP_ALIASES.get(o, o)
    if o in OPS_REMOVED:
        return (None, 'SGL')
    if o not in OPS:
        return None
    if b == NONE_LABEL:
        return (None, o)
    if b not in BUTTONS:
        return None
    return (b, o)


def load_settings():
    cp = read_ini()
    funcs = {}
    used = set()
    for f in FUNCS:
        raw = cp.get('functions', f, fallback=None)
        val = parse_assign(raw) if raw is not None else None
        if val is None:
            val = DEFAULT_FUNCS[f]
        if val[0] is not None:
            if val in used:                 # duplicate -> unassign later one
                val = (None, val[1])
            else:
                used.add(val)
        funcs[f] = val
    return funcs


def save_settings(cfg, funcs):
    lines = [
        '; FTX-1 tray tool settings',
        '; This file is rewritten when OK is pressed in the settings dialog.',
        '',
        '[rigctld]',
        f'host = {cfg.host}',
        f'port = {cfg.port}',
        '; seconds',
        f'timeout = {cfg.timeout}',
        '',
        '[functions]',
        '; <BUTTON> <OPE>',
        ';   BUTTON : L / C / R / -  (- = unassigned)',
        ';   OPE    : SGL / DBL / TPL / CTL (Ctrl+click)',
    ]
    for f in FUNCS:
        b, o = funcs[f]
        lines.append(f'{f} = {b if b else NONE_LABEL} {o}')
    with open(INI_PATH, 'w', encoding='utf-8') as fp:
        fp.write('\n'.join(lines) + '\n')


# ------------------------------------------------------------
# Tray app
# ------------------------------------------------------------

class Ftx1Tray(TrayApp):
    APP_NAME = 'FTX-1 トレイ'
    MENU_TITLE = f'FTX-1 トレイ Ver.{VERSION}'

    def __init__(self):
        super().__init__()
        self.funcs = load_settings()
        self.state = None               # 'MAIN' / 'SUB' / None
        self.last = ''
        self.count = {b: 0 for b in BUTTONS}
        self.settings_open = False
        self.settings_requested = False
        self._rebuild_map()

    # ---------- assignment map ----------
    def _rebuild_map(self):
        self.gmap = {v: f for f, v in self.funcs.items() if v[0] is not None}
        self.maxc = {}
        for b in BUTTONS:
            if (b, 'TPL') in self.gmap:
                self.maxc[b] = 3
            elif (b, 'DBL') in self.gmap:
                self.maxc[b] = 2
            else:
                self.maxc[b] = 1

    def _assign_text(self):
        # one line per group: SWAP VFO / M145 M433 / S145 S433
        lines = []
        for group in (['SWAP', 'VFO'], ['M145', 'M433'], ['S145', 'S433']):
            parts = [f'{f}={self.funcs[f][0]}-{self.funcs[f][1]}'
                     for f in group if self.funcs[f][0] is not None]
            if parts:
                lines.append(' '.join(parts))
        return '\n'.join(lines)

    # ---------- icon ----------
    def update_icon(self):
        s_on = self.state == 'SUB'
        m_on = self.state == 'MAIN'
        icon = make_icon([
            ('S', SUB_ON if s_on else OFF_BG, WHITE if s_on else OFF_FG),
            ('M', MAIN_ON if m_on else OFF_BG, WHITE if m_on else OFF_FG),
        ], font_ratio=0.65)
        tip = f'FTX-1 操作バンド: {self.state or "不明"}\n{self._assign_text()}'
        if self.last:
            tip += f'\n最終: {self.last}'
        self.set_icon(icon, tip)

    # ---------- lifecycle ----------
    def on_start(self):
        # Initial read. No balloon on failure (rigctld may not be up yet).
        try:
            self.state = normalize_vfo(rigctld(self.cfg, ['v'])[0])
        except RigctldError:
            self.state = None
        self.update_icon()

    def menu_items(self):
        return [(MENU_SETTINGS, '設定...'), None, (MENU_EXIT, '終了')]

    def on_menu(self, cmd):
        if cmd == MENU_SETTINGS:
            self.settings_requested = True   # opened from the main loop (on_idle)
        elif cmd == MENU_EXIT:
            self.quit()

    def on_idle(self):
        if self.settings_requested:
            self.settings_requested = False
            self.open_settings()

    # ---------- gesture detection ----------
    def _cancel(self, b):
        self.kill_timer(TIMER_ID[b])
        self.count[b] = 0

    def on_tray_event(self, event):
        if self.settings_open:
            return
        ev = EVENTS.get(event)
        if ev is None:
            return
        b, kind = ev
        if kind == 'down':
            return

        # --- button up ---
        if b == 'R' and key_down(VK_SHIFT):
            self._cancel(b)
            self.show_menu()
            return

        if key_down(VK_CONTROL):
            self._cancel(b)
            self.fire(b, 'CTL')
            return

        self.count[b] += 1
        if self.count[b] >= self.maxc[b]:
            n = self.count[b]
            self._cancel(b)
            self.fire(b, OP_BY_COUNT[n])
        else:
            self.set_timer(TIMER_ID[b], double_click_ms())

    def on_timer(self, tid):
        for b, t in TIMER_ID.items():
            if t == tid:
                n = self.count[b]
                self._cancel(b)
                if n:
                    self.fire(b, OP_BY_COUNT[min(n, 3)])

    # ---------- actions ----------
    def fire(self, b, op):
        func = self.gmap.get((b, op))
        if func is None:
            return
        try:
            self.do_function(func)
        except RigctldError as e:
            self.state = None
            self.last = f'{func} エラー'
            self.update_icon()
            self.balloon(self.APP_NAME, str(e))

    def do_function(self, func):
        if func == 'SWAP':
            current = normalize_vfo(rigctld(self.cfg, ['v'])[0])
            target = 'Sub' if current == 'MAIN' else 'Main'
            replies = rigctld(self.cfg, [f'V {target}', 'v'])
            self.state = normalize_vfo(replies[-1])
            self.last = f'SWAP → {self.state}'
        elif func == 'VFO':
            side = normalize_vfo(rigctld(self.cfg, ['v'])[0])
            self.state = side
            if ensure_vfo(self.cfg, side):
                self.last = f'{side} → VFO'
            else:
                self.last = f'{side} VFO（変更なし）'
        else:
            side = 'Main' if func[0] == 'M' else 'Sub'
            freq = FREQ_145 if func.endswith('145') else FREQ_433
            # V (band) -> VFO mode -> F (frequency) -> M (mode)
            rigctld(self.cfg, [f'V {side}'])
            ensure_vfo(self.cfg, side.upper())
            rigctld(self.cfg, [f'F {freq}', f'M {MODE} 0'])
            self.state = side.upper()
            self.last = f'{self.state} {freq / 1e6:.3f} {MODE}'
        self.update_icon()

    # ---------- settings dialog (tkinter) ----------
    def open_settings(self):
        import tkinter as tk
        from tkinter import ttk, messagebox

        self.settings_open = True
        for b in BUTTONS:
            self._cancel(b)
        try:
            root = tk.Tk()
            root.title(f'{self.APP_NAME} 設定')
            root.resizable(False, False)
            root.attributes('-topmost', True)
            root.attributes('-toolwindow', True)   # close button only

            frm = ttk.Frame(root, padding=12)
            frm.grid()
            for c, t in enumerate(['FUNC', 'BUTTON', 'OPE']):
                ttk.Label(frm, text=t).grid(row=0, column=c, padx=6, pady=(0, 6), sticky='w')

            vars_ = {}
            for r, f in enumerate(FUNCS, start=1):
                b, o = self.funcs[f]
                bv = tk.StringVar(value=b if b else NONE_LABEL)
                ov = tk.StringVar(value=o)
                ttk.Label(frm, text=f).grid(row=r, column=0, padx=6, pady=3, sticky='w')
                ttk.Combobox(frm, textvariable=bv, values=BUTTONS + [NONE_LABEL],
                             state='readonly', width=3).grid(row=r, column=1, padx=6, pady=3,
                                                             sticky='w')
                ttk.Combobox(frm, textvariable=ov, values=OPS,
                             state='readonly', width=4).grid(row=r, column=2, padx=6, pady=3,
                                                             sticky='w')
                vars_[f] = (bv, ov)

            ttk.Label(frm, text='L=左 C=ホイール R=右 -=なし\n'
                                'SGL=1回 DBL=2回 TPL=3回\n'
                                'CTL=Ctrl+クリック\n'
                                'Shift+右クリック=メニュー').grid(
                row=len(FUNCS) + 1, column=0, columnspan=3, padx=6, pady=(8, 0), sticky='w')

            def on_ok():
                new = {}
                seen = {}
                for f, (bv, ov) in vars_.items():
                    b, o = bv.get(), ov.get()
                    if b == NONE_LABEL:
                        new[f] = (None, o)
                        continue
                    key = (b, o)
                    if key in seen:
                        messagebox.showerror(
                            '設定エラー',
                            f'{seen[key]} と {f} が同じ操作（{b} {o}）になっています。',
                            parent=root)
                        return
                    seen[key] = f
                    new[f] = key
                try:
                    save_settings(self.cfg, new)
                except OSError as e:
                    messagebox.showerror('保存エラー', f'{INI_PATH}\n{e}', parent=root)
                    return
                self.funcs = new
                self._rebuild_map()
                self.update_icon()
                root.destroy()

            btns = ttk.Frame(frm)
            btns.grid(row=len(FUNCS) + 2, column=0, columnspan=3, pady=(10, 0), sticky='e')
            ttk.Button(btns, text='OK', command=on_ok).pack(side='left', padx=4)
            ttk.Button(btns, text='キャンセル', command=root.destroy).pack(side='left', padx=4)

            root.focus_force()
            root.mainloop()
        finally:
            self.settings_open = False


if __name__ == '__main__':
    Ftx1Tray().run()
