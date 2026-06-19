import M5
from M5 import *
import time
import gc
WIFI_SSID = "ElTigreJr"
WIFI_PASS = "Byebucho25$"
M5.begin()
M5.Lcd.setRotation(1)
W = M5.Lcd.width()
H = M5.Lcd.height()
C_BG = 0x001433
C_BG2 = 0x002255
C_TXT = 0xFFFFFF
C_DIM = 0x99AACC
C_SEL = 0x00CFFF
C_SELBG = 0x003D66
C_OK = 0x33FF99
C_WARN = 0xFF5555
C_BAR = 0x113355
LH = 16
PAD = 6
def safe_call(fn, *args):
    try:
        fn(*args)
        return True
    except Exception:
        return False
def lcd_fill(color):
    safe_call(M5.Lcd.fillScreen, color)
def lcd_rect(x, y, w, h, color):
    if not safe_call(M5.Lcd.fillRect, x, y, w, h, color):
        safe_call(M5.Lcd.drawRect, x, y, w, h, color)
def lcd_rect_outline(x, y, w, h, color):
    safe_call(M5.Lcd.drawRect, x, y, w, h, color)
def lcd_text(x, y, s, color, size=1):
    if not safe_call(M5.Lcd.setTextColor, color):
        safe_call(M5.Lcd.setTextColor, color, C_BG)
    safe_call(M5.Lcd.setTextSize, size)
    safe_call(M5.Lcd.setCursor, x, y)
    safe_call(M5.Lcd.print, s)
def text_w(s, size=1):
    return len(s) * 6 * size
