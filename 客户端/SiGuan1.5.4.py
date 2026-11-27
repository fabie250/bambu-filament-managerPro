import sys
import re
import json
import os
import time
import datetime
import urllib.request
import urllib.error
import urllib.parse
import webbrowser
import ctypes
from ctypes import wintypes
import threading
import sqlite3
import shutil
import subprocess
import tkinter as tk
from tkinter import messagebox, filedialog, colorchooser
from PIL import Image, ImageDraw
import customtkinter as ctk

# ==============================================================================
# 模块 0: 全局版本常量、加速接口与网盘备用配置 [START]
# ==============================================================================
CURRENT_VERSION = "v1.5.4"
IS_PRE_RELEASE = False

SURFACE_OPTIONS = ["标准", "哑光", "丝绸", "金属", "透明", "夜光", "木纹", "混色", "其他"]
BUILTIN_BRANDS = [
    "Bambu Lab", "Polymaker", "eSUN", "SUNLU", "Prusament", "Overture",
    "JAYO", "Kingroon", "Creality", "Anycubic",
]
BUILTIN_MATERIALS = [
    "PLA Basic", "PLA Matte", "PLA Silk", "PLA Metal", "PLA Marble",
    "PETG HF", "PETG Basic", "ABS", "ASA", "TPU", "PA-CF", "PC",
    "Support W", "PVA",
]

# 离线模式：--offline 参数，或可执行文件名为 SiGuan_Offline.exe
OFFLINE_MODE = os.environ.get("SIGUAN_OFFLINE") == "1" or "--offline" in sys.argv
if getattr(sys, "frozen", False) and "offline" in os.path.basename(sys.executable).lower():
    OFFLINE_MODE = True

# 离线版用独立版本标签，便于和在线版区分（同一个二进制，靠文件名/参数区分）
OFFLINE_VERSION = "v1.5.4-O"
VERSION_TAG = OFFLINE_VERSION if OFFLINE_MODE else CURRENT_VERSION
GITHUB_REPO = "fabie250/bambu-filament-managerPro"
UPDATE_API_URL = "http://mpdfyy.cn/api/pro/latest-version"

BACKUP_PAN_URL = "https://1823958828.share.123pan.cn/123pan/bTEGjv-ewgl3?pwd=FwtE"

GH_PROXY_NODES = [
    "https://gh-proxy.com/",
    "https://ghproxy.net/",
    "https://ghproxy.homeboyc.cn/",
    "https://github.akams.cn/",
    "https://ghfast.top/"
]
# ==============================================================================
# 模块 0: 全局版本常量、加速接口与网盘备用配置 [END]
# ==============================================================================


# ==============================================================================
# 模块 1: 语义化版本比对与解析算法 [START]
# ==============================================================================
def parse_version_tuple(ver_str: str):
    clean_str = ver_str.strip().lower().lstrip('v')
    is_beta = 0 if any(k in clean_str for k in ["beta", "rc", "alpha"]) else 1
    nums = re.findall(r'\d+', clean_str)
    major = int(nums[0]) if len(nums) > 0 else 0
    minor = int(nums[1]) if len(nums) > 1 else 0
    patch = int(nums[2]) if len(nums) > 2 else 0
    return (major, minor, patch, is_beta)

def is_newer_version(online_ver: str, current_ver: str) -> bool:
    try:
        return parse_version_tuple(online_ver) > parse_version_tuple(current_ver)
    except Exception:
        return False
# ==============================================================================
# 模块 1: 语义化版本比对与解析算法 [END]
# ==============================================================================


# ==============================================================================
# 模块 2: 基础路径、资源定位与全局日志系统 [START]
# ==============================================================================
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    # 源码运行时以脚本所在目录为准，不能依赖当前工作目录（否则字体会找不到而回退宋体/雅黑）
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
OFFLINE_DB_FILE = os.path.join(BASE_DIR, "siguan_offline.db")
MAPPING_CACHE_FILE = os.path.join(BASE_DIR, "slot_mapping.json")
LOG_FILE = os.path.join(BASE_DIR, "log.txt")

def write_log(content):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {content}\n")
    except Exception:
        pass

LOGO_PNG_FILE = resource_path("bambu_logo.png")
LOGO_ICO_FILE = resource_path("bambu_logo.ico")
FONT_REGULAR_PATH = resource_path("MiSans-Regular.ttf")
FONT_BOLD_PATH = resource_path("MiSans-Bold.ttf")
# ==============================================================================
# 模块 2: 基础路径、资源定位与全局日志系统 [END]
# ==============================================================================


# ==============================================================================
# 模块 3: Windows 凭据管理器安全存储 [START]
# ==============================================================================
KEYRING_SERVICE_NAME = "BambuFilamentStudio"
KEYRING_ACCOUNT_NAME = "script_api_key"

try:
    import keyring
    import keyring.backends.Windows
    keyring.set_keyring(keyring.backends.Windows.WinVaultKeyring())
    HAS_KEYRING = True
except Exception:
    HAS_KEYRING = False
# ==============================================================================
# 模块 3: Windows 凭据管理器安全存储 [END]
# ==============================================================================


# ==============================================================================
# 模块 4: Windows 原生渲染优化与字体池挂载 [START]
# ==============================================================================
def get_toplevel_hwnd(widget):
    """Tk 的 winfo_id() 返回内部 TkChild；真正带标题栏的窗口是它的 TkTopLevel 父窗口。"""
    if os.name != "nt":
        return 0
    try:
        user32 = ctypes.windll.user32
        hwnd = widget.winfo_id()
        root = user32.GetAncestor(hwnd, 2)  # GA_ROOT
        return root or user32.GetParent(hwnd) or hwnd
    except Exception:
        return 0


def enable_windows_rendering_optimizations(root=None):
    if os.name != "nt":
        return
    try:
        dwmapi = ctypes.windll.dwmapi
        if root is not None:
            hwnd = get_toplevel_hwnd(root)
            DWMWA_TRANSITIONS_FORCEDISABLED = 3
            value = ctypes.c_int(1)
            dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_TRANSITIONS_FORCEDISABLED, ctypes.byref(value), ctypes.sizeof(value))
        write_log("🖥️ [渲染优化] Windows DWM 合成/窗口过渡优化已启用")
    except Exception as e:
        write_log(f"⚠️ [渲染优化] DWM 优化不可用: {e}")

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# ---- 窗口几何（全程使用物理像素，绕开 DPI 二次缩放）----
class _WIN_RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

class _WIN_MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", _WIN_RECT),
                ("rcWork", _WIN_RECT), ("dwFlags", wintypes.DWORD)]

def get_work_area_for_point(x=None, y=None):
    """返回 (x,y) 所在显示器的工作区 (left, top, width, height)，单位物理像素；含任务栏扣除。"""
    if os.name != "nt":
        return (0, 0, 1280, 840)
    try:
        user32 = ctypes.windll.user32
        flags = 2 if (x is not None and y is not None) else 1  # MONITOR_DEFAULTTONEAREST / MONITOR_DEFAULTTOPRIMARY
        pt = wintypes.POINT(int(x or 0), int(y or 0))
        hmon = user32.MonitorFromPoint(pt, flags)
        mi = _WIN_MONITORINFO()
        mi.cbSize = ctypes.sizeof(_WIN_MONITORINFO)
        if hmon and user32.GetMonitorInfoW(wintypes.HMONITOR(hmon), ctypes.byref(mi)):
            r = mi.rcWork
            return (int(r.left), int(r.top), int(r.right - r.left), int(r.bottom - r.top))
    except Exception:
        pass
    try:
        r = _WIN_RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0):
            return (int(r.left), int(r.top), int(r.right - r.left), int(r.bottom - r.top))
    except Exception:
        pass
    return (0, 0, 1280, 840)

def get_dpi_factor_for_point(x=None, y=None):
    """取 (x, y) 所在显示器的有效 DPI 缩放因子；取不到返回 None（混合 DPI 多屏靠它换算旧配置）。"""
    if os.name != "nt":
        return None
    try:
        user32 = ctypes.windll.user32
        hmon = user32.MonitorFromPoint(wintypes.POINT(int(x or 0), int(y or 0)), 2)
        if not hmon:
            return None
        dpi_x, dpi_y = wintypes.UINT(0), wintypes.UINT(0)
        if ctypes.windll.shcore.GetDpiForMonitor(
                wintypes.HMONITOR(hmon), 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)) == 0:
            if dpi_x.value:
                return max(1.0, float(dpi_x.value) / 96.0)
    except Exception:
        pass
    return None

def clamp_rect_to_work_area(x, y, w, h, min_w=960, min_h=600, margin=8):
    """把窗口矩形收敛到所在显示器工作区内：超宽超高就压缩，越界就推回来，无坐标就居中。"""
    left, top, aw, ah = get_work_area_for_point(x, y)
    max_w = max(640, aw - margin * 2)
    max_h = max(480, ah - margin * 2)
    w = int(w)
    h = int(h)
    if w > max_w:
        w = max_w
    if h > max_h:
        h = max_h
    if w < min(min_w, max_w):
        w = min(min_w, max_w)
    if h < min(min_h, max_h):
        h = min(min_h, max_h)
    if x is None:
        x = left + (aw - w) // 2
    if y is None:
        y = top + (ah - h) // 2
    x = max(left + margin, min(int(x), left + aw - margin - w))
    y = max(top + margin, min(int(y), top + ah - margin - h))
    return (int(x), int(y), int(w), int(h))

def get_window_frame_rect(hwnd):
    """窗口外框（含标题栏/边框）的物理矩形。"""
    if os.name != "nt" or not hwnd:
        return None
    try:
        r = _WIN_RECT()
        if ctypes.windll.user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(r)):
            return (int(r.left), int(r.top), int(r.right - r.left), int(r.bottom - r.top))
    except Exception:
        pass
    return None

def get_client_rect_screen(hwnd):
    """客户区矩形（屏幕物理坐标）：GetClientRect + ClientToScreen。

    比直接对 winfo_id() 取 GetWindowRect 可靠——窗口还没完成布局时后者会返回 1x1 的假值。
    """
    if os.name != "nt" or not hwnd:
        return None
    try:
        user32 = ctypes.windll.user32
        r = _WIN_RECT()
        if not user32.GetClientRect(wintypes.HWND(hwnd), ctypes.byref(r)):
            return None
        w, h = int(r.right - r.left), int(r.bottom - r.top)
        if w <= 0 or h <= 0:
            return None
        pt = wintypes.POINT(0, 0)
        if not user32.ClientToScreen(wintypes.HWND(hwnd), ctypes.byref(pt)):
            return None
        return (int(pt.x), int(pt.y), w, h)
    except Exception:
        return None

def get_windows_system_theme():
    """读取 Windows「应用模式」：返回 light / dark。读不到时按 light 处理。"""
    if os.name != "nt":
        return "light"
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if int(value) else "dark"
    except Exception:
        return "light"


def force_redraw(widget):
    """同步重绘整窗及其子控件，用于切换页面/还原窗口后补画。"""
    if os.name != "nt":
        return
    try:
        hwnd = widget.winfo_id()
        ctypes.windll.user32.RedrawWindow(hwnd, None, None, 0x0001 | 0x0080 | 0x0100)
    except Exception:
        pass


def schedule_repaint(widget, delay=40):
    """去抖补绘：Map/Visibility 事件密集触发时，只保留最后一次重绘任务。"""
    try:
        if getattr(widget, "_repaint_job", None):
            return
        widget._repaint_job = widget.after(delay, lambda: _do_repaint(widget))
    except Exception:
        pass


def _do_repaint(widget):
    try:
        widget._repaint_job = None
    except Exception:
        pass
    try:
        widget.update_idletasks()
    except Exception:
        pass
    force_redraw(widget)


def is_left_button_down():
    """鼠标左键是否按住（用于判断用户是否正在拖动窗口边缘改尺寸）。"""
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
    except Exception:
        return False

def get_frame_metrics(hwnd, dpi=96):
    """返回 (dx, dy, dw, dh)：外框相对客户区的左/上偏移与宽/高差（dx = 客户区-外框）。

    优先实测；客户区还没铺开（1x1 / 0）时按窗口样式 + DPI 推算，避免把窗口算成几倍大。
    """
    frame = get_window_frame_rect(hwnd)
    client = get_client_rect_screen(hwnd)
    if frame and client and client[2] >= 64 and client[3] >= 64:
        dx, dy = client[0] - frame[0], client[1] - frame[1]
        dw, dh = frame[2] - client[2], frame[3] - client[3]
    elif os.name == "nt" and hwnd:
        dx = dy = dw = dh = 0
        try:
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(wintypes.HWND(hwnd), -16)
            exstyle = user32.GetWindowLongW(wintypes.HWND(hwnd), -20)
            r = _WIN_RECT(0, 0, 100, 100)
            ok = False
            try:
                ok = bool(user32.AdjustWindowRectExForDpi(
                    ctypes.byref(r), style, False, exstyle, int(dpi)))
            except Exception:
                ok = False
            if not ok:
                ok = bool(user32.AdjustWindowRectEx(ctypes.byref(r), style, False, exstyle))
            if ok:
                dx, dy = -int(r.left), -int(r.top)
                dw = int((r.right - r.left) - 100)
                dh = int((r.bottom - r.top) - 100)
        except Exception:
            pass
    else:
        return (0, 0, 0, 0)
    # 兜底：边框厚度不合理就按零处理（宁可不加边框，也不能把窗口撑出屏幕）
    if not (0 <= dw <= 240 and 0 <= dh <= 240 and 0 <= dx <= 240 and 0 <= dy <= 240):
        return (0, 0, 0, 0)
    return (dx, dy, dw, dh)

def register_font_to_windows_pool(font_path):
    if os.path.exists(font_path):
        try:
            # flags=0：注册到当前会话的字体表（Tk 才能枚举到）；FR_PRIVATE 的字体 Tk 看不到，会回退宋体
            res = ctypes.windll.gdi32.AddFontResourceExW(font_path, 0, 0)
            write_log(f"🔤 [字体池] 注册字体文件: {os.path.basename(font_path)} (状态码: {res})")
        except Exception as e:
            write_log(f"❌ [字体池] 注册失败: {e}")

register_font_to_windows_pool(FONT_REGULAR_PATH)
register_font_to_windows_pool(FONT_BOLD_PATH)

try:
    if os.path.exists(FONT_REGULAR_PATH):
        ctk.FontManager.load_font(FONT_REGULAR_PATH)
    if os.path.exists(FONT_BOLD_PATH):
        ctk.FontManager.load_font(FONT_BOLD_PATH)
except Exception:
    pass
# ==============================================================================
# 模块 4: Windows 原生渲染优化与字体池挂载 [END]
# ==============================================================================


# ==============================================================================
# 模块 5: 配置文件与网络 API 请求通信 [START]
# ==============================================================================
DEFAULT_CONFIG = {
    "server_url": "http://127.0.0.1:8000/api/ingest/script-report",
    "filaments_url": "http://127.0.0.1:8000/api/ingest/script-filaments",
    "api_key": "",
    "selected_printer_id": None,
    "selected_font": "Microsoft YaHei UI (微软高清)",
    "auto_watcher_enabled": True,
    "developer_mode": False,
    "debug_log_enabled": False,
    "window_width": 1280,
    "window_height": 840,
    "window_rect": None,
    "window_zoomed": False,
    "last_slice_weight": 0.0,
    "update_channel": "Release (正式版)",
    "skipped_version": "",
    "ui_theme": "light",
    "custom_brands": [],
    "custom_materials": [],
    "custom_colors": []
}

def get_secure_api_key():
    if HAS_KEYRING:
        try:
            key = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_ACCOUNT_NAME)
            if key:
                return key
        except Exception:
            pass
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get("api_key", "")
        except Exception:
            pass
    return ""

def set_secure_api_key(api_key):
    if HAS_KEYRING:
        try:
            keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_ACCOUNT_NAME, api_key)
            return True
        except Exception as e:
            write_log(f"保存凭据到 Windows 失败: {e}")
    return False

def load_config():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                user_cfg = json.load(f)
                config.update(user_cfg)
        except Exception:
            pass
    
    secure_key = get_secure_api_key()
    if secure_key:
        config["api_key"] = secure_key
    return config

def save_config(config):
    try:
        api_key = config.get("api_key", "")
        saved_to_keyring = set_secure_api_key(api_key)

        cfg_to_save = config.copy()
        if saved_to_keyring:
            cfg_to_save["api_key"] = "[Encrypted in Windows Credential Manager]"
            
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg_to_save, f, ensure_ascii=False, indent=2)
    except Exception as e:
        write_log(f"保存配置失败: {e}")

_API_CACHE = {}
_API_CACHE_LOCK = threading.RLock()
_API_CACHE_TTL = 2.5


def clear_api_cache():
    with _API_CACHE_LOCK:
        _API_CACHE.clear()


def _api_cache_key(url):
    try:
        parts = urllib.parse.urlsplit(url)
        query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True) if k != "_t"]
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path,
                                        urllib.parse.urlencode(query), ""))
    except Exception:
        return url


def api_request(url, api_key="", method="GET", data=None, use_cache=True):
    if OFFLINE_MODE:
        return offline_api_request(url, api_key=api_key, method=method, data=data)

    method = (method or "GET").upper()
    cache_key = _api_cache_key(url)
    if method == "GET" and use_cache:
        with _API_CACHE_LOCK:
            cached = _API_CACHE.get(cache_key)
            if cached and (time.time() - cached[0]) < _API_CACHE_TTL:
                return cached[1]
    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        req_data = json.dumps(data).encode('utf-8') if data else None
        sep = "&" if "?" in url else "?"
        req = urllib.request.Request(f"{url}{sep}_t={int(time.time()*1000)}", data=req_data,
                                     headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=6) as response:
            result = json.loads(response.read().decode('utf-8'))
        if method == "GET" and result is not None:
            with _API_CACHE_LOCK:
                _API_CACHE[cache_key] = (time.time(), result)
        elif method != "GET":
            clear_api_cache()
        return result
    except Exception as e:
        write_log(f"API请求失败 [{method} {url}]: {e}")
        return None
# --------------------------------------------------------------------------
# 离线模式本地数据层（SQLite，无需服务端）
# --------------------------------------------------------------------------
_OFFLINE_DB_READY = False
_OFFLINE_LOCK = threading.RLock()


def _offline_now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _offline_init_db():
    global _OFFLINE_DB_READY
    if _OFFLINE_DB_READY:
        return
    with _OFFLINE_LOCK:
        if _OFFLINE_DB_READY:
            return
        conn = sqlite3.connect(OFFLINE_DB_FILE, timeout=8)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS filaments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand TEXT DEFAULT 'Bambu Lab',
                material TEXT NOT NULL,
                color_name TEXT NOT NULL,
                color_hex TEXT DEFAULT '#000000',
                surface_effect TEXT DEFAULT '标准',
                diameter_mm REAL DEFAULT 1.75,
                nfc_uid TEXT,
                initial_weight_g REAL DEFAULT 1000,
                current_weight_g REAL DEFAULT 1000,
                spool_weight_g REAL DEFAULT 250,
                price REAL DEFAULT 0,
                purchase_url TEXT,
                remarks TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS printers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                model TEXT DEFAULT 'Bambu P1S',
                ip_address TEXT,
                ams_slots_json TEXT DEFAULT '{}',
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS usage_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filament_id INTEGER NOT NULL,
                printer_id INTEGER,
                used_weight_g REAL NOT NULL,
                remaining_weight_g REAL,
                source TEXT DEFAULT 'offline',
                task_name TEXT,
                created_at TEXT
            );
            """
        )
        try:
            conn.execute("ALTER TABLE filaments ADD COLUMN surface_effect TEXT DEFAULT '标准'")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE filaments ADD COLUMN diameter_mm REAL DEFAULT 1.75")
        except sqlite3.OperationalError:
            pass
        conn.commit()
        conn.close()
        _OFFLINE_DB_READY = True


def _offline_conn():
    _offline_init_db()
    conn = sqlite3.connect(OFFLINE_DB_FILE, timeout=8)
    conn.row_factory = sqlite3.Row
    return conn


def _offline_filament_out(row):
    return {
        "id": row["id"],
        "brand": row["brand"] or "Bambu Lab",
        "material": row["material"] or "",
        "color_name": row["color_name"] or "",
        "color_hex": row["color_hex"] or "#888888",
        "surface_effect": row["surface_effect"] if "surface_effect" in row.keys() else "标准",
        "diameter_mm": float(row["diameter_mm"] or 1.75) if "diameter_mm" in row.keys() else 1.75,
        "nfc_uid": row["nfc_uid"],
        "initial_weight_g": float(row["initial_weight_g"] or 1000),
        "current_weight_g": float(row["current_weight_g"] or 0),
        "spool_weight_g": float(row["spool_weight_g"] or 250),
        "price": float(row["price"] or 0),
        "purchase_url": row["purchase_url"],
        "remarks": row["remarks"],
        "created_at": row["created_at"] or "",
    }


def _offline_printer_out(row):
    try:
        slots = json.loads(row["ams_slots_json"] or "{}")
    except Exception:
        slots = {}
    return {
        "id": row["id"],
        "name": row["name"],
        "model": row["model"] or "Bambu P1S",
        "ip_address": row["ip_address"],
        "ams_slots": slots,
    }


def _offline_create_filament(conn, payload):
    now = _offline_now()
    cur = conn.execute(
        """INSERT INTO filaments
           (brand, material, color_name, color_hex, surface_effect, diameter_mm, nfc_uid, initial_weight_g,
            current_weight_g, spool_weight_g, price, purchase_url, remarks, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            payload.get("brand") or "Bambu Lab",
            payload.get("material") or "PLA",
            payload.get("color_name") or "自定义",
            payload.get("color_hex") or "#888888",
            payload.get("surface_effect") or "标准",
            float(payload.get("diameter_mm") or 1.75),
            payload.get("nfc_uid"),
            float(payload.get("initial_weight_g") or 1000),
            float(payload.get("current_weight_g") or payload.get("initial_weight_g") or 1000),
            float(payload.get("spool_weight_g") or 250),
            float(payload.get("price") or 0),
            payload.get("purchase_url") or "",
            payload.get("remarks") or "",
            now,
        ),
    )
    row = conn.execute("SELECT * FROM filaments WHERE id=?", (cur.lastrowid,)).fetchone()
    return _offline_filament_out(row)


def _offline_analytics():
    with _OFFLINE_LOCK:
        conn = _offline_conn()
        filaments = {r["id"]: r for r in conn.execute("SELECT * FROM filaments").fetchall()}
        printers = {r["id"]: r for r in conn.execute("SELECT * FROM printers").fetchall()}
        records = conn.execute("SELECT * FROM usage_records").fetchall()
        conn.close()
    total_g = 0.0
    total_cost = 0.0
    materials = {}
    printer_stats = {}
    for r in records:
        used = float(r["used_weight_g"] or 0)
        if used <= 0:
            continue
        total_g += used
        f = filaments.get(r["filament_id"])
        unit = 0.0
        if f:
            init = float(f["initial_weight_g"] or 1000)
            unit = (float(f["price"] or 0) / init) if init > 0 else 0.0
            materials[f["material"] or "未标注"] = materials.get(f["material"] or "未标注", 0.0) + used
        cost = used * unit
        total_cost += cost
        prow = printers.get(r["printer_id"]) if r["printer_id"] else None
        pname = prow["name"] if prow else "默认 / 未指定机位"
        stat = printer_stats.setdefault(pname, {"name": pname, "consumed_g": 0.0, "cost": 0.0})
        stat["consumed_g"] += used
        stat["cost"] += cost
    return {
        "total_consumed_g": round(total_g, 2),
        "total_consumed_cost": round(total_cost, 2),
        "task_count": len([r for r in records if float(r["used_weight_g"] or 0) > 0]),
        "materials_stat": [{"material": k, "consumed_g": round(v, 2)} for k, v in
                           sorted(materials.items(), key=lambda x: -x[1])],
        "printers_stat": sorted(printer_stats.values(), key=lambda x: -x["consumed_g"]),
    }


def offline_seed_sample(force=False):
    _offline_init_db()
    with _OFFLINE_LOCK:
        conn = _offline_conn()
        count = conn.execute("SELECT COUNT(*) FROM filaments").fetchone()[0]
        if count and not force:
            conn.close()
            return False
        if force:
            conn.execute("DELETE FROM filaments")
            conn.execute("DELETE FROM printers")
            conn.execute("DELETE FROM usage_records")
        samples = [
            ("Bambu Lab", "PLA Basic", "基础绿", "#00AE42", "04A2B3C4D5E6F7", 1000, 780, 99, 250, "标准", ""),
            ("Bambu Lab", "PLA Matte", "哑光白", "#F4F4F0", None, 1000, 312, 109, 250, "哑光", "哑光表面，批次 A"),
            ("Bambu Lab", "PETG HF", "曜石黑", "#1A1A1A", None, 1000, 940, 119, 250, "标准", ""),
            ("Polymaker", "PLA Pro", "雾霾蓝", "#7FA6C9", None, 1000, 150, 89, 200, "标准", ""),
            ("eSUN", "PLA+", "落日橙", "#F26B38", None, 1000, 76, 75, 230, "混色", "双色混色料盘，批次 B"),
            ("Bambu Lab", "ABS", "钛灰", "#6E7378", None, 1000, 620, 129, 250, "标准", ""),
        ]
        fids = []
        for brand, mat, color, hexv, nfc, init, cur, price, spool, surface, remark in samples:
            out = _offline_create_filament(conn, {
                "brand": brand, "material": mat, "color_name": color, "color_hex": hexv,
                "nfc_uid": nfc, "initial_weight_g": init, "current_weight_g": cur,
                "spool_weight_g": spool, "price": price, "surface_effect": surface,
                "remarks": remark, "purchase_url": "https://store.bambulab.com/",
            })
            fids.append(out["id"])
        now = _offline_now()
        p1 = conn.execute("INSERT INTO printers (name,model,ip_address,ams_slots_json,created_at) VALUES (?,?,?,?,?)",
                          ("1 号机 · X1C", "Bambu X1-Carbon", "192.168.1.21",
                           json.dumps({"1": fids[0], "2": fids[1], "3": fids[2], "4": fids[3]}), now))
        p2 = conn.execute("INSERT INTO printers (name,model,ip_address,ams_slots_json,created_at) VALUES (?,?,?,?,?)",
                          ("2 号机 · P1S", "Bambu P1S", "192.168.1.22",
                           json.dumps({"1": fids[4], "2": fids[5], "3": None, "4": None}), now))
        tasks = [
            (fids[0], 120, "Benchy 小船", p1.lastrowid), (fids[1], 340, "收纳盒_A1", p1.lastrowid),
            (fids[2], 60, "手机支架", p2.lastrowid), (fids[0], 40, "钥匙扣_批量", p1.lastrowid),
            (fids[3], 210, "灯罩_M", p1.lastrowid), (fids[2], 380, "工具托盘", p2.lastrowid),
        ]
        for fid, used, task, pid in tasks:
            row = conn.execute("SELECT current_weight_g FROM filaments WHERE id=?", (fid,)).fetchone()
            remaining = max(0.0, round(float(row["current_weight_g"] or 0) - used, 2))
            conn.execute("UPDATE filaments SET current_weight_g=? WHERE id=?", (remaining, fid))
            conn.execute("INSERT INTO usage_records (filament_id,printer_id,used_weight_g,remaining_weight_g,source,task_name,created_at) VALUES (?,?,?,?,?,?,?)",
                         (fid, pid, used, remaining, "sample", task, now))
        conn.commit()
        conn.close()
    return True


def offline_api_request(url, api_key="", method="GET", data=None):
    try:
        path = urllib.parse.urlsplit(url).path.rstrip("/")
        m = (method or "GET").upper()
        with _OFFLINE_LOCK:
            conn = _offline_conn()
            try:
                if path.endswith("/api/ingest/script-user-info"):
                    return {"status": "success", "username": "本地用户", "user_id": 0}

                if path.endswith("/api/ingest/script-filaments") and m == "GET":
                    return [_offline_filament_out(r) for r in conn.execute("SELECT * FROM filaments ORDER BY id").fetchall()]

                if path.endswith("/api/ingest/script-filaments-batch") and m == "POST":
                    created = [_offline_create_filament(conn, p) for p in (data or [])]
                    conn.commit()
                    return created

                if path.endswith("/api/ingest/script-report-create") and m == "POST":
                    out = _offline_create_filament(conn, data or {})
                    conn.commit()
                    return out

                if path.endswith("/api/ingest/script-report") and m == "POST":
                    payload = data or {}
                    fid = int(payload.get("filament_id") or 0)
                    used = float(payload.get("used_weight_g") or 0)
                    row = conn.execute("SELECT * FROM filaments WHERE id=?", (fid,)).fetchone()
                    if not row:
                        return None
                    remaining = max(0.0, round(float(row["current_weight_g"] or 0) - used, 2))
                    conn.execute("UPDATE filaments SET current_weight_g=? WHERE id=?", (remaining, fid))
                    conn.execute(
                        "INSERT INTO usage_records (filament_id,printer_id,used_weight_g,remaining_weight_g,source,task_name,created_at) VALUES (?,?,?,?,?,?,?)",
                        (fid, payload.get("printer_id"), used, remaining, "offline",
                         payload.get("task_name") or "手动调整", _offline_now()))
                    conn.commit()
                    return {"status": "success", "filament_id": fid, "used_weight_g": used,
                            "current_weight_g": remaining, "remaining_weight_g": remaining}

                match = re.search(r"/api/ingest/script-report-delete/(\d+)$", path)
                if match and m == "DELETE":
                    fid = int(match.group(1))
                    conn.execute("DELETE FROM usage_records WHERE filament_id=?", (fid,))
                    conn.execute("DELETE FROM filaments WHERE id=?", (fid,))
                    conn.commit()
                    return {"status": "success"}

                match = re.search(r"/api/ingest/script-filament-logs/(\d+)$", path)
                if match and m == "GET":
                    fid = int(match.group(1))
                    rows = conn.execute(
                        "SELECT * FROM usage_records WHERE filament_id=? ORDER BY id DESC", (fid,)
                    ).fetchall()
                    return [{"id": r["id"], "task_name": r["task_name"],
                             "used_weight_g": float(r["used_weight_g"] or 0),
                             "remaining_weight_g": r["remaining_weight_g"],
                             "created_at": r["created_at"] or ""} for r in rows]

                match = re.search(r"/api/ingest/script-undo-record/(\d+)$", path)
                if match and m == "DELETE":
                    rid = int(match.group(1))
                    rec = conn.execute("SELECT * FROM usage_records WHERE id=?", (rid,)).fetchone()
                    if rec:
                        conn.execute("UPDATE filaments SET current_weight_g=current_weight_g+? WHERE id=?",
                                     (float(rec["used_weight_g"] or 0), rec["filament_id"]))
                        conn.execute("DELETE FROM usage_records WHERE id=?", (rid,))
                        conn.commit()
                    return {"status": "success"}

                match = re.search(r"/api/ingest/script-filaments/(\d+)/url$", path)
                if match and m == "POST":
                    fid = int(match.group(1))
                    conn.execute("UPDATE filaments SET purchase_url=? WHERE id=?",
                                 ((data or {}).get("purchase_url") or "", fid))
                    conn.commit()
                    return {"status": "success"}

                if path.endswith("/api/ingest/script-filaments/apply-url") and m == "POST":
                    payload = data or {}
                    conn.execute("UPDATE filaments SET purchase_url=? WHERE brand=? AND material=?",
                                 (payload.get("purchase_url") or "", payload.get("brand") or "",
                                  payload.get("material") or ""))
                    conn.commit()
                    return {"status": "success"}

                if path.endswith("/api/ingest/script-filaments/import-urls") and m == "POST":
                    for item in (data or []):
                        conn.execute("UPDATE filaments SET purchase_url=? WHERE id=?",
                                     (item.get("purchase_url") or "", int(item.get("id") or 0)))
                    conn.commit()
                    return {"status": "success"}

                match = re.search(r"/api/ingest/script-filaments/(\d+)$", path)
                if match and m == "PUT":
                    fid = int(match.group(1))
                    payload = data or {}
                    fields = ["brand", "material", "color_name", "color_hex", "surface_effect", "diameter_mm", "nfc_uid",
                              "initial_weight_g", "current_weight_g", "spool_weight_g",
                              "price", "purchase_url", "remarks"]
                    sets = [f"{k}=?" for k in fields if k in payload]
                    vals = [payload[k] for k in fields if k in payload]
                    if sets:
                        conn.execute(f"UPDATE filaments SET {', '.join(sets)} WHERE id=?", vals + [fid])
                        conn.commit()
                    row = conn.execute("SELECT * FROM filaments WHERE id=?", (fid,)).fetchone()
                    return _offline_filament_out(row) if row else None

                if path.endswith("/api/ingest/script-filaments") and m == "POST":
                    out = _offline_create_filament(conn, data or {})
                    conn.commit()
                    return out

                if path.endswith("/api/ingest/script-printers") and m == "GET":
                    return [_offline_printer_out(r) for r in conn.execute("SELECT * FROM printers ORDER BY id").fetchall()]

                if path.endswith("/api/ingest/script-printers") and m == "POST":
                    payload = data or {}
                    cur = conn.execute("INSERT INTO printers (name,model,ip_address,ams_slots_json,created_at) VALUES (?,?,?,?,?)",
                                       (payload.get("name") or "打印机", payload.get("model") or "Bambu P1S",
                                        payload.get("ip_address") or "", "{}", _offline_now()))
                    conn.commit()
                    return {"status": "success", "id": cur.lastrowid, "name": payload.get("name") or "打印机"}

                match = re.search(r"/api/ingest/script-printers/(\d+)/ams$", path)
                if match and m == "POST":
                    pid = int(match.group(1))
                    conn.execute("UPDATE printers SET ams_slots_json=? WHERE id=?",
                                 (json.dumps((data or {}).get("ams_slots") or {}), pid))
                    conn.commit()
                    return {"status": "success"}

                match = re.search(r"/api/ingest/script-printers/(\d+)$", path)
                if match and m == "DELETE":
                    conn.execute("DELETE FROM printers WHERE id=?", (int(match.group(1)),))
                    conn.commit()
                    return {"status": "success"}

                if path.endswith("/api/ingest/script-analytics") and m == "GET":
                    return _offline_analytics()

                if "/api/scale/" in path:
                    return {"status": "error", "message": "离线版未启用电子秤"}
                return None
            finally:
                conn.close()
    except Exception as e:
        write_log(f"离线数据请求失败 [{method} {url}]: {e}")
        return None


# ==============================================================================
# 模块 5: 配置文件与网络 API 请求通信 [END]
# ==============================================================================


# ==============================================================================
# 模块 6: UI 配色方案与字体映射 [START]
# ==============================================================================
# 全部使用 (light, dark) 颜色元组，customtkinter 会在 Light/Dark 之间自动切换。
COLOR_PRESETS = [
    ("#00AE42", "基础绿"), ("#F4F4F0", "哑光白"), ("#1A1A1A", "曜石黑"),
    ("#6E7378", "钛灰"), ("#D7263D", "烈焰红"), ("#4A90E2", "天空蓝"),
    ("#F26B38", "日落橙"), ("#F2C94C", "柠檬黄"), ("#F7A8B8", "樱花粉"),
    ("#D9E2EC", "冰晶灰"),
]
COLOR_BG_MAIN = ("#F3F6FB", "#05080F")
COLOR_CARD_BG = ("#FFFFFF", "#0C1422")
COLOR_CARD_BORDER = ("#E4EAF3", "#1E2A3F")
COLOR_BAMBU_GREEN = ("#0E9F6E", "#34D399")
COLOR_TEXT_PRIMARY = ("#0B1424", "#E9EEFB")
COLOR_TEXT_MUTED = ("#64748B", "#8B9BB4")
COLOR_BADGE_RED = ("#E11D48", "#FB7185")