def truncate_to_width(s, max_w, size=1):
    cw = 6 * size
    max_chars = max(1, max_w // cw)
    if len(s) <= max_chars:
        return s
    if max_chars <= 1:
        return s[:1]
    return s[:max_chars - 1] + "."
def wrap_text(s, max_w, size=1):
    cw = 6 * size
    max_chars = max(1, max_w // cw)
    words = s.split(" ")
    lines = []
    cur = ""
    for w in words:
        if cur == "":
            trial = w
        else:
            trial = cur + " " + w
        if len(trial) <= max_chars:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            while len(w) > max_chars:
                lines.append(w[:max_chars])
                w = w[max_chars:]
            cur = w
    if cur:
        lines.append(cur)
    if not lines:
        lines = [""]
    return lines
class Scroller:
    def __init__(self, top_y, bottom_y):
        self.top_y = top_y
        self.bottom_y = bottom_y
        self.offset = 0
        self.content_h = 0
    def view_h(self):
        return self.bottom_y - self.top_y
    def max_offset(self):
        m = self.content_h - self.view_h()
        if m < 0:
            m = 0
        return m
    def clamp(self):
        if self.offset < 0:
            self.offset = 0
        mo = self.max_offset()
        if self.offset > mo:
            self.offset = mo
    def scroll_down(self, amount=LH):
        self.offset += amount
        self.clamp()
    def scroll_up(self, amount=LH):
        self.offset -= amount
        self.clamp()
    def y_for(self, abs_y):
        return self.top_y + (abs_y - self.offset)
    def visible(self, abs_y, h=LH):
        sy = self.y_for(abs_y)
        return (sy + h) > self.top_y and sy < self.bottom_y
    def draw_scrollbar(self):
        if self.content_h <= self.view_h():
            return
        track_x = W - 4
        track_h = self.view_h()
        lcd_rect(track_x, self.top_y, 3, track_h, C_BAR)
        thumb_h = max(8, int(track_h * (self.view_h() / self.content_h)))
        max_off = self.max_offset()
        if max_off > 0:
            thumb_y = self.top_y + int((track_h - thumb_h) * (self.offset / max_off))
        else:
            thumb_y = self.top_y
        lcd_rect(track_x, thumb_y, 3, thumb_h, C_SEL)
def draw_header(title):
    lcd_rect(0, 0, W, 18, C_BG2)
    lcd_text(PAD, 4, truncate_to_width(title, W - 2 * PAD), C_TXT, 1)
    lcd_rect(0, 18, W, 1, C_SEL)
def draw_footer(left_hint, right_hint):
    y = H - 14
    lcd_rect(0, y, W, 14, C_BG2)
    lcd_rect(0, y, W, 1, C_SEL)
    lt = truncate_to_width(left_hint, W // 2 - PAD)
    rt = truncate_to_width(right_hint, W // 2 - PAD)
    lcd_text(PAD, y + 3, lt, C_DIM, 1)
    rw = text_w(rt)
    lcd_text(W - PAD - rw, y + 3, rt, C_DIM, 1)
class VFS:
    def __init__(self):
        self.root = {"type": "dir", "name": "/", "children": {}}
    def _split(self, path):
        path = path.strip("/")
        if path == "":
            return []
        return path.split("/")
    def _resolve_dir(self, parts, create=False):
        node = self.root
        for p in parts:
            if p not in node["children"]:
                if create:
                    node["children"][p] = {"type": "dir", "name": p, "children": {}}
                else:
                    return None
            node = node["children"][p]
            if node["type"] != "dir":
                return None
        return node
    def mkdir(self, path):
        parts = self._split(path)
        if not parts:
            return False, "bad name"
        parent = self._resolve_dir(parts[:-1], create=True)
        if parent is None:
            return False, "bad path"
        name = parts[-1]
        if name in parent["children"]:
            return False, "exists"
        parent["children"][name] = {"type": "dir", "name": name, "children": {}}
        return True, "ok"
    def mkfile(self, path, content=""):
        parts = self._split(path)
        if not parts:
            return False, "bad name"
        parent = self._resolve_dir(parts[:-1], create=True)
        if parent is None:
            return False, "bad path"
        name = parts[-1]
        if name in parent["children"]:
            return False, "exists"
        parent["children"][name] = {"type": "file", "name": name, "content": content}
        return True, "ok"
    def write(self, path, content):
        parts = self._split(path)
        if not parts:
            return False, "bad name"
        parent = self._resolve_dir(parts[:-1], create=True)
        if parent is None:
            return False, "bad path"
        name = parts[-1]
        node = parent["children"].get(name)
        if node is None or node["type"] != "file":
            parent["children"][name] = {"type": "file", "name": name, "content": content}
        else:
            node["content"] = content
        return True, "ok"
    def read(self, path):
        parts = self._split(path)
        if not parts:
            return None
        parent = self._resolve_dir(parts[:-1])
        if parent is None:
            return None
        name = parts[-1]
        node = parent["children"].get(name)
        if node is None or node["type"] != "file":
            return None
        return node["content"]
    def move(self, src, dst_dir):
        sparts = self._split(src)
        if not sparts:
            return False, "bad src"
        sparent = self._resolve_dir(sparts[:-1])
        if sparent is None:
            return False, "no src dir"
        sname = sparts[-1]
        if sname not in sparent["children"]:
            return False, "no such file"
        target = self._resolve_dir(self._split(dst_dir), create=True)
        if target is None:
            return False, "bad dest"
        node = sparent["children"].pop(sname)
        target["children"][node["name"]] = node
        return True, "ok"
    def list(self, path=""):
        node = self._resolve_dir(self._split(path))
        if node is None:
            return None
        items = []
        for k, v in node["children"].items():
            items.append((k, v["type"]))
        items.sort()
        return items
    def all_paths(self):
        out = []
        def walk(node, prefix):
            for k, v in node["children"].items():
                p = prefix + "/" + k
                out.append((p, v["type"]))
                if v["type"] == "dir":
                    walk(v, p)
        walk(self.root, "")
        return out
fs = VFS()
fs.mkdir("/notes")
fs.mkdir("/incoming")
fs.mkfile("/notes/readme.txt", "M5OS demo file system. Lives in RAM only.")
boot_time = time.time()
STATE_BOOT = 0
STATE_MENU = 1
STATE_CMD = 2
STATE_CLOCK = 3
STATE_BATTERY = 4
STATE_FILES = 5
STATE_WIFI = 6
STATE_TRANSFER = 7
state = STATE_BOOT
MENU_ITEMS = [
    "CMD",
    "Clock",
    "Battery",
    "File Explorer",
    "WiFi Setup",
    "Transfer Mode",
]
menu_index = 0
menu_scroller = None
files_path = ""
files_index = 0
files_scroller = None
cmd_log = []
cmd_scroller = None
serial_buf = ""
wifi_ssid = WIFI_SSID
wifi_pass = WIFI_PASS
wifi_status = "not connected"
transfer_files = []
transfer_view_index = None
transfer_scroller = None
def now_str():
    t = time.localtime()
    return "%02d:%02d:%02d" % (t[3], t[4], t[5])
def date_str():
    t = time.localtime()
    return "%04d-%02d-%02d" % (t[0], t[1], t[2])
def uptime_str():
    s = int(time.time() - boot_time)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return "%02d:%02d:%02d" % (h, m, sec)
def get_battery_level():
    for name in ("getBatteryLevel", "getBatteryPercentage"):
        fn = getattr(M5.Power, name, None)
        if fn is not None:
            try:
                return int(fn())
            except Exception:
                pass
    return None
def get_battery_voltage():
    fn = getattr(M5.Power, "getBatteryVoltage", None)
    if fn is not None:
        try:
            return fn()
        except Exception:
            return None
    return None
def is_charging():
    fn = getattr(M5.Power, "isCharging", None)
    if fn is not None:
        try:
            return bool(fn())
        except Exception:
            return None
    return None
def get_ram_info():
    free = gc.mem_free() if hasattr(gc, "mem_free") else None
    alloc = gc.mem_alloc() if hasattr(gc, "mem_alloc") else None
    return free, alloc
def render_boot():
    lcd_fill(C_BG)
    msg1 = "M5OS"
    msg2 = "press front button"
    msg3 = "to start"
    lcd_text((W - text_w(msg1, 2)) // 2, H // 2 - 26, msg1, C_SEL, 2)
    lcd_text((W - text_w(msg2)) // 2, H // 2, msg2, C_TXT, 1)
    lcd_text((W - text_w(msg3)) // 2, H // 2 + 14, msg3, C_TXT, 1)
def render_menu():
    lcd_fill(C_BG)
    draw_header("M5OS Menu")
    top = 22
    bottom = H - 16
    global menu_scroller
    if menu_scroller is None:
        menu_scroller = Scroller(top, bottom)
    menu_scroller.content_h = len(MENU_ITEMS) * LH
    menu_scroller.top_y = top
    menu_scroller.bottom_y = bottom
    sel_abs_y = menu_index * LH
    sel_screen_y = menu_scroller.y_for(sel_abs_y)
    if sel_screen_y < top:
        menu_scroller.offset = sel_abs_y
    elif sel_screen_y + LH > bottom:
        menu_scroller.offset = sel_abs_y + LH - (bottom - top)
    menu_scroller.clamp()
    for i, item in enumerate(MENU_ITEMS):
        abs_y = i * LH
        if not menu_scroller.visible(abs_y):
            continue
        sy = menu_scroller.y_for(abs_y)
        if i == menu_index:
            lcd_rect(0, sy, W - 6, LH, C_SELBG)
            lcd_text(PAD, sy + 4, truncate_to_width(item, W - 2 * PAD - 6), C_SEL, 1)
        else:
            lcd_text(PAD, sy + 4, truncate_to_width(item, W - 2 * PAD - 6), C_TXT, 1)
    menu_scroller.draw_scrollbar()
    draw_footer("KEY2:move", "OK:select")
def cmd_add_line(s):
    for line in s.split("\n"):
        cmd_log.append(line)
    if len(cmd_log) > 300:
        del cmd_log[0:len(cmd_log) - 300]
def run_cmd(raw):
    raw = raw.strip()
    if raw == "":
        return
    cmd_add_line("> " + raw)
    parts = raw.split(" ")
    name = parts[0].lower()
    args = parts[1:]
    if name == "help":
        cmd_add_line("clk - show clock")
        cmd_add_line("ram - show ram usage")
        cmd_add_line("help - show commands")
        cmd_add_line("mkdir <path> - make folder")
        cmd_add_line("mkfile <path> - make file")
        cmd_add_line("ls [path] - list folder")
        cmd_add_line("mv <file> <dir> - move file to folder")
        cmd_add_line("cat <path> - show file content")
        cmd_add_line("write <path> <text> - set file content")
        cmd_add_line("clear - clear log")
    elif name == "clk":
        cmd_add_line(now_str() + "  " + date_str())
    elif name == "ram":
        free, alloc = get_ram_info()
        if free is None:
            cmd_add_line("ram info unavailable")
        else:
            total = free + alloc
            cmd_add_line("free: %d bytes" % free)
            cmd_add_line("used: %d bytes" % alloc)
            cmd_add_line("total: %d bytes" % total)
    elif name == "mkdir":
        if not args:
            cmd_add_line("usage: mkdir <path>")
        else:
            ok, msg = fs.mkdir(args[0])
            cmd_add_line("mkdir: " + msg)
    elif name == "mkfile":
        if not args:
            cmd_add_line("usage: mkfile <path>")
        else:
            ok, msg = fs.mkfile(args[0])
            cmd_add_line("mkfile: " + msg)
    elif name == "ls":
        target = args[0] if args else ""
        items = fs.list(target)
        if items is None:
            cmd_add_line("no such folder")
        elif not items:
            cmd_add_line("(empty)")
        else:
            for nm, tp in items:
                tag = "/" if tp == "dir" else ""
                cmd_add_line(nm + tag)
    elif name == "mv":
        if len(args) < 2:
            cmd_add_line("usage: mv <file> <dir>")
        else:
            ok, msg = fs.move(args[0], args[1])
            cmd_add_line("mv: " + msg)
    elif name == "cat":
        if not args:
            cmd_add_line("usage: cat <path>")
        else:
            content = fs.read(args[0])
            if content is None:
                cmd_add_line("no such file")
            else:
                cmd_add_line(content)
    elif name == "write":
        if len(args) < 2:
            cmd_add_line("usage: write <path> <text>")
        else:
            text_val = " ".join(args[1:])
            ok, msg = fs.write(args[0], text_val)
            cmd_add_line("write: " + msg)
    elif name == "clear":
        cmd_log.clear()
    else:
        cmd_add_line("unknown command: " + name)
        cmd_add_line("type help for list")
def render_cmd():
    lcd_fill(C_BG)
    draw_header("CMD - Serial REPL")
    top = 22
    bottom = H - 16
    global cmd_scroller
    if cmd_scroller is None:
        cmd_scroller = Scroller(top, bottom)
    cmd_scroller.top_y = top
    cmd_scroller.bottom_y = bottom
    max_w = W - 2 * PAD - 6
    all_wrapped = []
    for line in cmd_log:
        for wl in wrap_text(line, max_w):
            all_wrapped.append(wl)
    if not all_wrapped:
        all_wrapped = ["type 'help' over serial REPL"]
    cmd_scroller.content_h = len(all_wrapped) * LH
    cmd_scroller.offset = max(0, cmd_scroller.content_h - cmd_scroller.view_h())
    cmd_scroller.clamp()
    for i, line in enumerate(all_wrapped):
        abs_y = i * LH
        if not cmd_scroller.visible(abs_y):
            continue
        sy = cmd_scroller.y_for(abs_y)
        lcd_text(PAD, sy + 3, line, C_TXT, 1)
    cmd_scroller.draw_scrollbar()
    draw_footer("use serial", "BACK:menu")
def render_clock():
    lcd_fill(C_BG)
    draw_header("Clock")
    t1 = now_str()
    t2 = date_str()
    t3 = "uptime " + uptime_str()
    lcd_text((W - text_w(t1, 2)) // 2, 40, t1, C_SEL, 2)
    lcd_text((W - text_w(t2)) // 2, 70, t2, C_TXT, 1)
    lcd_text((W - text_w(t3)) // 2, 90, t3, C_DIM, 1)
    draw_footer("auto-refresh", "BACK:menu")
def render_battery():
    lcd_fill(C_BG)
    draw_header("Battery")
    level = get_battery_level()
    volt = get_battery_voltage()
    chg = is_charging()
    y = 26
    if level is not None:
        lcd_text(PAD, y, "Level: %d%%" % level, C_TXT, 1)
        y += LH
        bar_w = W - 2 * PAD - 6
        bar_h = 14
        lcd_rect_outline(PAD, y, bar_w, bar_h, C_DIM)
        fill_w = int((bar_w - 4) * max(0, min(100, level)) / 100)
        color = C_OK if level > 30 else C_WARN
        if fill_w > 0:
            lcd_rect(PAD + 2, y + 2, fill_w, bar_h - 4, color)
        y += bar_h + 8
    else:
        lcd_text(PAD, y, "Level: unavailable", C_DIM, 1)
        y += LH
    if volt is not None:
        try:
            lcd_text(PAD, y, "Voltage: %.2fV" % volt, C_TXT, 1)
        except Exception:
            lcd_text(PAD, y, "Voltage: " + str(volt), C_TXT, 1)
        y += LH
    else:
        lcd_text(PAD, y, "Voltage: unavailable", C_DIM, 1)
        y += LH
    if chg is None:
        lcd_text(PAD, y, "Charging: unknown", C_DIM, 1)
    elif chg:
        lcd_text(PAD, y, "Charging: yes", C_OK, 1)
    else:
        lcd_text(PAD, y, "Charging: no", C_TXT, 1)
    draw_footer("auto-refresh", "BACK:menu")
def render_files():
    lcd_fill(C_BG)
    title = "Files: /" + files_path if files_path else "Files: /"
    draw_header(title)
    top = 22
    bottom = H - 16
    global files_scroller
    if files_scroller is None:
        files_scroller = Scroller(top, bottom)
    files_scroller.top_y = top
    files_scroller.bottom_y = bottom
    items = fs.list(files_path)
    if items is None:
        items = []
    display_items = []
    if files_path != "":
        display_items.append(("..", "up"))
    display_items.extend(items)
    files_scroller.content_h = len(display_items) * LH
    global files_index
    if files_index >= len(display_items):
        files_index = max(0, len(display_items) - 1)
    sel_abs_y = files_index * LH
    sel_screen_y = files_scroller.y_for(sel_abs_y)
    if sel_screen_y < top:
        files_scroller.offset = sel_abs_y
    elif sel_screen_y + LH > bottom:
        files_scroller.offset = sel_abs_y + LH - (bottom - top)
    files_scroller.clamp()
    if not display_items:
        lcd_text(PAD, top + 4, "(empty folder)", C_DIM, 1)
    else:
        for i, (nm, tp) in enumerate(display_items):
            abs_y = i * LH
            if not files_scroller.visible(abs_y):
                continue
            sy = files_scroller.y_for(abs_y)
            if tp == "dir":
                label = "[DIR] " + nm
                color = C_SEL
            elif tp == "up":
                label = "[..] back"
                color = C_DIM
            else:
                label = nm
                color = C_TXT
            label = truncate_to_width(label, W - 2 * PAD - 6)
            if i == files_index:
                lcd_rect(0, sy, W - 6, LH, C_SELBG)
                lcd_text(PAD, sy + 4, label, C_SEL, 1)
            else:
                lcd_text(PAD, sy + 4, label, color, 1)
    files_scroller.draw_scrollbar()
    draw_footer("KEY2:move", "OK:open")
def files_enter():
    global files_path, files_index, state
    items = fs.list(files_path)
    if items is None:
        items = []
    display_items = []
    if files_path != "":
        display_items.append(("..", "up"))
    display_items.extend(items)
    if not display_items:
        return
    if files_index >= len(display_items):
        return
    nm, tp = display_items[files_index]
    if tp == "up":
        parts = files_path.split("/")
        files_path = "/".join(parts[:-1])
        files_index = 0
    elif tp == "dir":
        files_path = (files_path + "/" + nm) if files_path else nm
        files_index = 0
    else:
        full = (files_path + "/" + nm) if files_path else nm
        content = fs.read(full)
        view_file_content(full, content)
view_file_path = None
view_file_lines = []
view_scroller = None
def view_file_content(path, content):
    global view_file_path, view_file_lines, view_scroller, state
    view_file_path = path
    if content is None:
        content = ""
    lines = []
    max_w = W - 2 * PAD - 6
    for raw_line in content.split("\n"):
        for wl in wrap_text(raw_line, max_w):
            lines.append(wl)
    view_file_lines = lines if lines else [""]
    view_scroller = None
    state = STATE_VIEWFILE
STATE_VIEWFILE = 99
def render_viewfile():
    lcd_fill(C_BG)
    draw_header("File: " + truncate_to_width(view_file_path or "", W - 70))
    top = 22
    bottom = H - 16
    global view_scroller
    if view_scroller is None:
        view_scroller = Scroller(top, bottom)
    view_scroller.top_y = top
    view_scroller.bottom_y = bottom
    view_scroller.content_h = len(view_file_lines) * LH
    for i, line in enumerate(view_file_lines):
        abs_y = i * LH
        if not view_scroller.visible(abs_y):
            continue
        sy = view_scroller.y_for(abs_y)
        lcd_text(PAD, sy + 3, line, C_TXT, 1)
    view_scroller.draw_scrollbar()
    draw_footer("KEY2:scroll", "BACK:files")
def render_wifi():
    lcd_fill(C_BG)
    draw_header("WiFi Setup")
    y = 26
    ssid_show = wifi_ssid if wifi_ssid else "(not set)"
    lcd_text(PAD, y, "SSID:", C_DIM, 1)
    y += LH
    lcd_text(PAD, y, truncate_to_width(ssid_show, W - 2 * PAD), C_TXT, 1)
    y += LH + 4
    lcd_text(PAD, y, "Status:", C_DIM, 1)
    y += LH
    color = C_OK if wifi_status == "connected" else C_WARN if wifi_status == "failed" else C_DIM
    lcd_text(PAD, y, truncate_to_width(wifi_status, W - 2 * PAD), color, 1)
    y += LH + 8
    lcd_text(PAD, y, "Set WIFI_SSID/WIFI_PASS", C_DIM, 1)
    y += LH
    lcd_text(PAD, y, "at top of script", C_DIM, 1)
    draw_footer("OK:retry connect", "BACK:menu")
def try_wifi_connect():
    global wifi_status
    if not wifi_ssid:
        wifi_status = "no ssid set"
        return
    try:
        import network
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        sta.connect(wifi_ssid, wifi_pass)
        wifi_status = "connecting..."
        render_wifi()
        tries = 0
        while not sta.isconnected() and tries < 20:
            time.sleep_ms(250)
            tries += 1
        if sta.isconnected():
            wifi_status = "connected"
        else:
            wifi_status = "failed"
    except Exception:
        wifi_status = "failed"
def render_transfer():
    lcd_fill(C_BG)
    draw_header("Transfer Mode")
    top = 22
    bottom = H - 16
    global transfer_scroller
    if transfer_scroller is None:
        transfer_scroller = Scroller(top, bottom)
    transfer_scroller.top_y = top
    transfer_scroller.bottom_y = bottom
    lines = []
    lines.append("USB serial transfer.")
    lines.append("On PC run a script that")
    lines.append("sends:")
    lines.append("FILE:<name>:<text>")
    lines.append("over serial to load a")
    lines.append(".txt file here.")
    lines.append("")
    lines.append("Received files:")
    if not transfer_files:
        lines.append("(none yet)")
    else:
        for nm in transfer_files:
            lines.append("- " + nm)
    wrapped = []
    max_w = W - 2 * PAD - 6
    for line in lines:
        for wl in wrap_text(line, max_w):
            wrapped.append(wl)
    transfer_scroller.content_h = len(wrapped) * LH
    for i, line in enumerate(wrapped):
        abs_y = i * LH
        if not transfer_scroller.visible(abs_y):
            continue
        sy = transfer_scroller.y_for(abs_y)
        lcd_text(PAD, sy + 3, line, C_TXT, 1)
    transfer_scroller.draw_scrollbar()
    draw_footer("KEY2:scroll", "BACK:menu")
def handle_serial_input():
    global serial_buf
    try:
        import sys
        import select
        poller = select.poll()
        poller.register(sys.stdin, select.POLLIN)
        events = poller.poll(0)
        if events:
            ch = sys.stdin.read(1)
            if ch:
                if ch == "\n" or ch == "\r":
                    if serial_buf.strip():
                        if serial_buf.startswith("FILE:"):
                            handle_incoming_file(serial_buf)
                        else:
                            run_cmd(serial_buf)
                    serial_buf = ""
                else:
                    serial_buf += ch
    except Exception:
        pass
def handle_incoming_file(line):
    try:
        rest = line[len("FILE:"):]
        idx = rest.find(":")
        if idx == -1:
            return
        fname = rest[:idx]
        content = rest[idx + 1:]
        if not fname.endswith(".txt"):
            fname = fname + ".txt"
        path = "/incoming/" + fname
        fs.write(path, content)
        if fname not in transfer_files:
            transfer_files.append(fname)
        cmd_add_line("received file: " + fname)
    except Exception:
        pass
def btnB_was_pressed():
    if hasattr(M5.BtnB, "wasPressed"):
        try:
            return M5.BtnB.wasPressed()
        except Exception:
            pass
    if hasattr(M5.BtnB, "isPressed"):
        try:
            return M5.BtnB.isPressed()
        except Exception:
            pass
    return False
def btnA_was_pressed():
    if hasattr(M5.BtnA, "wasPressed"):
        try:
            return M5.BtnA.wasPressed()
        except Exception:
            pass
    if hasattr(M5.BtnA, "isPressed"):
        try:
            return M5.BtnA.isPressed()
        except Exception:
            pass
    return False
def btnC_was_pressed():
    if hasattr(M5, "BtnC") and hasattr(M5.BtnC, "wasPressed"):
        try:
            return M5.BtnC.wasPressed()
        except Exception:
            return False
    return False
render_boot()
last_clock_tick = time.time()
needs_redraw = True
while True:
    M5.update()
    if state == STATE_BOOT:
        if btnA_was_pressed():
            state = STATE_MENU
            needs_redraw = True
    elif state == STATE_MENU:
        if btnB_was_pressed():
            menu_index = (menu_index + 1) % len(MENU_ITEMS)
            needs_redraw = True
        if btnA_was_pressed():
            choice = MENU_ITEMS[menu_index]
            if choice == "CMD":
                state = STATE_CMD
                cmd_scroller = None
                if not cmd_log:
                    cmd_add_line("M5OS CMD ready.")
                    cmd_add_line("Connect serial REPL")
                    cmd_add_line("and type 'help'.")
            elif choice == "Clock":
                state = STATE_CLOCK
            elif choice == "Battery":
                state = STATE_BATTERY
            elif choice == "File Explorer":
                state = STATE_FILES
                files_scroller = None
            elif choice == "WiFi Setup":
                state = STATE_WIFI
            elif choice == "Transfer Mode":
                state = STATE_TRANSFER
                transfer_scroller = None
            needs_redraw = True
    elif state == STATE_CMD:
        handle_serial_input()
        if btnB_was_pressed():
            cmd_scroller.scroll_down() if cmd_scroller else None
            needs_redraw = True
        if btnA_was_pressed():
            state = STATE_MENU
            needs_redraw = True
        needs_redraw = True
    elif state == STATE_CLOCK:
        if btnA_was_pressed():
            state = STATE_MENU
            needs_redraw = True
        if time.time() != last_clock_tick:
            last_clock_tick = time.time()
            needs_redraw = True
    elif state == STATE_BATTERY:
        if btnA_was_pressed():
            state = STATE_MENU
            needs_redraw = True
        if time.time() != last_clock_tick:
            last_clock_tick = time.time()
            needs_redraw = True
    elif state == STATE_FILES:
        if btnB_was_pressed():
            items = fs.list(files_path) or []
            total = len(items) + (1 if files_path else 0)
            if total > 0:
                files_index = (files_index + 1) % total
            needs_redraw = True
        if btnA_was_pressed():
            files_enter()
            needs_redraw = True
        if btnC_was_pressed():
            if files_path:
                parts = files_path.split("/")
                files_path = "/".join(parts[:-1])
                files_index = 0
                needs_redraw = True
            else:
                state = STATE_MENU
                needs_redraw = True
    elif state == STATE_VIEWFILE:
        if btnB_was_pressed():
            if view_scroller:
                view_scroller.scroll_down()
            needs_redraw = True
        if btnA_was_pressed() or btnC_was_pressed():
            state = STATE_FILES
            needs_redraw = True
    elif state == STATE_WIFI:
        if btnA_was_pressed():
            try_wifi_connect()
            needs_redraw = True
        if btnC_was_pressed():
            state = STATE_MENU
            needs_redraw = True
        if btnB_was_pressed():
            state = STATE_MENU
            needs_redraw = True
    elif state == STATE_TRANSFER:
        handle_serial_input()
        if btnB_was_pressed():
            if transfer_scroller:
                transfer_scroller.scroll_down()
            needs_redraw = True
        if btnA_was_pressed() or btnC_was_pressed():
            state = STATE_MENU
            needs_redraw = True
        needs_redraw = True
    if needs_redraw:
        if state == STATE_BOOT:
            render_boot()
        elif state == STATE_MENU:
            render_menu()
        elif state == STATE_CMD:
            render_cmd()
        elif state == STATE_CLOCK:
            render_clock()
        elif state == STATE_BATTERY:
            render_battery()
        elif state == STATE_FILES:
            render_files()
        elif state == STATE_VIEWFILE:
            render_viewfile()
        elif state == STATE_WIFI:
            render_wifi()
        elif state == STATE_TRANSFER:
            render_transfer()
        needs_redraw = False
    time.sleep_ms(40)