COLOR_SURFACE_2 = ("#F8FAFD", "#111C2E")
COLOR_SIDEBAR = ("#FFFFFF", "#070D18")
COLOR_INPUT_BG = ("#F1F5F9", "#09111E")
COLOR_TRACK = ("#E8EEF6", "#16233A")
COLOR_DIVIDER = ("#EDF2F8", "#18243A")
COLOR_ACCENT_SOFT = ("#E7F8EE", "#0D2B1A")
COLOR_ON_ACCENT = ("#FFFFFF", "#04160C")
COLOR_AMBER = ("#B45309", "#FBBF24")
COLOR_BLUE = ("#2563EB", "#60A5FA")
COLOR_VIOLET = ("#6D28D9", "#A78BFA")
COLOR_HOVER = ("#EAF0F8", "#16233A")
COLOR_AMBER_SOFT = ("#FEF3C7", "#2A1F0A")
COLOR_RED_SOFT = ("#FEE2E2", "#2A1318")
COLOR_BLUE_SOFT = ("#DBEAFE", "#10213A")
COLOR_VIOLET_SOFT = ("#EDE9FE", "#1D1735")

# 2026-11 在售/常见机型（用于添加打印机卡片选择）
PRINTER_MODELS = [
    {"series": "A", "name": "Bambu A1 mini", "tag": "入门", "spec": "180×180×180 mm · 单喷嘴 300℃ · 开放式"},
    {"series": "A", "name": "Bambu A1", "tag": "入门", "spec": "256×256×256 mm · 单喷嘴 300℃ · 开放式"},
    {"series": "A", "name": "Bambu A2L", "tag": "新一代", "spec": "330×320×325 mm · 单喷嘴 300℃ · 支持刀切模块"},
    {"series": "P", "name": "Bambu P1P", "tag": "经典", "spec": "256×256×256 mm · CoreXY 开放式"},
    {"series": "P", "name": "Bambu P1S", "tag": "经典", "spec": "256×256×256 mm · CoreXY 封闭机箱"},
    {"series": "P", "name": "Bambu P2S", "tag": "主力", "spec": "256×256×256 mm · 触屏 · 快换喷嘴"},
    {"series": "P", "name": "Bambu P3C", "tag": "第三代", "spec": "多头闪切 · 5 标配 + 2 扩展槽 · 最多 7 头"},
    {"series": "X", "name": "Bambu X1 Carbon", "tag": "经典", "spec": "256×256×256 mm · 激光雷达 · 封闭机箱"},
    {"series": "X", "name": "Bambu X1E", "tag": "企业", "spec": "256×256×256 mm · 企业网络 · 主动控温"},
    {"series": "X", "name": "Bambu X2D", "tag": "新一代", "spec": "256×256×260 mm · 双喷嘴 · 主动控温 65℃"},
    {"series": "H", "name": "Bambu H2S", "tag": "大尺寸", "spec": "340×320×340 mm · 单喷嘴 350℃"},
    {"series": "H", "name": "Bambu H2D", "tag": "旗舰", "spec": "350×320×325 mm · 双喷嘴 350℃"},
    {"series": "H", "name": "Bambu H2D Pro", "tag": "旗舰", "spec": "350×320×325 mm · 企业网络 · 碳化钨喷嘴"},
    {"series": "H", "name": "Bambu H2C", "tag": "旗舰", "spec": "350×320×325 mm · 多热端系统"},
    {"series": "H", "name": "Bambu H3C", "tag": "第三代", "spec": "330×320×325 mm · Swaptek 九头（8×1.75 + 1×2.85） · 约 6 秒换头"},
]


def printer_head_count(model):
    """按机型返回标配/已安装喷头数；P3C 标配 5，H3C 标配 9。"""
    name = str(model or "").lower()
    if "p3c" in name:
        return 5
    if "h3c" in name:
        return 9
    if "x2d" in name or "h2d" in name:
        return 2
    return 1


def printer_max_head_count(model):
    """按机型返回最大可用头位；P3C 的两个空槽可扩展到 7 头。"""
    name = str(model or "").lower()
    if "p3c" in name:
        return 7
    if "h3c" in name:
        return 9
    if "x2d" in name or "h2d" in name:
        return 2
    return 1


def printer_slot_count(model):
    """设备页/映射弹窗使用的槽位数：普通 AMS 4 槽；多头机按最大头位生成。"""
    return max(4, printer_max_head_count(model))


def printer_slot_kind(model):
    return "喷头" if printer_max_head_count(model) >= 5 else "AMS"


def filament_diameter_mm(filament):
    """耗材线径，旧数据默认 1.75 mm。"""
    try:
        value = float((filament or {}).get("diameter_mm") or 1.75)
    except (TypeError, ValueError):
        value = 1.75
    return 2.85 if value >= 2.5 else 1.75


def printer_slot_label(model, slot_i):
    name = str(model or "").lower()
    if "p3c" in name and slot_i >= 6:
        return f"扩展槽 {slot_i}"
    if "h3c" in name and slot_i == 8:
        return f"喷头 {slot_i} · 2.85"
    return f"{printer_slot_kind(model)} {slot_i}"


def printer_slot_allowed_diameters(model, slot_i):
    """该槽位允许的耗材线径；None 表示该槽位不是打印头/不限制。"""
    name = str(model or "").lower()
    if "h3c" in name and slot_i == 8:
        return {2.85}
    if "p3c" in name and slot_i >= 6:
        return {1.75, 2.85}
    return {1.75}


def printer_slot_note(model, slot_i):
    name = str(model or "").lower()
    if "h3c" in name and slot_i == 8:
        return "2.85 mm TPU 专用头；只能映射 2.85 mm 耗材，改 1.75 需整头更换"
    if "p3c" in name and slot_i >= 6:
        return "扩展槽：可装 1.75 标准头、2.85 TPU 专用头或 CraftTool"
    return "1.75 mm 标准打印头" if printer_slot_kind(model) == "喷头" else "普通 AMS 槽位"


ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")


def make_ui_icon(kind, color, size=20):
    """用 PIL 画一套细线图标，避免客户端依赖外部图标库。"""
    scale = 4
    canvas = size * scale
    img = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = max(2, int(1.7 * scale))
    col = color

    def pt(x, y):
        return (int(x * scale), int(y * scale))

    def line(points, width=None):
        d.line([pt(x, y) for x, y in points], fill=col, width=width or w, joint="curve")

    def rrect(box, radius=2, width=None):
        x1, y1, x2, y2 = [int(v * scale) for v in box]
        d.rounded_rectangle([x1, y1, x2, y2], radius=radius * scale, outline=col, width=width or w)

    def circle(cx, cy, r, width=None):
        d.ellipse([pt(cx - r, cy - r), pt(cx + r, cy + r)], outline=col, width=width or w)

    def dot(cx, cy, r=1.2):
        d.ellipse([pt(cx - r, cy - r), pt(cx + r, cy + r)], fill=col)

    if kind == "dashboard":
        rrect((2.5, 2.5, 8.6, 9.2), 2)
        rrect((11.4, 2.5, 17.5, 6.6), 2)
        rrect((11.4, 9.0, 17.5, 17.5), 2)
        rrect((2.5, 11.6, 8.6, 17.5), 2)
    elif kind == "box":
        line([(10, 2.6), (17.3, 6.6), (17.3, 13.6), (10, 17.6), (2.7, 13.6), (2.7, 6.6), (10, 2.6)])
        line([(2.7, 6.6), (10, 10.6), (17.3, 6.6)])
        line([(10, 10.6), (10, 17.6)])
    elif kind == "printer":
        rrect((3.5, 8.0, 16.5, 14.5), 2)
        line([(7, 8), (7, 3.5), (13, 3.5), (13, 8)])
        line([(6.5, 15), (6.5, 17.5), (13.5, 17.5), (13.5, 15)])
        dot(14.6, 10.6, 0.9)
    elif kind == "chart":
        line([(3, 3), (3, 17), (17, 17)])
        line([(6.2, 14), (6.2, 10.5)])
        line([(10, 14), (10, 7)])
        line([(13.8, 14), (13.8, 11.6)])
    elif kind == "cart":
        line([(2.3, 3.2), (4.8, 3.8), (7.0, 13.4), (16.0, 13.4), (18.0, 6.0), (5.3, 5.2)])
        circle(8.2, 16.8, 1.35)
        circle(15.2, 16.8, 1.35)
    elif kind == "scale":
        line([(10, 4.2), (10, 17.2)])
        line([(5.5, 17.4), (14.5, 17.4)])
        line([(4.2, 7.6), (15.8, 7.6)])
        line([(5.2, 7.6), (3.2, 13.0), (7.2, 13.0), (5.2, 7.6)])
        line([(14.8, 7.6), (12.8, 13.0), (16.8, 13.0), (14.8, 7.6)])
    elif kind == "settings":
        for y, knob in ((6.2, 8.2), (10.0, 13.2), (13.8, 6.6)):
            line([(3.0, y), (17.0, y)])
            circle(knob, y, 2.0)
    elif kind == "logs":
        rrect((4.8, 2.5, 15.2, 17.5), 2)
        line([(7.3, 7.0), (12.7, 7.0)])
        line([(7.3, 10.6), (12.7, 10.6)])
        line([(7.3, 14.2), (11.3, 14.2)])
    elif kind == "sun":
        circle(10, 10, 3.4)
        for a, b in (((10, 2.2), (10, 4.0)), ((10, 16.0), (10, 17.8)),
                     ((2.2, 10), (4.0, 10)), ((16.0, 10), (17.8, 10)),
                     ((4.5, 4.5), (5.8, 5.8)), ((14.2, 14.2), (15.5, 15.5)),
                     ((4.5, 15.5), (5.8, 14.2)), ((14.2, 5.8), (15.5, 4.5))):
            line([a, b])
    elif kind == "moon":
        d.ellipse([pt(4.9, 2.5), pt(16.6, 17.4)], fill=col)
        d.ellipse([pt(7.9, 0.6), pt(18.6, 14.4)], fill=(0, 0, 0, 0))
    elif kind == "plus":
        line([(10, 4.5), (10, 15.5)])
        line([(4.5, 10), (15.5, 10)])
    elif kind == "refresh":
        d.arc([pt(3.2, 3.2), pt(16.8, 16.8)], start=35, end=320, fill=col, width=w)
        line([(16.4, 3.2), (16.8, 7.4), (12.6, 7.0)])
    elif kind == "search":
        circle(8.8, 8.8, 5.2)
        line([(12.8, 12.8), (17.2, 17.2)])
    elif kind == "close":
        line([(5.5, 5.5), (14.5, 14.5)])
        line([(14.5, 5.5), (5.5, 14.5)])
    elif kind == "check":
        line([(4.2, 10.4), (8.3, 14.5), (15.8, 5.8)])
    elif kind == "trash":
        line([(3.5, 5.8), (16.5, 5.8)])
        line([(8.0, 5.8), (8.0, 3.5), (12.0, 3.5), (12.0, 5.8)])
        line([(5.5, 5.8), (6.4, 17.3), (13.6, 17.3), (14.5, 5.8)])
        line([(9.0, 9.0), (9.0, 14.2)])
        line([(11.0, 9.0), (11.0, 14.2)])
    elif kind == "edit":
        line([(4.0, 16.0), (5.0, 11.8), (14.4, 2.4), (17.6, 5.6), (8.2, 15.0), (4.0, 16.0)])
    elif kind == "copy":
        rrect((8.2, 8.2, 17.2, 17.2), 2)
        line([(5.2, 12.0), (3.0, 12.0), (3.0, 3.0), (12.0, 3.0), (12.0, 5.2)])
    elif kind == "link":
        line([(8.4, 11.6), (11.6, 8.4)])
        d.arc([pt(2.2, 7.2), pt(10.8, 15.8)], start=90, end=270, fill=col, width=w)
        d.arc([pt(9.2, 4.2), pt(17.8, 12.8)], start=270, end=90, fill=col, width=w)
    elif kind == "wifi":
        d.arc([pt(2.6, 4.0), pt(17.4, 15.2)], start=210, end=330, fill=col, width=w)
        d.arc([pt(5.6, 7.0), pt(14.4, 15.0)], start=210, end=330, fill=col, width=w)
        dot(10, 16.2, 1.2)
    elif kind == "palette":
        d.arc([pt(3.0, 3.0), pt(17.0, 17.0)], start=30, end=300, fill=col, width=w)
        dot(8.0, 8.0, 1.1)
        dot(12.2, 7.0, 1.1)
        dot(13.6, 11.4, 1.1)
        dot(8.8, 13.0, 1.1)
    else:
        circle(10, 10, 6.0)

    return img.resize((size, size), Image.LANCZOS)


_UI_ICON_CACHE = {}
_UI_ICON_ACCENT_CACHE = {}


def ui_icon(kind, size=19):
    key = (kind, size)
    cached = _UI_ICON_CACHE.get(key)
    if cached is not None:
        return cached
    icon = ctk.CTkImage(
        light_image=make_ui_icon(kind, "#5B6B82", size).resize((size, size), Image.LANCZOS),
        dark_image=make_ui_icon(kind, "#93A4BC", size).resize((size, size), Image.LANCZOS),
        size=(size, size),
    )
    _UI_ICON_CACHE[key] = icon
    return icon


def ui_icon_on_accent(kind, size=17):
    key = (kind, size)
    cached = _UI_ICON_ACCENT_CACHE.get(key)
    if cached is not None:
        return cached
    icon = ctk.CTkImage(
        light_image=make_ui_icon(kind, "#FFFFFF", size),
        dark_image=make_ui_icon(kind, "#04160C", size),
        size=(size, size),
    )
    _UI_ICON_ACCENT_CACHE[key] = icon
    return icon

def map_font_family(cfg_font_str):
    if "YaHei" in cfg_font_str or "微软雅黑" in cfg_font_str:
        return "Microsoft YaHei UI"
    elif "Segoe" in cfg_font_str:
        return "Segoe UI Variable Text"
    candidate = "MiSans" if "MiSans" in cfg_font_str or not cfg_font_str else "MiSans"
    try:
        import tkinter.font as tkfont
        if candidate not in set(tkfont.families()):
            candidate = "Microsoft YaHei UI"
    except Exception:
        pass
    return candidate
# ==============================================================================
# 模块 6: UI 配色方案与字体映射 [END]
# ==============================================================================


# ==============================================================================
# 模块 7: 切片文件后台监听与多盘防抖引擎 [START]
# ==============================================================================
class BambuFileWatcher(threading.Thread):
    def __init__(self, app_instance):
        super().__init__()
        self.daemon = True
        self.app = app_instance
        self.running = False
        self.plate_cooldown = {}

    def run(self):
        self.running = True
        write_log("🚀 全局切片监控后台线程已启动 (独立分盘智能排队模式)...")
        
        appdata_local = os.getenv("LOCALAPPDATA", "")
        temp_dir = os.getenv("TEMP", "")
        
        watch_dirs = [
            os.path.join(appdata_local, "BambuStudio"),
            os.path.join(appdata_local, "OrcaSlicer"),
            temp_dir
        ]

        while self.running:
            try:
                current_cfg = self.app.cfg
                if current_cfg.get("auto_watcher_enabled", True):
                    now_time = time.time()
                    self.plate_cooldown = {k: v for k, v in self.plate_cooldown.items() if (now_time - v) < 30}

                    for w_dir in watch_dirs:
                        if not os.path.exists(w_dir):
                            continue
                        
                        for root, _, files in os.walk(w_dir):
                            for file in files:
                                f_lower = file.lower()
                                if f_lower.endswith(".tmp") or f_lower.endswith(".log") or "webcache" in root.lower() or f_lower.endswith(".3mf"):
                                    continue

                                if ".gcode" in f_lower:
                                    file_path = os.path.join(root, file)
                                    try:
                                        mtime = os.path.getmtime(file_path)
                                        if (now_time - mtime) < 3.5:
                                            slot_weights = get_bambu_project_info_strict(file_path)
                                            if slot_weights and sum(slot_weights) > 0:
                                                model_base_name = extract_model_name_from_file(file_path)
                                                plate_id = "1"
                                                p_match = re.search(r'plate_(\d+)', file, re.IGNORECASE)
                                                if p_match:
                                                    plate_id = p_match.group(1)
                                                else:
                                                    num_parts = re.findall(r'\d+', file)
                                                    if len(num_parts) >= 2:
                                                        plate_id = num_parts[-1]

                                                plate_fingerprint = f"{model_base_name}_plate_{plate_id}_{slot_weights}"
                                                last_t = self.plate_cooldown.get(plate_fingerprint, 0)
                                                
                                                if (now_time - last_t) > 4.0:
                                                    self.plate_cooldown[plate_fingerprint] = now_time
                                                    curr_total_w = round(sum(slot_weights), 2)
                                                    display_name = f"{model_base_name}_盘{plate_id}"
                                                    
                                                    write_log(f"🎯 [捕获切片盘] 任务: {display_name} | 耗材克重: {slot_weights} (总重: {curr_total_w}g)")
                                                    self.app.after(100, lambda fp=file_path, sw=slot_weights, mn=display_name: 
                                                        self.app.enqueue_auto_deduct(fp, sw, mn))
                                    except Exception:
                                        pass
            except Exception:
                pass
            time.sleep(1.2)
# ==============================================================================
# 模块 7: 切片文件后台监听与多盘防抖引擎 [END]
# ==============================================================================


# ==============================================================================
# 模块 8: 客户端主界面逻辑与核心组件 [START]
# ==============================================================================
class HyperOSFilamentApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        # 先把窗口藏起来，等导航/首页布局全部搭完再显示，避免启动时一块块往外蹦
        self.withdraw()

        self.cfg = load_config()
        self.font_family = map_font_family(self.cfg.get("selected_font", "Microsoft YaHei UI (微软高清)"))
        self.is_dialog_showing = False
        self.deduct_queue = []
        self._is_first_load = True
        self.latest_release_info = None
        self.current_user_name = "未登录"
        self.current_dashboard_filter = "全部打印机"

        raw_theme = str(self.cfg.get("ui_theme", "light")).lower()
        self.theme_mode = raw_theme if raw_theme in ("light", "dark", "system") else "light"
        self.ui_theme = get_windows_system_theme() if self.theme_mode == "system" else self.theme_mode
        ctk.set_appearance_mode("Light" if self.ui_theme == "light" else "Dark")

        write_log(f"🖥️ [初始化] 启动界面, 模式={self.theme_mode} 生效={self.ui_theme}, 字体={self.font_family}")

        self.title(f"丝衡 SiGuan · 耗材管理 {VERSION_TAG}" + (" · 离线版" if OFFLINE_MODE else ""))

        self._init_window_geometry()
        self.configure(fg_color=COLOR_BG_MAIN)
        # CTk 的 fg_color 只作用于内部画布，未绘制区域仍会露出 Tk 根窗口底色（默认灰/黑）。
        # 把根窗口底色也设成主题背景，布局/恢复的过渡帧就不会出现黑块。
        try:
            self.tk.call(self._w, "configure", "-background", COLOR_BG_MAIN)
        except Exception:
            pass
        enable_windows_rendering_optimizations(self)
        self._repaint_job = None
        self._restore_alpha_armed = False
        self._restore_release_job = None
        self.bind("<Map>", self._on_window_map, add="+")
        self.bind("<Unmap>", self._on_window_unmap, add="+")
        self.bind("<Visibility>", lambda _e: schedule_repaint(self, 20), add="+")
        self.after(500, self._poll_system_theme)

        if os.path.exists(LOGO_ICO_FILE):
            try:
                self.iconbitmap(LOGO_ICO_FILE)
            except Exception:
                pass

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._resize_after_id = None
        self._is_resizing = False
        self._last_resize_geometry = None
        self._last_window_size = None
        self._layout_frozen = False
        self._resize_mask = None
        self.bind("<Configure>", self._on_window_configure, add="+")
        self._apply_windows_resize_optimizations()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        self.views = {}
        self.nav_buttons = {}
        self.registered_widgets_font = []
        self.current_tab = "dashboard"
        self._tab_seq = 0
        self._tab_loading = False
        self._view_loaded_at = {}
        self._tab_overlay = None
        self._tab_spinner_canvas = None
        self._tab_spinner_job = None
        self._tab_load_token = 0
        self._tab_overlay_visible = False
        self._tab_overlay_started_at = 0.0

        # ---- 左侧导航 + 顶栏 + 内容区 ----
        self.sidebar = ctk.CTkFrame(self, width=232, corner_radius=0, fg_color=COLOR_SIDEBAR, border_width=0)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(1, weight=1)

        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_rowconfigure(1, weight=1)
        self.main.grid_columnconfigure(0, weight=1)

        self._build_sidebar()
        self._build_topbar()

        self.content_area = ctk.CTkFrame(self.main, corner_radius=0, fg_color="transparent")
        self.content_area.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 22))
        self.content_area.grid_columnconfigure(0, weight=1)
        self.content_area.grid_rowconfigure(0, weight=1)

        self.build_navigation()

        self.init_dashboard_view()
        self.switch_tab("dashboard")
        self._ensure_resize_mask()
        self.after(120, lambda: self._set_titlebar_dark(self))

        self.watcher = BambuFileWatcher(self)
        self.watcher.start()

        threading.Thread(target=self.silent_check_update, daemon=True).start()
        threading.Thread(target=self.fetch_user_info_async, daemon=True).start()
        self.after(0, self._reveal_initial_window)

    def _reveal_initial_window(self):
        try:
            self.update_idletasks()
        except Exception:
            pass
        try:
            self.deiconify()
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # 窗口位置/尺寸记忆（物理像素，跨 DPI 稳定，且不会把窗口丢到屏幕外）
    # --------------------------------------------------------------------------
    def _dpi_factor(self):
        try:
            return max(1.0, float(self.winfo_fpixels("1i")) / 96.0)
        except Exception:
            return 1.0

    def _init_window_geometry(self):
        """优先用上次保存的客户区矩形（物理像素）；旧配置按逻辑尺寸 × DPI 换算后收敛。"""
        factor = self._dpi_factor()
        self._window_dpi_factor = factor

        rect = None
        saved_rect = self.cfg.get("window_rect")
        if isinstance(saved_rect, (list, tuple)) and len(saved_rect) == 4:
            try:
                rect = tuple(int(v) for v in saved_rect)
            except Exception:
                rect = None
        if rect is None or rect[2] <= 0 or rect[3] <= 0:
            try:
                legacy_w = int(self.cfg.get("window_width", 1280) or 1280)
                legacy_h = int(self.cfg.get("window_height", 840) or 840)
            except Exception:
                legacy_w, legacy_h = 1280, 840
            # 旧配置里可能已经被 DPI 放大过，先卡在合理区间再换算
            legacy_w = min(max(legacy_w, 960), 2400)
            legacy_h = min(max(legacy_h, 640), 1500)
            if legacy_w > 1920 or legacy_h > 1080:
                # 超过常见逻辑分辨率的旧值只能是物理像素（老版本存的就是 winfo 物理值），直接沿用
                rect = (None, None, legacy_w, legacy_h)
            else:
                rect = (None, None, int(legacy_w * factor), int(legacy_h * factor))

        # 先做粗收敛（允许贴边），精确的贴边修正放在 _apply_window_rect 里按真实边框厚度做
        x, y, w, h = clamp_rect_to_work_area(rect[0], rect[1], rect[2], rect[3], margin=0)
        self._restore_rect = (x, y, w, h)
        self._restore_zoomed = bool(self.cfg.get("window_zoomed", False))
        self._last_normal_rect = (x, y, w, h)
        self._geometry_settled = False

        # 目标显示器可能和启动时不是一块屏（笔记本 + 外接 4K 常见）：按落点那块屏的 DPI 算最小值
        factor_target = get_dpi_factor_for_point(x, y) or factor
        min_w = int(min(1120 * factor_target, w))
        min_h = int(min(680 * factor_target, h))
        # 逻辑值 = 物理最小值 / 目标屏 DPI；CTk 会按「窗口当前 DPI」再乘回来，换屏后仍等于原物理值
        self.minsize(max(1, round(min_w / factor_target)), max(1, round(min_h / factor_target)))
        # 几何先按窗口当前 DPI 给一份近似值，最终尺寸由 _apply_window_rect 用物理像素校正
        self.geometry(f"{max(1, round(w / factor))}x{max(1, round(h / factor))}")

        self.after(60, self._apply_window_rect)
        self.after(300, self._apply_window_rect)
        if self._restore_zoomed:
            # 先摆好普通尺寸的落点，最后再最大化，避免 SetWindowPos 把最大化状态顶掉
            self.after(420, self._apply_maximize)
        write_log(f"🪟 [窗口] dpi={factor:.2f} 工作区={get_work_area_for_point()} "
                  f"目标={self._restore_rect} 最大化={self._restore_zoomed}")

    def _window_frame_hwnd(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(wintypes.HWND(self.winfo_id()))
            return hwnd or self.winfo_id()
        except Exception:
            return None

    def _frame_rect_physical(self):
        return get_window_frame_rect(self._window_frame_hwnd())

    def _client_rect_physical(self):
        """客户区矩形（不含标题栏/边框），物理像素；保存和还原都用它。"""
        rect = get_client_rect_screen(self._window_frame_hwnd())
        return rect or get_window_frame_rect(self.winfo_id())

    def _apply_window_rect(self):
        """把客户区放到目标位置：用外框-客户区差反推外框坐标，避免与 Tk 的尺寸语义打架。"""
        if os.name != "nt":
            return
        try:
            if self.state() == "zoomed":
                return
            frame = self._frame_rect_physical()
            if not frame:
                return
            tx, ty, tw, th = self._restore_rect
            dpi_factor = get_dpi_factor_for_point(tx, ty) or self._window_dpi_factor
            dx, dy, dw, dh = get_frame_metrics(self._window_frame_hwnd(),
                                               dpi=round(dpi_factor * 96))
            fw, fh = tw + dw, th + dh
            # 按真实边框厚度把整窗（外框）压回工作区：尺寸放得下就一点不缩，放不下才裁
            left, top, aw, ah = get_work_area_for_point(tx, ty)
            tw = max(1, min(tw, aw - dw))
            th = max(1, min(th, ah - dh))
            fw, fh = tw + dw, th + dh
            tx = max(left + dx, min(int(tx), left + aw - fw + dx))
            ty = max(top + dy, min(int(ty), top + ah - fh + dy))
            self._restore_rect = (int(tx), int(ty), int(tw), int(th))
            self._last_normal_rect = self._restore_rect
            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            ctypes.windll.user32.SetWindowPos(
                wintypes.HWND(self._window_frame_hwnd()), wintypes.HWND(0),
                int(tx - dx), int(ty - dy), int(fw), int(fh),
                SWP_NOZORDER | SWP_NOACTIVATE)
            self._geometry_settled = True
            write_log(f"🪟 [窗口落位] 目标={self._restore_rect} 外框={frame} 边框差=({dx},{dy},{dw},{dh}) "
                      f"→ ({int(tx-dx)},{int(ty-dy)}) {int(fw)}x{int(fh)}")
        except Exception:
            pass

    def _apply_maximize(self):
        try:
            if self._restore_zoomed and self.state() != "zoomed":
                self.state("zoomed")
                self._geometry_settled = True
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # 现代化 UI 组件库（深/浅色自动切换）
    # --------------------------------------------------------------------------
    def ui_card(self, parent, **kwargs):
        return ctk.CTkFrame(
            parent,
            corner_radius=kwargs.pop("corner_radius", 18),
            fg_color=kwargs.pop("fg_color", COLOR_CARD_BG),
            border_width=kwargs.pop("border_width", 1),
            border_color=kwargs.pop("border_color", COLOR_CARD_BORDER),
            **kwargs,
        )

    def ui_scroll(self, parent, **kwargs):
        kwargs.setdefault("scrollbar_button_color", COLOR_CARD_BORDER)
        kwargs.setdefault("scrollbar_button_hover_color", COLOR_TEXT_MUTED)
        kwargs.setdefault("scrollbar_fg_color", COLOR_BG_MAIN)
        return ctk.CTkScrollableFrame(parent, **kwargs)

    def ui_label(self, parent, text, size=12, weight="normal", color=None, **kwargs):
        widget = ctk.CTkLabel(
            parent, text=text, font=self.get_font(size, weight),
            text_color=color if color is not None else COLOR_TEXT_PRIMARY, **kwargs
        )
        self.register_widget_font(widget, size, weight)
        return widget

    def ui_button(self, parent, text, command, kind="ghost", width=0, height=38,
                  icon_name=None, font_size=12, **kwargs):
        if kind == "primary":
            fg, hover, text_color = COLOR_BAMBU_GREEN, ("#0B8A5F", "#4ADE80"), COLOR_ON_ACCENT
            border_width, border_color = 0, None
            image = ui_icon_on_accent(icon_name, 16) if icon_name else None
        elif kind == "soft":
            fg, hover, text_color = COLOR_ACCENT_SOFT, COLOR_HOVER, COLOR_BAMBU_GREEN
            border_width, border_color = 0, None
            image = ui_icon(icon_name, 16) if icon_name else None
        elif kind == "danger":
            fg, hover, text_color = ("#FEE2E2", "#2A1318"), ("#FECDD3", "#3A1820"), ("#B91C1C", "#FDA4AF")
            border_width, border_color = 0, None
            image = ui_icon(icon_name, 16) if icon_name else None
        else:
            fg, hover, text_color = COLOR_SURFACE_2, COLOR_HOVER, COLOR_TEXT_PRIMARY
            border_width, border_color = 1, COLOR_CARD_BORDER
            image = ui_icon(icon_name, 16) if icon_name else None
        widget = ctk.CTkButton(
            parent, text=text, command=command, image=image, compound="left",
            font=self.get_font(font_size, "bold"), height=height, width=width or 0,
            corner_radius=kwargs.pop("corner_radius", 10),
            fg_color=fg, hover_color=hover, text_color=text_color,
            border_width=border_width, border_color=border_color or COLOR_CARD_BORDER, **kwargs
        )
        self.register_widget_font(widget, font_size, "bold")
        return widget

    def ui_dot(self, parent, color=COLOR_TEXT_MUTED, size=8):
        return ctk.CTkLabel(parent, text="", width=size, height=size, corner_radius=size,
                            fg_color=color)

    def ui_divider(self, parent, pady=0):
        line = ctk.CTkFrame(parent, height=1, fg_color=COLOR_DIVIDER, corner_radius=0)
        line.pack(fill="x", pady=pady)
        return line

    def ui_pill(self, parent, text, fg_color=COLOR_ACCENT_SOFT, text_color=COLOR_BAMBU_GREEN):
        lbl = ctk.CTkLabel(parent, text=text, font=self.get_font(10, "bold"), text_color=text_color,
                           fg_color=fg_color, corner_radius=20, padx=9, pady=3)
        self.register_widget_font(lbl, 10, "bold")
        return lbl

    def _set_titlebar_dark(self, widget):
        if os.name != "nt":
            return
        try:
            hwnd = ctypes.windll.user32.GetParent(widget.winfo_id())
            value = ctypes.c_int(1 if self.ui_theme == "dark" else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
        except Exception:
            pass

    def _prepare_modal(self, modal):
        try:
            modal.attributes("-topmost", True)
        except Exception:
            pass
        try:
            modal.configure(fg_color=COLOR_BG_MAIN)
        except Exception:
            pass
        try:
            modal.transient(self)
        except Exception:
            pass
        if os.path.exists(LOGO_ICO_FILE):
            try:
                modal.iconbitmap(LOGO_ICO_FILE)
            except Exception:
                pass
        try:
            modal.update_idletasks()
            mw, mh = modal.winfo_width(), modal.winfo_height()
            if mw > 100 and mh > 100:
                x = self.winfo_rootx() + (self.winfo_width() - mw) // 2
                y = self.winfo_rooty() + (self.winfo_height() - mh) // 2
                modal.geometry(f"+{x}+{y}")
            self._set_titlebar_dark(modal)
            modal.bind("<Map>", lambda _e, m=modal: schedule_repaint(m, 40), add="+")
        except Exception:
            pass

    def _add_tooltip(self, widget, text):
        state = {"win": None}

        def show(_event=None):
            if state["win"] is not None:
                return
            try:
                x = widget.winfo_rootx() + widget.winfo_width() // 2
                y = widget.winfo_rooty() - 30
                win = tk.Toplevel(self)
                win.title("tooltip")
                win.wm_overrideredirect(True)
                win.attributes("-topmost", True)
                try:
                    win.wm_attributes("-toolwindow", True)
                except Exception:
                    pass
                win.wm_geometry(f"+{x}+{y}")
                ctk.CTkLabel(win, text=text, font=self.get_font(9), text_color=COLOR_TEXT_PRIMARY,
                             fg_color=COLOR_SURFACE_2, corner_radius=6, padx=8, pady=3).pack()
                state["win"] = win
            except Exception:
                state["win"] = None

        def hide(_event=None):
            if state["win"] is not None:
                try:
                    state["win"].destroy()
                except Exception:
                    pass
                state["win"] = None

        widget.bind("<Enter>", show, add="+")
        widget.bind("<Leave>", hide, add="+")

    # --------------------------------------------------------------------------
    # 外壳：侧边栏 / 顶栏 / 主题切换
    # --------------------------------------------------------------------------
    def _build_sidebar(self):
        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=18, pady=(22, 14))

        if os.path.exists(LOGO_PNG_FILE):
            try:
                pil_img = Image.open(LOGO_PNG_FILE)
                self.bambu_icon = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(36, 36))
                ctk.CTkLabel(brand, image=self.bambu_icon, text="").pack(side="left", padx=(0, 10))
            except Exception:
                pass

        name_box = ctk.CTkFrame(brand, fg_color="transparent")
        name_box.pack(side="left")
        self.ui_label(name_box, "丝衡", 15, "bold").pack(anchor="w")
        self.ui_label(name_box, "SIGUAN STUDIO", 8, "bold", COLOR_TEXT_MUTED).pack(anchor="w")

        nav_wrap = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav_wrap.grid(row=1, column=0, sticky="nsew")
        nav_wrap.grid_rowconfigure(1, weight=1)
        nav_wrap.grid_columnconfigure(0, weight=1)
        self.ui_label(nav_wrap, "W O R K S P A C E", 8, "bold", COLOR_TEXT_MUTED).grid(
            row=0, column=0, sticky="w", padx=22, pady=(8, 6))

        self.nav_list = ctk.CTkFrame(nav_wrap, fg_color="transparent")
        self.nav_list.grid(row=1, column=0, sticky="new")
        self.nav_list.grid_columnconfigure(0, weight=1)

        bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="ew", padx=14, pady=(8, 14))

        status_card = self.ui_card(bottom, corner_radius=14, fg_color=COLOR_SURFACE_2)
        status_card.pack(fill="x")
        status_top = ctk.CTkFrame(status_card, fg_color="transparent")
        status_top.pack(fill="x", padx=12, pady=(10, 2))
        self.side_status_dot = self.ui_dot(status_top, COLOR_TEXT_MUTED, 8)
        self.side_status_dot.pack(side="left", padx=(0, 7))
        self.side_status_text = self.ui_label(status_top, "未连接", 10, "bold", COLOR_TEXT_MUTED)
        self.side_status_text.pack(side="left")
        self.side_user_text = self.ui_label(status_card, "未登录", 12, "bold")
        self.side_user_text.pack(anchor="w", padx=12, pady=(0, 10))

        self.btn_theme_side = self.ui_button(
            bottom, "浅色模式", self.toggle_ui_theme, kind="ghost", height=34,
            icon_name="sun", font_size=11)
        self.btn_theme_side.pack(fill="x", pady=(10, 4))

        self.ui_label(bottom, f"SiGuan Client {VERSION_TAG}", 9, "normal", COLOR_TEXT_MUTED).pack(anchor="w", padx=4, pady=(2, 0))

    def _build_topbar(self):
        bar = ctk.CTkFrame(self.main, fg_color="transparent", corner_radius=0)
        bar.grid(row=0, column=0, sticky="ew", padx=28, pady=(22, 14))
        bar.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")
        self.top_title = self.ui_label(left, "耗材台账", 22, "bold")
        self.top_title.pack(anchor="w")
        self.top_sub = self.ui_label(left, "库存总览与快速操作", 11, "normal", COLOR_TEXT_MUTED)
        self.top_sub.pack(anchor="w", pady=(2, 0))

        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")

        self.top_status = ctk.CTkFrame(right, corner_radius=20, fg_color=COLOR_SURFACE_2,
                                       border_width=1, border_color=COLOR_CARD_BORDER)
        self.top_status.pack(side="left", padx=(0, 8))
        self.top_status_dot = self.ui_dot(self.top_status, COLOR_TEXT_MUTED, 8)
        self.top_status_dot.pack(side="left", padx=(10, 6), pady=6)
        self.top_status_text = self.ui_label(self.top_status, "未连接", 10, "bold", COLOR_TEXT_MUTED)
        self.top_status_text.pack(side="left", padx=(0, 10), pady=6)

        self.btn_theme = self.ui_button(right, "浅色模式", self.toggle_ui_theme, kind="ghost",
                                        height=36, icon_name="sun", font_size=11)
        self.btn_theme.pack(side="left", padx=(0, 8))

        self.btn_refresh = ctk.CTkButton(
            right, text="", image=ui_icon("refresh", 18), width=38, height=36, corner_radius=10,
            fg_color=COLOR_SURFACE_2, hover_color=COLOR_HOVER, border_width=1,
            border_color=COLOR_CARD_BORDER, command=self.refresh_current_tab)
        self.btn_refresh.pack(side="left", padx=(0, 8))

        cfg_btn = ctk.CTkButton(
            right, text="", image=ui_icon("settings", 18), width=38, height=36, corner_radius=10,
            fg_color=COLOR_SURFACE_2, hover_color=COLOR_HOVER, border_width=1,
            border_color=COLOR_CARD_BORDER, command=lambda: self.switch_tab("settings"))
        cfg_btn.pack(side="left")

    def _update_theme_ui(self):
        light = self.ui_theme == "light"
        text = "深色模式" if light else "浅色模式"
        icon_name = "moon" if light else "sun"
        for btn in (getattr(self, "btn_theme", None), getattr(self, "btn_theme_side", None)):
            if btn is not None:
                try:
                    btn.configure(text=text, image=ui_icon(icon_name, 16))
                except Exception:
                    pass
        if hasattr(self, "seg_theme"):
            try:
                self.seg_theme.set({"light": "浅色", "dark": "深色", "system": "跟随系统"}.get(self.theme_mode, "跟随系统"))
            except Exception:
                pass
        if getattr(self, "_tab_overlay", None) is not None:
            self._refresh_tab_overlay_theme()

    def _poll_system_theme(self):
        """跟随系统模式下轮询注册表，系统切换深浅色时本程序同步。"""
        try:
            if getattr(self, "theme_mode", "light") != "system":
                return
            effective = get_windows_system_theme()
            if effective != self.ui_theme:
                self.ui_theme = effective
                ctk.set_appearance_mode("Light" if effective == "light" else "Dark")
                try:
                    self.configure(fg_color=COLOR_BG_MAIN)
                except Exception:
                    pass
                self._update_theme_ui()
                try:
                    self._set_titlebar_dark(self)
                except Exception:
                    pass
                force_redraw(self)
                write_log(f"🎨 [主题] 跟随系统切换为 {'Light' if effective == 'light' else 'Dark'}")
        except Exception as e:
            write_log(f"主题轮询异常: {e}")
        finally:
            if getattr(self, "theme_mode", "light") == "system":
                try:
                    self.after(5000, self._poll_system_theme)
                except Exception:
                    pass

    def set_ui_theme(self, theme, persist=True):
        value = str(theme).lower()
        if value in ("system", "跟随系统", "自动", "auto"):
            mode = "system"
        elif value in ("light", "浅色", "白天"):
            mode = "light"
        else:
            mode = "dark"
        self.theme_mode = mode
        self.ui_theme = get_windows_system_theme() if mode == "system" else mode
        ctk.set_appearance_mode("Light" if self.ui_theme == "light" else "Dark")
        if persist:
            self.cfg["ui_theme"] = mode
            save_config(self.cfg)
        try:
            self.configure(fg_color=COLOR_BG_MAIN)
            self.tk.call(self._w, "configure", "-background", COLOR_BG_MAIN)
        except Exception:
            pass
        self._update_theme_ui()
        self.after(40, lambda: self._set_titlebar_dark(self))
        self.after(80, lambda: force_redraw(self))
        if mode == "system":
            self.after(300, self._poll_system_theme)
        write_log(f"🎨 [主题] 模式={mode} 生效={'Light' if self.ui_theme == 'light' else 'Dark'}")

    def toggle_ui_theme(self):
        self.set_ui_theme("light" if self.ui_theme == "dark" else "dark")

    def on_theme_segment(self, value):
        mapping = {"浅色": "light", "深色": "dark", "跟随系统": "system"}
        self.set_ui_theme(mapping.get(value, "system"))

    def _tab_prefetch_urls(self, tab):
        base = self.cfg.get("server_url", "").replace('/api/ingest/script-report', '')
        filaments_url = self.cfg.get("filaments_url", f"{base}/api/ingest/script-filaments")
        printers_url = f"{base}/api/ingest/script-printers"
        analytics_url = f"{base}/api/ingest/script-analytics"
        if tab in ("dashboard", "printers"):
            return [printers_url, filaments_url]
        if tab == "shopping":
            return [filaments_url]
        if tab == "analytics":
            return [analytics_url]
        if tab == "scale_workbench":
            return [f"{base}/api/scale/status", f"{base}/api/scale/device/status?device_id=scale_001"]
        return []

    def _prefetch_tab(self, tab):
        key = self.cfg.get("api_key", "")
        for url in self._tab_prefetch_urls(tab):
            try:
                api_request(url, key, method="GET")
            except Exception:
                pass

    def _refresh_tab_now(self, tab):
        if tab == "dashboard":
            self.refresh_dashboard()
        elif tab == "printers":
            self.refresh_printers_view()
        elif tab == "analytics":
            self.refresh_analytics_view()
        elif tab == "shopping":
            self.refresh_shopping_view()
        elif tab == "scale_workbench":
            self.refresh_scale_workbench()
            self.refresh_device_status()
        elif tab == "logs":
            self.load_logs()

    def _refresh_tab_async(self, tab, on_done=None):
        self._tab_seq += 1
        seq = self._tab_seq
        self._tab_loading = True

        def worker():
            self._prefetch_tab(tab)

            def apply():
                if seq != self._tab_seq or self.current_tab != tab:
                    return
                self._tab_loading = False
                try:
                    self._refresh_tab_now(tab)
                    self._view_loaded_at[tab] = time.time()
                except Exception as e:
                    write_log(f"页面刷新失败 [{tab}]: {e}")
                finally:
                    if on_done is not None:
                        try:
                            self.after(0, on_done)
                        except Exception:
                            pass

            try:
                self.after(0, apply)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def refresh_current_tab(self):
        tab = getattr(self, "current_tab", "dashboard")
        clear_api_cache()
        self._start_tab_transition(tab, self._tab_titles())

    def build_navigation(self):
        if not hasattr(self, "nav_list"):
            return
        for w in self.nav_list.winfo_children():
            w.destroy()
        self.nav_buttons.clear()

        tabs = [
            ("耗材台账", "dashboard", "dashboard"),
            ("设备管理", "printers", "printer"),
            ("数据洞察", "analytics", "chart"),
            ("补货清单", "shopping", "cart"),
            ("称重工作台", "scale_workbench", "scale"),
            ("服务设置", "settings", "settings"),
        ]
        if self.cfg.get("developer_mode", False):
            tabs.append(("运行日志", "logs", "logs"))
        if OFFLINE_MODE:
            tabs = [t for t in tabs if t[1] != "scale_workbench"]

        for text, key, icon_name in tabs:
            btn = ctk.CTkButton(
                self.nav_list, text="  " + text, image=ui_icon(icon_name, 19),
                compound="left", anchor="w", font=self.get_font(13, "bold"),
                height=42, corner_radius=10, fg_color="transparent",
                text_color=COLOR_TEXT_MUTED, hover_color=COLOR_HOVER,
                command=lambda k=key: self.switch_tab(k)
            )
            btn.pack(fill="x", padx=12, pady=2)
            self.register_widget_font(btn, 13, "bold")
            self.nav_buttons[key] = btn

    def _apply_windows_resize_optimizations(self):
        if os.name != "nt":
            return
        try:
            hwnd = get_toplevel_hwnd(self) or self.winfo_id()
            user32 = ctypes.windll.user32
            GWL_STYLE = -16
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            WS_CLIPCHILDREN = 0x02000000
            WS_CLIPSIBLINGS = 0x04000000
            new_style = style | WS_CLIPCHILDREN | WS_CLIPSIBLINGS
            if new_style != style:
                user32.SetWindowLongW(hwnd, GWL_STYLE, new_style)

            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            SWP_FRAMECHANGED = 0x0020
            user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER |
                SWP_NOACTIVATE | SWP_FRAMECHANGED
            )
        except Exception:
            pass

    def _restore_paint_hold_ms(self):
        """恢复时按当前页卡片数量决定透明遮罩保持时长。

        CustomTkinter 的卡片由多个 Canvas 逐层绘制，数据较多时恢复后要 200~500ms
        才能把卡片、色块和进度条全部画完。只等 140ms 会在遮罩关闭后露出未绘制的
        黑/白空框，因此这里按卡片数量自适应等待。
        """
        count = 0
        try:
            if getattr(self, "current_tab", "") == "dashboard":
                count = len(self.scroll_list.winfo_children())
        except Exception:
            pass
        return min(650, 320 + count * 8)

    def _prime_restore_paint(self):
        """在透明遮罩期间多推几轮补绘，让卡片子控件先画完。"""
        if not getattr(self, "_restore_alpha_armed", False):
            return
        try:
            self.update_idletasks()
        except Exception:
            pass
        force_redraw(self)

    def _on_window_map(self, event):
        if event.widget is not self:
            return
        # 恢复瞬间先同步补绘，再等 DWM 呈现，避免先露黑底
        try:
            self.update_idletasks()
        except Exception:
            pass
        force_redraw(self)
        schedule_repaint(self, 20)
        if getattr(self, "_restore_alpha_armed", False):
            try:
                if self._restore_release_job:
                    self.after_cancel(self._restore_release_job)
            except Exception:
                pass
            hold_ms = self._restore_paint_hold_ms()
            for delay in (90, 170, 250):
                self.after(delay, self._prime_restore_paint)
            self._restore_release_job = self.after(hold_ms, self._release_restore_alpha)

    def _on_window_unmap(self, event):
        if event.widget is not self:
            return
        self.after(30, self._arm_restore_alpha)

    def _arm_restore_alpha(self):
        """最小化时把窗口设为全透明，DWM 的恢复动画就不会先显示黑底。"""
        try:
            if self.state() != "iconic" or self._restore_alpha_armed:
                return
        except Exception:
            return
        try:
            self.attributes("-alpha", 0.0)
        except Exception:
            return
        self._restore_alpha_armed = True
        self.after(1500, self._restore_alpha_failsafe)
        write_log("🪟 [重绘] 最小化：启用恢复透明遮罩")

    def _restore_alpha_failsafe(self):
        """兜底：万一没收到 Map，恢复正常状态时不要一直透明。"""
        if not getattr(self, "_restore_alpha_armed", False):
            return
        try:
            if self.state() != "iconic":
                self._release_restore_alpha()
        except Exception:
            pass

    def _release_restore_alpha(self):
        self._restore_release_job = None
        if not getattr(self, "_restore_alpha_armed", False):
            return
        self._restore_alpha_armed = False
        try:
            self.attributes("-alpha", 1.0)
        except Exception:
            pass
        force_redraw(self)
        schedule_repaint(self, 30)
        write_log("🪟 [重绘] 恢复完成：关闭透明遮罩")

    def _on_window_configure(self, event):
        try:
            if event.widget is not self:
                return

            # 用户按住鼠标拖边框改尺寸时，先把重内容换成轻量占位层，松手再一次性恢复
            size = (event.width, event.height)
            size_changed = self._last_window_size is not None and size != self._last_window_size
            self._last_window_size = size
            if (size_changed and not self._layout_frozen and self.state() == "normal"
                    and self.winfo_ismapped() and is_left_button_down()):
                self._freeze_layout_for_resize()

            geometry = (event.width, event.height, event.x, event.y)
            if geometry == self._last_resize_geometry:
                return
            self._last_resize_geometry = geometry
            self._is_resizing = True

            # 只在“普通窗口”状态记录，最大化时不覆盖用户实际调好的尺寸
            if self._geometry_settled and self.state() == "normal" and self.winfo_ismapped():
                rect = self._client_rect_physical()
                if rect:
                    self._last_normal_rect = rect

            if self._resize_after_id is not None:
                try:
                    self.after_cancel(self._resize_after_id)
                except Exception:
                    pass
            self._resize_after_id = self.after(120, self._finish_window_resize)
        except Exception:
            pass

    def _finish_window_resize(self):
        self._resize_after_id = None
        if self._layout_frozen:
            # 还按着鼠标就继续等，松手后再恢复界面
            if is_left_button_down():
                self._resize_after_id = self.after(120, self._finish_window_resize)
                return
            self._thaw_layout_after_resize()
        self._is_resizing = False

    def _ensure_resize_mask(self):
        """轻量占位层：一张纯色底 + 两行文字，拖动时每帧只重绘它。"""
        if self._resize_mask is not None:
            return self._resize_mask
        try:
            mask = ctk.CTkFrame(self, corner_radius=0, fg_color=COLOR_BG_MAIN)
            ctk.CTkLabel(mask, text="丝衡 SiGuan", font=self.get_font(20, "bold"),
                         text_color=COLOR_TEXT_PRIMARY).place(relx=0.5, rely=0.5, anchor="center")
            ctk.CTkLabel(mask, text="正在调整窗口大小，松开鼠标后恢复界面",
                         font=self.get_font(11), text_color=COLOR_TEXT_MUTED).place(
                relx=0.5, rely=0.5, anchor="center", y=28)
            mask.grid_remove()
            self._resize_mask = mask
        except Exception:
            self._resize_mask = None
        return self._resize_mask

    def _freeze_layout_for_resize(self):
        """拖动改尺寸期间隐藏近 200 个圆角控件，只留占位层（实测每帧 300ms → 10ms）。"""
        try:
            mask = self._ensure_resize_mask()
            if mask is None:
                return
            mask.grid(row=0, column=0, columnspan=2, sticky="nsew")
            self.sidebar.grid_remove()
            self.main.grid_remove()
            self._layout_frozen = True
            write_log("🪟 [拖动优化] 进入轻量占位（暂停重排）")
        except Exception:
            self._layout_frozen = False

    def _thaw_layout_after_resize(self):
        try:
            if self._resize_mask is not None:
                self._resize_mask.grid_remove()
            self.sidebar.grid(row=0, column=0, sticky="nsw")
            self.main.grid(row=0, column=1, sticky="nsew")
        except Exception:
            pass
        finally:
            self._layout_frozen = False
            self._is_resizing = False
            write_log("🪟 [拖动优化] 恢复界面")

    def on_close(self):
        try:
            if self._resize_after_id is not None:
                self.after_cancel(self._resize_after_id)
                self._resize_after_id = None
        except Exception:
            pass
        try:
            zoomed = self.state() == "zoomed"
            rect = self._last_normal_rect if zoomed else self._client_rect_physical()
            if rect and rect[2] > 0 and rect[3] > 0:
                self.cfg["window_rect"] = [int(v) for v in rect]
                factor = getattr(self, "_window_dpi_factor", 1.0) or 1.0
                # 兼容旧字段：按逻辑尺寸回写，避免旧版本再把它当逻辑值放大
                self.cfg["window_width"] = max(1, round(rect[2] / factor))
                self.cfg["window_height"] = max(1, round(rect[3] / factor))
            self.cfg["window_zoomed"] = bool(zoomed)
            save_config(self.cfg)
            write_log(f"🪟 [窗口保存] 最大化={zoomed} 矩形={self.cfg.get('window_rect')}")
        except Exception:
            pass
        self.destroy()

    def get_font(self, size, weight="normal"):
        return ctk.CTkFont(family=self.font_family, size=size + 1, weight=weight)

    def register_widget_font(self, widget, size, weight="normal"):
        self.registered_widgets_font.append((widget, size, weight))

    def _refresh_all_fonts(self):
        for widget, size, weight in list(self.registered_widgets_font):
            try:
                if widget.winfo_exists():
                    widget.configure(font=self.get_font(size, weight))
            except Exception:
                pass

        try:
            current_view = next(
                (view for view in self.views.values() if view.winfo_ismapped()),
                None
            )
            if current_view is not None:
                self._refresh_font_family_only(current_view)
            self._refresh_font_family_only(self.sidebar)
            self._refresh_font_family_only(self.main)
        except Exception:
            pass

    def _refresh_font_family_only(self, widget):
        try:
            font_widgets = (ctk.CTkLabel, ctk.CTkButton, ctk.CTkEntry, ctk.CTkTextbox,
                            ctk.CTkComboBox, ctk.CTkOptionMenu, ctk.CTkCheckBox, ctk.CTkSwitch,
                            ctk.CTkSlider, ctk.CTkProgressBar)
            if isinstance(widget, font_widgets):
                current_font = widget.cget("font")
                if current_font is not None:
                    try:
                        current_size = abs(int(current_font.cget("size")))
                    except Exception:
                        current_size = 13
                    try:
                        current_weight = current_font.cget("weight")
                    except Exception:
                        current_weight = "normal"
                    widget.configure(font=ctk.CTkFont(family=self.font_family, size=current_size, weight=current_weight))
        except Exception:
            pass
        try:
            for child in widget.winfo_children():
                self._refresh_font_family_only(child)
        except Exception:
            pass

    def _tab_titles(self):
        return {
            "dashboard": ("耗材台账", "库存总览、低库存提醒与快速操作"),
            "printers": ("设备管理", "机位与虚拟 AMS 槽位映射"),
            "analytics": ("数据洞察", "消耗结构、机位成本与任务统计"),
            "shopping": ("补货清单", "低库存耗材与采购链接"),
            "scale_workbench": ("称重工作台", "ESP32 称重节点、待确认与设备控制"),
            "settings": ("服务设置", "连接、外观、监听与版本信息"),
            "logs": ("运行日志", "开发者模式下的本地运行记录"),
        }

    def _theme_color(self, value):
        if isinstance(value, (tuple, list)):
            return value[1] if getattr(self, "ui_theme", "light") == "dark" else value[0]
        return value

    def _select_tab_view(self, tab_name):
        for name, view in self.views.items():
            if name == tab_name:
                view.grid(row=0, column=0, sticky="nsew")
            else:
                view.grid_forget()

    def _set_active_tab_ui(self, tab_name, titles=None):
        titles = titles or self._tab_titles()
        for name, btn in self.nav_buttons.items():
            active = name == tab_name
            try:
                btn.configure(
                    fg_color=COLOR_ACCENT_SOFT if active else "transparent",
                    text_color=COLOR_BAMBU_GREEN if active else COLOR_TEXT_MUTED
                )
            except Exception:
                pass
        title, sub = titles[tab_name]
        try:
            self.top_title.configure(text=title)
            self.top_sub.configure(text=sub)
        except Exception:
            pass

    def _build_tab_overlay(self):
        overlay = getattr(self, "_tab_overlay", None)
        try:
            if overlay is not None and overlay.winfo_exists():
                self._refresh_tab_overlay_theme()
                return overlay
        except Exception:
            self._tab_overlay = None

        # 用原生 tk.Frame 而不是 CTkFrame：CTk 的 Canvas 背景晚一帧才画，
        # 切页瞬间会透出旧页面的卡片；原生 Frame 会立刻铺满纯背景。
        bg = self._theme_color(COLOR_BG_MAIN)
        overlay = tk.Frame(self.main, bg=bg, highlightthickness=0, bd=0)
        overlay.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 22))
        overlay.grid_rowconfigure(0, weight=1)
        overlay.grid_columnconfigure(0, weight=1)

        center = tk.Frame(overlay, bg=bg, highlightthickness=0, bd=0)
        center.grid(row=0, column=0)
        self._tab_overlay_center = center

        self._tab_spinner_canvas = tk.Canvas(
            center, width=46, height=46, highlightthickness=0, bd=0, bg=bg)
        self._tab_spinner_canvas.pack()
        self._tab_spinner_track = self._tab_spinner_canvas.create_oval(
            6, 6, 40, 40, outline=self._theme_color(COLOR_SURFACE_2), width=1)
        self._tab_spinner_arc = self._tab_spinner_canvas.create_arc(
            6, 6, 40, 40, start=0, extent=280, style="arc",
            outline=self._theme_color(COLOR_BAMBU_GREEN), width=4)

        self._tab_overlay_label = tk.Label(
            center, text="正在加载…", bg=bg,
            fg=self._theme_color(COLOR_TEXT_PRIMARY),
            font=(self.font_family, 14, "bold"))
        self._tab_overlay_label.pack(pady=(10, 0))
        self._tab_overlay_sub = tk.Label(
            center, text="正在准备页面内容", bg=bg,
            fg=self._theme_color(COLOR_TEXT_MUTED),
            font=(self.font_family, 10))
        self._tab_overlay_sub.pack(pady=(4, 0))

        self._tab_overlay = overlay
        return overlay

    def _refresh_tab_overlay_theme(self):
        overlay = getattr(self, "_tab_overlay", None)
        if overlay is None:
            return
        bg = self._theme_color(COLOR_BG_MAIN)
        try:
            overlay.configure(bg=bg)
            self._tab_overlay_center.configure(bg=bg)
            self._tab_spinner_canvas.configure(bg=bg)
            self._tab_spinner_canvas.itemconfigure(
                self._tab_spinner_track, outline=self._theme_color(COLOR_SURFACE_2))
            self._tab_spinner_canvas.itemconfigure(
                self._tab_spinner_arc, outline=self._theme_color(COLOR_BAMBU_GREEN))
            self._tab_overlay_label.configure(
                bg=bg, fg=self._theme_color(COLOR_TEXT_PRIMARY),
                font=(self.font_family, 14, "bold"))
            self._tab_overlay_sub.configure(
                bg=bg, fg=self._theme_color(COLOR_TEXT_MUTED),
                font=(self.font_family, 10))
        except Exception:
            pass

    def _animate_tab_spinner(self, token):
        if token != self._tab_load_token or not self._tab_overlay_visible:
            return
        try:
            angle = (getattr(self, "_tab_spinner_angle", 0) - 14) % 360
            self._tab_spinner_angle = angle
            self._tab_spinner_canvas.itemconfigure(self._tab_spinner_arc, start=angle)
        except Exception:
            pass
        try:
            self._tab_spinner_job = self.after(
                30, lambda: self._animate_tab_spinner(token))
        except Exception:
            self._tab_spinner_job = None

    def _show_tab_overlay(self, tab_name, titles, token):
        self._tab_overlay_started_at = time.perf_counter()
        self._tab_overlay_visible = True
        overlay = self._build_tab_overlay()
        try:
            title = titles.get(tab_name, ("页面", ""))[0]
            self._tab_overlay_label.configure(text=f"正在加载{title}…")
            self._tab_overlay_sub.configure(text="正在准备页面内容")
        except Exception:
            pass
        try:
            # 把整个 content_area 摘下来，而不是逐个隐藏 views：
            # 旧页的卡片、滚动条、Canvas 子控件会随着父容器一起消失，
            # 不会出现“遮罩上还残留一张旧卡片”的残影。
            self.content_area.grid_remove()
            overlay.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 22))
            overlay.lift()
            overlay.update_idletasks()
        except Exception:
            pass
        try:
            if self._tab_spinner_job:
                self.after_cancel(self._tab_spinner_job)
        except Exception:
            pass
        self._tab_spinner_job = None
        self._tab_spinner_angle = 0
        try:
            self._tab_spinner_canvas.itemconfigure(self._tab_spinner_arc, start=0)
        except Exception:
            pass
        try:
            self._tab_spinner_job = self.after(
                30, lambda: self._animate_tab_spinner(token))
        except Exception:
            self._tab_spinner_job = None
        # 兜底：网络极慢或回调丢失时，遮罩最多停留 6 秒
        self.after(6000, lambda: self._failsafe_tab_transition(tab_name, token))

    def _failsafe_tab_transition(self, tab_name, token):
        if token != self._tab_load_token:
            return
        if tab_name in self.views:
            try:
                self._select_tab_view(tab_name)
            except Exception:
                pass
        self._hide_tab_overlay()

    def _lift_tab_overlay(self):
        try:
            if self._tab_overlay is not None and self._tab_overlay_visible:
                self._tab_overlay.lift()
        except Exception:
            pass

    def _hide_tab_overlay(self, token=None):
        if token is not None and token != self._tab_load_token:
            return
        self._tab_overlay_visible = False
        try:
            if self._tab_spinner_job:
                self.after_cancel(self._tab_spinner_job)
        except Exception:
            pass
        self._tab_spinner_job = None
        try:
            if self._tab_overlay is not None:
                # 先恢复内容区（仍在遮罩下面），再撤遮罩，避免中间露出空白
                self.content_area.grid()
                self._tab_overlay.grid_remove()
        except Exception:
            pass

    def _cancel_tab_transition(self):
        self._tab_load_token += 1
        self._hide_tab_overlay()

    def _start_tab_transition(self, tab_name, titles=None):
        titles = titles or self._tab_titles()
        self._tab_load_token += 1
        token = self._tab_load_token
        self._show_tab_overlay(tab_name, titles, token)
        try:
            self.after(25, lambda: self._run_tab_transition(tab_name, token, titles))
        except Exception:
            self._finish_tab_transition(tab_name, token)

    def _run_tab_transition(self, tab_name, token, titles):
        if token != self._tab_load_token or self.current_tab != tab_name:
            return
        try:
            if tab_name not in self.views:
                if tab_name == "dashboard":
                    self.init_dashboard_view()
                elif tab_name == "printers":
                    self.init_printers_view()
                elif tab_name == "analytics":
                    self.init_analytics_view()
                elif tab_name == "shopping":
                    self.init_shopping_view()
                elif tab_name == "scale_workbench":
                    self.init_scale_workbench_view()
                elif tab_name == "settings":
                    self.init_settings_view()
                elif tab_name == "logs":
                    self.init_logs_view()

            self._select_tab_view(tab_name)
            self._lift_tab_overlay()

            if tab_name in ("dashboard", "printers", "analytics", "shopping", "scale_workbench"):
                self._refresh_tab_async(
                    tab_name,
                    on_done=lambda: self._finish_tab_transition(tab_name, token))
            elif tab_name == "settings":
                self.fetch_user_info_async()
                self.after(120, lambda: self._finish_tab_transition(tab_name, token))
            elif tab_name == "logs":
                self.load_logs()
                self.after(100, lambda: self._finish_tab_transition(tab_name, token))
            else:
                self.after(100, lambda: self._finish_tab_transition(tab_name, token))
        except Exception as e:
            write_log(f"页面切换失败 [{tab_name}]: {e}")
            if tab_name in self.views:
                self._select_tab_view(tab_name)
            self._finish_tab_transition(tab_name, token)

    def _finish_tab_transition(self, tab_name, token):
        if token != self._tab_load_token or self.current_tab != tab_name:
            return
        try:
            self.update_idletasks()
            self._lift_tab_overlay()
            force_redraw(self)
        except Exception:
            pass
        elapsed_ms = (time.perf_counter() - self._tab_overlay_started_at) * 1000
        # 至少让转圈稳定显示一小段时间，避免一闪而过
        delay_ms = max(60, int(220 - elapsed_ms))
        self.after(delay_ms, lambda: self._hide_tab_transition(tab_name, token))

    def _hide_tab_transition(self, tab_name, token):
        if token != self._tab_load_token or self.current_tab != tab_name:
            return
        if tab_name in self.views:
            try:
                self._select_tab_view(tab_name)
            except Exception:
                pass
        try:
            self.update_idletasks()
        except Exception:
            pass
        self._hide_tab_overlay()
        force_redraw(self)
        schedule_repaint(self, 20)

    def switch_tab(self, tab_name):
        titles = self._tab_titles()
        if tab_name == "scale_workbench" and OFFLINE_MODE:
            tab_name = "dashboard"
        if tab_name not in titles:
            tab_name = "dashboard"

        self.current_tab = tab_name

        # 已有视图且 4 秒内刷新过：直接切换，不重建、不显示遮罩
        if (tab_name in self.views and tab_name not in ("scale_workbench", "logs")
                and (time.time() - self._view_loaded_at.get(tab_name, 0)) < 4.0):
            self._set_active_tab_ui(tab_name, titles)
            self._cancel_tab_transition()
            self._select_tab_view(tab_name)
            # 切页后补一次整窗重绘，避免 Tk 暴露事件留下黑色碎块
            self.after(15, lambda: (self.update_idletasks(), force_redraw(self)))
            return

        # 先铺遮罩/藏旧页，再改标题和导航高亮：
        # 这样不会出现“标题已经变成新页、下面还是旧页卡片”的中间帧。
        self._start_tab_transition(tab_name, titles)
        self._set_active_tab_ui(tab_name, titles)

    # --------------------------------------------------------------------------
    # 子功能: 账号/API 校验与用户名动态显示 [START]
    # --------------------------------------------------------------------------
    def fetch_user_info_async(self):
        if OFFLINE_MODE:
            self.current_user_name = "本地用户"
            self._user_info_connected = True
            self.update_user_display("本地用户", True)
            return
        base_url = self.cfg.get("server_url", "").replace('/api/ingest/script-report', '')
        api_key = self.cfg.get("api_key", "")
        if not base_url or not api_key:
            self._user_info_connected = False
            self.update_user_display("未配置/未连接", False)
            return

        # 已校验且未过期：直接复用，切到服务设置不再等网络
        if self.current_user_name and (time.time() - getattr(self, "_user_info_checked_at", 0)) < 30:
            self.update_user_display(self.current_user_name, getattr(self, "_user_info_connected", False))
            return
        if getattr(self, "_user_info_loading", False):
            return
        self._user_info_loading = True
        user_info_url = f"{base_url}/api/ingest/script-user-info"

        def worker():
            res = api_request(user_info_url, api_key=api_key, method="GET")

            def apply():
                self._user_info_loading = False
                self._user_info_checked_at = time.time()
                if res and res.get("status") == "success":
                    username = res.get("username", "已连接用户")
                    self.current_user_name = username
                    self._user_info_connected = True
                    self.update_user_display(username, True)
                else:
                    self.current_user_name = "未连接"
                    self._user_info_connected = False
                    self.update_user_display("未连接或 Key 无效", False)

            try:
                self.after(0, apply)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def update_user_display(self, username, is_connected):
        def _update():
            status_color = COLOR_BAMBU_GREEN if is_connected else COLOR_TEXT_MUTED
            if hasattr(self, "top_status_text") and self.top_status_text.winfo_exists():
                if OFFLINE_MODE:
                    status_text = "离线 · " + str(username)
                else:
                    status_text = ("已连接 · " + str(username)) if is_connected else "未连接"
                self.top_status_text.configure(text=status_text, text_color=status_color)
            if hasattr(self, "top_status_dot") and self.top_status_dot.winfo_exists():
                self.top_status_dot.configure(fg_color=status_color)
            if hasattr(self, "side_status_text") and self.side_status_text.winfo_exists():
                self.side_status_text.configure(
                    text="本地数据" if OFFLINE_MODE else ("服务已连接" if is_connected else "等待连接"),
                    text_color=status_color)
            if hasattr(self, "side_status_dot") and self.side_status_dot.winfo_exists():
                self.side_status_dot.configure(fg_color=status_color)
            if hasattr(self, "side_user_text") and self.side_user_text.winfo_exists():
                self.side_user_text.configure(text=str(username))
            if hasattr(self, 'lbl_user_status') and self.lbl_user_status.winfo_exists():
                if is_connected:
                    self.lbl_user_status.configure(text=f"账号: {username}", text_color=COLOR_BAMBU_GREEN, fg_color=COLOR_ACCENT_SOFT)
                else:
                    self.lbl_user_status.configure(text=f"状态: {username}", text_color=COLOR_TEXT_MUTED, fg_color=COLOR_SURFACE_2)
            if hasattr(self, 'lbl_settings_user') and self.lbl_settings_user.winfo_exists():
                if is_connected:
                    self.lbl_settings_user.configure(text=f"当前已认证用户: {username}", text_color=COLOR_BAMBU_GREEN)
                else:
                    self.lbl_settings_user.configure(text="当前未连接或 API Key 无效", text_color=COLOR_TEXT_MUTED)
        self.after(0, _update)

    def open_quick_login_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("账号登录换取 API Key")
        modal.geometry("420x360")
        modal.resizable(False, False)
        self._prepare_modal(modal)
        modal.configure(fg_color=COLOR_BG_MAIN)

        container = ctk.CTkFrame(modal, corner_radius=18, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(container, text="🔑 登录并一键获取 Key", font=self.get_font(17, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(container, text="输入网页端注册的账号密码，将自动生成并绑定永久 API Key", font=self.get_font(10), text_color=COLOR_TEXT_MUTED, wraplength=350, justify="left").pack(anchor="w", padx=16, pady=(0, 10))

        u_box = ctk.CTkFrame(container, fg_color="transparent")
        u_box.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(u_box, text="用户名 / 账号:", font=self.get_font(12, "bold")).pack(anchor="w")
        entry_user = ctk.CTkEntry(u_box, height=36, corner_radius=8, font=self.get_font(12), placeholder_text="请输入用户名")
        entry_user.pack(fill="x", pady=(2, 0))

        p_box = ctk.CTkFrame(container, fg_color="transparent")
        p_box.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(p_box, text="密码:", font=self.get_font(12, "bold")).pack(anchor="w")
        entry_pwd = ctk.CTkEntry(p_box, height=36, corner_radius=8, show="*", font=self.get_font(12), placeholder_text="请输入密码")
        entry_pwd.pack(fill="x", pady=(2, 0))

        lbl_tip = ctk.CTkLabel(container, text="", font=self.get_font(11), text_color="#EF4444")
        lbl_tip.pack(anchor="w", padx=16, pady=(4, 0))

        def do_quick_login():
            user = entry_user.get().strip()
            pwd = entry_pwd.get().strip()
            if not user or not pwd:
                lbl_tip.configure(text="⚠️ 请输入完整的用户名与密码！")
                return

            base_url = self.entry_server_url.get().strip().replace('/api/ingest/script-report', '')
            if not base_url:
                lbl_tip.configure(text="⚠️ 请先在设置页填写正确的扣减上报地址！")
                return

            lbl_tip.configure(text="正在连接服务端校验...", text_color=COLOR_TEXT_MUTED)
            modal.update_idletasks()

            def _login_thread():
                try:
                    login_url = f"{base_url}/api/auth/quick-api-key"
                    res = api_request(login_url, method="POST", data={"username": user, "password": pwd})
                    if res and res.get("status") == "success":
                        key = res.get("api_key")
                        name = res.get("username")
                        self.after(0, lambda: self.apply_quick_api_key(key, name, modal))
                    else:
                        self.after(0, lambda: lbl_tip.configure(text="❌ 账号或密码错误，请检查！", text_color="#EF4444"))
                except Exception as e:
                    self.after(0, lambda err=str(e): lbl_tip.configure(text=f"❌ 连接失败: {err}", text_color="#EF4444"))

            threading.Thread(target=_login_thread, daemon=True).start()

        ctk.CTkButton(
            container, text="✔ 立即获取并绑定", height=38, corner_radius=12,
            fg_color=COLOR_BAMBU_GREEN, hover_color=("#0B8A5F", "#4ADE80"),
            font=self.get_font(13, "bold"), command=do_quick_login
        ).pack(fill="x", padx=16, pady=(12, 12), side="bottom")

    def apply_quick_api_key(self, api_key, username, modal_window):
        self.entry_api_key.delete(0, tk.END)
        self.entry_api_key.insert(0, api_key)
        self.save_settings(silent=True)
        self.fetch_user_info_async()
        messagebox.showinfo("成功", f"🎉 欢迎回来，{username}！\n已成功获取专属 API Key 并加密存储。")
        modal_window.destroy()
    # --------------------------------------------------------------------------
    # 子功能: 账号/API 校验与用户名动态显示 [END]
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # 子功能: 智能更新检测与自覆盖 [START]
    # --------------------------------------------------------------------------
    def pick_update_asset(self, assets):
        """按客户端形态挑选安装包：离线版只认文件名含 offline 的 exe。
        返回 (asset, reason)，reason 为空表示成功。"""
        exes = [a for a in (assets or []) if str(a.get("name", "")).lower().endswith(".exe")]

        def _usable(a):
            n = str(a.get("name", "")).lower()
            return "server" not in n and "standalone" not in n and "单机" not in n

        cand = [a for a in exes if _usable(a)]
        if OFFLINE_MODE:
            off = [a for a in cand if "offline" in str(a.get("name", "")).lower()]
            return (off[0], "") if off else (None, "NO_OFFLINE_ASSET")
        on = [a for a in cand if "offline" not in str(a.get("name", "")).lower()]
        if on:
            return on[0], ""
        return (None, "NO_ONLINE_ASSET" if cand else "NO_EXE_ASSET")

    def check_github_releases(self):
        channel = self.cfg.get("update_channel", "Release (正式版)")
        url = f"{UPDATE_API_URL}?_t={int(time.time()*1000)}"
        req = urllib.request.Request(url, headers={"User-Agent": "BambuStudio-Client"})
        
        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    releases = json.loads(resp.read().decode('utf-8'))
                    if not isinstance(releases, list):
                        return (False, None, "INVALID_RESPONSE")
                    for r in releases:
                        if "Release" in channel and r.get("prerelease", False):
                            continue
                        online_tag = r.get("tag_name", "").strip()
                        if is_newer_version(online_tag, CURRENT_VERSION):
                            return (True, r, "OK")
                    return (False, None, "LATEST")
            except urllib.error.HTTPError as e:
                if e.code == 403:
                    return (False, None, "RATE_LIMIT")
                return (False, None, f"HTTP_{e.code}")
            except Exception as e:
                if attempt == 1:
                    return (False, None, str(e))
                time.sleep(1)

    def silent_check_update(self):
        try:
            has_update, rel, code = self.check_github_releases()
            if has_update and rel:
                # 离线版只提示离线包；发布页没传离线包就不打扰用户
                if OFFLINE_MODE:
                    asset, _ = self.pick_update_asset(rel.get("assets", []))
                    if not asset:
                        write_log("ℹ️ 新版本未提供离线包，离线版跳过更新提示")
                        return
                self.latest_release_info = rel
                online_tag = rel.get("tag_name", "")
                self.after(100, self.show_new_badge)
                if self.cfg.get("skipped_version", "") != online_tag:
                    self.after(600, lambda: self.open_update_modal(is_startup=True))
            elif code == "RATE_LIMIT":
                write_log("ℹ️ GitHub API 触发限流，已由服务器缓存保护并跳过")
        except Exception as e:
            write_log(f"静默检查异常: {e}")

    def manual_check_update(self):
        self.save_settings(silent=True)

        def _worker():
            has_update, rel, code = self.check_github_releases()
            if has_update and rel:
                if OFFLINE_MODE:
                    asset, _ = self.pick_update_asset(rel.get("assets", []))
                    tag = rel.get("tag_name", "新版本")
                    if not asset:
                        self.after(50, lambda t=tag: messagebox.showwarning(
                            "检查更新",
                            f"发现新版本 {t}，但该版本未上传离线包。\n"
                            "离线包文件名需包含 offline（如 SiGuan_Offline_1.4.2.exe），请稍后再试。"))
                        return
                self.latest_release_info = rel
                self.after(50, self.show_new_badge)
                self.after(50, lambda: self.open_update_modal(is_startup=False))
            elif code == "LATEST":
                self.after(50, lambda: messagebox.showinfo("检查更新", f"当前已是最新版本 ({VERSION_TAG})！"))
            elif code == "RATE_LIMIT":
                self.after(50, lambda: messagebox.showwarning("提示", "访问频次触发限制（403）！\n请稍后再试或点击【网盘备用下载】。"))
            else:
                self.after(50, lambda: messagebox.showerror("错误", f"检查更新失败: {code}"))
        threading.Thread(target=_worker, daemon=True).start()

    def show_new_badge(self):
        if hasattr(self, 'badge_new') and self.badge_new.winfo_exists():
            self.badge_new.pack(side="left", padx=(6, 0))

    def open_update_modal(self, is_startup=False):
        if not self.latest_release_info:
            return

        tag_name = self.latest_release_info.get("tag_name", "新版本")
        body = self.latest_release_info.get("body", "无更新说明。")
        html_url = self.latest_release_info.get("html_url", f"https://github.com/{GITHUB_REPO}/releases")

        raw_download_url = None
        asset_exe_name = None
        asset, asset_reason = self.pick_update_asset(self.latest_release_info.get("assets", []))
        if asset:
            raw_download_url = asset.get("browser_download_url")
            asset_exe_name = asset.get("name")
        elif asset_reason in ("NO_OFFLINE_ASSET", "NO_ONLINE_ASSET", "NO_EXE_ASSET"):
            if OFFLINE_MODE:
                title, msg = "无离线安装包", (
                    f"发现新版本 {tag_name}，但该版本未上传离线包。\n"
                    "离线包文件名需包含 offline（如 SiGuan_Offline_1.4.2.exe）。")
            else:
                title, msg = "无在线安装包", (
                    f"发现新版本 {tag_name}，但该版本没有可用的在线安装包。\n"
                    "请前往发布页下载，或等待作者补传在线 exe。")
            self.after(50, lambda t=title, m=msg: messagebox.showwarning(t, m))
            return

        modal = ctk.CTkToplevel(self)
        modal.title(f"发现新版本 - {tag_name}")
        modal.geometry("640x510")
        modal.minsize(620, 480)
        self._prepare_modal(modal)
        modal.configure(fg_color=COLOR_BG_MAIN)

        container = ctk.CTkFrame(modal, corner_radius=20, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(container, text=f"✨ 发现新版本: {tag_name}", font=self.get_font(18, "bold"), text_color=COLOR_BAMBU_GREEN).pack(anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(container, text=f"当前运行版本: {VERSION_TAG}", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 10))

        txt_body = ctk.CTkTextbox(container, corner_radius=12, fg_color=COLOR_BG_MAIN, font=self.get_font(12))
        txt_body.pack(fill="both", expand=True, padx=16, pady=6)
        txt_body.insert("1.0", body)
        txt_body.configure(state="disabled")

        lbl_status = ctk.CTkLabel(container, text="", font=self.get_font(11), text_color=COLOR_TEXT_MUTED)
        lbl_status.pack(anchor="w", padx=16, pady=(2, 0))

        btn_box = ctk.CTkFrame(container, fg_color="transparent")
        btn_box.pack(fill="x", padx=16, pady=12)

        def skip_this_version():
            self.cfg["skipped_version"] = tag_name
            save_config(self.cfg)
            modal.destroy()

        btn_auto_update = ctk.CTkButton(
            btn_box, text="⚡ 一键自覆盖更新", height=38, corner_radius=12,
            fg_color=COLOR_BAMBU_GREEN, hover_color=("#0B8A5F", "#4ADE80"),
            font=self.get_font(13, "bold"),
            command=lambda: self.start_auto_replace_update(raw_download_url, tag_name, asset_exe_name, lbl_status, btn_auto_update)
        )
        btn_auto_update.pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            btn_box, text="☁️ 网盘备用下载", height=38, corner_radius=12,
            fg_color="#2563EB", hover_color="#1D4ED8",
            font=self.get_font(12, "bold"),
            command=lambda: webbrowser.open(BACKUP_PAN_URL)
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            btn_box, text="🌐 GitHub", height=38, corner_radius=12,
            fg_color=COLOR_CARD_BG, hover_color=COLOR_CARD_BORDER, border_width=1, border_color=COLOR_CARD_BORDER,
            font=self.get_font(12),
            command=lambda: webbrowser.open(html_url)
        ).pack(side="right", padx=(6, 0))

        if is_startup:
            ctk.CTkButton(
                btn_box, text="跳过此版本", height=38, corner_radius=12,
                fg_color="transparent", hover_color=COLOR_CARD_BORDER,
                font=self.get_font(12), command=skip_this_version
            ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            btn_box, text="稍后", height=38, corner_radius=12,
            fg_color="transparent", hover_color=COLOR_CARD_BORDER,
            font=self.get_font(12), command=modal.destroy
        ).pack(side="right")

    def start_auto_replace_update(self, raw_github_download_url, new_tag_name, asset_exe_name, lbl_status, btn_ctrl):
        if not getattr(sys, 'frozen', False):
            messagebox.showinfo("提示", "当前为源码运行模式，请打包为 exe 后体验自覆盖更新！")
            return

        if not raw_github_download_url:
            messagebox.showwarning("提示", "当前 Release 资产中未检测到 exe 文件，请点击【网盘备用下载】！")
            return

        btn_ctrl.configure(state="disabled", text="正在下载...")
        lbl_status.configure(text="正在连接国内加速节点，请稍候...")

        def _worker():
            try:
                temp_exe = os.path.join(os.getenv("TEMP", "."), f"bambu_new_{int(time.time())}.exe")
                download_success = False
                last_err = ""

                candidate_urls = [f"{prefix}{raw_github_download_url}" for prefix in GH_PROXY_NODES]
                candidate_urls.append(raw_github_download_url)

                for idx, download_url in enumerate(candidate_urls):
                    node_label = f"节点 {idx+1}/{len(candidate_urls)}"
                    self.after(0, lambda n=node_label: lbl_status.configure(text=f"正在通过 [{n}] 下载更新包..."))
                    try:
                        req = urllib.request.Request(download_url, headers={"User-Agent": "BambuStudio-Updater"})
                        with urllib.request.urlopen(req, timeout=12) as resp, open(temp_exe, 'wb') as f:
                            total_size = int(resp.getheader('Content-Length', 0))
                            downloaded = 0
                            while True:
                                chunk = resp.read(64 * 1024)
                                if not chunk:
                                    break
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    percent = int(downloaded / total_size * 100)
                                    self.after(0, lambda p=percent, d=downloaded, t=total_size, n=node_label: 
                                        lbl_status.configure(text=f"[{n}] 进度: {p}% ({d//1024}KB / {t//1024}KB)"))

                            if downloaded > 5 * 1024 * 1024:
                                download_success = True
                                break
                            else:
                                raise Exception("文件体积异常，切换备用节点")
                    except Exception as e:
                        last_err = str(e)
                        write_log(f"加速节点 [{download_url}] 尝试失败: {e}")
                        if os.path.exists(temp_exe):
                            try: os.remove(temp_exe)
                            except Exception: pass
                        continue

                if not download_success:
                    raise Exception(f"所有镜像加速节点均超时，建议使用网盘下载: {last_err}")

                current_exe = sys.executable
                current_dir = os.path.dirname(current_exe)
                if OFFLINE_MODE:
                    # 离线版沿用当前文件名（含 offline），否则换名后会退回在线模式
                    target_exe_name = os.path.basename(current_exe)
                else:
                    target_exe_name = asset_exe_name if asset_exe_name else os.path.basename(current_exe)
                target_exe_path = os.path.join(current_dir, target_exe_name)

                bat_script = os.path.join(os.getenv("TEMP", "."), "bambu_updater.bat")
                bat_content = f"""@echo off
chcp 65001 > nul
timeout /t 3 /nobreak > nul

:retry_del
if exist "{current_exe}" (
    del /f /q "{current_exe}" > nul 2>&1
    if exist "{current_exe}" (
        timeout /t 1 /nobreak > nul
        goto retry_del
    )
)

:move_file
move /y "{temp_exe}" "{target_exe_path}" > nul 2>&1
if not exist "{target_exe_path}" (
    timeout /t 1 /nobreak > nul
    goto move_file
)

timeout /t 1 /nobreak > nul
start "" "{target_exe_path}"
del "%~f0"
"""
                with open(bat_script, 'w', encoding='utf-8') as f:
                    f.write(bat_content)

                self.after(0, lambda: lbl_status.configure(text="下载完毕，正在重启并替换为新版本..."))
                time.sleep(1)
                subprocess.Popen(f'cmd /c "{bat_script}"', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                os._exit(0)
            except Exception as e:
                write_log(f"自覆盖更新异常: {e}")
                self.after(50, lambda: messagebox.showerror("更新失败", f"下载出错: {e}\n\n请点击【☁️ 网盘备用下载】手动获取最新安装包。"))
                self.after(50, lambda: btn_ctrl.configure(state="normal", text="⚡ 一键自覆盖更新"))

        threading.Thread(target=_worker, daemon=True).start()
    # --------------------------------------------------------------------------
    # 子功能: 智能更新检测与自覆盖 [END]
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # 子功能: 扣减任务队列与自动处理 [START]
    # --------------------------------------------------------------------------
    def enqueue_auto_deduct(self, gcode_path, slot_weights, detected_model_name):
        self.deduct_queue.append((gcode_path, slot_weights, detected_model_name))
        self.process_deduct_queue()

    def process_deduct_queue(self):
        if self.is_dialog_showing or not self.deduct_queue:
            return

        self.is_dialog_showing = True
        gcode_path, slot_weights, detected_model_name = self.deduct_queue.pop(0)

        base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
        web_filaments = api_request(self.cfg["filaments_url"], self.cfg["api_key"], method="GET") or []
        printers = api_request(f"{base_url}/api/ingest/script-printers", self.cfg["api_key"], method="GET") or []
        
        current_total_w = sum(slot_weights)
        last_w = self.cfg.get("last_slice_weight", 0.0)
        
        is_confirmed, task_name, slot_map, target_printer_id = ask_user_multi_slot_mapping_modern(
            slot_weights, web_filaments, detected_model_name=detected_model_name, 
            parent_window=self, font_family=self.font_family, last_weight=last_w,
            printers=printers, default_printer_id=self.cfg.get("selected_printer_id")
        )

        if is_confirmed:
            self.cfg["last_slice_weight"] = round(current_total_w, 2)
            if target_printer_id:
                self.cfg["selected_printer_id"] = target_printer_id
            save_config(self.cfg)

            time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            for slot_idx, deductions in slot_map.items():
                for info in deductions:
                    f_id = info["filament_id"]
                    w = info["used_weight_g"]
                    if w <= 0:
                        continue
                    
                    is_backup = (len(deductions) > 1 and info == deductions[-1])
                    suffix = "_(自动续打)" if is_backup else ""
                    full_task_name = f"{task_name}_槽{slot_idx}{suffix}_{time_str}_{w}g.gcode"
                    
                    payload = {
                        "filament_id": f_id,
                        "used_weight_g": w,
                        "task_name": full_task_name,
                        "printer_id": target_printer_id
                    }
                    res = api_request(self.cfg["server_url"], self.cfg["api_key"], method="POST", data=payload)
                    if res:
                        write_log(f"✅ [自动扣减成功] 槽位{slot_idx} -> 耗材ID:{f_id} 扣除 {w}g, 设备ID: {target_printer_id}")
                    else:
                        write_log(f"❌ 槽位{slot_idx} 上报失败")
            self.refresh_dashboard()

        self.is_dialog_showing = False
        if self.deduct_queue:
            self.after(200, self.process_deduct_queue)
    # --------------------------------------------------------------------------
    # 子功能: 扣减任务队列与自动处理 [END]
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # 子功能: 1. 耗材台账看板视图 [START]
    # --------------------------------------------------------------------------
    def init_dashboard_view(self):
        view = ctk.CTkFrame(self.content_area, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(4, weight=1)
        self._dash_filaments = []
        self._dash_printers = []
        self.dash_only_low = False
        self.current_surface_filter = "全部表面"

        toolbar = ctk.CTkFrame(view, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        toolbar.grid_columnconfigure(3, weight=1)

        self.dash_search = ctk.CTkEntry(
            toolbar, width=240, height=38, corner_radius=10,
            placeholder_text="搜索品牌 / 材质 / 颜色 / 表面 / 备注…",
            fg_color=COLOR_INPUT_BG, border_color=COLOR_CARD_BORDER,
            text_color=COLOR_TEXT_PRIMARY, placeholder_text_color=COLOR_TEXT_MUTED,
            font=self.get_font(12))
        self.dash_search.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.dash_search.bind("<KeyRelease>", lambda _e: self.render_dash_cards())

        self.combo_dash_filter = ctk.CTkComboBox(
            toolbar, values=["全部打印机"], width=156, height=38, corner_radius=10,
            font=self.get_font(11), command=self.on_dash_filter_change,
            fg_color=COLOR_INPUT_BG, border_color=COLOR_CARD_BORDER,
            button_color=COLOR_SURFACE_2, button_hover_color=COLOR_HOVER,
            text_color=COLOR_TEXT_PRIMARY, dropdown_fg_color=COLOR_CARD_BG,
            dropdown_text_color=COLOR_TEXT_PRIMARY, dropdown_hover_color=COLOR_HOVER)
        self.combo_dash_filter.grid(row=0, column=1, sticky="w", padx=(0, 8))

        self.btn_low = self.ui_button(toolbar, "只看低库存", self.toggle_dash_low, kind="ghost",
                                      height=38, icon_name="alert", font_size=11)
        self.btn_low.grid(row=0, column=2, sticky="w", padx=(0, 8))

        self.surface_bar = ctk.CTkFrame(view, fg_color="transparent")
        self.surface_bar.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.surface_chips = {}
        self._build_surface_chips()

        self.ui_button(toolbar, "刷新", self.refresh_current_tab, kind="ghost",
                       height=38, icon_name="refresh", font_size=11).grid(row=0, column=4, padx=(0, 8))
        self.ui_button(toolbar, "新增耗材", self.open_add_filament_modal, kind="primary",
                       height=38, icon_name="plus", font_size=12).grid(row=0, column=5)

        self.banner = ctk.CTkFrame(view, fg_color="transparent")
        self.banner.grid(row=2, column=0, sticky="ew", pady=(0, 18))
        for i in range(4):
            self.banner.grid_columnconfigure(i, weight=1, uniform="stat")
        self.stat_value_labels = {}
        self._make_stat_card(self.banner, 0, "库存价值", "¥ --", "按剩余克重折算", COLOR_BAMBU_GREEN, "value")
        self._make_stat_card(self.banner, 1, "剩余总重", "-- g", "全部在册耗材", COLOR_BLUE, "weight")
        self._make_stat_card(self.banner, 2, "平均克重单价", "¥ --/g", "库存价值 ÷ 总重", COLOR_VIOLET, "unit")
        self._make_stat_card(self.banner, 3, "在册耗材", "-- 款", "点击下方卡片管理", COLOR_AMBER, "count")

        list_head = ctk.CTkFrame(view, fg_color="transparent")
        list_head.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        title_row = ctk.CTkFrame(list_head, fg_color="transparent")
        title_row.pack(side="left")
        self.ui_label(title_row, "在册耗材", 14, "bold").pack(side="left")
        self.dash_count_label = self.ui_label(title_row, "0", 10, "bold", COLOR_BAMBU_GREEN,
                                              fg_color=COLOR_ACCENT_SOFT, corner_radius=20, padx=9, pady=3)
        self.dash_count_label.pack(side="left", padx=(8, 0))
        self.badge_new = ctk.CTkButton(
            title_row, text="NEW", width=44, height=22, corner_radius=20,
            fg_color=COLOR_BADGE_RED, hover_color=COLOR_BADGE_RED,
            font=self.get_font(9, "bold"), text_color=("#FFFFFF", "#FFFFFF"),
            command=self.open_update_modal)
        self.ui_label(list_head, "调整 / 历史 / 删除均在行尾", 10, "normal", COLOR_TEXT_MUTED).pack(side="right")

        self.scroll_list = self.ui_scroll(view, fg_color="transparent")
        self.scroll_list.grid(row=4, column=0, sticky="nsew")
        self.scroll_list.grid_columnconfigure(0, weight=1)

        self.views["dashboard"] = view
        self.render_dash_cards()

    def _build_surface_chips(self):
        for w in self.surface_bar.winfo_children():
            w.destroy()
        self.surface_chips = {}
        for opt in ["全部表面"] + SURFACE_OPTIONS:
            btn = ctk.CTkButton(
                self.surface_bar, text=opt, height=28, corner_radius=14, width=64,
                fg_color=COLOR_SURFACE_2, hover_color=COLOR_HOVER, text_color=COLOR_TEXT_MUTED,
                font=self.get_font(10, "bold"),
                command=lambda o=opt: self.set_surface_filter(o))
            btn.pack(side="left", padx=(0, 6))
            self.surface_chips[opt] = btn
        self._sync_surface_chips()

    def _sync_surface_chips(self):
        current = getattr(self, "current_surface_filter", "全部表面")
        for name, btn in getattr(self, "surface_chips", {}).items():
            active = name == current
            try:
                btn.configure(
                    fg_color=COLOR_ACCENT_SOFT if active else COLOR_SURFACE_2,
                    text_color=COLOR_BAMBU_GREEN if active else COLOR_TEXT_MUTED,
                    border_width=1 if active else 0,
                    border_color=COLOR_BAMBU_GREEN if active else COLOR_SURFACE_2)
            except Exception:
                pass

    def set_surface_filter(self, choice):
        self.current_surface_filter = choice
        self._sync_surface_chips()
        self.render_dash_cards()

    def _make_stat_card(self, parent, column, title, value, caption, accent, key):
        card = self.ui_card(parent, corner_radius=16)
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 5, 0 if column == 3 else 5))
        bar = ctk.CTkFrame(card, height=3, corner_radius=2, fg_color=accent)
        bar.pack(fill="x")
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(10, 12))
        self.ui_label(body, title, 10, "bold", COLOR_TEXT_MUTED).pack(anchor="w")
        value_lbl = self.ui_label(body, value, 24, "bold")
        value_lbl.pack(anchor="w", pady=(2, 0))
        self.ui_label(body, caption, 9, "normal", COLOR_TEXT_MUTED).pack(anchor="w", pady=(2, 0))
        self.stat_value_labels[key] = value_lbl

    def toggle_dash_low(self):
        self.dash_only_low = not getattr(self, "dash_only_low", False)
        try:
            if self.dash_only_low:
                self.btn_low.configure(fg_color=COLOR_ACCENT_SOFT, text_color=COLOR_BAMBU_GREEN)
            else:
                self.btn_low.configure(fg_color=COLOR_SURFACE_2, text_color=COLOR_TEXT_PRIMARY)
        except Exception:
            pass
        self.render_dash_cards()

    def on_dash_filter_change(self, choice):
        self.current_dashboard_filter = choice
        self.render_dash_cards()

    def on_surface_filter_change(self, choice):
        self.set_surface_filter(choice)

    def refresh_dashboard(self):
        base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
        self._dash_printers = api_request(f"{base_url}/api/ingest/script-printers", self.cfg["api_key"], method="GET") or []
        p_names = ["全部打印机"] + [p["name"] for p in self._dash_printers]
        try:
            self.combo_dash_filter.configure(values=p_names)
        except Exception:
            pass
        if self.current_dashboard_filter not in p_names:
            self.current_dashboard_filter = "全部打印机"
            try:
                self.combo_dash_filter.set("全部打印机")
            except Exception:
                pass

        filaments = api_request(self.cfg["filaments_url"], self.cfg["api_key"], method="GET")
        self._dash_filaments = filaments if isinstance(filaments, list) else []

        total_types = len(self._dash_filaments)
        total_weight = sum([item.get('current_weight_g', 0) or 0 for item in self._dash_filaments])
        total_value = 0.0
        for item in self._dash_filaments:
            price = item.get('price', 0) or 0
            init_w = item.get('initial_weight_g', 1000) or 1000
            curr_w = item.get('current_weight_g', 0) or 0
            if init_w > 0:
                total_value += (price / init_w) * curr_w
        avg_unit_price = (total_value / total_weight) if total_weight > 0 else 0.0

        try:
            self.stat_value_labels["value"].configure(text=f"¥ {total_value:,.2f}")
            self.stat_value_labels["weight"].configure(text=f"{total_weight:,.1f} g")
            self.stat_value_labels["unit"].configure(text=f"¥ {avg_unit_price:.3f}/g")
            self.stat_value_labels["count"].configure(text=f"{total_types} 款")
        except Exception:
            pass

        self.render_dash_cards()

    def _dash_filtered(self):
        items = list(getattr(self, "_dash_filaments", []))
        if self.current_dashboard_filter != "全部打印机":
            matched = next((p for p in getattr(self, "_dash_printers", []) if p["name"] == self.current_dashboard_filter), None)
            if matched:
                ams_slots = matched.get("ams_slots") or {}
                mounted = [int(v) for v in ams_slots.values() if v]
                items = [f for f in items if f.get("id") in mounted]
        if getattr(self, "current_surface_filter", "全部表面") != "全部表面":
            items = [f for f in items if (f.get("surface_effect") or "标准") == self.current_surface_filter]
        query = ""
        try:
            query = self.dash_search.get().strip().lower()
        except Exception:
            pass
        if query:
            items = [f for f in items if query in " ".join([
                str(f.get("brand", "")), str(f.get("material", "")),
                str(f.get("color_name", "")), str(f.get("surface_effect", "")),
                f"{filament_diameter_mm(f):g} mm",
                str(f.get("remarks", "")), str(f.get("nfc_uid", ""))]).lower()]
        if getattr(self, "dash_only_low", False):
            items = [f for f in items if (f.get("current_weight_g") or 0) < 200]
        return items

    def render_dash_cards(self):
        if not hasattr(self, "scroll_list"):
            return
        for w in self.scroll_list.winfo_children():
            w.destroy()
        items = self._dash_filtered()
        try:
            self.dash_count_label.configure(text=str(len(items)))
        except Exception:
            pass
        if not items:
            empty = ctk.CTkFrame(self.scroll_list, fg_color="transparent")
            empty.pack(fill="both", expand=True, pady=40)
            self.ui_label(empty, "没有匹配的耗材", 15, "bold").pack(anchor="w")
            self.ui_label(empty, "可以调整筛选条件，或先新增一卷耗材。", 11, "normal", COLOR_TEXT_MUTED).pack(anchor="w", pady=(4, 12))
            action_row = ctk.CTkFrame(empty, fg_color="transparent")
            action_row.pack(anchor="w")
            self.ui_button(action_row, "新增耗材", self.open_add_filament_modal, kind="primary",
                           height=36, icon_name="plus", font_size=11).pack(side="left", padx=(0, 8))
            if OFFLINE_MODE:
                def seed_local():
                    offline_seed_sample(True)
                    clear_api_cache()
                    self.refresh_dashboard()
                self.ui_button(action_row, "载入示例数据", seed_local, kind="ghost",
                               height=36, icon_name="box", font_size=11).pack(side="left")
            return

        for item in items:
            self._render_filament_row(item)

    def _render_filament_row(self, item):
        fid = item.get('id', '-')
        brand = item.get('brand', 'Bambu')
        material = item.get('material', '-')
        color_name = item.get('color_name', '-')
        curr_w = item.get('current_weight_g', 0) or 0
        init_w = item.get('initial_weight_g', 1000) or 1000
        price = item.get('price', 0) or 0
        curr_val = (price / init_w * curr_w) if init_w > 0 else 0.0
        ratio = max(0.0, min(1.0, (curr_w / init_w) if init_w > 0 else 0.0))

        card = self.ui_card(self.scroll_list, corner_radius=16)
        card.pack(fill="x", pady=5)
        card.grid_columnconfigure(1, weight=1)

        color = item.get('color_hex') or "#6B7280"
        try:
            swatch = ctk.CTkFrame(card, width=42, height=42, corner_radius=12, fg_color=color,
                                  border_width=1, border_color=COLOR_CARD_BORDER)
        except Exception:
            swatch = ctk.CTkFrame(card, width=42, height=42, corner_radius=12, fg_color="#6B7280")
        swatch.grid(row=0, column=0, padx=(16, 12), pady=14)
        swatch.grid_propagate(False)

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.grid(row=0, column=1, sticky="w", pady=14)
        self.ui_label(info, f"{brand} {material}", 13, "bold").pack(anchor="w")
        nfc_txt = " · NFC 已绑定" if item.get("nfc_uid") else ""
        surface = item.get("surface_effect") or "标准"
        diameter = filament_diameter_mm(item)
        self.ui_label(info, f"#{fid} · {color_name} · {surface} · {diameter:g} mm{nfc_txt}", 10, "normal", COLOR_TEXT_MUTED).pack(anchor="w", pady=(2, 0))
        remark = str(item.get("remarks") or "").strip()
        if remark:
            self.ui_label(info, "备注：" + (remark[:42] + ("…" if len(remark) > 42 else "")),
                          9, "normal", COLOR_TEXT_MUTED).pack(anchor="w", pady=(1, 0))

        progress_box = ctk.CTkFrame(card, fg_color="transparent")
        progress_box.grid(row=0, column=2, sticky="w", padx=(6, 18), pady=14)
        bar_color = COLOR_BAMBU_GREEN if ratio > 0.5 else (COLOR_AMBER if ratio > 0.2 else COLOR_BADGE_RED)
        bar = ctk.CTkProgressBar(progress_box, width=180, height=6, corner_radius=3,
                                 fg_color=COLOR_TRACK, progress_color=bar_color)
        bar.pack(anchor="w")
        bar.set(ratio)
        self.ui_label(progress_box, f"{curr_w:.1f} g / {init_w:.0f} g", 9, "normal", COLOR_TEXT_MUTED).pack(anchor="w", pady=(4, 0))

        value_box = ctk.CTkFrame(card, fg_color="transparent")
        value_box.grid(row=0, column=3, sticky="e", padx=(0, 16), pady=14)
        self.ui_label(value_box, f"¥ {curr_val:,.2f}", 13, "bold").pack(anchor="e")
        self.ui_label(value_box, "剩余价值", 9, "normal", COLOR_TEXT_MUTED).pack(anchor="e")

        if ratio > 0.5:
            pill = self.ui_pill(card, "充足", COLOR_ACCENT_SOFT, COLOR_BAMBU_GREEN)
        elif ratio > 0.2:
            pill = self.ui_pill(card, "偏低", COLOR_AMBER_SOFT, COLOR_AMBER)
        else:
            pill = self.ui_pill(card, "告急", COLOR_RED_SOFT, COLOR_BADGE_RED)
        pill.grid(row=0, column=4, padx=(0, 14))

        ops = ctk.CTkFrame(card, fg_color="transparent")
        ops.grid(row=0, column=5, padx=(0, 12), pady=14)
        self.ui_button(ops, "调整", lambda f=item: self.open_adjust_modal(f), kind="ghost",
                       width=44, height=28, font_size=10).pack(side="left", padx=2)
        self.ui_button(ops, "编辑", lambda f=item: self.open_edit_filament_modal(f), kind="ghost",
                       width=44, height=28, font_size=10).pack(side="left", padx=2)
        self.ui_button(ops, "复制", lambda f=item: self.copy_filament(f), kind="ghost",
                       width=44, height=28, font_size=10).pack(side="left", padx=2)
        self.ui_button(ops, "历史", lambda f=item: self.open_history_modal(f), kind="ghost",
                       width=44, height=28, font_size=10).pack(side="left", padx=2)
        self.ui_button(ops, "删除", lambda i=fid: self.delete_filament(i), kind="danger",
                       width=44, height=28, font_size=10).pack(side="left", padx=2)

    # --------------------------------------------------------------------------
    # 子功能: 1. 耗材台账看板视图 [END]
    # --------------------------------------------------------------------------
    # 子功能: 1. 耗材台账看板视图 [END]
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # 子功能: 2. 设备管理视图 (Printers & 虚拟 AMS) [START]
    # --------------------------------------------------------------------------
    def init_printers_view(self):
        view = ctk.CTkFrame(self.content_area, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(2, weight=1)

        toolbar = ctk.CTkFrame(view, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.ui_label(toolbar, "机位与虚拟 AMS", 14, "bold").pack(side="left")
        self.printer_count_label = self.ui_label(toolbar, "0 台", 10, "bold", COLOR_BAMBU_GREEN,
                                                 fg_color=COLOR_ACCENT_SOFT, corner_radius=20, padx=9, pady=3)
        self.printer_count_label.pack(side="left", padx=(8, 0))
        self.ui_button(toolbar, "刷新", self.refresh_current_tab, kind="ghost",
                       height=36, icon_name="refresh", font_size=11).pack(side="right", padx=(8, 0))
        self.ui_button(toolbar, "添加打印机", self.open_add_printer_modal, kind="primary",
                       height=36, icon_name="plus", font_size=11).pack(side="right")

        hint = self.ui_label(view, "普通 AMS 机型映射 1–4 槽；P3C / H3C 等多头机型按喷头槽位映射，切片上报后按颜色自动预填。",
                             10, "normal", COLOR_TEXT_MUTED)
        hint.grid(row=1, column=0, sticky="w", pady=(0, 14))

        self.scroll_printers = self.ui_scroll(view, fg_color="transparent")
        self.scroll_printers.grid(row=2, column=0, sticky="nsew")
        self.scroll_printers.grid_columnconfigure(0, weight=1)

        self.views["printers"] = view

    def refresh_printers_view(self):
        if not hasattr(self, "scroll_printers"):
            return
        for w in self.scroll_printers.winfo_children():
            w.destroy()

        base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
        printers = api_request(f"{base_url}/api/ingest/script-printers", self.cfg["api_key"], method="GET") or []
        filaments = api_request(self.cfg["filaments_url"], self.cfg["api_key"], method="GET") or []
        f_dict = {f["id"]: f for f in filaments}
        try:
            self.printer_count_label.configure(text=f"{len(printers)} 台")
        except Exception:
            pass

        if not printers:
            empty = ctk.CTkFrame(self.scroll_printers, fg_color="transparent")
            empty.pack(fill="both", expand=True, pady=50)
            self.ui_label(empty, "还没有打印机", 15, "bold").pack(anchor="w")
            self.ui_label(empty, "先添加机位，再为它映射 AMS 槽位。", 11, "normal", COLOR_TEXT_MUTED).pack(anchor="w", pady=(4, 12))
            self.ui_button(empty, "添加打印机", self.open_add_printer_modal, kind="primary",
                           height=36, icon_name="plus", font_size=11).pack(anchor="w")
            return

        for p in printers:
            card = self.ui_card(self.scroll_printers, corner_radius=18)
            card.pack(fill="x", pady=6)
            card.grid_columnconfigure(1, weight=1)

            ams_slots = p.get("ams_slots") or {}
            slot_count = printer_slot_count(p.get("model"))
            slot_kind = printer_slot_kind(p.get("model"))
            heads = printer_head_count(p.get("model"))
            max_heads = printer_max_head_count(p.get("model"))
            model_l = str(p.get("model") or "").lower()
            mounted = sum(1 for k, v in ams_slots.items() if v and str(k).isdigit() and int(k) <= slot_count)
            icon_box = ctk.CTkLabel(card, text="", image=ui_icon("printer", 24), width=46, height=46,
                                    fg_color=COLOR_BLUE_SOFT, corner_radius=14)
            icon_box.grid(row=0, column=0, padx=(18, 14), pady=(16, 6))

            head = ctk.CTkFrame(card, fg_color="transparent")
            head.grid(row=0, column=1, sticky="ew", pady=(14, 4))
            title_row = ctk.CTkFrame(head, fg_color="transparent")
            title_row.pack(anchor="w")
            self.ui_label(title_row, p["name"], 15, "bold").pack(side="left")
            self.ui_pill(title_row, p.get("model", "Bambu"), COLOR_BLUE_SOFT, COLOR_BLUE).pack(side="left", padx=(8, 0))
            if p.get("ip_address"):
                self.ui_pill(title_row, p["ip_address"], COLOR_SURFACE_2, COLOR_TEXT_MUTED).pack(side="left", padx=(6, 0))
            if "p3c" in model_l:
                spec_text = f"{heads} 标配 / 最多 {max_heads} 头 · 2 个扩展槽"
            elif "h3c" in model_l:
                spec_text = f"{max_heads} 喷头 · 8×1.75 + 1×2.85"
            elif max_heads > 4:
                spec_text = f"{max_heads} 喷头"
            else:
                spec_text = ""
            if slot_kind == "喷头":
                sub_text = f"{spec_text} · 已挂载 {mounted}/{slot_count} 槽位 · 设备 #{p.get('id')}"
            else:
                sub_text = f"已挂载 {mounted}/{slot_count} 个 AMS 槽位 · 设备 #{p.get('id')}"
            self.ui_label(head, sub_text, 10, "normal", COLOR_TEXT_MUTED).pack(anchor="w", pady=(3, 0))

            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.grid(row=0, column=2, padx=(8, 18), pady=(14, 4))
            self.ui_button(actions, "复制", lambda pr=p: self.copy_printer(pr),
                           kind="ghost", height=30, font_size=10, icon_name="copy").pack(side="left", padx=(0, 6))
            self.ui_button(actions, "映射槽位", lambda pr=p, fl=filaments: self.open_ams_mount_modal(pr, fl),
                           kind="soft", height=30, font_size=10, icon_name="sliders").pack(side="left", padx=(0, 6))
            self.ui_button(actions, "删除", lambda pid=p['id']: self.delete_printer(pid),
                           kind="danger", height=30, font_size=10, icon_name="trash").pack(side="left")

            slots_box = ctk.CTkFrame(card, fg_color="transparent")
            slots_box.grid(row=1, column=0, columnspan=3, sticky="ew", padx=18, pady=(2, 16))
            slot_cols = 4 if slot_count <= 4 else 3
            slot_rows = (slot_count + slot_cols - 1) // slot_cols
            for c in range(slot_cols):
                slots_box.grid_columnconfigure(c, weight=1, uniform="ams")
            for r in range(slot_rows):
                slots_box.grid_rowconfigure(r, weight=1, uniform="amsrow")
            for slot_i in range(1, slot_count + 1):
                fid = ams_slots.get(str(slot_i))
                f_obj = f_dict.get(int(fid)) if fid else None
                slot = ctk.CTkFrame(slots_box, fg_color=COLOR_SURFACE_2, corner_radius=12,
                                    border_width=1, border_color=COLOR_DIVIDER)
                slot.grid(row=(slot_i - 1) // slot_cols, column=(slot_i - 1) % slot_cols,
                          sticky="nsew", padx=5, pady=2)
                top = ctk.CTkFrame(slot, fg_color="transparent")
                top.pack(anchor="w", padx=12, pady=(10, 0))
                if f_obj:
                    color = f_obj.get("color_hex") or "#6B7280"
                    try:
                        dot = ctk.CTkFrame(top, width=16, height=16, corner_radius=8, fg_color=color,
                                           border_width=1, border_color=COLOR_CARD_BORDER)
                        dot.pack(side="left", padx=(0, 7))
                    except Exception:
                        pass
                self.ui_label(top, printer_slot_label(p.get("model"), slot_i), 9, "bold",
                              COLOR_BAMBU_GREEN if f_obj else COLOR_TEXT_MUTED).pack(side="left")
                if f_obj:
                    self.ui_label(slot, f"{f_obj.get('material', '')} · {f_obj.get('color_name', '')}",
                                  11, "bold").pack(anchor="w", padx=12, pady=(6, 0))
                    init_w = f_obj.get("initial_weight_g", 1000) or 1000
                    curr_w = f_obj.get("current_weight_g", 0) or 0
                    ratio = max(0.0, min(1.0, curr_w / init_w))
                    bar = ctk.CTkProgressBar(slot, height=5, corner_radius=3, fg_color=COLOR_TRACK,
                                             progress_color=COLOR_BAMBU_GREEN if ratio > 0.5 else
                                             (COLOR_AMBER if ratio > 0.2 else COLOR_BADGE_RED))
                    bar.pack(fill="x", padx=12, pady=(8, 4))
                    bar.set(ratio)
                    self.ui_label(slot, f"剩 {curr_w} g", 9, "normal", COLOR_TEXT_MUTED).pack(anchor="w", padx=12, pady=(0, 10))
                else:
                    self.ui_label(slot, "未挂载", 11, "normal", COLOR_TEXT_MUTED).pack(anchor="w", padx=12, pady=(6, 0))
                    self.ui_label(slot, "点击「映射槽位」", 9, "normal", COLOR_TEXT_MUTED).pack(anchor="w", padx=12, pady=(2, 12))

    def open_add_printer_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("添加 3D 打印机")
        modal.geometry("780x720")
        modal.minsize(720, 640)
        self._prepare_modal(modal)
        modal.configure(fg_color=COLOR_BG_MAIN)

        container = ctk.CTkFrame(modal, corner_radius=20, fg_color=COLOR_CARD_BG,
                                 border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        head = ctk.CTkFrame(container, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(16, 2))
        self.ui_label(head, "选择打印机机型", 16, "bold").pack(anchor="w")
        self.ui_label(container, "按系列筛选，点击卡片选中；机型信息更新至 2026 年 11 月（含 H3C / P3C / X2D / A2L）。",
                      10, "normal", COLOR_TEXT_MUTED).pack(anchor="w", padx=20, pady=(2, 10))

        chips = ctk.CTkFrame(container, fg_color="transparent")
        chips.pack(fill="x", padx=20)

        models_box = ctk.CTkFrame(container, fg_color=COLOR_SURFACE_2, corner_radius=14)
        models_box.pack(fill="both", expand=True, padx=20, pady=(10, 6))
        models_scroll = self.ui_scroll(models_box, fg_color="transparent")
        models_scroll.pack(fill="both", expand=True, padx=8, pady=8)
        models_scroll.grid_columnconfigure((0, 1), weight=1, uniform="models")

        state = {"model": None, "cards": {}, "series": "全部"}

        def style_selected():
            for name, card in state["cards"].items():
                selected = name == state["model"]
                try:
                    card.configure(border_color=COLOR_BAMBU_GREEN if selected else COLOR_CARD_BORDER,
                                   border_width=2 if selected else 1,
                                   fg_color=COLOR_ACCENT_SOFT if selected else COLOR_CARD_BG)
                except Exception:
                    pass

        def pick(name):
            state["model"] = name
            style_selected()
            model_lbl.configure(text=f"已选机型：{name}" if name != "其他 / 自定义" else "已选机型：自定义")
            if name != "其他 / 自定义" and not entry_name.get().strip():
                entry_name.insert(0, name.replace("Bambu ", ""))

        def render(series="全部"):
            state["series"] = series
            for w in models_scroll.winfo_children():
                w.destroy()
            state["cards"] = {}
            items = [m for m in PRINTER_MODELS if series == "全部" or m["series"] == series]
            items.append({"series": "其他", "name": "其他 / 自定义", "tag": "自定义",
                          "spec": "手动填写机型名称，适合旧机型或第三方设备"})
            for idx, m in enumerate(items):
                card = ctk.CTkFrame(models_scroll, corner_radius=14, fg_color=COLOR_CARD_BG,
                                    border_width=1, border_color=COLOR_CARD_BORDER)
                card.grid(row=idx // 2, column=idx % 2, sticky="ew", padx=8, pady=6)
                inner = ctk.CTkFrame(card, fg_color="transparent")
                inner.pack(fill="x", padx=14, pady=12)
                top = ctk.CTkFrame(inner, fg_color="transparent")
                top.pack(fill="x")
                self.ui_label(top, m["name"], 12, "bold").pack(side="left")
                tag_color = COLOR_ACCENT_SOFT if m["tag"] in ("第三代", "新一代") else COLOR_BLUE_SOFT
                text_color = COLOR_BAMBU_GREEN if m["tag"] in ("第三代", "新一代") else COLOR_BLUE
                tag = ctk.CTkLabel(top, text=m["tag"], font=self.get_font(9, "bold"), text_color=text_color,
                                   fg_color=tag_color, corner_radius=20, padx=8, pady=2)
                tag.pack(side="right")
                spec = self.ui_label(inner, m["spec"], 9, "normal", COLOR_TEXT_MUTED, wraplength=300, justify="left")
                spec.pack(anchor="w", pady=(6, 0))
                for w in (card, inner, top, tag, spec):
                    w.bind("<Button-1>", lambda _e, n=m["name"]: pick(n))
                state["cards"][m["name"]] = card
            style_selected()

        def build_chips():
            for w in chips.winfo_children():
                w.destroy()
            for label, series in (("全部", "全部"), ("A 系列", "A"), ("P 系列", "P"),
                                   ("X 系列", "X"), ("H 系列", "H"), ("其他", "其他")):
                active = state["series"] == series
                btn = ctk.CTkButton(
                    chips, text=label, height=30, corner_radius=15, width=64,
                    font=self.get_font(10, "bold"),
                    fg_color=COLOR_BAMBU_GREEN if active else COLOR_SURFACE_2,
                    hover_color=("#0B8A5F", "#4ADE80") if active else COLOR_HOVER,
                    text_color=COLOR_ON_ACCENT if active else COLOR_TEXT_PRIMARY,
                    border_width=0 if active else 1, border_color=COLOR_CARD_BORDER,
                    command=lambda s=series: (render(s), build_chips()))
                btn.pack(side="left", padx=(0, 8))

        build_chips()
        render("全部")

        footer = ctk.CTkFrame(container, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(8, 16))
        model_lbl = self.ui_label(footer, "已选机型：未选择", 10, "normal", COLOR_TEXT_MUTED)
        model_lbl.pack(anchor="w", pady=(0, 6))

        row = ctk.CTkFrame(footer, fg_color="transparent")
        row.pack(fill="x")
        entry_name = ctk.CTkEntry(row, height=38, corner_radius=10, font=self.get_font(12),
                                  placeholder_text="设备名称，例如 1号机-X2D")
        entry_name.pack(side="left", fill="x", expand=True, padx=(0, 8))
        entry_custom = ctk.CTkEntry(row, height=38, corner_radius=10, font=self.get_font(12), width=170,
                                    placeholder_text="自定义机型（选其他时填）")
        entry_custom.pack(side="left", padx=(0, 8))

        def submit():
            name = entry_name.get().strip()
            model = state["model"]
            if not name:
                return messagebox.showwarning("提示", "请输入设备名称！", parent=modal)
            if not model:
                return messagebox.showwarning("提示", "请先选择一个机型卡片。", parent=modal)
            if model == "其他 / 自定义":
                model = entry_custom.get().strip() or "其他"
            base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
            res = api_request(f"{base_url}/api/ingest/script-printers", self.cfg["api_key"],
                              method="POST", data={"name": name, "model": model})
            if res:
                messagebox.showinfo("成功", "打印机添加成功！", parent=modal)
                modal.destroy()
                self.refresh_printers_view()

        ctk.CTkButton(row, text="添加设备", height=38, corner_radius=10, width=110,
                      fg_color=COLOR_BAMBU_GREEN, hover_color=("#0B8A5F", "#4ADE80"),
                      text_color=COLOR_ON_ACCENT, font=self.get_font(12, "bold"),
                      command=submit).pack(side="right")

    def open_ams_mount_modal(self, printer, filaments):
        model = printer.get("model")
        slot_count = printer_slot_count(model)
        slot_kind = printer_slot_kind(model)
        max_heads = printer_max_head_count(model)
        cols = 2 if slot_count <= 4 else 3
        if slot_count <= 4:
            win_w, win_h = 620, 480
        elif slot_count <= 6:
            win_w, win_h = 790, 580
        else:
            win_w, win_h = 820, 730
        modal = ctk.CTkToplevel(self)
        modal.title(f"映射{slot_kind}槽位 - {printer['name']}")
        modal.geometry(f"{win_w}x{win_h}")
        modal.minsize(560, 440)
        self._prepare_modal(modal)
        modal.configure(fg_color=COLOR_BG_MAIN)

        container = ctk.CTkFrame(modal, corner_radius=20, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        head = ctk.CTkFrame(container, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(16, 2))
        self.ui_label(head, printer.get("name", "打印机"), 16, "bold").pack(side="left")
        self.ui_pill(head, printer.get("model", "Bambu"), COLOR_BLUE_SOFT, COLOR_BLUE).pack(side="left", padx=(8, 0))
        model_l = str(model or "").lower()
        if "p3c" in model_l:
            hint_text = f"P3C 按 {max_heads} 个槽位显示：前 5 个是 1.75 mm 标配头，6/7 是扩展槽；扩展槽可装 1.75 标准头、2.85 TPU 专用头或 CraftTool。"
        elif "h3c" in model_l:
            hint_text = "H3C 共 9 个头位：1–7 号为 1.75 mm 标准头，8 号位为 2.85 mm TPU 专用头，只能映射 2.85 mm 耗材。"
        elif max_heads > 4:
            hint_text = f"为 {slot_count} 个{slot_kind}槽位选择耗材；切片任务里的颜色槽位会自动预填对应耗材。"
        else:
            hint_text = "为 4 个 AMS 槽位选择耗材；卡片左上角圆点会实时显示所选颜色。"
        self.ui_label(container, hint_text, 10, "normal", COLOR_TEXT_MUTED, wraplength=740,
                      justify="left").pack(anchor="w", padx=20, pady=(2, 10))

        filament_by_id = {int(f['id']): f for f in filaments}
        opt_to_id = {"未挂载 (空)": None}
        id_to_opt = {None: "未挂载 (空)"}
        label_color = {"未挂载 (空)": None}

        def filament_label(f):
            d = filament_diameter_mm(f)
            return f"#{f['id']} {f['material']} · {f['color_name']} · {d:g}mm · {f.get('current_weight_g')}g"

        for f in filaments:
            label = filament_label(f)
            opt_to_id[label] = f['id']
            id_to_opt[f['id']] = label
            label_color[label] = f.get("color_hex") or "#6B7280"

        combos = {}
        dots = {}
        status_labels = {}
        ams_slots = printer.get("ams_slots") or {}

        grid_box = ctk.CTkFrame(container, fg_color="transparent")
        grid_box.pack(fill="both", expand=True, padx=14, pady=4)
        for c in range(cols):
            grid_box.grid_columnconfigure(c, weight=1, uniform="ams")
        slot_rows = (slot_count + cols - 1) // cols
        for r in range(slot_rows):
            grid_box.grid_rowconfigure(r, weight=1, uniform="amsrow")

        for slot_i in range(1, slot_count + 1):
            slot_card = ctk.CTkFrame(grid_box, fg_color=COLOR_SURFACE_2, corner_radius=14,
                                     border_width=1, border_color=COLOR_DIVIDER)
            slot_card.grid(row=(slot_i - 1) // cols, column=(slot_i - 1) % cols, sticky="nsew", padx=6, pady=6)
            top = ctk.CTkFrame(slot_card, fg_color="transparent")
            top.pack(fill="x", padx=14, pady=(12, 0))
            dot = ctk.CTkLabel(top, text="", width=16, height=16, corner_radius=8,
                               fg_color=COLOR_TRACK, border_width=1, border_color=COLOR_CARD_BORDER)
            dot.pack(side="left", padx=(0, 8))
            self.ui_label(top, printer_slot_label(model, slot_i), 10, "bold").pack(side="left")
            status = self.ui_label(top, "空", 9, "normal", COLOR_TEXT_MUTED)
            status.pack(side="right")
            self.ui_label(slot_card, printer_slot_note(model, slot_i), 8, "normal", COLOR_TEXT_MUTED,
                          wraplength=210, justify="left").pack(anchor="w", padx=14, pady=(4, 0))
            allowed = printer_slot_allowed_diameters(model, slot_i)
            slot_options = ["未挂载 (空)"] + [
                filament_label(f) for f in filaments if filament_diameter_mm(f) in allowed
            ]
            cur_fid = int(ams_slots.get(str(slot_i))) if ams_slots.get(str(slot_i)) else None
            cur_label = id_to_opt.get(cur_fid, "未挂载 (空)")
            if cur_fid and cur_label not in slot_options:
                cur_f = filament_by_id.get(cur_fid)
                if cur_f:
                    cur_label = filament_label(cur_f) + " · 不兼容"
                    slot_options.append(cur_label)
                    opt_to_id[cur_label] = cur_fid
                    label_color[cur_label] = cur_f.get("color_hex") or "#6B7280"
                    id_to_opt[cur_fid] = cur_label
            cb = ctk.CTkComboBox(slot_card, values=slot_options, height=34, font=self.get_font(10),
                                 fg_color=COLOR_CARD_BG, border_color=COLOR_CARD_BORDER,
                                 button_color=COLOR_SURFACE_2, button_hover_color=COLOR_HOVER,
                                 text_color=COLOR_TEXT_PRIMARY, dropdown_fg_color=COLOR_CARD_BG,
                                 dropdown_text_color=COLOR_TEXT_PRIMARY, dropdown_hover_color=COLOR_HOVER)
            cb.pack(fill="x", padx=14, pady=(4, 4))
            cb.set(cur_label)

            def refresh_dot(value=None, _cb=cb, _dot=dot, _status=status):
                label = _cb.get()
                color = label_color.get(label)
                fid = opt_to_id.get(label)
                try:
                    _dot.configure(fg_color=color or COLOR_TRACK)
                    if fid:
                        d = filament_diameter_mm(filament_by_id.get(fid))
                        _status.configure(text=f"已挂载 {d:g}mm", text_color=COLOR_BAMBU_GREEN)
                    else:
                        _status.configure(text="空", text_color=COLOR_TEXT_MUTED)
                except Exception:
                    pass

            try:
                cb.configure(command=lambda v, fn=refresh_dot: fn(v))
            except Exception:
                pass
            refresh_dot()
            combos[str(slot_i)] = cb
            dots[str(slot_i)] = dot
            status_labels[str(slot_i)] = status

        def clear_all():
            for s_key, cb in combos.items():
                cb.set("未挂载 (空)")
                color = label_color.get(cb.get())
                dots[s_key].configure(fg_color=color or COLOR_TRACK)
                status_labels[s_key].configure(text="空", text_color=COLOR_TEXT_MUTED)

        def submit():
            new_mapping = {}
            errors = []
            for s_str, cb in combos.items():
                fid = opt_to_id.get(cb.get())
                new_mapping[s_str] = fid
                if fid:
                    d = filament_diameter_mm(filament_by_id.get(fid))
                    allowed = printer_slot_allowed_diameters(model, int(s_str))
                    if d not in allowed:
                        errors.append(f"{printer_slot_label(model, int(s_str))} 不支持 {d:g} mm 耗材")
            if errors:
                messagebox.showwarning("槽位不兼容", "请先处理以下槽位：\n" + "\n".join(errors), parent=modal)
                return

            base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
            res = api_request(f"{base_url}/api/ingest/script-printers/{printer['id']}/ams", self.cfg["api_key"], method="POST", data={"ams_slots": new_mapping})
            if res:
                messagebox.showinfo("成功", f"{slot_kind}槽位映射已保存！", parent=modal)
                modal.destroy()
                self.refresh_printers_view()

        btns = ctk.CTkFrame(container, fg_color="transparent")
        btns.pack(fill="x", padx=20, pady=(10, 16))
        self.ui_button(btns, "全部清空", clear_all, kind="ghost", height=40, font_size=11, icon_name="close").pack(side="left")
        ctk.CTkButton(btns, text=f"保存{slot_kind}配置", height=40, corner_radius=12, fg_color=COLOR_BAMBU_GREEN,
                      hover_color=("#0B8A5F", "#4ADE80"), text_color=COLOR_ON_ACCENT,
                      font=self.get_font(12, "bold"), command=submit).pack(side="right", fill="x", expand=True, padx=(12, 0))

    def copy_printer(self, printer):
        count = self.ask_copy_count(
            "复制设备",
            printer.get("name", "打印机"),
            f"将批量创建设备副本（{printer.get('model', '未知机型')}）；"
            "槽位映射不随复制，创建后需分别映射耗材。",
            unit="台",
            accent=COLOR_BLUE,
        )
        if not count:
            return
        base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
        ok = 0
        for i in range(count):
            suffix = f" 副本{i + 1}" if count > 1 else " 副本"
            payload = {
                "name": f"{printer.get('name', '打印机')}{suffix}",
                "model": printer.get("model") or "Bambu P1S",
                "ip_address": printer.get("ip_address") or "",
            }
            res = api_request(f"{base_url}/api/ingest/script-printers", self.cfg["api_key"],
                              method="POST", data=payload)
            if res:
                ok += 1
        if ok:
            messagebox.showinfo("复制成功", f"已创建设备 {ok} 台。")
            self.refresh_printers_view()
        else:
            messagebox.showerror("复制失败", "请检查服务连接或服务端打印机接口。")

    def delete_printer(self, pid):
        if messagebox.askyesno("确认", "确定删除该打印机设备吗？历史打印记录仍将保留。"):
            base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
            api_request(f"{base_url}/api/ingest/script-printers/{pid}", self.cfg["api_key"], method="DELETE")
            self.refresh_printers_view()
    # --------------------------------------------------------------------------
    # 子功能: 2. 设备管理视图 (Printers & 虚拟 AMS) [END]
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # 子功能: 3. 数据洞察大屏 (Analytics) [START]
    # --------------------------------------------------------------------------
    def init_analytics_view(self):
        view = ctk.CTkFrame(self.content_area, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(view, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.ui_label(toolbar, "消耗与成本", 14, "bold").pack(side="left")
        self.ui_label(toolbar, "基于全部上报记录累计统计", 10, "normal", COLOR_TEXT_MUTED).pack(side="left", padx=(10, 0))
        self.ui_button(toolbar, "刷新", self.refresh_current_tab, kind="ghost",
                       height=36, icon_name="refresh", font_size=11).pack(side="right")

        self.scroll_analytics = self.ui_scroll(view, fg_color="transparent")
        self.scroll_analytics.grid(row=1, column=0, sticky="nsew")
        self.scroll_analytics.grid_columnconfigure((0, 1), weight=1, uniform="analytics")

        self.views["analytics"] = view

    def _analytics_stat(self, parent, column, title, value, caption, accent):
        card = self.ui_card(parent, corner_radius=16)
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 5, 0 if column == 2 else 5))
        bar = ctk.CTkFrame(card, height=3, corner_radius=2, fg_color=accent)
        bar.pack(fill="x")
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(10, 12))
        self.ui_label(body, title, 10, "bold", COLOR_TEXT_MUTED).pack(anchor="w")
        self.ui_label(body, value, 22, "bold").pack(anchor="w", pady=(2, 0))
        self.ui_label(body, caption, 9, "normal", COLOR_TEXT_MUTED).pack(anchor="w")

    def refresh_analytics_view(self):
        if not hasattr(self, "scroll_analytics"):
            return
        for w in self.scroll_analytics.winfo_children():
            w.destroy()

        base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
        data = api_request(f"{base_url}/api/ingest/script-analytics", self.cfg["api_key"], method="GET") or {}
        total_g = data.get("total_consumed_g", 0) or 0
        total_cost = data.get("total_consumed_cost", 0) or 0
        task_count = data.get("task_count", 0) or 0

        stats = ctk.CTkFrame(self.scroll_analytics, fg_color="transparent")
        stats.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        for c in range(3):
            stats.grid_columnconfigure(c, weight=1, uniform="astat")
        self._analytics_stat(stats, 0, "累计消耗", f"{total_g:,.1f} g", "切片扣减 + 手动调整", COLOR_BAMBU_GREEN)
        self._analytics_stat(stats, 1, "折算金额", f"¥ {total_cost:,.2f}", "按入库单价 / 初始克重", COLOR_VIOLET)
        self._analytics_stat(stats, 2, "任务次数", f"{task_count} 次", "上报记录数量", COLOR_BLUE)

        def make_list_card(parent, column, title, subtitle):
            card = self.ui_card(parent, corner_radius=16)
            card.grid(row=1, column=column, sticky="new", padx=(0 if column == 0 else 6, 0 if column == 1 else 6))
            head = ctk.CTkFrame(card, fg_color="transparent")
            head.pack(fill="x", padx=16, pady=(14, 4))
            self.ui_label(head, title, 13, "bold").pack(side="left")
            self.ui_label(head, subtitle, 9, "normal", COLOR_TEXT_MUTED).pack(side="right")
            body = ctk.CTkFrame(card, fg_color="transparent")
            body.pack(fill="both", expand=True, padx=16, pady=(4, 14))
            return body

        printer_body = make_list_card(self.scroll_analytics, 0, "机位消耗", "克重 / 成本")
        printers_stat = data.get("printers_stat", []) or []
        if not printers_stat:
            self.ui_label(printer_body, "暂无各机位任务记录", 11, "normal", COLOR_TEXT_MUTED).pack(anchor="w", pady=20)
        else:
            max_p = max([p.get("consumed_g", 0) for p in printers_stat] + [1])
            for p in printers_stat:
                row = ctk.CTkFrame(printer_body, fg_color="transparent")
                row.pack(fill="x", pady=6)
                top = ctk.CTkFrame(row, fg_color="transparent")
                top.pack(fill="x")
                self.ui_label(top, p.get("name", "未指定机位"), 11, "bold").pack(side="left")
                self.ui_label(top, f"{p.get('consumed_g', 0):,.1f} g · ¥{p.get('cost', 0):,.2f}",
                              9, "normal", COLOR_TEXT_MUTED).pack(side="right")
                bar = ctk.CTkProgressBar(row, height=6, corner_radius=3, width=300,
                                         fg_color=COLOR_TRACK, progress_color=COLOR_BLUE)
                bar.pack(fill="x", pady=(3, 0))
                bar.set(max(0.0, min(1.0, (p.get("consumed_g", 0) or 0) / max_p)))

        material_body = make_list_card(self.scroll_analytics, 1, "材质排行", "累计克重")
        materials_stat = data.get("materials_stat", []) or []
        if not materials_stat:
            self.ui_label(material_body, "暂无材质消耗记录", 11, "normal", COLOR_TEXT_MUTED).pack(anchor="w", pady=20)
        else:
            max_m = max([m.get("consumed_g", 0) for m in materials_stat] + [1])
            for m in materials_stat:
                row = ctk.CTkFrame(material_body, fg_color="transparent")
                row.pack(fill="x", pady=6)
                top = ctk.CTkFrame(row, fg_color="transparent")
                top.pack(fill="x")
                self.ui_label(top, m.get("material", "-"), 11, "bold").pack(side="left")
                self.ui_label(top, f"{m.get('consumed_g', 0):,.1f} g", 9, "normal", COLOR_TEXT_MUTED).pack(side="right")
                bar = ctk.CTkProgressBar(row, height=6, corner_radius=3, width=300,
                                         fg_color=COLOR_TRACK, progress_color=COLOR_BAMBU_GREEN)
                bar.pack(fill="x", pady=(3, 0))
                bar.set(max(0.0, min(1.0, (m.get("consumed_g", 0) or 0) / max_m)))

        note = self.ui_label(self.scroll_analytics, "提示：统计为全量累计，不按时间过滤；成本按当前入库单价折算。",
                             9, "normal", COLOR_TEXT_MUTED)
        note.grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))

    def init_shopping_view(self):
        view = ctk.CTkFrame(self.content_area, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(2, weight=1)

        toolbar = ctk.CTkFrame(view, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.ui_label(toolbar, "待补货耗材", 14, "bold").pack(side="left")
        self.shop_count_label = self.ui_label(toolbar, "0 卷", 10, "bold", COLOR_AMBER,
                                              fg_color=COLOR_AMBER_SOFT, corner_radius=20, padx=9, pady=3)
        self.shop_count_label.pack(side="left", padx=(8, 0))
        self.ui_button(toolbar, "复制采购单", self.copy_shopping_list_clipboard, kind="ghost",
                       height=34, icon_name="copy", font_size=10).pack(side="right", padx=(6, 0))
        self.ui_button(toolbar, "导出", self.export_shopping_json, kind="ghost",
                       height=34, icon_name="download", font_size=10).pack(side="right", padx=(6, 0))
        self.ui_button(toolbar, "导入链接", self.import_shopping_json, kind="ghost",
                       height=34, icon_name="upload", font_size=10).pack(side="right")

        self.shop_sub_label = self.ui_label(view, "低于 200 g 的耗材会自动进入清单。", 10, "normal", COLOR_TEXT_MUTED)
        self.shop_sub_label.grid(row=1, column=0, sticky="w", pady=(0, 12))

        self.scroll_shopping = self.ui_scroll(view, fg_color="transparent")
        self.scroll_shopping.grid(row=2, column=0, sticky="nsew")
        self.scroll_shopping.grid_columnconfigure(0, weight=1)

        self.views["shopping"] = view

    def refresh_shopping_view(self):
        if not hasattr(self, "scroll_shopping"):
            return
        for w in self.scroll_shopping.winfo_children():
            w.destroy()

        filaments = api_request(self.cfg["filaments_url"], self.cfg["api_key"], method="GET") or []
        low_filaments = [f for f in filaments if (f.get("current_weight_g") or 0) < 200]
        estimate = sum([(f.get("price") or 0) for f in low_filaments])
        try:
            self.shop_count_label.configure(text=f"{len(low_filaments)} 卷")
            self.shop_sub_label.configure(text=f"低于 200 g 的耗材会自动进入清单 · 按单价预估补货成本 ¥{estimate:,.2f}")
        except Exception:
            pass

        if not low_filaments:
            empty = ctk.CTkFrame(self.scroll_shopping, fg_color="transparent")
            empty.pack(fill="both", expand=True, pady=55)
            self.ui_label(empty, "库存充足", 15, "bold", COLOR_BAMBU_GREEN).pack(anchor="w")
            self.ui_label(empty, "当前没有低于 200 g 的耗材。", 11, "normal", COLOR_TEXT_MUTED).pack(anchor="w", pady=(4, 0))
            return

        for item in low_filaments:
            card = self.ui_card(self.scroll_shopping, corner_radius=16)
            card.pack(fill="x", pady=5)
            card.grid_columnconfigure(1, weight=1)

            try:
                dot = ctk.CTkFrame(card, width=40, height=40, corner_radius=12,
                                   fg_color=item.get("color_hex") or "#6B7280",
                                   border_width=1, border_color=COLOR_CARD_BORDER)
                dot.grid(row=0, column=0, padx=(16, 12), pady=14)
                dot.grid_propagate(False)
            except Exception:
                pass

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.grid(row=0, column=1, sticky="w", pady=14)
            self.ui_label(info, f"{item.get('brand', '')} {item.get('material', '')} · {item.get('color_name', '')}",
                          13, "bold").pack(anchor="w")
            self.ui_label(info, f"#{item.get('id')} · 剩余 {item.get('current_weight_g', 0)} g · 单价 ¥{item.get('price', 0)}",
                          9, "normal", COLOR_TEXT_MUTED).pack(anchor="w", pady=(2, 0))

            weight_box = ctk.CTkFrame(card, fg_color="transparent")
            weight_box.grid(row=0, column=2, sticky="e", padx=(10, 18), pady=14)
            self.ui_label(weight_box, f"{item.get('current_weight_g', 0)} g", 16, "bold", COLOR_BADGE_RED).pack(anchor="e")
            self.ui_label(weight_box, "仅剩", 9, "normal", COLOR_TEXT_MUTED).pack(anchor="e")

            link_box = ctk.CTkFrame(card, fg_color="transparent")
            link_box.grid(row=1, column=0, columnspan=4, sticky="ew", padx=16, pady=(0, 14))
            link_box.grid_columnconfigure(0, weight=1)
            entry_url = ctk.CTkEntry(link_box, height=34, corner_radius=9,
                                     placeholder_text="粘贴购买链接（淘宝 / 拼多多 / 官方店）",
                                     fg_color=COLOR_INPUT_BG, border_color=COLOR_CARD_BORDER,
                                     text_color=COLOR_TEXT_PRIMARY, placeholder_text_color=COLOR_TEXT_MUTED,
                                     font=self.get_font(10))
            entry_url.grid(row=0, column=0, sticky="ew", padx=(0, 6))
            entry_url.insert(0, item.get("purchase_url") or "")
            self.ui_button(link_box, "保存", lambda fid=item['id'], ent=entry_url: self.save_filament_url(fid, ent.get().strip()),
                           kind="primary", height=34, font_size=10, icon_name="check").grid(row=0, column=1, padx=(0, 5))
            self.ui_button(link_box, "应用到同款",
                           lambda brand=item['brand'], mat=item['material'], ent=entry_url: self.apply_url_to_same(brand, mat, ent.get().strip()),
                           kind="ghost", height=34, font_size=10, icon_name="copy").grid(row=0, column=2, padx=(0, 5))
            if item.get("purchase_url"):
                self.ui_button(link_box, "去购买", lambda u=item["purchase_url"]: webbrowser.open(u),
                               kind="ghost", height=34, font_size=10, icon_name="link").grid(row=0, column=3, padx=(0, 5))
            self.ui_button(link_box, "调整", lambda f=item: self.open_adjust_modal(f),
                           kind="ghost", height=34, font_size=10, icon_name="sliders").grid(row=0, column=4)

    def save_filament_url(self, fid, url):
        base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
        res = api_request(f"{base_url}/api/ingest/script-filaments/{fid}/url", self.cfg["api_key"], method="POST", data={"purchase_url": url})
        if res:
            messagebox.showinfo("成功", "购买链接已保存！")

    def apply_url_to_same(self, brand, material, url):
        if not url:
            return messagebox.showwarning("提示", "请先填入购买链接！")
        base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
        res = api_request(f"{base_url}/api/ingest/script-filaments/apply-url", self.cfg["api_key"], method="POST", data={"brand": brand, "material": material, "purchase_url": url})
        if res:
            messagebox.showinfo("成功", f"已成功批量应用至所有 {brand} {material} 耗材！")
            self.refresh_shopping_view()

    def copy_shopping_list_clipboard(self):
        filaments = api_request(self.cfg["filaments_url"], self.cfg["api_key"], method="GET") or []
        low_filaments = [f for f in filaments if (f.get("current_weight_g") or 0) < 200]
        if not low_filaments:
            return messagebox.showinfo("提示", "当前没有需要补货的耗材！")

        lines = [f"🛒 【拓竹耗材补货采购单 - {datetime.datetime.now().strftime('%Y-%m-%d')}】"]
        for idx, f in enumerate(low_filaments, 1):
            url_str = f"\n   🔗 购买链接: {f['purchase_url']}" if f.get('purchase_url') else ""
            lines.append(f"{idx}. {f['brand']} {f['material']} [{f['color_name']}] - 余量: {f.get('current_weight_g')}g (建议采购 1 卷){url_str}")

        text = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("已复制", "采购单排版文本已成功复制到剪贴板，可直接粘贴分享！")

    def export_shopping_json(self):
        filaments = api_request(self.cfg["filaments_url"], self.cfg["api_key"], method="GET") or []
        low_filaments = [f for f in filaments if (f.get("current_weight_g") or 0) < 200]
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")], title="导出待补货清单 JSON")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(low_filaments, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("导出成功", f"已导出 {len(low_filaments)} 款待补货耗材！")

    def import_shopping_json(self):
        path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")], title="导入补货链接 JSON")
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
            api_request(f"{base_url}/api/ingest/script-filaments/import-urls", self.cfg["api_key"], method="POST", data=data)
            messagebox.showinfo("导入成功", "已同步并更新补货链接！")
            self.refresh_shopping_view()
    # --------------------------------------------------------------------------
    # 子功能: 4. 补货清单与分享导出 (Shopping List) [END]
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # 子功能: 5. 服务设置视图 [START]
    # --------------------------------------------------------------------------
    def _settings_entry(self, parent, value, show=None, width=360):
        entry = ctk.CTkEntry(
            parent, height=38, corner_radius=9, show=show or "", width=width,
            fg_color=COLOR_INPUT_BG, border_color=COLOR_CARD_BORDER,
            text_color=COLOR_TEXT_PRIMARY, placeholder_text_color=COLOR_TEXT_MUTED,
            font=self.get_font(11))
        entry.insert(0, value or "")
        return entry

    def _settings_row(self, parent, title, subtitle, first=False):
        if not first:
            self.ui_divider(parent)
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=12)
        row.grid_columnconfigure(1, weight=1)
        labels = ctk.CTkFrame(row, fg_color="transparent")
        labels.grid(row=0, column=0, sticky="w")
        self.ui_label(labels, title, 12, "bold").pack(anchor="w")
        if subtitle:
            self.ui_label(labels, subtitle, 9, "normal", COLOR_TEXT_MUTED).pack(anchor="w", pady=(1, 0))
        right = ctk.CTkFrame(row, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e", padx=(18, 0))
        return right

    def init_settings_view(self):
        scroll_view = self.ui_scroll(self.content_area, fg_color="transparent")
        scroll_view.grid_columnconfigure(0, weight=1)

        self.ui_label(scroll_view, "本地数据与外观" if OFFLINE_MODE else "连接与外观", 14, "bold").pack(anchor="w")
        self.ui_label(scroll_view,
                      "离线版数据保存在本机 SQLite，不需要服务端。" if OFFLINE_MODE
                      else "服务地址、API Key、主题与字体都在这里配置。",
                      10, "normal", COLOR_TEXT_MUTED).pack(anchor="w", pady=(1, 14))

        card = self.ui_card(scroll_view, corner_radius=16)
        if not OFFLINE_MODE:
            card.pack(fill="x", pady=(0, 14))
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(14, 2))
        self.ui_label(head, "服务连接", 13, "bold").pack(side="left")
        self.ui_label(head, "Windows 服务端 / Linux 后端", 9, "normal", COLOR_TEXT_MUTED).pack(side="right")

        right = self._settings_row(card, "扣减上报地址", "必须以 /api/ingest/script-report 结尾", first=True)
        self.entry_server_url = self._settings_entry(right, self.cfg.get("server_url", ""))
        self.entry_server_url.pack(fill="x")

        right = self._settings_row(card, "耗材台账地址", "用于拉取库存与筛选列表")
        self.entry_filaments_url = self._settings_entry(right, self.cfg.get("filaments_url", ""))
        self.entry_filaments_url.pack(fill="x")

        right = self._settings_row(card, "API Key", "Windows 凭据管理器加密保存")
        key_box = ctk.CTkFrame(right, fg_color="transparent")
        key_box.pack(fill="x")
        self.entry_api_key = self._settings_entry(key_box, self.cfg.get("api_key", ""), show="*", width=230)
        self.entry_api_key.pack(side="left")
        self.ui_button(key_box, "一键登录", self.open_quick_login_modal, kind="ghost",
                       height=38, font_size=10, icon_name="key").pack(side="left", padx=(8, 0))
        self.lbl_settings_user = self.ui_label(key_box, "校验中…", 9, "normal", COLOR_TEXT_MUTED)
        self.lbl_settings_user.pack(side="left", padx=(10, 0))

        if OFFLINE_MODE:
            local_card = self.ui_card(scroll_view, corner_radius=16)
            local_card.pack(fill="x", pady=(0, 14))
            local_head = ctk.CTkFrame(local_card, fg_color="transparent")
            local_head.pack(fill="x", padx=20, pady=(14, 2))
            self.ui_label(local_head, "离线数据", 13, "bold").pack(side="left")
            self.ui_label(local_head, "SQLite · 无需服务端", 9, "normal", COLOR_TEXT_MUTED).pack(side="right")
            path_box = ctk.CTkFrame(local_card, fg_color="transparent")
            path_box.pack(fill="x", padx=20, pady=12)
            self.ui_label(path_box, "数据文件", 10, "bold", COLOR_TEXT_MUTED).pack(anchor="w")
            self.ui_label(path_box, OFFLINE_DB_FILE, 9, "normal", COLOR_TEXT_MUTED,
                          wraplength=760, justify="left").pack(anchor="w", pady=(2, 10))

            local_actions = ctk.CTkFrame(path_box, fg_color="transparent")
            local_actions.pack(anchor="w")

            def open_data_folder():
                try:
                    os.startfile(BASE_DIR)
                except Exception as e:
                    messagebox.showerror("打开失败", str(e))

            def seed_data():
                if messagebox.askyesno("载入示例数据", "会覆盖当前离线数据，确定继续吗？", parent=self):
                    offline_seed_sample(True)
                    messagebox.showinfo("完成", "示例数据已载入。")
                    clear_api_cache()
                    self.refresh_dashboard()

            def backup_data():
                target = filedialog.asksaveasfilename(
                    title="备份离线数据库", defaultextension=".db",
                    initialfile=f"siguan_offline_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.db",
                    filetypes=[("SQLite 数据库", "*.db"), ("所有文件", "*.*")])
                if target:
                    try:
                        shutil.copy2(OFFLINE_DB_FILE, target)
                        messagebox.showinfo("备份完成", f"已保存到：\n{target}")
                    except Exception as e:
                        messagebox.showerror("备份失败", str(e))

            self.ui_button(local_actions, "打开数据文件夹", open_data_folder, kind="ghost",
                           height=34, font_size=10, icon_name="file").pack(side="left", padx=(0, 6))
            self.ui_button(local_actions, "备份数据库", backup_data, kind="ghost",
                           height=34, font_size=10, icon_name="download").pack(side="left", padx=(0, 6))
            self.ui_button(local_actions, "载入示例数据", seed_data, kind="soft",
                           height=34, font_size=10, icon_name="plus").pack(side="left")

        card2 = self.ui_card(scroll_view, corner_radius=16)
        card2.pack(fill="x", pady=(0, 14))
        head2 = ctk.CTkFrame(card2, fg_color="transparent")
        head2.pack(fill="x", padx=20, pady=(14, 2))
        self.ui_label(head2, "外观", 13, "bold").pack(side="left")
        self.ui_label(head2, "日夜模式即时生效", 9, "normal", COLOR_TEXT_MUTED).pack(side="right")

        right = self._settings_row(card2, "主题", "浅色 / 深色 / 跟随系统，即时生效", first=True)
        self.seg_theme = ctk.CTkSegmentedButton(
            right, values=["浅色", "深色", "跟随系统"], command=self.on_theme_segment,
            height=34, corner_radius=9, font=self.get_font(10, "bold"),
            selected_color=COLOR_BAMBU_GREEN, selected_hover_color=COLOR_BAMBU_GREEN,
            unselected_color=COLOR_SURFACE_2, unselected_hover_color=COLOR_HOVER,
            text_color=COLOR_TEXT_PRIMARY)
        self.seg_theme.set({"light": "浅色", "dark": "深色", "system": "跟随系统"}.get(self.theme_mode, "浅色"))
        self.seg_theme.pack()

        right = self._settings_row(card2, "界面字体", "切换后全界面即时刷新")
        self.combo_font = ctk.CTkComboBox(
            right, values=["MiSans (小米澎湃)", "Microsoft YaHei UI (微软高清)", "Segoe UI Variable (Win11 字体)"],
            height=36, corner_radius=9, width=230, font=self.get_font(11),
            command=self.on_font_change_live,
            fg_color=COLOR_INPUT_BG, border_color=COLOR_CARD_BORDER,
            button_color=COLOR_SURFACE_2, button_hover_color=COLOR_HOVER,
            text_color=COLOR_TEXT_PRIMARY, dropdown_fg_color=COLOR_CARD_BG,
            dropdown_text_color=COLOR_TEXT_PRIMARY, dropdown_hover_color=COLOR_HOVER)
        self.combo_font.set(self.cfg.get("selected_font", "Microsoft YaHei UI (微软高清)"))
        self.combo_font.pack()
        self.font_preview = self.ui_label(right, "丝衡 SiGuan · 耗材管理 0123", 10, "normal", COLOR_TEXT_MUTED)
        self.font_preview.pack(pady=(6, 0))

        card3 = self.ui_card(scroll_view, corner_radius=16)
        card3.pack(fill="x", pady=(0, 14))
        head3 = ctk.CTkFrame(card3, fg_color="transparent")
        head3.pack(fill="x", padx=20, pady=(14, 2))
        self.ui_label(head3, "自动化", 13, "bold").pack(side="left")
        self.ui_label(head3, "切片监听与调试", 9, "normal", COLOR_TEXT_MUTED).pack(side="right")

        right = self._settings_row(card3, "切片打印自动监听", "切片完成后自动唤醒扣减弹窗", first=True)
        self.switch_watcher = ctk.CTkSwitch(
            right, text="实时监听", font=self.get_font(10, "bold"),
            progress_color=COLOR_BAMBU_GREEN, command=self.toggle_watcher)
        if self.cfg.get("auto_watcher_enabled", True):
            self.switch_watcher.select()
        self.switch_watcher.pack()

        right = self._settings_row(card3, "开发者调试", "开启后左侧导航出现「运行日志」")
        self.switch_dev = ctk.CTkSwitch(
            right, text="开发者模式", font=self.get_font(10, "bold"),
            progress_color=COLOR_BAMBU_GREEN, command=self.toggle_developer_mode)
        if self.cfg.get("developer_mode", False):
            self.switch_dev.select()
        self.switch_dev.pack()

        btn_box = ctk.CTkFrame(scroll_view, fg_color="transparent")
        btn_box.pack(fill="x", pady=(4, 16))
        if not OFFLINE_MODE:
            self.ui_button(btn_box, "测试连接", self.test_connection, kind="ghost",
                           height=40, icon_name="wifi", font_size=11).pack(side="left", padx=(0, 8))
        self.ui_button(btn_box, "检查更新", self.manual_check_update, kind="ghost",
                       height=40, icon_name="refresh", font_size=11).pack(side="left", padx=(0, 8))
        self.ui_button(btn_box, "保存设置", self.save_settings, kind="primary",
                       height=40, icon_name="check", font_size=11).pack(side="left")

        about = self.ui_card(scroll_view, corner_radius=16, fg_color=COLOR_SURFACE_2)
        about.pack(fill="x", pady=(0, 32))
        about_inner = ctk.CTkFrame(about, fg_color="transparent")
        about_inner.pack(fill="x", padx=20, pady=16)
        self.ui_label(about_inner, f"丝衡 SiGuan Client {VERSION_TAG}", 14, "bold").pack(anchor="w")
        self.ui_label(about_inner, "拓竹 3D 打印耗材资产与机群成本管理 · 切片自动扣减 / NFC 称重 / AMS 映射",
                      10, "normal", COLOR_TEXT_MUTED).pack(anchor="w", pady=(3, 10))
        tag_row = ctk.CTkFrame(about_inner, fg_color="transparent")
        tag_row.pack(anchor="w")
        self.ui_pill(tag_row, "GPL-3.0", COLOR_SURFACE_2, COLOR_TEXT_MUTED).pack(side="left", padx=(0, 6))
        self.ui_pill(tag_row, "WinVault 加密", COLOR_BLUE_SOFT, COLOR_BLUE).pack(side="left", padx=(0, 6))
        self.ui_pill(tag_row, "本地优先", COLOR_ACCENT_SOFT, COLOR_BAMBU_GREEN).pack(side="left")
        self.ui_button(about_inner, "GitHub 仓库",
                       lambda: webbrowser.open(f"https://github.com/{GITHUB_REPO}"),
                       kind="ghost", height=36, font_size=10, icon_name="link").pack(anchor="e", pady=(10, 0))

        self.views["settings"] = scroll_view

    def toggle_developer_mode(self):
        is_on = bool(self.switch_dev.get())
        if is_on:
            if messagebox.askyesno("开发者模式警告", "⚠️ 警告：开发者模式包含深度调试信息与日志拦截，可能产生详细文件记录。\n\n是否确认开启？"):
                self.cfg["developer_mode"] = True
                self.switch_dev.configure(text="已启用")
            else:
                self.switch_dev.deselect()
                self.cfg["developer_mode"] = False
                self.switch_dev.configure(text="已停用")
                return
        else:
            self.cfg["developer_mode"] = False
            self.switch_dev.configure(text="已停用")

        save_config(self.cfg)
        self.build_navigation()

    def on_font_change_live(self, choice):
        self.font_family = map_font_family(choice)
        self.cfg["selected_font"] = choice
        try:
            if hasattr(self, "combo_font"):
                self.combo_font.set(choice)
        except Exception:
            pass
        save_config(self.cfg)
        write_log(f"🔤 [字体动态切换] 全界面即时切换为: {self.font_family}")
        self._refresh_all_fonts()
        try:
            self.update_idletasks()
        except Exception:
            pass

    def toggle_watcher(self):
        is_on = bool(self.switch_watcher.get())
        self.cfg["auto_watcher_enabled"] = is_on
        save_config(self.cfg)
        status_str = "已开启" if is_on else "已关闭"
        messagebox.showinfo("状态已切换", f"切片打印自动监听功能{status_str}！")

    def save_settings(self, silent=False):
        self.cfg["server_url"] = self.entry_server_url.get().strip()
        self.cfg["filaments_url"] = self.entry_filaments_url.get().strip()
        self.cfg["api_key"] = self.entry_api_key.get().strip()
        self.cfg["selected_font"] = self.combo_font.get()
        save_config(self.cfg)
        self._user_info_checked_at = 0
        self.fetch_user_info_async()
        
        if not silent:
            messagebox.showinfo("成功", "设置与凭据已加密保存并即时生效！")

    def test_connection(self):
        key = self.entry_api_key.get().strip()
        base_url = self.entry_server_url.get().strip().replace('/api/ingest/script-report', '')
        info = api_request(f"{base_url}/api/ingest/script-user-info", key, method="GET") if base_url else None
        if info and info.get("status") == "success":
            self.current_user_name = info.get("username", "已连接用户")
            self._user_info_connected = True
            self._user_info_checked_at = time.time()
            self.update_user_display(self.current_user_name, True)
        res = api_request(self.entry_filaments_url.get().strip(), key, method="GET")
        if res is not None:
            messagebox.showinfo("测试成功", f"🎉 成功连通服务器！\n当前登录用户: {self.current_user_name}\n读取到 {len(res)} 条耗材档案。")
        else:
            messagebox.showerror("连接失败", "无法连接服务器或 API Key 错误！")
    # --------------------------------------------------------------------------
    # 子功能: 5. 服务设置视图 [END]
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # 子功能: 6. 运行日志视图 (开发者模式专属) [START]
    # --------------------------------------------------------------------------
    def init_logs_view(self):
        view = ctk.CTkFrame(self.content_area, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(1, weight=1)

        top_row = ctk.CTkFrame(view, fg_color="transparent")
        top_row.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.ui_label(top_row, "运行日志", 14, "bold").pack(side="left")
        self.ui_label(top_row, "开发者模式 · 本地 log.txt", 9, "normal", COLOR_TEXT_MUTED).pack(side="left", padx=(10, 0))
        self.ui_button(top_row, "清空日志", self.clear_logs, kind="danger",
                       height=32, font_size=10, icon_name="trash").pack(side="right")

        self.txt_log = ctk.CTkTextbox(
            view, corner_radius=14, fg_color=COLOR_SURFACE_2, border_width=1,
            border_color=COLOR_CARD_BORDER, text_color=COLOR_TEXT_PRIMARY,
            font=ctk.CTkFont(family="Cascadia Code", size=11), wrap="word")
        self.txt_log.grid(row=1, column=0, sticky="nsew")

        self.views["logs"] = view

    def clear_logs(self):
        try:
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 日志已清空\n")
            self.load_logs()
        except Exception:
            pass

    def load_logs(self):
        self.txt_log.delete("1.0", tk.END)
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                self.txt_log.insert(tk.END, f.read())
        self.txt_log.see(tk.END)
    # --------------------------------------------------------------------------
    # 子功能: 6. 运行日志视图 (开发者模式专属) [END]
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # 弹窗组件: 耗材管理 (新增批量/调整/历史/撤销/删除) [START]
    # --------------------------------------------------------------------------
    def open_history_modal(self, filament):
        modal = ctk.CTkToplevel(self)
        modal.title(f"消耗与变动历史 - #{filament['id']}")
        modal.geometry("560x520")
        self._prepare_modal(modal)
        modal.configure(fg_color=COLOR_BG_MAIN)

        container = ctk.CTkFrame(modal, corner_radius=20, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        header_box = ctk.CTkFrame(container, fg_color="transparent")
        header_box.pack(fill="x", padx=16, pady=(14, 8))

        ctk.CTkLabel(header_box, text=f"耗材: {filament.get('brand')} {filament.get('material')} [{filament.get('color_name')}]", font=self.get_font(15, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(header_box, text="包含所有切片自动扣减与手动调整记录", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        logs_scroll = self.ui_scroll(container, fg_color="transparent")
        logs_scroll.pack(fill="both", expand=True, padx=12, pady=6)
        logs_scroll.grid_columnconfigure(0, weight=1)

        base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
        logs_url = f"{base_url}/api/ingest/script-filament-logs/{filament['id']}"
        logs = api_request(logs_url, self.cfg['api_key'], method="GET")

        if not logs:
            ctk.CTkLabel(logs_scroll, text="暂无消耗变动记录", text_color=COLOR_TEXT_MUTED, font=self.get_font(13)).pack(pady=40)
        else:
            for log in logs:
                log_card = ctk.CTkFrame(logs_scroll, corner_radius=12, fg_color=COLOR_BG_MAIN, border_width=1, border_color=COLOR_CARD_BORDER)
                log_card.pack(fill="x", pady=4)
                log_card.grid_columnconfigure(0, weight=1)

                task_name = str(log.get('task_name') or '打印任务/变动')
                used_w = log.get('used_weight_g', 0)
                created_at = str(log.get('created_at', ''))

                info_box = ctk.CTkFrame(log_card, fg_color="transparent")
                info_box.grid(row=0, column=0, padx=(12, 4), pady=10, sticky="ew")

                display_task_name = task_name if len(task_name) <= 34 else task_name[:33] + "…"
                ctk.CTkLabel(info_box, text=display_task_name, font=self.get_font(13, "bold"), text_color=COLOR_TEXT_PRIMARY, anchor="w").pack(anchor="w")
                ctk.CTkLabel(info_box, text=created_at, font=self.get_font(10), text_color=COLOR_TEXT_MUTED, anchor="w").pack(anchor="w", pady=(2, 0))

                is_reduce = used_w > 0
                val_str = f"-{used_w:.1f} g" if is_reduce else f"+{abs(used_w):.1f} g"
                val_color = "#EF4444" if is_reduce else COLOR_BAMBU_GREEN

                ctk.CTkLabel(log_card, text=val_str, font=self.get_font(14, "bold"), text_color=val_color).grid(row=0, column=1, padx=12)

                rec_id = log.get('id')
                ctk.CTkButton(
                    log_card, text="撤销", width=50, height=28, corner_radius=6,
                    fg_color="#DC2626", hover_color="#B91C1C", font=self.get_font(11, "bold"),
                    command=lambda rid=rec_id, modal_w=modal: self.undo_usage_record(rid, modal_w)
                ).grid(row=0, column=2, padx=(0, 12))

    def undo_usage_record(self, record_id, modal_window):
        if messagebox.askyesno("确认撤销", "确定要撤销这条记录吗？\n撤销后服务端将基于历史快照精准恢复到变动前的真实余量。"):
            base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
            undo_url = f"{base_url}/api/ingest/script-undo-record/{record_id}"
            res = api_request(undo_url, self.cfg['api_key'], method="DELETE")
            if res:
                messagebox.showinfo("成功", "已成功撤销该记录并恢复库存！")
                modal_window.destroy()
                self.refresh_dashboard()
            else:
                messagebox.showerror("失败", "撤销记录失败，请检查网络或后端配置！")

    def catalog_values(self, category):
        builtin = {"brand": BUILTIN_BRANDS, "material": BUILTIN_MATERIALS,
                   "color": [name for _, name in COLOR_PRESETS]}.get(category, [])
        custom = self.cfg.get(f"custom_{category}s", []) or []
        field = "color_name" if category == "color" else category
        existing = []
        for f in getattr(self, "_dash_filaments", []):
            value = str(f.get(field) or "").strip()
            if value:
                existing.append(value)
        seen, values = set(), []
        for value in list(builtin) + list(custom) + existing:
            if value and value not in seen:
                seen.add(value)
                values.append(value)
        return values

    def remember_catalog_value(self, category, value):
        value = str(value or "").strip()
        if not value:
            return
        builtin = {"brand": BUILTIN_BRANDS, "material": BUILTIN_MATERIALS,
                   "color": [name for _, name in COLOR_PRESETS]}.get(category, [])
        if value in builtin:
            return
        key = f"custom_{category}s"
        values = list(self.cfg.get(key, []) or [])
        if value not in values:
            values.append(value)
            self.cfg[key] = values
            save_config(self.cfg)

    def combo_field(self, parent, row, col, title, default, values, columnspan=1):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.grid(row=row, column=col, columnspan=columnspan, sticky="ew", padx=6, pady=5)
        self.ui_label(box, title, 10, "bold", COLOR_TEXT_MUTED).pack(anchor="w")
        combo = ctk.CTkComboBox(
            box, values=values or [""], height=36, corner_radius=8, font=self.get_font(11),
            fg_color=COLOR_INPUT_BG, border_color=COLOR_CARD_BORDER,
            button_color=COLOR_SURFACE_2, button_hover_color=COLOR_HOVER,
            text_color=COLOR_TEXT_PRIMARY, dropdown_fg_color=COLOR_CARD_BG,
            dropdown_text_color=COLOR_TEXT_PRIMARY, dropdown_hover_color=COLOR_HOVER)
        combo.set(str(default or ""))
        combo.pack(fill="x", pady=(2, 0))
        return combo

    def surface_field(self, parent, row, default):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.grid(row=row, column=0, columnspan=2, sticky="ew", padx=6, pady=5)
        self.ui_label(box, "表面 / 类型", 10, "bold", COLOR_TEXT_MUTED).pack(anchor="w")
        combo = ctk.CTkOptionMenu(
            box, values=SURFACE_OPTIONS, height=36, corner_radius=8, font=self.get_font(11),
            fg_color=COLOR_INPUT_BG, button_color=COLOR_SURFACE_2,
            button_hover_color=COLOR_HOVER, text_color=COLOR_TEXT_PRIMARY,
            dropdown_fg_color=COLOR_CARD_BG, dropdown_text_color=COLOR_TEXT_PRIMARY,
            dropdown_hover_color=COLOR_HOVER)
        combo.set(default or "标准")
        combo.pack(fill="x", pady=(2, 0))
        self.ui_label(box, "哑光 / 丝绸 / 金属 / 透明 / 夜光 / 木纹 / 混色 / 其他", 9,
                      "normal", COLOR_TEXT_MUTED).pack(anchor="w", pady=(3, 0))
        return combo

    def remarks_field(self, parent, row, value=""):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.grid(row=row, column=0, columnspan=2, sticky="ew", padx=6, pady=5)
        self.ui_label(box, "材料备注（选填）", 10, "bold", COLOR_TEXT_MUTED).pack(anchor="w")
        text = ctk.CTkTextbox(box, height=58, corner_radius=8, font=self.get_font(11),
                              fg_color=COLOR_INPUT_BG, border_color=COLOR_CARD_BORDER,
                              text_color=COLOR_TEXT_PRIMARY, border_width=1, wrap="word")
        text.pack(fill="x", pady=(2, 0))
        text.insert("1.0", value or "")
        return text

    def build_color_picker(self, parent, initial_hex, name_entry=None):
        """可视化选色：原生调色盘 + 常用色块 + HEX 输入 + 实时预览。"""
        def normalize(value):
            value = str(value or "").strip()
            return value.upper() if re.fullmatch(r"#[0-9a-fA-F]{6}", value) else "#888888"

        color = normalize(initial_hex)
        box = ctk.CTkFrame(parent, fg_color="transparent")
        self.ui_label(box, "颜色", 10, "bold", COLOR_TEXT_MUTED).pack(anchor="w")

        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(fill="x", pady=(2, 0))
        preview = ctk.CTkFrame(row, width=34, height=34, corner_radius=8,
                               fg_color=color, border_width=1, border_color=COLOR_CARD_BORDER)
        preview.pack(side="left", padx=(0, 6))
        preview.pack_propagate(False)

        entry = ctk.CTkEntry(row, height=34, corner_radius=8, width=60, font=self.get_font(11),
                             fg_color=COLOR_INPUT_BG, border_color=COLOR_CARD_BORDER,
                             text_color=COLOR_TEXT_PRIMARY)
        entry.pack(side="left", fill="x", expand=True)
        entry.insert(0, color)

        def set_color(code, preset_name=None):
            code = normalize(code)
            preview.configure(fg_color=code)
            entry.delete(0, "end")
            entry.insert(0, code)
            if preset_name and name_entry is not None:
                current = name_entry.get().strip()
                preset_names = {n for _, n in COLOR_PRESETS}
                if not current or current in preset_names:
                    name_entry.delete(0, "end")
                    name_entry.insert(0, preset_name)

        def pick_color():
            _, code = colorchooser.askcolor(color=entry.get().strip() or color,
                                            parent=box.winfo_toplevel(),
                                            title="选择耗材颜色")
            if code:
                set_color(code)

        self.ui_button(row, "调色盘", pick_color, kind="ghost", height=34,
                       font_size=10, icon_name="palette", width=76).pack(side="left", padx=(6, 0))

        colors = ctk.CTkFrame(box, fg_color="transparent")
        colors.pack(fill="x", pady=(7, 0))
        for hex_value, label in COLOR_PRESETS:
            ctk.CTkButton(
                colors, text="", width=18, height=18, corner_radius=9,
                fg_color=hex_value, hover_color=hex_value,
                border_width=1, border_color=COLOR_CARD_BORDER,
                command=lambda h=hex_value, n=label: set_color(h, n),
            ).pack(side="left", padx=2)
        self.ui_label(box, "点色块快速选色，或点「调色盘」自定义。", 9,
                      "normal", COLOR_TEXT_MUTED).pack(anchor="w", pady=(4, 0))
        entry.bind("<KeyRelease>", lambda _e: preview.configure(fg_color=normalize(entry.get())))
        return box, entry

    def open_edit_filament_modal(self, filament):
        modal = ctk.CTkToplevel(self)
        modal.title(f"编辑耗材档案 - #{filament.get('id')}")
        modal.geometry("540x820")
        modal.minsize(500, 700)
        self._prepare_modal(modal)
        modal.configure(fg_color=COLOR_BG_MAIN)

        container = ctk.CTkFrame(modal, corner_radius=18, fg_color=COLOR_CARD_BG,
                                 border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        head = ctk.CTkFrame(container, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(16, 4))
        self.ui_label(head, "编辑耗材档案", 18, "bold").pack(anchor="w")
        self.ui_label(head, "修改品牌、材质、颜色、线径、价格与链接；存量请用「调整」。", 10,
                      "normal", COLOR_TEXT_MUTED).pack(anchor="w", pady=(2, 0))

        form = self.ui_scroll(container, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=12, pady=(4, 8))
        form.grid_columnconfigure((0, 1), weight=1, uniform="edit")

        def field(parent, row, col, title, value, key, placeholder=""):
            box = ctk.CTkFrame(parent, fg_color="transparent")
            box.grid(row=row, column=col, sticky="ew", padx=6, pady=5)
            self.ui_label(box, title, 10, "bold", COLOR_TEXT_MUTED).pack(anchor="w")
            entry = ctk.CTkEntry(box, height=36, corner_radius=8, font=self.get_font(11),
                                 placeholder_text=placeholder,
                                 fg_color=COLOR_INPUT_BG, border_color=COLOR_CARD_BORDER,
                                 text_color=COLOR_TEXT_PRIMARY,
                                 placeholder_text_color=COLOR_TEXT_MUTED)
            entry.pack(fill="x", pady=(2, 0))
            entry.insert(0, "" if value is None else str(value))
            return entry

        fields = {}
        brand_current = filament.get("brand", "Bambu")
        material_current = filament.get("material", "PLA")
        color_current = filament.get("color_name", "")
        brand_values = self.catalog_values("brand")
        material_values = self.catalog_values("material")
        color_values = self.catalog_values("color")
        if brand_current and brand_current not in brand_values:
            brand_values.insert(0, brand_current)
        if material_current and material_current not in material_values:
            material_values.insert(0, material_current)
        if color_current and color_current not in color_values:
            color_values.insert(0, color_current)
        fields["brand"] = self.combo_field(form, 0, 0, "品牌（可输入新品牌）", brand_current, brand_values)
        fields["material"] = self.combo_field(form, 0, 1, "材质（可输入新材质）", material_current, material_values)
        fields["color_name"] = self.combo_field(form, 1, 0, "颜色名称", color_current, color_values)
        color_box, color_entry = self.build_color_picker(form, filament.get("color_hex", "#888888"), fields["color_name"])
        color_box.grid(row=1, column=1, sticky="ew", padx=6, pady=5)
        fields["color_hex"] = color_entry
        fields["surface_effect"] = self.surface_field(form, 2, filament.get("surface_effect", "标准"))
        fields["initial_weight_g"] = field(form, 3, 0, "初始重量 (g)", filament.get("initial_weight_g", 1000), "initial_weight_g")
        diameter_value = f"{filament_diameter_mm(filament):g} mm"
        fields["diameter_mm"] = self.combo_field(form, 3, 1, "耗材线径 / 打印头适配", diameter_value, ["1.75 mm", "2.85 mm"])
        fields["price"] = field(form, 4, 0, "买入单价 (¥)", filament.get("price", 0), "price")
        fields["purchase_url"] = field(form, 4, 1, "购买链接", filament.get("purchase_url", ""), "purchase_url", "https://…")
        current_box = ctk.CTkFrame(form, fg_color="transparent")
        current_box.grid(row=5, column=0, sticky="ew", padx=6, pady=5)
        self.ui_label(current_box, "当前存量", 10, "bold", COLOR_TEXT_MUTED).pack(anchor="w")
        self.ui_label(current_box, f"{filament.get('current_weight_g', 0)} g（只读）", 12, "bold",
                      COLOR_BAMBU_GREEN).pack(anchor="w", pady=(8, 0))
        fields["remarks"] = self.remarks_field(form, 6, filament.get("remarks", ""))

        def submit():
            try:
                payload = {
                    "brand": fields["brand"].get().strip() or "Bambu",
                    "material": fields["material"].get().strip(),
                    "color_name": fields["color_name"].get().strip(),
                    "color_hex": (fields["color_hex"].get().strip().upper() if re.fullmatch(r"#[0-9a-fA-F]{6}", fields["color_hex"].get().strip()) else "#888888"),
                    "surface_effect": fields["surface_effect"].get(),
                    "diameter_mm": float(fields["diameter_mm"].get().replace("mm", "").strip() or 1.75),
                    "initial_weight_g": float(fields["initial_weight_g"].get().strip()),
                    "price": float(fields["price"].get().strip() or 0),
                    "purchase_url": fields["purchase_url"].get().strip(),
                    "remarks": fields["remarks"].get("1.0", "end").strip(),
                }
                if not payload["material"] or not payload["color_name"]:
                    return messagebox.showwarning("提示", "材质和颜色名称不能为空", parent=modal)
                base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
                res = api_request(f"{base_url}/api/ingest/script-filaments/{filament['id']}",
                                  self.cfg['api_key'], method="PUT", data=payload)
                if res:
                    self.remember_catalog_value("brand", payload["brand"])
                    self.remember_catalog_value("material", payload["material"])
                    self.remember_catalog_value("color", payload["color_name"])
                    messagebox.showinfo("成功", "耗材档案已更新！", parent=modal)
                    modal.destroy()
                    self.refresh_dashboard()
                else:
                    messagebox.showerror("保存失败",
                                         "服务端未接受更新。\n请确认服务端已包含 PUT /api/ingest/script-filaments/{id}（本仓库新版已自带）。",
                                         parent=modal)
            except Exception as e:
                messagebox.showerror("错误", f"请检查输入格式：\n{e}", parent=modal)

        ctk.CTkButton(container, text="保存修改", height=42, corner_radius=12,
                      fg_color=COLOR_BAMBU_GREEN, hover_color=("#0B8A5F", "#4ADE80"),
                      text_color=COLOR_ON_ACCENT, font=self.get_font(13, "bold"),
                      command=submit).pack(fill="x", padx=18, pady=(0, 16), side="bottom")

    def ask_copy_count(self, title, headline, subtitle, unit="卷", max_count=30, accent=COLOR_BAMBU_GREEN):
        """现代数量选择弹窗：- / + 步进 + 快捷数量，返回选择的份数（取消返回 None）。"""
        result = {"n": None}
        modal = ctk.CTkToplevel(self)
        modal.title(title)
        modal.geometry("440x320")
        modal.resizable(False, False)
        self._prepare_modal(modal)
        try:
            modal.grab_set()
        except Exception:
            pass

        container = ctk.CTkFrame(modal, corner_radius=20, fg_color=COLOR_CARD_BG,
                                 border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        head = ctk.CTkFrame(container, fg_color="transparent")
        head.pack(fill="x", padx=22, pady=(20, 4))
        self.ui_label(head, headline, 15, "bold").pack(anchor="w")
        self.ui_label(container, subtitle, 10, "normal", COLOR_TEXT_MUTED, wraplength=360,
                      justify="left").pack(anchor="w", padx=22, pady=(2, 14))

        stepper = ctk.CTkFrame(container, fg_color=COLOR_SURFACE_2, corner_radius=16)
        stepper.pack(fill="x", padx=22, pady=6)
        ctrl = ctk.CTkFrame(stepper, fg_color="transparent")
        ctrl.pack(expand=True, pady=12)
        value_lbl = ctk.CTkLabel(ctrl, text="1", font=self.get_font(28, "bold"), text_color=COLOR_TEXT_PRIMARY,
                                 width=64)
        unit_lbl = ctk.CTkLabel(ctrl, text=unit, font=self.get_font(11), text_color=COLOR_TEXT_MUTED, width=24)
        state = {"n": 1}

        def render():
            value_lbl.configure(text=str(state["n"]))

        def change(delta):
            state["n"] = max(1, min(max_count, state["n"] + delta))
            render()

        self.ui_button(ctrl, "−", lambda: change(-1), kind="ghost", width=44, height=40,
                       font_size=16).pack(side="left", padx=(0, 10))
        value_lbl.pack(side="left")
        unit_lbl.pack(side="left", padx=(4, 10))
        self.ui_button(ctrl, "+", lambda: change(1), kind="soft", width=44, height=40,
                       font_size=16).pack(side="left")

        quick = ctk.CTkFrame(container, fg_color="transparent")
        quick.pack(fill="x", padx=22, pady=(6, 0))
        self.ui_label(quick, "快捷：", 10, "normal", COLOR_TEXT_MUTED).pack(side="left")
        for q in (1, 3, 5, 10):
            self.ui_button(quick, str(q), lambda v=q: (state.__setitem__("n", v), render()),
                           kind="ghost", width=40, height=26, font_size=10).pack(side="left", padx=(4, 0))

        btns = ctk.CTkFrame(container, fg_color="transparent")
        btns.pack(fill="x", padx=22, pady=(18, 18), side="bottom")

        def confirm():
            result["n"] = state["n"]
            modal.destroy()

        ctk.CTkButton(btns, text="取消", height=40, corner_radius=12, fg_color=COLOR_SURFACE_2,
                      hover_color=COLOR_HOVER, text_color=COLOR_TEXT_PRIMARY, font=self.get_font(11),
                      command=modal.destroy).pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkButton(btns, text=f"确认复制", height=40, corner_radius=12, fg_color=accent,
                      hover_color=("#0B8A5F", "#4ADE80"), text_color=COLOR_ON_ACCENT,
                      font=self.get_font(12, "bold"), command=confirm).pack(side="left", expand=True, fill="x")

        modal.wait_window()
        return result["n"]

    def copy_filament(self, filament):
        title = f"{filament.get('brand', '')} {filament.get('material', '')} · {filament.get('color_name', '')}"
        init_w = filament.get("initial_weight_g", 1000)
        count = self.ask_copy_count(
            "复制耗材",
            title,
            f"将生成多张同款料盘，每卷剩余重量重置为 {init_w} g；品牌、颜色、价格与购买链接保持一致。",
            unit="卷",
        )
        if not count:
            return
        ok = 0
        for i in range(count):
            payload = {
                "brand": filament.get("brand", "Bambu"),
                "material": filament.get("material", "PLA"),
                "color_name": filament.get("color_name", "自定义"),
                "color_hex": filament.get("color_hex", "#888888"),
                "surface_effect": filament.get("surface_effect", "标准"),
                "diameter_mm": filament_diameter_mm(filament),
                "initial_weight_g": init_w,
                "current_weight_g": init_w,
                "price": filament.get("price", 0),
                "purchase_url": filament.get("purchase_url") or "",
                "remarks": f"复制自 #{filament.get('id')}" + (f"（{i + 1}/{count}）" if count > 1 else ""),
            }
            res = api_request(f"{self.cfg['server_url']}-create", self.cfg['api_key'], method="POST", data=payload)
            if res:
                ok += 1
        if ok:
            messagebox.showinfo("复制成功", f"已生成 {ok} 卷同款料盘。")
            self.refresh_dashboard()
        else:
            messagebox.showerror("复制失败", "请检查服务连接或服务端是否支持新增耗材接口。")

    def open_add_filament_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("新增耗材")
        modal.geometry("580x820")
        modal.minsize(540, 700)
        self._prepare_modal(modal)

        container = ctk.CTkFrame(modal, corner_radius=18, fg_color=COLOR_CARD_BG,
                                 border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        head = ctk.CTkFrame(container, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(16, 4))
        self.ui_label(head, "新增耗材", 18, "bold").pack(anchor="w")
        self.ui_label(head, "录入一卷新耗材，支持一次批量生成多卷。", 10, "normal", COLOR_TEXT_MUTED).pack(anchor="w", pady=(2, 0))

        form = self.ui_scroll(container, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=12, pady=(4, 8))
        form.grid_columnconfigure((0, 1), weight=1, uniform="add")

        def field(row, col, title, default, placeholder=""):
            box = ctk.CTkFrame(form, fg_color="transparent")
            box.grid(row=row, column=col, sticky="ew", padx=6, pady=5)
            self.ui_label(box, title, 10, "bold", COLOR_TEXT_MUTED).pack(anchor="w")
            entry = ctk.CTkEntry(box, height=36, corner_radius=8, font=self.get_font(11),
                                 placeholder_text=placeholder,
                                 fg_color=COLOR_INPUT_BG, border_color=COLOR_CARD_BORDER,
                                 text_color=COLOR_TEXT_PRIMARY,
                                 placeholder_text_color=COLOR_TEXT_MUTED)
            entry.pack(fill="x", pady=(2, 0))
            entry.insert(0, default)
            return entry

        fields = {}
        brand_values = self.catalog_values("brand")
        material_values = self.catalog_values("material")
        color_values = self.catalog_values("color")
        fields["brand"] = self.combo_field(form, 0, 0, "耗材品牌（可输入新品牌）", "Bambu Lab", brand_values)
        fields["material"] = self.combo_field(form, 0, 1, "耗材材质（可输入新材质）", "PLA Basic", material_values)
        fields["color_name"] = self.combo_field(form, 1, 0, "颜色名称", "基础绿", color_values)
        color_box, color_entry = self.build_color_picker(form, "#00AE42", fields["color_name"])
        color_box.grid(row=1, column=1, sticky="ew", padx=6, pady=5)
        fields["color_hex"] = color_entry
        fields["surface_effect"] = self.surface_field(form, 2, "标准")
        fields["initial_weight_g"] = field(3, 0, "单卷初始克重 (g)", "1000")
        fields["diameter_mm"] = self.combo_field(form, 3, 1, "耗材线径 / 打印头适配", "1.75 mm", ["1.75 mm", "2.85 mm"])
        fields["price"] = field(4, 0, "单卷买入价格 (¥)", "99.0")
        fields["purchase_url"] = field(4, 1, "购买链接（选填）", "", "https://…")
        fields["count"] = field(5, 0, "批量入库数量（卷）", "1")
        fields["remarks"] = self.remarks_field(form, 6)
        self.ui_label(form, "2.85 mm 用于 TPU 75A 等 2.85 线径耗材；数量大于 1 时会批量创建。", 9,
                      "normal", COLOR_TEXT_MUTED).grid(row=7, column=0, columnspan=2, sticky="w", padx=6, pady=(2, 0))

        def submit():
            try:
                count = int(fields["count"].get().strip() or 1)
                if count < 1:
                    count = 1
                payload = {
                    "brand": fields["brand"].get().strip() or "Bambu",
                    "material": fields["material"].get().strip(),
                    "color_name": fields["color_name"].get().strip(),
                    "color_hex": (fields["color_hex"].get().strip().upper() if re.fullmatch(r"#[0-9a-fA-F]{6}", fields["color_hex"].get().strip()) else "#888888"),
                    "surface_effect": fields["surface_effect"].get(),
                    "diameter_mm": float(fields["diameter_mm"].get().replace("mm", "").strip() or 1.75),
                    "initial_weight_g": float(fields["initial_weight_g"].get().strip()),
                    "current_weight_g": float(fields["initial_weight_g"].get().strip()),
                    "price": float(fields["price"].get().strip() or 0),
                    "purchase_url": fields["purchase_url"].get().strip(),
                    "remarks": fields["remarks"].get("1.0", "end").strip(),
                }
                if not payload["material"] or not payload["color_name"]:
                    return messagebox.showwarning("提示", "材质和颜色名称不能为空", parent=modal)
                base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
                if count == 1:
                    res = api_request(f"{self.cfg['server_url']}-create", self.cfg['api_key'], method="POST", data=payload)
                else:
                    batch = [payload.copy() for _ in range(count)]
                    res = api_request(f"{base_url}/api/ingest/script-filaments-batch", self.cfg['api_key'], method="POST", data=batch)
                if res:
                    self.remember_catalog_value("brand", payload["brand"])
                    self.remember_catalog_value("material", payload["material"])
                    self.remember_catalog_value("color", payload["color_name"])
                    messagebox.showinfo("成功", f"成功录入 {count} 卷耗材！", parent=modal)
                    modal.destroy()
                    self.refresh_dashboard()
                else:
                    messagebox.showerror("录入失败", "请检查服务连接或服务端接口。", parent=modal)
            except Exception as e:
                messagebox.showerror("错误", f"录入失败，请检查输入格式：\n{e}", parent=modal)

        ctk.CTkButton(container, text="保存入库", height=42, corner_radius=12,
                      fg_color=COLOR_BAMBU_GREEN, hover_color=("#0B8A5F", "#4ADE80"),
                      text_color=COLOR_ON_ACCENT, font=self.get_font(13, "bold"),
                      command=submit).pack(fill="x", padx=18, pady=(0, 16), side="bottom")

    def open_adjust_modal(self, filament):
        modal = ctk.CTkToplevel(self)
        modal.title(f"调整存量 - #{filament['id']}")
        modal.geometry("500x560")
        modal.minsize(460, 500)
        self._prepare_modal(modal)

        container = ctk.CTkFrame(modal, corner_radius=18, fg_color=COLOR_CARD_BG,
                                 border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        head = ctk.CTkFrame(container, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(16, 4))
        self.ui_label(head, "调整存量", 18, "bold").pack(anchor="w")
        self.ui_label(head, f"{filament.get('brand', '')} {filament.get('material', '')} · {filament.get('color_name', '')}",
                      10, "normal", COLOR_TEXT_MUTED).pack(anchor="w", pady=(2, 0))
        current = self.ui_label(head, f"当前剩余 {filament.get('current_weight_g', 0)} g", 12, "bold", COLOR_BAMBU_GREEN)
        current.pack(anchor="w", pady=(6, 0))

        body = ctk.CTkFrame(container, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=(10, 0))
        body.grid_columnconfigure((0, 1), weight=1, uniform="adj")

        def entry(parent, title, placeholder=""):
            box = ctk.CTkFrame(parent, fg_color="transparent")
            box.grid_columnconfigure(0, weight=1)
            self.ui_label(box, title, 10, "bold", COLOR_TEXT_MUTED).pack(anchor="w")
            e = ctk.CTkEntry(box, height=36, corner_radius=8, font=self.get_font(11),
                             placeholder_text=placeholder,
                             fg_color=COLOR_INPUT_BG, border_color=COLOR_CARD_BORDER,
                             text_color=COLOR_TEXT_PRIMARY,
                             placeholder_text_color=COLOR_TEXT_MUTED)
            e.pack(fill="x", pady=(2, 0))
            return box, e

        type_box = ctk.CTkFrame(body, fg_color="transparent")
        type_box.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=5)
        self.ui_label(type_box, "调整类型", 10, "bold", COLOR_TEXT_MUTED).pack(anchor="w")
        cb_action = ctk.CTkComboBox(type_box, values=["减少 (-)", "增加 (+)"], height=36,
                                    corner_radius=8, font=self.get_font(11),
                                    fg_color=COLOR_INPUT_BG, border_color=COLOR_CARD_BORDER,
                                    button_color=COLOR_SURFACE_2, button_hover_color=COLOR_HOVER,
                                    text_color=COLOR_TEXT_PRIMARY, dropdown_fg_color=COLOR_CARD_BG,
                                    dropdown_text_color=COLOR_TEXT_PRIMARY, dropdown_hover_color=COLOR_HOVER)
        cb_action.pack(fill="x", pady=(2, 0))
        cb_action.set("减少 (-)")

        weight_box, entry_weight = entry(body, "变动克重 (g)", "例如 50")
        weight_box.grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=5)
        entry_weight.configure(placeholder_text="例如 50")

        model_box, entry_model = entry(body, "模型 / 原因", "手动样品、测试件…")
        model_box.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=5)
        remark_box, entry_remark = entry(body, "备注（选填）", "管道残料清理 / 补充新卷")
        remark_box.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=5)

        self.ui_label(body, "每次调整都会写入历史流水，可在「历史」里撤销。", 9,
                      "normal", COLOR_TEXT_MUTED).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

        def submit():
            try:
                raw_w = float(entry_weight.get().strip())
                if raw_w <= 0:
                    return messagebox.showwarning("提示", "克重请输入大于 0 的数值！", parent=modal)
                act = cb_action.get()
                model_name = entry_model.get().strip() or "手动调整"
                remark_str = entry_remark.get().strip()
                final_change_g = raw_w if "减少" in act else -raw_w
                act_text = "手动减少" if "减少" in act else "手动增加"
                full_task_name = f"{act_text}（{model_name} - {remark_str}）" if remark_str else f"{act_text}（{model_name}）"
                payload = {
                    "filament_id": filament['id'],
                    "used_weight_g": final_change_g,
                    "task_name": full_task_name,
                }
                res = api_request(self.cfg['server_url'], self.cfg['api_key'], method="POST", data=payload)
                if res:
                    messagebox.showinfo("成功", "克重调整完成并已记录！", parent=modal)
                    modal.destroy()
                    self.refresh_dashboard()
                else:
                    messagebox.showerror("错误", "上报调整失败，请检查服务连接！", parent=modal)
            except Exception as e:
                messagebox.showerror("错误", f"提交失败，请输入格式正确的克重数值！\n{e}", parent=modal)

        ctk.CTkButton(container, text="确认调整", height=42, corner_radius=12,
                      fg_color=COLOR_BAMBU_GREEN, hover_color=("#0B8A5F", "#4ADE80"),
                      text_color=COLOR_ON_ACCENT, font=self.get_font(13, "bold"),
                      command=submit).pack(fill="x", padx=18, pady=(0, 16), side="bottom")

    def delete_filament(self, fid):
        if messagebox.askyesno("确认", f"确定要彻底删除 ID #{fid} 的耗材档案吗？"):
            api_request(f"{self.cfg['server_url']}-delete/{fid}", self.cfg['api_key'], method="DELETE")
            self.refresh_dashboard()

    # --------------------------------------------------------------------------
    # 子功能: 智能称重工作台 (Scale Workbench + 包含完整控制、双轨OTA与校准) [START]
    # --------------------------------------------------------------------------
    def init_scale_workbench_view(self):
        if "scale_workbench" in self.views:
            return
        view = ctk.CTkFrame(self.content_area, corner_radius=0, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1, uniform="col")
        view.grid_columnconfigure(1, weight=1, uniform="col")
        view.grid_rowconfigure(0, weight=1)
        self.views["scale_workbench"] = view
        self._scale_poll_running = False
        self._scale_current_pending = None

        left = self.ui_scroll(view, corner_radius=18, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        left.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=16)
        left.grid_columnconfigure(0, weight=1)

        self.scale_status_label = ctk.CTkLabel(left, text="秤休眠中", font=self.get_font(16, "bold"), text_color=COLOR_TEXT_MUTED, fg_color=COLOR_SURFACE_2, corner_radius=20, height=40)
        self.scale_status_label.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        self.register_widget_font(self.scale_status_label, 16, "bold")

        self.scale_weight_label = ctk.CTkLabel(left, text="--.- g", font=self.get_font(42, "bold"), text_color=COLOR_TEXT_PRIMARY)
        self.scale_weight_label.grid(row=1, column=0, pady=(20, 8))
        self.register_widget_font(self.scale_weight_label, 42, "bold")

        self.scale_uid_label = ctk.CTkLabel(left, text="NFC UID: --", font=self.get_font(12), text_color=COLOR_TEXT_MUTED)
        self.scale_uid_label.grid(row=2, column=0, pady=(4, 2))
        self.register_widget_font(self.scale_uid_label, 12)
        self.scale_name_label = ctk.CTkLabel(left, text="耗材: 未识别", font=self.get_font(13, "bold"), text_color=COLOR_TEXT_PRIMARY)
        self.scale_name_label.grid(row=3, column=0, pady=(2, 4))
        self.register_widget_font(self.scale_name_label, 13, "bold")
        self.scale_color_dot = ctk.CTkLabel(left, text="", width=24, height=24, corner_radius=12, fg_color="#888888")
        self.scale_color_dot.grid(row=4, column=0, pady=(4, 16))

        self.scale_refresh_btn = ctk.CTkButton(left, text="立即刷新", font=self.get_font(13, "bold"), height=36, corner_radius=18, fg_color=COLOR_BAMBU_GREEN, hover_color=("#0B8A5F", "#4ADE80"), command=self.refresh_current_tab)
        self.scale_refresh_btn.grid(row=5, column=0, sticky="ew", padx=16, pady=(8, 4))
        self.register_widget_font(self.scale_refresh_btn, 13, "bold")

        self.scale_manual_btn = ctk.CTkButton(left, text="手动称重（无 NFC）", font=self.get_font(12, "bold"), height=32, corner_radius=16, fg_color=COLOR_SURFACE_2, hover_color=COLOR_HOVER, text_color=COLOR_TEXT_PRIMARY, border_width=1, border_color=COLOR_CARD_BORDER, command=self.open_manual_weigh_modal)
        self.scale_manual_btn.grid(row=6, column=0, sticky="ew", padx=16, pady=(0, 8))
        self.register_widget_font(self.scale_manual_btn, 12, "bold")

        # 设备控制区域
        ctk.CTkLabel(left, text="设备远程控制", font=self.get_font(11, "bold"), text_color=COLOR_TEXT_MUTED).grid(row=7, column=0, sticky="w", padx=16, pady=(8, 2))
        self.device_status_label = ctk.CTkLabel(left, text="状态: 未连接", font=self.get_font(10), text_color=COLOR_TEXT_MUTED, anchor="w")
        self.device_status_label.grid(row=8, column=0, sticky="ew", padx=16, pady=(0, 4))
        self.register_widget_font(self.device_status_label, 10)

        dev_btn_frame = ctk.CTkFrame(left, fg_color="transparent")
        dev_btn_frame.grid(row=9, column=0, sticky="ew", padx=16, pady=(0, 4))
        dev_btn_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        ctk.CTkButton(dev_btn_frame, text="称重", font=self.get_font(10), height=26, corner_radius=10, fg_color=COLOR_BAMBU_GREEN, hover_color=("#0B8A5F", "#4ADE80"), command=lambda: self.send_device_command("switch_page", {"page": "weighing"})).grid(row=0, column=0, padx=1)
        ctk.CTkButton(dev_btn_frame, text="设备信息", font=self.get_font(10), height=26, corner_radius=10, fg_color=COLOR_BLUE, hover_color=("#1D4ED8", "#93C5FD"), command=lambda: self.send_device_command("switch_page", {"page": "device_info"})).grid(row=0, column=1, padx=1)
        ctk.CTkButton(dev_btn_frame, text="WiFi 状态", font=self.get_font(10), height=26, corner_radius=10, fg_color=COLOR_AMBER, hover_color=("#B45309", "#FCD34D"), command=lambda: self.send_device_command("switch_page", {"page": "wifi_config"})).grid(row=0, column=2, padx=1)
        ctk.CTkButton(dev_btn_frame, text="远程开机", font=self.get_font(10), height=26, corner_radius=10, fg_color=COLOR_BAMBU_GREEN, hover_color=("#0B8A5F", "#4ADE80"), command=self.send_wake_pc).grid(row=0, column=3, padx=1)
        ctk.CTkButton(left, text="重启设备", font=self.get_font(10), height=26, corner_radius=10, fg_color=COLOR_SURFACE_2, hover_color=COLOR_HOVER, text_color=COLOR_TEXT_PRIMARY, border_width=1, border_color=COLOR_CARD_BORDER, command=lambda: self.send_device_command("reboot", {})).grid(row=10, column=0, sticky="ew", padx=16, pady=(0, 4))

        # 🧪 电子秤开发者模式（开启后禁止自动休眠）
        devmode_frame = ctk.CTkFrame(left, fg_color="transparent")
        devmode_frame.grid(row=11, column=0, sticky="ew", padx=16, pady=(0, 4))
        devmode_frame.grid_columnconfigure((0, 1), weight=1)
        self.dev_mode_btn = ctk.CTkButton(devmode_frame, text="开发者模式: 关", font=self.get_font(10), height=26, corner_radius=10, fg_color=COLOR_VIOLET, hover_color=("#5B21B6", "#C4B5FD"), command=self.toggle_dev_mode)
        self.dev_mode_btn.grid(row=0, column=0, columnspan=2, sticky="ew", padx=1)
        ctk.CTkLabel(left, text="开启后电子秤不会自动休眠，建议插电使用", font=self.get_font(9), text_color=COLOR_TEXT_MUTED, anchor="w").grid(row=12, column=0, sticky="ew", padx=16, pady=(0, 4))

        # 🎯 传感器向导式校准按钮
        ctk.CTkLabel(left, text="传感器校准", font=self.get_font(11, "bold"), text_color=COLOR_TEXT_MUTED).grid(row=13, column=0, sticky="w", padx=16, pady=(8, 2))
        calib_btn_frame = ctk.CTkFrame(left, fg_color="transparent")
        calib_btn_frame.grid(row=14, column=0, sticky="ew", padx=16, pady=(0, 4))
        calib_btn_frame.grid_columnconfigure((0, 1), weight=1)

        def do_tare():
            if messagebox.askyesno("第一步：清空秤盘", "请确保秤盘上无任何物品，点击确认开始去皮。"):
                self.send_device_command("tare")

        def do_calib():
            dialog = ctk.CTkInputDialog(text="第二步：放上标准砝码并输入准确克重 (如: 500):", title="标定系数")
            w_str = dialog.get_input()
            if w_str:
                try:
                    w = float(w_str)
                    self.send_device_command("calibrate", {"weight": w})
                    messagebox.showinfo("成功", "校准指令已下发！")
                except:
                    messagebox.showerror("错误", "请输入有效的数字！")

        ctk.CTkButton(calib_btn_frame, text="① 清空并去皮", font=self.get_font(10), height=26, corner_radius=10, fg_color=COLOR_AMBER, command=do_tare).grid(row=0, column=0, padx=1)
        ctk.CTkButton(calib_btn_frame, text="② 标定已知重量", font=self.get_font(10), height=26, corner_radius=10, fg_color=COLOR_BLUE, command=do_calib).grid(row=0, column=1, padx=1)

        # 🚀 双轨固件 OTA 升级按钮
        def trigger_fw_update():
            if not messagebox.askyesno("ESP32 固件更新", "确认向 ESP32 下发自动更新指令？\n硬件将自动从云端拉取最新固件。"): return
            base_url = self.cfg.get("server_url", "").replace('/api/ingest/script-report', '')
            api_key = self.cfg.get("api_key", "")
            try:
                res = api_request(f"{base_url}/api/scale/ota_check", api_key=api_key, method="GET")
                if res and res.get("status") == "success":
                    api_request(f"{base_url}/api/scale/ota/push", api_key=api_key, method="POST", data={"download_url": res["download_url"]})
                    messagebox.showinfo("成功", "✅ 固件 OTA 指令下发成功！硬件将自动重启并更新。")
                else: messagebox.showerror("错误", "获取最新固件地址失败！")
            except Exception as e: messagebox.showerror("错误", f"网络异常: {e}")

        ctk.CTkButton(left, text="ESP32 固件更新", font=self.get_font(10), height=26, corner_radius=10, fg_color=COLOR_VIOLET, command=trigger_fw_update).grid(row=15, column=0, sticky="ew", padx=16, pady=(6, 4))
        ctk.CTkButton(left, text="重置配网", font=self.get_font(10), height=26, corner_radius=10, fg_color="#DC2626", hover_color="#B91C1C", command=lambda: self.send_device_command("reset_config", {})).grid(row=16, column=0, sticky="ew", padx=16, pady=(0, 16))

        right = ctk.CTkFrame(view, corner_radius=18, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=16)
        right.grid_columnconfigure(0, weight=1)

        # 未绑定提示区域（默认隐藏）
        self.scale_unbound_frame = ctk.CTkFrame(right, corner_radius=10, fg_color=COLOR_AMBER_SOFT, border_width=1, border_color=COLOR_AMBER)
        self.scale_unbound_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        self.scale_unbound_frame.grid_columnconfigure(0, weight=1)
        self.scale_unbound_frame.grid_remove()
        ctk.CTkLabel(self.scale_unbound_frame, text="NFC 未绑定耗材", font=self.get_font(14, "bold"), text_color=COLOR_AMBER).grid(row=0, column=0, pady=(10, 4))
        self.register_widget_font(self.scale_unbound_frame.winfo_children()[-1], 14, "bold")
        self.scale_unbound_uid_label = ctk.CTkLabel(self.scale_unbound_frame, text="NFC UID: --", font=self.get_font(11), text_color=COLOR_TEXT_MUTED)
        self.scale_unbound_uid_label.grid(row=1, column=0, pady=(0, 2))
        self.register_widget_font(self.scale_unbound_uid_label, 11)
        self.scale_unbound_weight_label = ctk.CTkLabel(self.scale_unbound_frame, text="实测毛重: -- g", font=self.get_font(12, "bold"), text_color=COLOR_TEXT_PRIMARY)
        self.scale_unbound_weight_label.grid(row=2, column=0, pady=(0, 8))
        self.register_widget_font(self.scale_unbound_weight_label, 12, "bold")
        self.scale_bind_btn = ctk.CTkButton(self.scale_unbound_frame, text="绑定耗材", font=self.get_font(13, "bold"), height=36, corner_radius=18, fg_color=COLOR_BAMBU_GREEN, hover_color=("#0B8A5F", "#4ADE80"), command=self.open_scale_bind_modal)
        self.scale_bind_btn.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 12))
        self.register_widget_font(self.scale_bind_btn, 13, "bold")

        ctk.CTkLabel(right, text="账面对比", font=self.get_font(16, "bold"), text_color=COLOR_TEXT_PRIMARY).grid(row=1, column=0, sticky="w", padx=16, pady=(16, 8))
        self.register_widget_font(right.winfo_children()[-1], 16, "bold")

        cmp_frame = ctk.CTkFrame(right, corner_radius=10, fg_color=COLOR_SURFACE_2, border_width=1, border_color=COLOR_CARD_BORDER)
        cmp_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))
        cmp_frame.grid_columnconfigure(0, weight=1)
        cmp_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(cmp_frame, text="系统理论剩余", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).grid(row=0, column=0, pady=(8, 2))
        ctk.CTkLabel(cmp_frame, text="秤端实测剩余", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).grid(row=0, column=1, pady=(8, 2))
        self.scale_theory_label = ctk.CTkLabel(cmp_frame, text="-- g", font=self.get_font(18, "bold"), text_color=COLOR_TEXT_PRIMARY)
        self.scale_theory_label.grid(row=1, column=0, pady=(0, 8))
        self.register_widget_font(self.scale_theory_label, 18, "bold")
        self.scale_actual_label = ctk.CTkLabel(cmp_frame, text="-- g", font=self.get_font(18, "bold"), text_color=COLOR_BAMBU_GREEN)
        self.scale_actual_label.grid(row=1, column=1, pady=(0, 8))
        self.register_widget_font(self.scale_actual_label, 18, "bold")

        self.scale_diff_label = ctk.CTkLabel(right, text="Δ 误差: -- g", font=self.get_font(20, "bold"), text_color=COLOR_TEXT_MUTED)
        self.scale_diff_label.grid(row=3, column=0, pady=(8, 12))
        self.register_widget_font(self.scale_diff_label, 20, "bold")

        btn_frame = ctk.CTkFrame(right, corner_radius=0, fg_color="transparent")
        btn_frame.grid(row=4, column=0, sticky="ew", padx=16, pady=(4, 8))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        btn_frame.grid_columnconfigure(2, weight=1)

        self.scale_btn_failure = ctk.CTkButton(btn_frame, text="打印失败纠正", font=self.get_font(11, "bold"), height=44, corner_radius=10, fg_color=COLOR_BADGE_RED, hover_color="#C02828", state="disabled", command=lambda: self.scale_confirm_action("failure_correction"))
        self.scale_btn_failure.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.register_widget_font(self.scale_btn_failure, 11, "bold")

        self.scale_btn_normal = ctk.CTkButton(btn_frame, text="常规误差同步", font=self.get_font(11, "bold"), height=44, corner_radius=10, fg_color=COLOR_BLUE, hover_color=("#1D4ED8", "#93C5FD"), state="disabled", command=lambda: self.scale_confirm_action("normal_sync"))
        self.scale_btn_normal.grid(row=0, column=1, sticky="ew", padx=4)
        self.register_widget_font(self.scale_btn_normal, 11, "bold")

        self.scale_btn_new = ctk.CTkButton(btn_frame, text="新料盘 / 重置皮重", font=self.get_font(11, "bold"), height=44, corner_radius=10, fg_color=COLOR_BAMBU_GREEN, hover_color=("#0B8A5F", "#4ADE80"), state="disabled", command=self.scale_new_spool)
        self.scale_btn_new.grid(row=0, column=2, sticky="ew", padx=(4, 0))
        self.register_widget_font(self.scale_btn_new, 11, "bold")

        self.scale_hint_label = ctk.CTkLabel(right, text="等待秤端上报数据...", font=self.get_font(11), text_color=COLOR_TEXT_MUTED)
        self.scale_hint_label.grid(row=5, column=0, pady=(8, 8))
        self.register_widget_font(self.scale_hint_label, 11)

        # 历史待确认记录
        ctk.CTkLabel(right, text="历史待确认记录", font=self.get_font(13, "bold"), text_color=COLOR_TEXT_PRIMARY).grid(row=6, column=0, sticky="w", padx=16, pady=(8, 4))
        self.register_widget_font(right.winfo_children()[-1], 13, "bold")
        self.scale_history_frame = self.ui_scroll(right, height=180, fg_color=COLOR_INPUT_BG, corner_radius=8)
        self.scale_history_frame.grid(row=7, column=0, sticky="nsew", padx=16, pady=(0, 16))
        right.grid_rowconfigure(7, weight=1)

        self._start_scale_polling()

    def _start_scale_polling(self):
        if self._scale_poll_running:
            return
        self._scale_poll_running = True
        self._scale_poll_loop()

    def _scale_poll_loop(self):
        if not self._scale_poll_running:
            return
        try:
            if "scale_workbench" in self.views and self.views["scale_workbench"].winfo_ismapped() and not self._tab_loading:
                self._refresh_tab_async("scale_workbench")
        except Exception:
            pass
        self.after(5000, self._scale_poll_loop)

    def refresh_scale_workbench(self, silent=False):
        base_url = self.cfg.get("server_url", "").replace('/api/ingest/script-report', '')
        api_key = self.cfg.get("api_key", "")
        if not base_url or not api_key:
            if not silent:
                messagebox.showwarning("提示", "请先在服务设置中配置服务器地址和 API Key")
            return
        status_url = f"{base_url}/api/scale/status"
        res = api_request(status_url, api_key=api_key, method="GET")
        if not res:
            self.scale_status_label.configure(text="连接服务器失败", text_color=COLOR_BADGE_RED, fg_color=COLOR_RED_SOFT)
            return
        items = res.get("items", [])
        if not items:
            self._scale_current_pending = None
            self.scale_status_label.configure(text="秤休眠中 / 无待确认", text_color=COLOR_TEXT_MUTED, fg_color=COLOR_SURFACE_2)
            self.scale_weight_label.configure(text="--.- g")
            self.scale_uid_label.configure(text="NFC UID: --")
            self.scale_name_label.configure(text="耗材: 未识别")
            self.scale_color_dot.configure(fg_color="#888888")
            self.scale_theory_label.configure(text="-- g")
            self.scale_actual_label.configure(text="-- g")
            self.scale_diff_label.configure(text="Δ 误差: -- g", text_color=COLOR_TEXT_MUTED)
            self.scale_btn_failure.configure(state="disabled")
            self.scale_btn_normal.configure(state="disabled")
            self.scale_btn_new.configure(state="disabled")
            self.scale_hint_label.configure(text="等待秤端上报数据...")
            return
        item = items[0]
        self._scale_current_pending = item
        is_unbound = not item.get("filament_id") or item.get("filament_name", "") == "未绑定耗材"
        if is_unbound:
            self.scale_unbound_frame.grid()
            self.scale_unbound_uid_label.configure(text=f"NFC UID: {item.get('nfc_uid', '--')}")
            self.scale_unbound_weight_label.configure(text=f"实测毛重: {item.get('measured_weight_g', 0):.1f} g")
            self.scale_status_label.configure(text="等待绑定", text_color=COLOR_AMBER, fg_color=COLOR_AMBER_SOFT)
            self.scale_weight_label.configure(text=f"{item.get('measured_weight_g', 0):.1f} g")
            self.scale_uid_label.configure(text=f"NFC UID: {item.get('nfc_uid', '--')}")
            self.scale_name_label.configure(text="耗材: 未绑定")
            self.scale_color_dot.configure(fg_color="#888888")
            self.scale_theory_label.configure(text="-- g")
            self.scale_actual_label.configure(text="-- g")
            self.scale_diff_label.configure(text="Δ 误差: -- g", text_color=COLOR_TEXT_MUTED)
            self.scale_btn_failure.configure(state="disabled")
            self.scale_btn_normal.configure(state="disabled")
            self.scale_btn_new.configure(state="disabled")
            self.scale_hint_label.configure(text="点击「绑定耗材」完成绑定后自动计算净重")
            return
        self.scale_unbound_frame.grid_remove()
        self.scale_status_label.configure(text="硬件已就绪", text_color=COLOR_BAMBU_GREEN, fg_color=COLOR_ACCENT_SOFT)
        self.scale_weight_label.configure(text=f"{item.get('measured_weight_g', 0):.1f} g")
        self.scale_uid_label.configure(text=f"NFC UID: {item.get('nfc_uid', '--')}")
        self.scale_name_label.configure(text=f"耗材: {item.get('filament_name', '未绑定')}")
        self.scale_color_dot.configure(fg_color=item.get('color_hex', "#888888"))
        theory = item.get('expected_weight_g')
        actual = item.get('measured_weight_g', 0)
        self.scale_theory_label.configure(text=f"{theory:.1f} g" if theory is not None else "-- g")
        self.scale_actual_label.configure(text=f"{actual:.1f} g")
        diff = item.get('difference_g')
        if diff is not None:
            color = COLOR_BADGE_RED if diff < 0 else COLOR_BAMBU_GREEN
            sign = "+" if diff > 0 else ""
            self.scale_diff_label.configure(text=f"Δ 误差: {sign}{diff:.1f} g", text_color=color)
        else:
            self.scale_diff_label.configure(text="Δ 误差: -- g", text_color=COLOR_TEXT_MUTED)
        self.scale_btn_failure.configure(state="normal")
        self.scale_btn_normal.configure(state="normal")
        self.scale_btn_new.configure(state="normal")
        self.scale_hint_label.configure(text=f"共 {res.get('count', 0)} 条待确认，显示最新一条")

        self._refresh_scale_history()

    def _refresh_scale_history(self):
        base_url = self.cfg.get("server_url", "").replace('/api/ingest/script-report', '')
        api_key = self.cfg.get("api_key", "")
        if not base_url or not api_key:
            return
        for widget in self.scale_history_frame.winfo_children():
            widget.destroy()
        res = api_request(f"{base_url}/api/scale/pending", api_key=api_key, method="GET")
        if not res or len(res) == 0:
            ctk.CTkLabel(self.scale_history_frame, text="暂无待确认记录", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(pady=10)
            return
        for p in res:
            row = ctk.CTkFrame(self.scale_history_frame, fg_color="#121216", corner_radius=6)
            row.pack(fill="x", padx=4, pady=2)
            info_frame = ctk.CTkFrame(row, fg_color="transparent")
            info_frame.pack(side="left", fill="x", expand=True, padx=8, pady=4)
            uid = p.get("nfc_uid", "--")
            measured = p.get("measured_weight_g", 0)
            expected = p.get("expected_weight_g")
            diff = p.get("difference_g")
            diff_color = COLOR_BADGE_RED if (diff is not None and diff < 0) else COLOR_BAMBU_GREEN
            diff_str = f"+{diff:.1f}" if (diff is not None and diff > 0) else (f"{diff:.1f}" if diff is not None else "--")
            ctk.CTkLabel(info_frame, text=f"NFC: {uid[:14]}...  实测: {measured:.1f}g  预期: {expected:.1f}g" if expected is not None else f"NFC: {uid[:14]}...  实测: {measured:.1f}g  预期: --", font=self.get_font(10), text_color=COLOR_TEXT_PRIMARY, anchor="w").pack(fill="x")
            ctk.CTkLabel(info_frame, text=f"误差: {diff_str}g  {p.get('created_at', '')[:16]}", font=self.get_font(9), text_color=diff_color, anchor="w").pack(fill="x")
            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.pack(side="right", padx=4, pady=4)
            pid = p.get("id") or p.get("pending_id")
            ctk.CTkButton(btn_frame, text="确认", width=50, height=24, font=self.get_font(10, "bold"), fg_color=COLOR_BAMBU_GREEN, hover_color=("#0B8A5F", "#4ADE80"), command=lambda pid=pid: self._scale_history_confirm(pid)).pack(side="left", padx=2)
            ctk.CTkButton(btn_frame, text="忽略", width=50, height=24, font=self.get_font(10, "bold"), fg_color=COLOR_CARD_BG, hover_color="#2A2A30", command=lambda pid=pid: self._scale_history_reject(pid)).pack(side="left", padx=2)

    def _scale_history_confirm(self, pending_id):
        base_url = self.cfg.get("server_url", "").replace('/api/ingest/script-report', '')
        api_key = self.cfg.get("api_key", "")
        res = api_request(f"{base_url}/api/scale/pending/{pending_id}/confirm", api_key=api_key, method="POST", data={"action_type": "normal_sync"})
        if res and res.get("status") == "success":
            messagebox.showinfo("成功", "已确认，重量已同步")
            self.refresh_scale_workbench()
        else:
            messagebox.showerror("失败", "确认失败")

    def _scale_history_reject(self, pending_id):
        if not messagebox.askyesno("确认", "确定忽略这条待确认记录吗？"):
            return
        base_url = self.cfg.get("server_url", "").replace('/api/ingest/script-report', '')
        api_key = self.cfg.get("api_key", "")
        api_request(f"{base_url}/api/scale/pending/{pending_id}/reject", api_key=api_key, method="POST")
        self.refresh_scale_workbench()

    def scale_confirm_action(self, action_type):
        if not self._scale_current_pending:
            return
        pending_id = self._scale_current_pending.get("pending_id")
        actual = self._scale_current_pending.get("measured_weight_g", 0)
        diff = self._scale_current_pending.get("difference_g", 0)
        if action_type == "failure_correction":
            lost = abs(diff) if diff < 0 else 0
            msg = f"将把丢失的 {lost:.1f} 克计入打印报废损耗，并覆盖重量为 {actual:.1f}g，是否继续？"
            if not messagebox.askyesno("确认打印失败纠正", msg):
                return
        elif action_type == "normal_sync":
            if not messagebox.askyesno("确认常规同步", f"将直接覆盖重量为 {actual:.1f}g，记为日常累积误差校准，是否继续？"):
                return
        base_url = self.cfg.get("server_url", "").replace('/api/ingest/script-report', '')
        api_key = self.cfg.get("api_key", "")
        confirm_url = f"{base_url}/api/scale/pending/{pending_id}/confirm"
        res = api_request(confirm_url, api_key=api_key, method="POST", data={"action_type": action_type})
        if res and res.get("status") == "success":
            messagebox.showinfo("成功", "重量已同步，对账流水已记录")
            self.refresh_scale_workbench()
        else:
            messagebox.showerror("失败", "确认失败，请检查网络连接")

    def scale_new_spool(self):
        if not self._scale_current_pending:
            return
        self.open_scale_bind_modal()

    def open_scale_bind_modal(self):
        if not self._scale_current_pending:
            return
        uid = self._scale_current_pending.get("nfc_uid", "")
        win = ctk.CTkToplevel(self)
        win.title("🔗 绑定耗材到 NFC")
        win.geometry("520x680")
        win.transient(self)
        win.grab_set()
        win.attributes("-topmost", True)

        ctk.CTkLabel(win, text="🔗 绑定耗材到 NFC", font=self.get_font(18, "bold")).pack(pady=(16, 8))
        self.register_widget_font(win.winfo_children()[-1], 18, "bold")

        form = ctk.CTkFrame(win, fg_color="transparent")
        form.pack(fill="x", padx=20, pady=8)
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="NFC UID:", font=self.get_font(12, "bold")).grid(row=0, column=0, sticky="w", pady=4)
        ctk.CTkLabel(form, text=uid, font=self.get_font(12), text_color=COLOR_TEXT_MUTED).grid(row=0, column=1, sticky="w", pady=4)

        ctk.CTkLabel(form, text="绑定方式:", font=self.get_font(12, "bold")).grid(row=1, column=0, sticky="w", pady=4)
        bind_mode_var = ctk.StringVar(value="existing")
        bind_mode_menu = ctk.CTkOptionMenu(form, values=["选择已有耗材", "新增耗材"], variable=bind_mode_var, width=200, font=self.get_font(12))
        bind_mode_menu.grid(row=1, column=1, sticky="w", pady=4)

        existing_frame = ctk.CTkFrame(win, fg_color="transparent")
        existing_frame.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(existing_frame, text="选择耗材:", font=self.get_font(12, "bold")).pack(anchor="w")
        base_url = self.cfg.get("server_url", "").replace('/api/ingest/script-report', '')
        api_key = self.cfg.get("api_key", "")
        filaments = []
        try:
            res = api_request(f"{base_url}/api/ingest/script-filaments", api_key=api_key, method="GET")
            if res: filaments = res
        except Exception: pass
        filament_options = [f"{f['brand']} {f['material']} [{f['color_name']}] - 剩余{f['current_weight_g']}g" for f in filaments]
        filament_var = ctk.StringVar(value=filament_options[0] if filament_options else "暂无耗材")
        filament_menu = ctk.CTkOptionMenu(existing_frame, values=filament_options if filament_options else ["暂无耗材"], variable=filament_var, width=440, font=self.get_font(12))
        filament_menu.pack(fill="x", pady=4)

        new_frame = ctk.CTkFrame(win, fg_color="transparent")
        new_frame.pack(fill="x", padx=20, pady=4)
        new_frame.pack_forget()
        row_frame1 = ctk.CTkFrame(new_frame, fg_color="transparent")
        row_frame1.pack(fill="x", pady=2)
        ctk.CTkLabel(row_frame1, text="品牌:", font=self.get_font(11)).pack(side="left", padx=(0, 4))
        brand_entry = ctk.CTkEntry(row_frame1, width=120, font=self.get_font(11)); brand_entry.insert(0, "Bambu Lab"); brand_entry.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(row_frame1, text="材质:", font=self.get_font(11)).pack(side="left", padx=(0, 4))
        material_entry = ctk.CTkEntry(row_frame1, width=100, font=self.get_font(11)); material_entry.insert(0, "PLA"); material_entry.pack(side="left")
        row_frame2 = ctk.CTkFrame(new_frame, fg_color="transparent")
        row_frame2.pack(fill="x", pady=2)
        ctk.CTkLabel(row_frame2, text="颜色名:", font=self.get_font(11)).pack(side="left", padx=(0, 4))
        color_name_entry = ctk.CTkEntry(row_frame2, width=120, font=self.get_font(11)); color_name_entry.insert(0, "自定义"); color_name_entry.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(row_frame2, text="初始料重(g):", font=self.get_font(11)).pack(side="left", padx=(0, 4))
        initial_entry = ctk.CTkEntry(row_frame2, width=80, font=self.get_font(11)); initial_entry.insert(0, "1000"); initial_entry.pack(side="left")

        mode_frame = ctk.CTkFrame(win, fg_color="transparent")
        mode_frame.pack(fill="x", padx=20, pady=(8, 4))
        ctk.CTkLabel(mode_frame, text="称重模式:", font=self.get_font(12, "bold")).pack(anchor="w")
        scale_mode_var = ctk.StringVar(value="spool")
        scale_mode_menu = ctk.CTkOptionMenu(mode_frame, values=["已知空盘重量（直接输入皮重）", "未知空盘重量（称总重+料重自动算）"], variable=scale_mode_var, width=300, font=self.get_font(12))
        scale_mode_menu.pack(fill="x", pady=4)

        spool_frame = ctk.CTkFrame(win, fg_color="transparent")
        spool_frame.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(spool_frame, text="空盘皮重 (g):", font=self.get_font(12)).pack(anchor="w")
        spool_entry = ctk.CTkEntry(spool_frame, width=200, font=self.get_font(12)); spool_entry.insert(0, "250"); spool_entry.pack(fill="x", pady=4)

        calibrate_frame = ctk.CTkFrame(win, fg_color="transparent")
        calibrate_frame.pack(fill="x", padx=20, pady=4)
        calibrate_frame.pack_forget()
        ctk.CTkLabel(calibrate_frame, text="当前总重 (g，盘+料):", font=self.get_font(12)).pack(anchor="w")
        total_entry = ctk.CTkEntry(calibrate_frame, width=200, font=self.get_font(12)); total_entry.pack(fill="x", pady=4)
        ctk.CTkLabel(calibrate_frame, text="当前料重 (g):", font=self.get_font(12)).pack(anchor="w")
        material_entry = ctk.CTkEntry(calibrate_frame, width=200, font=self.get_font(12)); material_entry.insert(0, "1000"); material_entry.pack(fill="x", pady=4)

        def toggle_bind_mode(*args):
            if bind_mode_var.get() == "选择已有耗材": existing_frame.pack(fill="x", padx=20, pady=4); new_frame.pack_forget()
            else: existing_frame.pack_forget(); new_frame.pack(fill="x", padx=20, pady=4)
        bind_mode_var.trace_add("write", toggle_bind_mode)

        def toggle_scale_mode(*args):
            if "皮重" in scale_mode_var.get(): spool_frame.pack(fill="x", padx=20, pady=4); calibrate_frame.pack_forget()
            else: spool_frame.pack_forget(); calibrate_frame.pack(fill="x", padx=20, pady=4)
        scale_mode_var.trace_add("write", toggle_scale_mode)

        def submit():
            payload = {"nfc_uid": uid, "mode": "spool" if "皮重" in scale_mode_var.get() else "calibrate"}
            if bind_mode_var.get() == "选择已有耗材":
                idx = filament_options.index(filament_var.get()) if filament_var.get() in filament_options else 0
                payload["filament_id"] = filaments[idx]["id"]
            else:
                payload["brand"] = brand_entry.get() or "Bambu Lab"
                payload["material"] = material_entry.get() or "PLA"
                payload["color_name"] = color_name_entry.get() or "自定义"
                payload["color_hex"] = "#888888"
                try: payload["initial_weight_g"] = float(initial_entry.get()) or 1000
                except ValueError: payload["initial_weight_g"] = 1000
            if payload["mode"] == "spool":
                try: payload["spool_weight_g"] = float(spool_entry.get()) or 250
                except ValueError: payload["spool_weight_g"] = 250
            else:
                try: total = float(total_entry.get()); current_mat = float(material_entry.get())
                except ValueError: messagebox.showerror("错误", "请输入有效的数字"); return
                spool_weight = round(total - current_mat, 2)
                if spool_weight < 0: messagebox.showerror("错误", "皮重不能为负"); return
                payload["spool_weight_g"] = spool_weight
                if "filament_id" not in payload: payload["initial_weight_g"] = current_mat
            res = api_request(f"{base_url}/api/scale/bind", api_key=api_key, method="POST", data=payload)
            if res and res.get("status") == "success":
                messagebox.showinfo("成功", "绑定成功！")
                win.destroy(); self.refresh_scale_workbench(); self.refresh_dashboard()
            else: messagebox.showerror("失败", "绑定失败")

        btn_frame = ctk.CTkFrame(win, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(12, 16))
        ctk.CTkButton(btn_frame, text="确认绑定", font=self.get_font(13, "bold"), height=40, corner_radius=10, fg_color=COLOR_BAMBU_GREEN, hover_color=("#0B8A5F", "#4ADE80"), command=submit).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(btn_frame, text="取消", font=self.get_font(13, "bold"), height=40, corner_radius=10, fg_color=COLOR_CARD_BG, hover_color="#2A2A30", command=win.destroy).pack(side="left", expand=True, fill="x", padx=(4, 0))

    def open_manual_weigh_modal(self):
        base_url = self.cfg.get("server_url", "").replace('/api/ingest/script-report', '')
        api_key = self.cfg.get("api_key", "")
        if not base_url or not api_key:
            messagebox.showwarning("提示", "请先配置服务器与 API Key")
            return
        filaments = api_request(f"{base_url}/api/ingest/script-filaments", api_key=api_key, method="GET") or []
        if not filaments:
            messagebox.showwarning("提示", "暂无耗材")
            return

        win = ctk.CTkToplevel(self)
        win.title("✋ 手动称重")
        win.geometry("480x420")
        win.transient(self); win.grab_set(); win.attributes("-topmost", True)

        ctk.CTkLabel(win, text="✋ 手动称重 (无NFC)", font=self.get_font(18, "bold")).pack(pady=(16, 12))
        form = ctk.CTkFrame(win, fg_color="transparent")
        form.pack(fill="x", padx=20, pady=4)
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="选择耗材:", font=self.get_font(12, "bold")).grid(row=0, column=0, sticky="w", pady=6)
        opts = [f"{f['brand']} {f['material']} [{f['color_name']}] - 剩余{f['current_weight_g']}g" for f in filaments]
        f_var = ctk.StringVar(value=opts[0])
        ctk.CTkOptionMenu(form, values=opts, variable=f_var, width=300).grid(row=0, column=1, sticky="ew", pady=6)

        ctk.CTkLabel(form, text="当前毛重(g):", font=self.get_font(12, "bold")).grid(row=1, column=0, sticky="w", pady=6)
        w_entry = ctk.CTkEntry(form, width=150, font=self.get_font(14, "bold"))
        w_entry.grid(row=1, column=1, sticky="w", pady=6)

        def submit():
            f = filaments[opts.index(f_var.get())]
            try: gross = float(w_entry.get())
            except ValueError: messagebox.showerror("错误", "请输入数字"); return
            net = round(gross - f.get("spool_weight_g", 250), 2)
            if not messagebox.askyesno("确认", f"计算净重: {net}g，确认更新？"): return
            res = api_request(f"{base_url}/api/scale/correct", api_key=api_key, method="POST", data={
                "uid": f.get("nfc_uid", f"MANUAL_{f['id']}"), "action_type": "normal_sync", "confirmed_weight": net
            })
            if res and res.get("status") == "success":
                messagebox.showinfo("成功", f"重量已更新为 {net}g")
                win.destroy(); self.refresh_scale_workbench(); self.refresh_dashboard()

        ctk.CTkButton(win, text="确认更新", fg_color=COLOR_BAMBU_GREEN, command=submit).pack(fill="x", padx=20, pady=20)

    def send_device_command(self, command, params=None):
        base_url = self.cfg.get("server_url", "").replace('/api/ingest/script-report', '')
        api_key = self.cfg.get("api_key", "")
        if not base_url or not api_key: return
        if command == "reboot" and not messagebox.askyesno("确认", "确认远程重启设备？"): return
        if command == "reset_config" and not messagebox.askyesno("确认", "确认清除 WiFi 密码？"): return
        res = api_request(f"{base_url}/api/scale/device/command", api_key=api_key, method="POST", data={"device_id": "scale_001", "command": command, "params": params or {}})
        if res: self.device_status_label.configure(text=f"状态: 指令已下发({command})", text_color=COLOR_BAMBU_GREEN)

    @staticmethod
    def normalize_mac(raw):
        """MAC 容错：横杠/全角冒号/点/空格 一律转半角冒号"""
        import re
        if not raw: return ""
        return re.sub(r"[\-\uFF0D\u2014\u2013\uFF0E.\s\uFF1A:]+", ":", raw.strip().upper()).strip(":")

    def send_wake_pc(self):
        # ===== 远程开机（WOL 魔术包）=====
        import re
        base_url = self.cfg.get("server_url", "").replace('/api/ingest/script-report', '')
        api_key = self.cfg.get("api_key", "")
        if not base_url or not api_key:
            messagebox.showwarning("提示", "请先配置服务器与 API Key"); return
        mac = self.normalize_mac(self.cfg.get("wol_mac", ""))
        if not mac:
            dlg = ctk.CTkInputDialog(text="首次使用，请输入目标电脑网卡 MAC\n\n支持任意格式，自动识别：\n  00-E2-69-9A-8C-2A\n  00:E2:69:9A:8C:2A\n  00：E2：69：9A：8C：2A\n\n(电脑上运行 ipconfig /all 看物理地址)", title="配置 WOL 目标")
            mac = self.normalize_mac(dlg.get_input())
            if not mac:
                messagebox.showwarning("提示", "已取消，未保存 MAC"); return
            if not re.match(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$", mac):
                messagebox.showerror("错误", "MAC 格式不对！\n应为 6 组两位十六进制，如 00-E2-69-9A-8C-2A\n请重新点击[🖥️开机]配置"); return
            self.cfg["wol_mac"] = mac
            messagebox.showinfo("已保存", f"MAC 已保存: {mac}\n下次可直接一键开机")
        else:
            if not messagebox.askyesno("远程开机", "目标 MAC: " + mac + "\n\n确认发送 WOL 魔术包？\n\n(点[否]可修改 MAC)"):
                dlg = ctk.CTkInputDialog(text="修改目标 MAC（重新输入完整 MAC，支持横杠/冒号）:", title="修改 WOL MAC")
                new_mac = self.normalize_mac(dlg.get_input())
                if not new_mac: return
                if not re.match(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$", new_mac):
                    messagebox.showerror("错误", "MAC 格式不对！\n应为 6 组两位十六进制，如 00-E2-69-9A-8C-2A"); return
                self.cfg["wol_mac"] = new_mac
                mac = new_mac
        try: save_config(self.cfg)
        except Exception as e: write_log(f"保存 wol_mac 失败: {e}")
        res = api_request(f"{base_url}/api/scale/device/command", api_key=api_key, method="POST",
                          data={"device_id": "scale_001", "command": "wake_pc", "params": {"mac": mac}})
        if res:
            messagebox.showinfo("已下发", f"✅ WOL 魔术包已下发\n目标: {mac}\n\n约 5~10 秒后电脑应开机")
            self.device_status_label.configure(text="状态: 开机指令已下发", text_color=COLOR_BAMBU_GREEN)
        else:
            messagebox.showerror("失败", "指令下发失败！请检查服务器连接与 API Key")

    def toggle_dev_mode(self):
        """电子秤开发者模式开关：开启后禁止自动休眠"""
        base_url = self.cfg.get("server_url", "").replace('/api/ingest/script-report', '')
        api_key = self.cfg.get("api_key", "")
        if not base_url or not api_key:
            messagebox.showwarning("提示", "请先在服务设置中配置服务器地址和 API Key")
            return
        # 当前状态从按钮文本判断（刷新时会同步）
        is_on = getattr(self, "_dev_mode_on", False)
        if not is_on:
            if not messagebox.askyesno("🧪 开发者模式", "⚠️ 开启开发者模式后，电子秤将不会自动休眠！\n\n长时间运行建议插电使用，否则电池会很快耗尽。\n\n确认开启？"):
                return
            target = 1
        else:
            if not messagebox.askyesno("🧪 开发者模式", "确认关闭开发者模式？\n\n关闭后电子秤将恢复 80 秒无操作自动休眠。"):
                return
            target = 0
        res = api_request(f"{base_url}/api/scale/device/command", api_key=api_key, method="POST",
                          data={"device_id": "scale_001", "command": "set_dev_mode", "params": {"enabled": target}})
        if res:
            self._dev_mode_on = bool(target)
            self.dev_mode_btn.configure(text="开发者模式: 开" if target else "开发者模式: 关",
                                        fg_color=COLOR_BAMBU_GREEN if target else "#8B5CF6",
                                        hover_color=("#0B8A5F", "#4ADE80") if target else "#7C3AED")
            self.device_status_label.configure(text=f"状态: 开发者模式{'开启' if target else '关闭'}指令已下发", text_color=COLOR_BAMBU_GREEN)
            messagebox.showinfo("已下发", "✅ 开发者模式已下发\n\n开启后电子秤不会休眠，请保持供电。\n设备将在下次轮询时生效（约 5 秒）。" if target else "✅ 已下发关闭开发者模式指令\n\n恢复 80 秒无操作自动休眠。")
        else:
            messagebox.showerror("失败", "指令下发失败！请检查服务器连接与 API Key")

    def refresh_device_status(self):
        base_url = self.cfg.get("server_url", "").replace('/api/ingest/script-report', '')
        api_key = self.cfg.get("api_key", "")
        if not base_url or not api_key: return
        res = api_request(f"{base_url}/api/scale/device/status?device_id=scale_001", api_key=api_key, method="GET")
        if not res or not res.get("online"):
            self.device_status_label.configure(text="状态: 设备离线", text_color=COLOR_TEXT_MUTED)
            return
        self.device_status_label.configure(text=f"在线 | {res.get('current_weight', 0):.1f}g | WiFi{res.get('wifi_bars', 0)}格", text_color=COLOR_BAMBU_GREEN)
        # 同步开发者模式状态显示
        if hasattr(self, "dev_mode_btn"):
            dev_on = bool(res.get("dev_mode", False))
            self._dev_mode_on = dev_on
            self.dev_mode_btn.configure(text="开发者模式: 开" if dev_on else "开发者模式: 关",
                                        fg_color=COLOR_BAMBU_GREEN if dev_on else "#8B5CF6",
                                        hover_color=("#0B8A5F", "#4ADE80") if dev_on else "#7C3AED")

    # --------------------------------------------------------------------------
    # 子功能: 智能称重工作台 (Scale Workbench) [END]
    # --------------------------------------------------------------------------
# ==============================================================================
# 模块 8: 客户端主界面逻辑与核心组件 [END]
# ==============================================================================


# ==============================================================================
# 模块 9: 多色切片扣减弹窗与 AMS 自动续打拆分引擎 [START]
# ==============================================================================
def ask_backup_spool(parent, name, rem_w, total, deficit, options, id_map, filament_data_map):
    result = {"backup_id": None}
    win = ctk.CTkToplevel(parent)
    win.title("AMS 自动续料设置")
    win.geometry("500x340")
    win.attributes("-topmost", True)
    win.transient(parent); win.grab_set()
    
    ctk.CTkLabel(win, text="🔄 发现耗材存量不足", font=ctk.CTkFont(family="MiSans", size=16, weight="bold"), text_color="#EF4444").pack(pady=(20,10))
    msg = f"耗材 [{name}] 需要 {total}g，但仅剩 {rem_w}g。\n缺少 {deficit:.1f}g，是否启用了 AMS 自动续接？"
    ctk.CTkLabel(win, text=msg, font=ctk.CTkFont(family="MiSans", size=13)).pack(pady=(0, 15))
    
    ctk.CTkLabel(win, text="请选择续接的备用耗材盘：", font=ctk.CTkFont(family="MiSans", size=12, weight="bold")).pack()
    cb_var = ctk.StringVar()
    cb = ctk.CTkComboBox(win, variable=cb_var, values=options, width=350, height=36, font=ctk.CTkFont(family="MiSans", size=12))
    cb.pack(pady=10)
    
    def on_ok():
        selected = cb.get()
        bid = id_map.get(selected, 1)
        backup_rem = filament_data_map[bid]["rem_w"]
        
        if backup_rem < deficit:
            if not messagebox.askyesno("警告", f"选中的续接耗材剩余量 ({backup_rem}g) 也不足补齐缺口 ({deficit}g)！\n强行扣减将导致其库存变负，是否继续？", parent=win):
                return
        result["backup_id"] = bid
        win.destroy()
        
    def on_cancel(): win.destroy()
        
    btn_box = ctk.CTkFrame(win, fg_color="transparent")
    btn_box.pack(pady=20)
    ctk.CTkButton(btn_box, text="确认续打拆分", fg_color="#00AE42", command=on_ok).pack(side="left", padx=10)
    ctk.CTkButton(btn_box, text="取消", fg_color=COLOR_SURFACE_2, hover_color=COLOR_HOVER, text_color=COLOR_TEXT_PRIMARY, command=on_cancel).pack(side="left", padx=10)
    
    win.wait_window()
    return result["backup_id"]

def ask_user_multi_slot_mapping_modern(
    slot_weights, web_filaments, detected_model_name="Bambu_Model", 
    parent_window=None, font_family="MiSans", last_weight=0.0,
    printers=None, default_printer_id=None
):
    user_choice = {"confirmed": False, "task_name": "", "slot_map": {}, "target_printer_id": None}
    slot_cache = load_slot_cache()

    dialog = ctk.CTkToplevel(parent_window) if parent_window else ctk.CTk()
    dialog.title("Bambu Lab 多色切片扣减助手")
    dialog.attributes('-topmost', True)

    w_width, w_height = 660, 420 + (len(slot_weights) * 58)
    if parent_window:
        x = parent_window.winfo_x() + (parent_window.winfo_width() - w_width) // 2
        y = parent_window.winfo_y() + (parent_window.winfo_height() - w_height) // 2
    else:
        x = (dialog.winfo_screenwidth() - w_width) // 2
        y = (dialog.winfo_screenheight() - w_height) // 2

    dialog.geometry(f"{w_width}x{w_height}+{x}+{y}")
    dialog.resizable(False, False)

    container = ctk.CTkFrame(dialog, corner_radius=22, fg_color=COLOR_BG_MAIN)
    container.pack(fill="both", expand=True, padx=20, pady=20)

    total_w = sum(slot_weights)
    compare_str = f"（上盘: {last_weight:.2f}g | 差异: {'+' if (total_w - last_weight)>0 else ''}{total_w - last_weight:.2f}g）" if last_weight > 0 else ""

    lbl_info = ctk.CTkLabel(
        container, 
        text=f"🌈 检测到切片任务: 共 {len(slot_weights)} 色, 总重: {total_w:.2f}g {compare_str}\n请确认目标打印机及槽位耗材分配：",
        font=ctk.CTkFont(family=font_family, size=13, weight="bold"), text_color=COLOR_TEXT_PRIMARY, justify="left"
    )
    lbl_info.pack(anchor="w", padx=20, pady=(14, 8))

    top_row = ctk.CTkFrame(container, fg_color="transparent")
    top_row.pack(fill="x", padx=20, pady=4)

    ctk.CTkLabel(top_row, text="目标机位:", font=ctk.CTkFont(family=font_family, size=12, weight="bold")).pack(side="left", padx=(0, 6))
    printer_opts = ["默认机位 (未绑定)"]
    p_id_map = {"默认机位 (未绑定)": None}
    p_objs = {}

    if printers:
        for p in printers:
            label = f"{p['name']} ({p.get('model', 'Bambu')})"
            printer_opts.append(label)
            p_id_map[label] = p['id']
            p_objs[p['id']] = p

    cb_printer = ctk.CTkComboBox(top_row, values=printer_opts, height=36, corner_radius=10, width=190, font=ctk.CTkFont(family=font_family, size=12))
    cb_printer.pack(side="left", padx=(0, 14))

    time_suffix = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    default_full_name = f"{detected_model_name}_{time_suffix}"
    ctk.CTkLabel(top_row, text="任务名称:", font=ctk.CTkFont(family=font_family, size=12, weight="bold")).pack(side="left", padx=(0, 6))
    entry_name = ctk.CTkEntry(top_row, height=36, corner_radius=10, font=ctk.CTkFont(family=font_family, size=12))
    entry_name.pack(side="left", fill="x", expand=True)
    entry_name.insert(0, default_full_name)

    filament_options = []
    filament_id_map = {}
    filament_data_map = {}
    
    for f in web_filaments:
        f_id = f['id']
        name_str = f"{f.get('brand','')} {f.get('material','')} [{f.get('color_name','')}]"
        rem_w = f.get('current_weight_g', 0)
        opt_str = f"ID:{f_id} - {name_str} (剩:{rem_w}g)"
        filament_options.append(opt_str)
        filament_id_map[opt_str] = f_id
        filament_data_map[f_id] = {"name": name_str, "rem_w": rem_w}

    if not filament_options:
        filament_options = ["ID:1 - 默认耗材档案"]
        filament_id_map["ID:1 - 默认耗材档案"] = 1
        filament_data_map[1] = {"name": "默认耗材档案", "rem_w": 9999}

    combobox_vars = []
    cb_widgets = []
    for idx, w in enumerate(slot_weights):
        slot_idx = idx + 1
        s_card = ctk.CTkFrame(container, corner_radius=16, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        s_card.pack(fill="x", padx=20, pady=4)

        ctk.CTkLabel(s_card, text=f"🎨 槽位 {slot_idx} ({w}g) ➔", font=ctk.CTkFont(family=font_family, size=13, weight="bold")).pack(side="left", padx=16)

        cb_var = ctk.StringVar()
        cb = ctk.CTkComboBox(s_card, variable=cb_var, values=filament_options, corner_radius=10, width=360, height=36, font=ctk.CTkFont(family=font_family, size=12))
        cb.pack(side="right", padx=12, pady=8)

        cached_id = slot_cache.get(str(slot_idx))
        matched_opt = None
        if cached_id:
            for opt in filament_options:
                if opt.startswith(f"ID:{cached_id} "):
                    matched_opt = opt
                    break

        cb.set(matched_opt if matched_opt else filament_options[idx if idx < len(filament_options) else 0])
        combobox_vars.append((slot_idx, w, cb_var))
        cb_widgets.append(cb)

    def on_printer_change(choice):
        pid = p_id_map.get(choice)
        if pid and pid in p_objs:
            ams_slots = p_objs[pid].get("ams_slots") or {}
            for idx_c, cb_w in enumerate(cb_widgets):
                mounted_fid = ams_slots.get(str(idx_c + 1))
                if mounted_fid:
                    for opt in filament_options:
                        if opt.startswith(f"ID:{mounted_fid} "):
                            cb_w.set(opt); break

    cb_printer.configure(command=on_printer_change)

    def on_confirm():
        usage_by_id = {}
        for slot_idx, w, cb_var in combobox_vars:
            selected_f_id = filament_id_map.get(cb_var.get(), 1)
            usage_by_id[selected_f_id] = usage_by_id.get(selected_f_id, 0.0) + float(w)
            
        replacements = {}
        for f_id, total_used in usage_by_id.items():
            f_info = filament_data_map.get(f_id)
            if not f_info: continue
            if total_used > f_info["rem_w"]:
                backup_id = ask_backup_spool(dialog, f_info['name'], f_info["rem_w"], total_used, total_used - f_info["rem_w"], filament_options, filament_id_map, filament_data_map)
                if backup_id is None: return
                replacements[f_id] = {"backup_id": backup_id}

        user_choice["confirmed"] = True
        user_choice["task_name"] = entry_name.get().strip() or default_full_name
        user_choice["target_printer_id"] = p_id_map.get(cb_printer.get())
        user_choice["slot_map"] = {}
        
        new_cache = {}
        f_id_remaining = {fid: filament_data_map[fid]["rem_w"] for fid in usage_by_id}
        
        for slot_idx, w, cb_var in combobox_vars:
            f_id = filament_id_map.get(cb_var.get(), 1)
            needed = float(w)
            user_choice["slot_map"][slot_idx] = []
            if f_id in replacements:
                take = min(needed, f_id_remaining[f_id])
                if take > 0:
                    user_choice["slot_map"][slot_idx].append({"filament_id": f_id, "used_weight_g": round(take, 2)})
                    f_id_remaining[f_id] -= take; needed -= take
                if needed > 0:
                    user_choice["slot_map"][slot_idx].append({"filament_id": replacements[f_id]["backup_id"], "used_weight_g": round(needed, 2)})
            else:
                user_choice["slot_map"][slot_idx].append({"filament_id": f_id, "used_weight_g": round(needed, 2)})
                f_id_remaining[f_id] -= needed
            new_cache[str(slot_idx)] = f_id
            
        save_slot_cache(new_cache)
        dialog.destroy()

    btn_frame = ctk.CTkFrame(container, fg_color="transparent")
    btn_frame.pack(fill="x", side="bottom", padx=20, pady=12)
    ctk.CTkButton(btn_frame, text="确认扣减", height=40, corner_radius=20, fg_color=COLOR_BAMBU_GREEN, command=on_confirm).pack(side="right", padx=6)
    ctk.CTkButton(btn_frame, text="取消", height=40, corner_radius=20, fg_color=COLOR_CARD_BG, command=dialog.destroy).pack(side="right", padx=6)

    if parent_window: dialog.wait_window()
    else: dialog.mainloop()
    return user_choice["confirmed"], user_choice["task_name"], user_choice["slot_map"], user_choice["target_printer_id"]

def load_slot_cache():
    if os.path.exists(MAPPING_CACHE_FILE):
        try:
            with open(MAPPING_CACHE_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except Exception: pass
    return {}

def save_slot_cache(mapping):
    try:
        with open(MAPPING_CACHE_FILE, 'w', encoding='utf-8') as f: json.dump(mapping, f, ensure_ascii=False, indent=2)
    except Exception: pass
# ==============================================================================
# 模块 9: 多色切片扣减弹窗与 AMS 自动续打拆分引擎 [END]
# ==============================================================================


# ==============================================================================
# 模块 10: G-code 解析与克重提取算法 [START]
# ==============================================================================
def extract_model_name_from_file(file_path):
    base_name = os.path.basename(file_path).lstrip('.')
    for ext in ['.gcode.3mf', '.gcode', '.3mf']:
        if base_name.lower().endswith(ext): base_name = base_name[:-len(ext)]; break
    return re.sub(r'_[A-Z0-9]+_\d+h\d+m.*', '', base_name, flags=re.IGNORECASE).strip() or "Bambu_Model"

def parse_multi_filament_weights(text):
    weights = []
    m = re.search(r';\s*(?:total\s+)?filament\s*(?:weight|used)\s*\[g\]\s*[:=]\s*([^\r\n]+)', text, re.IGNORECASE)
    if m: weights = [float(v) for v in re.findall(r'[\d\.]+', m.group(1).strip()) if float(v) > 0]
    if not weights:
        m_cfg = re.search(r'"filament_weight"\s*:\s*\[([^\]]+)\]', text, re.IGNORECASE)
        if m_cfg: weights = [float(v) for v in re.findall(r'[\d\.]+', m_cfg.group(1)) if float(v) > 0]
    return weights

def get_bambu_project_info_strict(gcode_path):
    if os.path.exists(gcode_path) and os.path.isfile(gcode_path):
        try:
            with open(gcode_path, 'r', encoding='utf-8', errors='ignore') as f:
                w = parse_multi_filament_weights(f.read(131072))
                if w: return w
        except Exception: pass
    return []
# ==============================================================================
# 模块 10: G-code 解析与克重提取算法 [END]
# ==============================================================================


# ==============================================================================
# 模块 11: 主程序入口 (GUI / 命令行后处理双分支) [START]
# ==============================================================================
if __name__ == "__main__":
    cli_files = [a for a in sys.argv[1:] if not str(a).startswith("--")]
    if not cli_files:
        app = HyperOSFilamentApp()
        app.mainloop()
    else:
        cfg = load_config()
        gcode_path = cli_files[-1]
        slot_weights = get_bambu_project_info_strict(gcode_path)
        detected_model_name = extract_model_name_from_file(gcode_path)
        if slot_weights and sum(slot_weights) > 0:
            base_url = cfg['server_url'].replace('/api/ingest/script-report', '')
            web_filaments = api_request(cfg["filaments_url"], cfg["api_key"], method="GET") or []
            printers = api_request(f"{base_url}/api/ingest/script-printers", cfg["api_key"], method="GET") or []
            is_confirmed, task_name, slot_map, target_printer_id = ask_user_multi_slot_mapping_modern(
                slot_weights, web_filaments, detected_model_name=detected_model_name, 
                font_family=map_font_family(cfg.get("selected_font", "Microsoft YaHei UI (微软高清)")), printers=printers, default_printer_id=cfg.get("selected_printer_id")
            )
            if is_confirmed:
                time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M")
                for slot_idx, deductions in slot_map.items():
                    for info in deductions:
                        if info["used_weight_g"] <= 0: continue
                        api_request(cfg["server_url"], cfg["api_key"], method="POST", data={
                            "filament_id": info["filament_id"], "used_weight_g": info["used_weight_g"],
                            "task_name": f"{task_name}_槽{slot_idx}_{time_str}.gcode", "printer_id": target_printer_id
                        })
# ==============================================================================
# 模块 11: 主程序入口 (GUI / 命令行后处理双分支) [END]
# ==============================================================================
