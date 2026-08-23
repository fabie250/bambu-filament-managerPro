import sys
import re
import json
import os
import time
import datetime
import urllib.request
import urllib.error
import webbrowser
import ctypes
from ctypes import wintypes
import threading
import subprocess
import tkinter as tk
from tkinter import messagebox, filedialog
from PIL import Image
import customtkinter as ctk

# ==============================================================================
# 模块 0: 全局版本常量、加速接口与网盘备用配置 [START]
# ==============================================================================
CURRENT_VERSION = "v1.2.0"
IS_PRE_RELEASE = False
GITHUB_REPO = "fabie250/-bambu-filament-manager"
UPDATE_API_URL = "http://mpdfyy.cn/api/latest-version"

BACKUP_PAN_URL = "https://1823958828.share.123pan.cn/123pan/bTEGjv-hWTS3?pwd=p3lJ"

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
    return os.path.join(os.path.abspath("."), relative_path)

BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
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
def enable_windows_rendering_optimizations(root=None):
    if os.name != "nt":
        return
    try:
        dwmapi = ctypes.windll.dwmapi
        if root is not None:
            hwnd = root.winfo_id()
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

def register_font_to_windows_pool(font_path):
    if os.path.exists(font_path):
        try:
            FR_PRIVATE = 0x10
            res = ctypes.windll.gdi32.AddFontResourceExW(font_path, FR_PRIVATE, 0)
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
    "selected_font": "MiSans (小米澎湃)",
    "auto_watcher_enabled": True,
    "developer_mode": False,
    "debug_log_enabled": False,
    "window_width": 1160,
    "window_height": 820,
    "last_slice_weight": 0.0,
    "update_channel": "Release (正式版)",
    "skipped_version": ""
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

def api_request(url, api_key="", method="GET", data=None):
    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        req_data = json.dumps(data).encode('utf-8') if data else None
        req = urllib.request.Request(f"{url}?_t={int(time.time()*1000)}", data=req_data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=6) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        write_log(f"API请求失败 [{method} {url}]: {e}")
        return None
# ==============================================================================
# 模块 5: 配置文件与网络 API 请求通信 [END]
# ==============================================================================


# ==============================================================================
# 模块 6: UI 配色方案与字体映射 [START]
# ==============================================================================
COLOR_BG_MAIN = "#0C0C0E"       
COLOR_CARD_BG = "#16161A"       
COLOR_CARD_BORDER = "#26262B"   
COLOR_BAMBU_GREEN = "#00AE42"   
COLOR_TEXT_PRIMARY = "#FFFFFF" 
COLOR_TEXT_MUTED = "#8E8E93"   
COLOR_BADGE_RED = "#FA3534"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

def map_font_family(cfg_font_str):
    if "MiSans" in cfg_font_str:
        return "MiSans"
    elif "YaHei" in cfg_font_str or "微软雅黑" in cfg_font_str:
        return "Microsoft YaHei UI"
    elif "Segoe" in cfg_font_str:
        return "Segoe UI Variable Text"
    return "MiSans"
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

        self.cfg = load_config()
        self.font_family = map_font_family(self.cfg.get("selected_font", "MiSans (小米澎湃)"))
        self.is_dialog_showing = False
        self.deduct_queue = []
        self._is_first_load = True
        self.latest_release_info = None
        self.current_user_name = "未登录"
        self.current_dashboard_filter = "全部打印机"

        write_log(f"🖥️ [初始化] 启动界面, 当前全局字体设定: {self.font_family}")

        self.title("拓竹耗材台账助手")
        
        saved_w = self.cfg.get("window_width", 1160)
        saved_h = self.cfg.get("window_height", 820)
        self.geometry(f"{saved_w}x{saved_h}")
        self.minsize(960, 640)
        self.configure(fg_color=COLOR_BG_MAIN)
        enable_windows_rendering_optimizations(self)

        if os.path.exists(LOGO_ICO_FILE):
            try:
                self.iconbitmap(LOGO_ICO_FILE)
            except Exception:
                pass

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._resize_after_id = None
        self._is_resizing = False
        self._last_resize_geometry = None
        self.bind("<Configure>", self._on_window_configure, add="+")
        self._apply_windows_resize_optimizations()

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)

        self.content_area = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content_area.grid(row=0, column=0, sticky="nsew", padx=24, pady=(16, 10))
        self.content_area.grid_columnconfigure(0, weight=1)
        self.content_area.grid_rowconfigure(0, weight=1)

        self.views = {}
        self.nav_buttons = {}
        self.registered_widgets_font = []
        
        # 底部悬浮导航条
        self.bottom_nav = ctk.CTkFrame(self, height=60, corner_radius=30, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        self.bottom_nav.grid(row=1, column=0, pady=(0, 16), padx=20)

        self.build_navigation()

        self.init_dashboard_view()
        self.switch_tab("dashboard")

        self.watcher = BambuFileWatcher(self)
        self.watcher.start()

        threading.Thread(target=self.silent_check_update, daemon=True).start()
        threading.Thread(target=self.fetch_user_info_async, daemon=True).start()

    def build_navigation(self):
        for w in self.bottom_nav.winfo_children():
            w.destroy()
        self.nav_buttons.clear()

        tabs = [
            ("📦  耗材台账", "dashboard"),
            ("🖨️  设备管理", "printers"),
            ("📊  数据洞察", "analytics"),
            ("🛒  补货清单", "shopping"),
            ("⚖️  称重工作台", "scale_workbench"),
            ("⚙️  服务设置", "settings"),
        ]

        if self.cfg.get("developer_mode", False):
            tabs.append(("📜  运行日志", "logs"))

        for text, key in tabs:
            btn = ctk.CTkButton(
                self.bottom_nav, text=text, font=self.get_font(13, "bold"),
                width=110, height=40, corner_radius=20, fg_color="transparent",
                text_color=COLOR_TEXT_MUTED, hover_color=COLOR_CARD_BORDER,
                command=lambda k=key: self.switch_tab(k)
            )
            btn.pack(side="left", padx=8, pady=6)
            self.register_widget_font(btn, 13, "bold")
            self.nav_buttons[key] = btn

    def _apply_windows_resize_optimizations(self):
        if os.name != "nt":
            return
        try:
            hwnd = self.winfo_id()
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

    def _on_window_configure(self, event):
        try:
            if event.widget is not self:
                return
            geometry = (event.width, event.height)
            if geometry == self._last_resize_geometry:
                return
            self._last_resize_geometry = geometry
            self._is_resizing = True

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
        self._is_resizing = False

    def on_close(self):
        try:
            if self._resize_after_id is not None:
                self.after_cancel(self._resize_after_id)
                self._resize_after_id = None
        except Exception:
            pass
        try:
            self.cfg["window_width"] = self.winfo_width()
            self.cfg["window_height"] = self.winfo_height()
            save_config(self.cfg)
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
            self._refresh_font_family_only(self.bottom_nav)
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

    def switch_tab(self, tab_name):
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

        for name, view in self.views.items():
            if name == tab_name:
                view.grid(row=0, column=0, sticky="nsew")
            else:
                view.grid_forget()

        for name, btn in self.nav_buttons.items():
            btn.configure(
                fg_color=COLOR_BAMBU_GREEN if name == tab_name else "transparent",
                text_color="#FFFFFF" if name == tab_name else COLOR_TEXT_MUTED
            )

        if tab_name == "dashboard":
            self.refresh_dashboard()
        elif tab_name == "printers":
            self.refresh_printers_view()
        elif tab_name == "analytics":
            self.refresh_analytics_view()
        elif tab_name == "shopping":
            self.refresh_shopping_view()
        elif tab_name == "scale_workbench":
            self.refresh_scale_workbench()
        elif tab_name == "logs":
            self.load_logs()

    # --------------------------------------------------------------------------
    # 子功能: 账号/API 校验与用户名动态显示 [START]
    # --------------------------------------------------------------------------
    def fetch_user_info_async(self):
        base_url = self.cfg.get("server_url", "").replace('/api/ingest/script-report', '')
        api_key = self.cfg.get("api_key", "")
        if not base_url or not api_key:
            self.update_user_display("未配置/未连接", False)
            return

        user_info_url = f"{base_url}/api/ingest/script-user-info"
        res = api_request(user_info_url, api_key=api_key, method="GET")
        if res and res.get("status") == "success":
            username = res.get("username", "已连接用户")
            self.current_user_name = username
            self.update_user_display(username, True)
        else:
            self.current_user_name = "未连接"
            self.update_user_display("未连接或 Key 无效", False)

    def update_user_display(self, username, is_connected):
        def _update():
            if hasattr(self, 'lbl_user_status') and self.lbl_user_status.winfo_exists():
                if is_connected:
                    self.lbl_user_status.configure(text=f"🟢 账号: {username}", text_color=COLOR_BAMBU_GREEN, fg_color="#0D2B1A")
                else:
                    self.lbl_user_status.configure(text=f"⚪ 状态: {username}", text_color=COLOR_TEXT_MUTED, fg_color="#202025")
            if hasattr(self, 'lbl_settings_user') and self.lbl_settings_user.winfo_exists():
                if is_connected:
                    self.lbl_settings_user.configure(text=f"🟢 当前已认证用户: {username}", text_color=COLOR_BAMBU_GREEN)
                else:
                    self.lbl_settings_user.configure(text="⚪ 当前未连接或 API Key 无效", text_color=COLOR_TEXT_MUTED)
        self.after(0, _update)

    def open_quick_login_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("账号登录换取 API Key")
        modal.geometry("420x360")
        modal.resizable(False, False)
        modal.attributes('-topmost', True)
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
            fg_color=COLOR_BAMBU_GREEN, hover_color="#008F32",
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
                self.latest_release_info = rel
                self.after(50, self.show_new_badge)
                self.after(50, lambda: self.open_update_modal(is_startup=False))
            elif code == "LATEST":
                self.after(50, lambda: messagebox.showinfo("检查更新", f"当前已是最新版本 ({CURRENT_VERSION})！"))
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
        for asset in self.latest_release_info.get("assets", []):
            name = asset.get("name", "")
            if name.endswith(".exe") and "standalone" not in name.lower() and "单机" not in name and "server" not in name.lower():
                raw_download_url = asset.get("browser_download_url")
                asset_exe_name = name
                break
        
        if not raw_download_url:
            for asset in self.latest_release_info.get("assets", []):
                name = asset.get("name", "")
                if name.endswith(".exe") and "server" not in name.lower():
                    raw_download_url = asset.get("browser_download_url")
                    asset_exe_name = name
                    break

        modal = ctk.CTkToplevel(self)
        modal.title(f"发现新版本 - {tag_name}")
        modal.geometry("640x510")
        modal.minsize(620, 480)
        modal.attributes('-topmost', True)
        modal.configure(fg_color=COLOR_BG_MAIN)

        container = ctk.CTkFrame(modal, corner_radius=20, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(container, text=f"✨ 发现新版本: {tag_name}", font=self.get_font(18, "bold"), text_color=COLOR_BAMBU_GREEN).pack(anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(container, text=f"当前运行版本: {CURRENT_VERSION}", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=16, pady=(0, 10))

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
            fg_color=COLOR_BAMBU_GREEN, hover_color="#008F32",
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
        view.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(view, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))

        logo_box = ctk.CTkFrame(header, fg_color="transparent")
        logo_box.pack(side="left")

        if os.path.exists(LOGO_PNG_FILE):
            try:
                pil_img = Image.open(LOGO_PNG_FILE)
                self.bambu_icon = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(38, 38))
                icon_lbl = ctk.CTkLabel(logo_box, image=self.bambu_icon, text="")
                icon_lbl.pack(side="left", padx=(0, 12))
            except Exception:
                pass

        title_sub_box = ctk.CTkFrame(logo_box, fg_color="transparent")
        title_sub_box.pack(side="left")

        t_row = ctk.CTkFrame(title_sub_box, fg_color="transparent")
        t_row.pack(anchor="w")
        self.lbl_dash_title = ctk.CTkLabel(t_row, text="拓竹耗材台账", font=self.get_font(23, "bold"), text_color=COLOR_TEXT_PRIMARY)
        self.lbl_dash_title.pack(side="left")
        self.register_widget_font(self.lbl_dash_title, 23, "bold")
        
        self.badge_new = ctk.CTkButton(
            t_row, text="NEW", width=42, height=18, corner_radius=9,
            fg_color=COLOR_BADGE_RED, hover_color="#D92828",
            font=self.get_font(10, "bold"), text_color="#FFFFFF",
            command=self.open_update_modal
        )

        sub_row = ctk.CTkFrame(title_sub_box, fg_color="transparent")
        sub_row.pack(anchor="w")
        
        lbl_sub = ctk.CTkLabel(sub_row, text=f"Bambu Inventory Studio • {CURRENT_VERSION}", font=self.get_font(11), text_color=COLOR_TEXT_MUTED)
        lbl_sub.pack(side="left")
        self.register_widget_font(lbl_sub, 11)

        self.lbl_user_status = ctk.CTkLabel(
            sub_row, text="⚪ 正在同步账号...", font=self.get_font(10, "bold"),
            text_color=COLOR_TEXT_MUTED, fg_color="#202025", corner_radius=6, padx=8, pady=1
        )
        self.lbl_user_status.pack(side="left", padx=(8, 0))

        btn_box = ctk.CTkFrame(header, fg_color="transparent")
        btn_box.pack(side="right")

        self.combo_dash_filter = ctk.CTkComboBox(
            btn_box, values=["全部打印机"], width=140, height=36, corner_radius=18,
            font=self.get_font(12), command=self.on_dash_filter_change
        )
        self.combo_dash_filter.pack(side="left", padx=(0, 8))

        btn_add = ctk.CTkButton(
            btn_box, text="＋ 新增耗材", width=110, height=36, corner_radius=18,
            fg_color=COLOR_BAMBU_GREEN, hover_color="#008F32",
            font=self.get_font(13, "bold"),
            command=self.open_add_filament_modal
        )
        btn_add.pack(side="left", padx=(0, 8))
        self.register_widget_font(btn_add, 13, "bold")

        btn_refresh = ctk.CTkButton(
            btn_box, text="🔄 刷新", width=80, height=36, corner_radius=18,
            fg_color=COLOR_CARD_BG, hover_color=COLOR_CARD_BORDER, border_width=1, border_color=COLOR_CARD_BORDER,
            font=self.get_font(13, "bold"),
            command=self.refresh_dashboard
        )
        btn_refresh.pack(side="left")
        self.register_widget_font(btn_refresh, 13, "bold")

        self.banner = ctk.CTkFrame(view, height=92, fg_color=COLOR_CARD_BG, corner_radius=20, border_width=1, border_color=COLOR_CARD_BORDER)
        self.banner.grid(row=1, column=0, sticky="ew", pady=(0, 14))

        self.scroll_list = ctk.CTkScrollableFrame(view, fg_color="transparent")
        self.scroll_list.grid(row=2, column=0, sticky="nsew")
        self.scroll_list.grid_columnconfigure(0, weight=1)

        self.views["dashboard"] = view

    def on_dash_filter_change(self, choice):
        self.current_dashboard_filter = choice
        self.refresh_dashboard()

    def refresh_dashboard(self):
        for w in self.scroll_list.winfo_children():
            w.destroy()
        for w in self.banner.winfo_children():
            w.destroy()

        base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
        printers = api_request(f"{base_url}/api/ingest/script-printers", self.cfg["api_key"], method="GET") or []
        p_names = ["全部打印机"] + [p["name"] for p in printers]
        self.combo_dash_filter.configure(values=p_names)
        if self.current_dashboard_filter not in p_names:
            self.current_dashboard_filter = "全部打印机"
            self.combo_dash_filter.set("全部打印机")

        filaments = api_request(self.cfg["filaments_url"], self.cfg["api_key"], method="GET")
        if filaments is None:
            filaments = []

        if self.current_dashboard_filter != "全部打印机":
            matched_printer = next((p for p in printers if p["name"] == self.current_dashboard_filter), None)
            if matched_printer:
                ams_slots = matched_printer.get("ams_slots") or {}
                mounted_fids = [int(v) for v in ams_slots.values() if v]
                filaments = [f for f in filaments if f["id"] in mounted_fids]

        total_types = len(filaments)
        total_weight = sum([item.get('current_weight_g', 0) or 0 for item in filaments])
        
        total_value = 0.0
        for item in filaments:
            price = item.get('price', 0) or 0
            init_w = item.get('initial_weight_g', 1000) or 1000
            curr_w = item.get('current_weight_g', 0) or 0
            if init_w > 0:
                total_value += (price / init_w) * curr_w

        avg_unit_price = (total_value / total_weight) if total_weight > 0 else 0.0

        b_box1 = ctk.CTkFrame(self.banner, fg_color="transparent")
        b_box1.pack(side="left", padx=24, pady=12)
        ctk.CTkLabel(b_box1, text="库存预估价值", font=self.get_font(11, "bold"), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
        ctk.CTkLabel(b_box1, text=f"¥ {total_value:.2f}", font=self.get_font(24, "bold"), text_color=COLOR_BAMBU_GREEN if total_value > 0 else COLOR_TEXT_PRIMARY).pack(anchor="w")

        ctk.CTkFrame(self.banner, width=1, fg_color=COLOR_CARD_BORDER).pack(side="left", fill="y", pady=14)

        b_box2 = ctk.CTkFrame(self.banner, fg_color="transparent")
        b_box2.pack(side="left", padx=24, pady=12)
        ctk.CTkLabel(b_box2, text="剩余存量总重", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
        ctk.CTkLabel(b_box2, text=f"{total_weight:.1f} g", font=self.get_font(18, "bold"), text_color=COLOR_BAMBU_GREEN).pack(anchor="w")

        ctk.CTkFrame(self.banner, width=1, fg_color=COLOR_CARD_BORDER).pack(side="left", fill="y", pady=14)

        b_box3 = ctk.CTkFrame(self.banner, fg_color="transparent")
        b_box3.pack(side="left", padx=24, pady=12)
        ctk.CTkLabel(b_box3, text="平均克重单价", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
        ctk.CTkLabel(b_box3, text=f"¥ {avg_unit_price:.3f} /g", font=self.get_font(18, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")

        b_box4 = ctk.CTkFrame(self.banner, fg_color="transparent")
        b_box4.pack(side="right", padx=24, pady=12)
        ctk.CTkLabel(b_box4, text="在册耗材种类", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="e")
        ctk.CTkLabel(b_box4, text=f"{total_types} 款", font=self.get_font(18, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="e")

        if not filaments:
            ctk.CTkLabel(self.scroll_list, text="⚠️ 暂未匹配到耗材数据，请点击右上角 [＋ 新增耗材]", text_color=COLOR_TEXT_MUTED, font=self.get_font(13)).pack(pady=60)
            return

        for item in filaments:
            card = ctk.CTkFrame(self.scroll_list, corner_radius=18, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
            card.pack(fill="x", pady=6)
            card.grid_columnconfigure(2, weight=1)

            fid = item.get('id', '-')
            brand = item.get('brand', 'Bambu')
            material = item.get('material', '-')
            color_name = item.get('color_name', '-')
            curr_w = item.get('current_weight_g', 0) or 0
            price = item.get('price', 0) or 0
            init_w = item.get('initial_weight_g', 1000) or 1000
            
            curr_val = (price / init_w * curr_w) if init_w > 0 else 0.0

            id_badge = ctk.CTkFrame(card, corner_radius=10, fg_color="#0D2B1A")
            id_badge.grid(row=0, column=0, padx=16, pady=14)
            ctk.CTkLabel(id_badge, text=f"#{fid}", text_color=COLOR_BAMBU_GREEN, font=self.get_font(13, "bold")).pack(padx=12, pady=5)

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.grid(row=0, column=1, padx=6, pady=12, sticky="w")
            ctk.CTkLabel(info, text=f"{brand} {material} • {color_name}", font=self.get_font(15, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")
            ctk.CTkLabel(info, text=f"买入价: ¥{price} / {init_w}g", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

            val_box = ctk.CTkFrame(card, fg_color="transparent")
            val_box.grid(row=0, column=2, padx=16, pady=12, sticky="e")

            w_color = COLOR_BAMBU_GREEN if curr_w >= 200 else "#EF4444"
            w_row = ctk.CTkFrame(val_box, fg_color="transparent")
            w_row.pack(anchor="e")
            
            if curr_w < 200:
                ctk.CTkLabel(w_row, text="余量告急", font=self.get_font(10, "bold"), text_color="#FFFFFF", fg_color="#EF4444", corner_radius=6, padx=6, pady=2).pack(side="left", padx=(0, 8))
                
            ctk.CTkLabel(w_row, text=f"{curr_w} g", font=self.get_font(16, "bold"), text_color=w_color).pack(side="left")
            ctk.CTkLabel(val_box, text=f"约 ¥ {curr_val:.2f}", font=self.get_font(12), text_color=COLOR_TEXT_MUTED).pack(anchor="e")

            ops_box = ctk.CTkFrame(card, fg_color="transparent")
            ops_box.grid(row=0, column=3, padx=16, pady=12)

            ctk.CTkButton(
                ops_box, text="手动调整", width=72, height=30, corner_radius=8,
                fg_color="#2563EB", hover_color="#1D4ED8", font=self.get_font(11, "bold"),
                command=lambda f=item: self.open_adjust_modal(f)
            ).pack(side="left", padx=2)

            ctk.CTkButton(
                ops_box, text="历史", width=52, height=30, corner_radius=8,
                fg_color="#475569", hover_color="#334155", font=self.get_font(11, "bold"),
                command=lambda f=item: self.open_history_modal(f)
            ).pack(side="left", padx=2)

            ctk.CTkButton(
                ops_box, text="删除", width=52, height=30, corner_radius=8,
                fg_color="#DC2626", hover_color="#B91C1C", font=self.get_font(11, "bold"),
                command=lambda fid=fid: self.delete_filament(fid)
            ).pack(side="left", padx=2)
    # --------------------------------------------------------------------------
    # 子功能: 1. 耗材台账看板视图 [END]
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # 子功能: 2. 设备管理视图 (Printers & 虚拟 AMS) [START]
    # --------------------------------------------------------------------------
    def init_printers_view(self):
        view = ctk.CTkFrame(self.content_area, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(view, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))

        ctk.CTkLabel(header, text="🖨️ 3D 打印机设备组", font=self.get_font(23, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(side="left")

        ctk.CTkButton(
            header, text="＋ 添加打印机", width=120, height=36, corner_radius=18,
            fg_color=COLOR_BAMBU_GREEN, hover_color="#008F32", font=self.get_font(13, "bold"),
            command=self.open_add_printer_modal
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            header, text="🔄 刷新", width=80, height=36, corner_radius=18,
            fg_color=COLOR_CARD_BG, hover_color=COLOR_CARD_BORDER, border_width=1, border_color=COLOR_CARD_BORDER,
            font=self.get_font(13, "bold"), command=self.refresh_printers_view
        ).pack(side="right")

        self.scroll_printers = ctk.CTkScrollableFrame(view, fg_color="transparent")
        self.scroll_printers.grid(row=1, column=0, sticky="nsew")
        self.scroll_printers.grid_columnconfigure(0, weight=1)

        self.views["printers"] = view

    def refresh_printers_view(self):
        for w in self.scroll_printers.winfo_children():
            w.destroy()

        base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
        printers = api_request(f"{base_url}/api/ingest/script-printers", self.cfg["api_key"], method="GET") or []
        filaments = api_request(self.cfg["filaments_url"], self.cfg["api_key"], method="GET") or []
        f_dict = {f["id"]: f for f in filaments}

        if not printers:
            ctk.CTkLabel(self.scroll_printers, text="⚠️ 暂未添加打印机设备，点击右上角 [＋ 添加打印机] 建立虚拟机群", text_color=COLOR_TEXT_MUTED, font=self.get_font(13)).pack(pady=60)
            return

        for p in printers:
            p_card = ctk.CTkFrame(self.scroll_printers, corner_radius=18, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
            p_card.pack(fill="x", pady=8)

            head_row = ctk.CTkFrame(p_card, fg_color="transparent")
            head_row.pack(fill="x", padx=18, pady=(14, 10))

            ctk.CTkLabel(head_row, text=f"🖨️ {p['name']} ({p.get('model', 'Bambu')})", font=self.get_font(16, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(side="left")
            
            ctk.CTkButton(
                head_row, text="删除设备", width=70, height=28, corner_radius=8,
                fg_color="#DC2626", hover_color="#B91C1C", font=self.get_font(11, "bold"),
                command=lambda pid=p['id']: self.delete_printer(pid)
            ).pack(side="right")

            ctk.CTkButton(
                head_row, text="⚙️ 映射 AMS 槽位", width=120, height=28, corner_radius=8,
                fg_color="#2563EB", hover_color="#1D4ED8", font=self.get_font(11, "bold"),
                command=lambda pr=p, fl=filaments: self.open_ams_mount_modal(pr, fl)
            ).pack(side="right", padx=8)

            slots_box = ctk.CTkFrame(p_card, fg_color="#111114", corner_radius=12)
            slots_box.pack(fill="x", padx=18, pady=(0, 14))
            slots_box.grid_columnconfigure((0, 1, 2, 3), weight=1)

            ams_slots = p.get("ams_slots") or {}
            for slot_i in range(1, 5):
                fid = ams_slots.get(str(slot_i))
                f_obj = f_dict.get(int(fid)) if fid else None
                s_frame = ctk.CTkFrame(slots_box, fg_color="transparent")
                s_frame.grid(row=0, column=slot_i-1, padx=10, pady=10, sticky="ew")

                ctk.CTkLabel(s_frame, text=f"AMS 槽位 {slot_i}", font=self.get_font(11, "bold"), text_color=COLOR_BAMBU_GREEN).pack(anchor="w")
                if f_obj:
                    ctk.CTkLabel(s_frame, text=f"{f_obj['brand']} {f_obj['material']}", font=self.get_font(12, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")
                    ctk.CTkLabel(s_frame, text=f"[{f_obj['color_name']}] 剩 {f_obj.get('current_weight_g')}g", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
                else:
                    ctk.CTkLabel(s_frame, text="[ 未挂载耗材 ]", font=self.get_font(12), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

    def open_add_printer_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("添加 3D 打印机")
        modal.geometry("400x320")
        modal.resizable(False, False)
        modal.attributes('-topmost', True)
        modal.configure(fg_color=COLOR_BG_MAIN)

        container = ctk.CTkFrame(modal, corner_radius=18, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(container, text="录入新打印机设备", font=self.get_font(16, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(14, 10))

        ctk.CTkLabel(container, text="设备自定义名称:", font=self.get_font(12, "bold")).pack(anchor="w", padx=16)
        entry_name = ctk.CTkEntry(container, height=36, corner_radius=8, font=self.get_font(12), placeholder_text="例如: 1号机-X1C")
        entry_name.pack(fill="x", padx=16, pady=(2, 8))

        ctk.CTkLabel(container, text="机型:", font=self.get_font(12, "bold")).pack(anchor="w", padx=16)
        cb_model = ctk.CTkComboBox(container, values=["Bambu A1 mini", "Bambu A1", "Bambu A2L", "Bambu P1P", "Bambu P1S", "Bambu P2S", "Bambu X1 Carbon", "Bambu X1E", "Bambu X2D", "Bambu H2S", "Bambu H2D", "Bambu H2C", "Bambu H2D Pro", "Other"], height=36, font=self.get_font(12))
        cb_model.pack(fill="x", padx=16, pady=(2, 8))

        def submit():
            name = entry_name.get().strip()
            if not name:
                return messagebox.showwarning("提示", "请输入设备名称！", parent=modal)
            base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
            res = api_request(f"{base_url}/api/ingest/script-printers", self.cfg["api_key"], method="POST", data={"name": name, "model": cb_model.get()})
            if res:
                messagebox.showinfo("成功", "打印机添加成功！", parent=modal)
                modal.destroy()
                self.refresh_printers_view()

        ctk.CTkButton(container, text="确认添加", height=38, corner_radius=10, fg_color=COLOR_BAMBU_GREEN, font=self.get_font(13, "bold"), command=submit).pack(fill="x", padx=16, pady=(10, 0))

    def open_ams_mount_modal(self, printer, filaments):
        modal = ctk.CTkToplevel(self)
        modal.title(f"映射 AMS 槽位 - {printer['name']}")
        modal.geometry("520x460")
        modal.attributes('-topmost', True)
        modal.configure(fg_color=COLOR_BG_MAIN)

        container = ctk.CTkFrame(modal, corner_radius=18, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(container, text=f"设置 [{printer['name']}] 的虚拟 AMS 耗材挂载", font=self.get_font(16, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(14, 10))

        options = ["未挂载 (空)"]
        opt_to_id = {"未挂载 (空)": None}
        id_to_opt = {None: "未挂载 (空)"}

        for f in filaments:
            label = f"ID:{f['id']} - {f['brand']} {f['material']} [{f['color_name']}] (剩 {f.get('current_weight_g')}g)"
            options.append(label)
            opt_to_id[label] = f['id']
            id_to_opt[f['id']] = label

        combos = {}
        ams_slots = printer.get("ams_slots") or {}

        for slot_i in range(1, 5):
            s_box = ctk.CTkFrame(container, fg_color="transparent")
            s_box.pack(fill="x", padx=16, pady=6)
            ctk.CTkLabel(s_box, text=f"AMS 槽位 {slot_i}:", font=self.get_font(12, "bold"), width=90).pack(side="left")
            cb = ctk.CTkComboBox(s_box, values=options, height=36, font=self.get_font(12))
            cb.pack(side="left", fill="x", expand=True)
            
            cur_fid = int(ams_slots.get(str(slot_i))) if ams_slots.get(str(slot_i)) else None
            cb.set(id_to_opt.get(cur_fid, "未挂载 (空)"))
            combos[str(slot_i)] = cb

        def submit():
            new_mapping = {}
            for s_str, cb in combos.items():
                selected_val = cb.get()
                new_mapping[s_str] = opt_to_id.get(selected_val)

            base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
            res = api_request(f"{base_url}/api/ingest/script-printers/{printer['id']}/ams", self.cfg["api_key"], method="POST", data={"ams_slots": new_mapping})
            if res:
                messagebox.showinfo("成功", "AMS 槽位映射已保存！", parent=modal)
                modal.destroy()
                self.refresh_printers_view()

        ctk.CTkButton(container, text="保存 AMS 配置", height=40, corner_radius=12, fg_color=COLOR_BAMBU_GREEN, font=self.get_font(13, "bold"), command=submit).pack(fill="x", padx=16, pady=(16, 0))

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

        header = ctk.CTkFrame(view, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))

        ctk.CTkLabel(header, text="📊 耗材消耗数据洞察", font=self.get_font(23, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(side="left")

        ctk.CTkButton(
            header, text="🔄 刷新统计", width=90, height=36, corner_radius=18,
            fg_color=COLOR_CARD_BG, hover_color=COLOR_CARD_BORDER, border_width=1, border_color=COLOR_CARD_BORDER,
            font=self.get_font(13, "bold"), command=self.refresh_analytics_view
        ).pack(side="right")

        self.scroll_analytics = ctk.CTkScrollableFrame(view, fg_color="transparent")
        self.scroll_analytics.grid(row=1, column=0, sticky="nsew")
        self.scroll_analytics.grid_columnconfigure((0, 1), weight=1)

        self.views["analytics"] = view

    def refresh_analytics_view(self):
        for w in self.scroll_analytics.winfo_children():
            w.destroy()

        base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
        data = api_request(f"{base_url}/api/ingest/script-analytics", self.cfg["api_key"], method="GET") or {}

        # 核心指标总览卡片
        summary_card = ctk.CTkFrame(self.scroll_analytics, corner_radius=18, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        summary_card.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        b1 = ctk.CTkFrame(summary_card, fg_color="transparent")
        b1.pack(side="left", padx=24, pady=16)
        ctk.CTkLabel(b1, text="累计打印消耗总重", font=self.get_font(11, "bold"), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
        ctk.CTkLabel(b1, text=f"{data.get('total_consumed_g', 0):.1f} g", font=self.get_font(22, "bold"), text_color=COLOR_BAMBU_GREEN).pack(anchor="w")

        ctk.CTkFrame(summary_card, width=1, fg_color=COLOR_CARD_BORDER).pack(side="left", fill="y", pady=14)

        b2 = ctk.CTkFrame(summary_card, fg_color="transparent")
        b2.pack(side="left", padx=24, pady=16)
        ctk.CTkLabel(b2, text="累计消耗折算金额", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
        ctk.CTkLabel(b2, text=f"¥ {data.get('total_consumed_cost', 0):.2f}", font=self.get_font(22, "bold"), text_color="#F59E0B").pack(anchor="w")

        ctk.CTkFrame(summary_card, width=1, fg_color=COLOR_CARD_BORDER).pack(side="left", fill="y", pady=14)

        b3 = ctk.CTkFrame(summary_card, fg_color="transparent")
        b3.pack(side="left", padx=24, pady=16)
        ctk.CTkLabel(b3, text="总计打印/切片任务", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")
        ctk.CTkLabel(b3, text=f"{data.get('task_count', 0)} 次", font=self.get_font(22, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")

        # 各打印机消耗分布
        p_card = ctk.CTkFrame(self.scroll_analytics, corner_radius=18, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        p_card.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=6)
        ctk.CTkLabel(p_card, text="🖨️ 各机位产出与消耗占比", font=self.get_font(14, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", padx=16, pady=14)

        printers_stat = data.get("printers_stat", [])
        if not printers_stat:
            ctk.CTkLabel(p_card, text="暂无各机位任务记录", text_color=COLOR_TEXT_MUTED, font=self.get_font(12)).pack(pady=30)
        else:
            for p in printers_stat:
                row = ctk.CTkFrame(p_card, fg_color="transparent")
                row.pack(fill="x", padx=16, pady=6)
                ctk.CTkLabel(row, text=p["name"], font=self.get_font(13, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(side="left")
                ctk.CTkLabel(row, text=f"{p['consumed_g']:.1f} g (¥{p['cost']:.2f})", font=self.get_font(12), text_color=COLOR_BAMBU_GREEN).pack(side="right")

        # 耗材材质消耗排行榜
        m_card = ctk.CTkFrame(self.scroll_analytics, corner_radius=18, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        m_card.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=6)
        ctk.CTkLabel(m_card, text="🧵 热门耗材材质排行", font=self.get_font(14, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", padx=16, pady=14)

        materials_stat = data.get("materials_stat", [])
        if not materials_stat:
            ctk.CTkLabel(m_card, text="暂无材质消耗记录", text_color=COLOR_TEXT_MUTED, font=self.get_font(12)).pack(pady=30)
        else:
            for m in materials_stat:
                row = ctk.CTkFrame(m_card, fg_color="transparent")
                row.pack(fill="x", padx=16, pady=6)
                ctk.CTkLabel(row, text=m["material"], font=self.get_font(13, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(side="left")
                ctk.CTkLabel(row, text=f"{m['consumed_g']:.1f} g", font=self.get_font(12), text_color="#38BDF8").pack(side="right")
    # --------------------------------------------------------------------------
    # 子功能: 3. 数据洞察大屏 (Analytics) [END]
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # 子功能: 4. 补货清单与分享导出 (Shopping List) [START]
    # --------------------------------------------------------------------------
    def init_shopping_view(self):
        view = ctk.CTkFrame(self.content_area, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(view, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))

        ctk.CTkLabel(header, text="🛒 待补货耗材清单", font=self.get_font(23, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(side="left")

        btn_box = ctk.CTkFrame(header, fg_color="transparent")
        btn_box.pack(side="right")

        ctk.CTkButton(
            btn_box, text="📋 复制精美采购单", width=130, height=36, corner_radius=18,
            fg_color="#3B82F6", hover_color="#2563EB", font=self.get_font(12, "bold"),
            command=self.copy_shopping_list_clipboard
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_box, text="📤 导出 JSON", width=100, height=36, corner_radius=18,
            fg_color=COLOR_CARD_BG, hover_color=COLOR_CARD_BORDER, border_width=1, border_color=COLOR_CARD_BORDER,
            font=self.get_font(12, "bold"), command=self.export_shopping_json
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_box, text="📥 导入 JSON", width=100, height=36, corner_radius=18,
            fg_color=COLOR_CARD_BG, hover_color=COLOR_CARD_BORDER, border_width=1, border_color=COLOR_CARD_BORDER,
            font=self.get_font(12, "bold"), command=self.import_shopping_json
        ).pack(side="left")

        self.scroll_shopping = ctk.CTkScrollableFrame(view, fg_color="transparent")
        self.scroll_shopping.grid(row=1, column=0, sticky="nsew")
        self.scroll_shopping.grid_columnconfigure(0, weight=1)

        self.views["shopping"] = view

    def refresh_shopping_view(self):
        for w in self.scroll_shopping.winfo_children():
            w.destroy()

        filaments = api_request(self.cfg["filaments_url"], self.cfg["api_key"], method="GET") or []
        low_filaments = [f for f in filaments if (f.get("current_weight_g") or 0) < 200]

        if not low_filaments:
            ctk.CTkLabel(self.scroll_shopping, text="🎉 耗材库存非常充裕，暂无需要补货的耗材！", text_color=COLOR_BAMBU_GREEN, font=self.get_font(14, "bold")).pack(pady=60)
            return

        for item in low_filaments:
            card = ctk.CTkFrame(self.scroll_shopping, corner_radius=18, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
            card.pack(fill="x", pady=6)
            card.grid_columnconfigure(1, weight=1)

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.grid(row=0, column=0, padx=16, pady=12, sticky="w")
            ctk.CTkLabel(info, text=f"#{item['id']} {item['brand']} {item['material']} • {item['color_name']}", font=self.get_font(14, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")
            ctk.CTkLabel(info, text=f"仅剩 {item.get('current_weight_g')}g (买入单价约 ¥{item.get('price')})", font=self.get_font(11), text_color="#EF4444").pack(anchor="w")

            url_box = ctk.CTkFrame(card, fg_color="transparent")
            url_box.grid(row=0, column=1, padx=12, pady=12, sticky="ew")
            
            entry_url = ctk.CTkEntry(url_box, height=34, corner_radius=8, font=self.get_font(11), placeholder_text="粘贴购买链接 (如 淘宝/拼多多)")
            entry_url.pack(side="left", fill="x", expand=True, padx=(0, 6))
            entry_url.insert(0, item.get("purchase_url") or "")

            btn_save_url = ctk.CTkButton(
                url_box, text="保存", width=50, height=34, corner_radius=8,
                fg_color=COLOR_BAMBU_GREEN, hover_color="#008F32", font=self.get_font(11, "bold"),
                command=lambda fid=item['id'], ent=entry_url: self.save_filament_url(fid, ent.get().strip())
            )
            btn_save_url.pack(side="left", padx=(0, 6))

            btn_apply_same = ctk.CTkButton(
                url_box, text="一键应用同款", width=95, height=34, corner_radius=8,
                fg_color="#334155", hover_color="#475569", font=self.get_font(11),
                command=lambda brand=item['brand'], mat=item['material'], ent=entry_url: self.apply_url_to_same(brand, mat, ent.get().strip())
            )
            btn_apply_same.pack(side="left")

            ops = ctk.CTkFrame(card, fg_color="transparent")
            ops.grid(row=0, column=2, padx=16, pady=12)

            if item.get("purchase_url"):
                ctk.CTkButton(
                    ops, text="🌐 去购买", width=70, height=34, corner_radius=8,
                    fg_color="#2563EB", hover_color="#1D4ED8", font=self.get_font(11, "bold"),
                    command=lambda u=item["purchase_url"]: webbrowser.open(u)
                ).pack(side="left")

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
    def init_settings_view(self):
        scroll_view = ctk.CTkScrollableFrame(self.content_area, fg_color="transparent")
        scroll_view.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(scroll_view, text="设置与关于", font=self.get_font(24, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", pady=(0, 16))

        card = ctk.CTkFrame(scroll_view, corner_radius=20, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        card.pack(fill="x", pady=(0, 14))
        card.grid_columnconfigure(1, weight=1)

        # 扣减上报地址
        item1 = ctk.CTkFrame(card, fg_color="transparent")
        item1.pack(fill="x", padx=20, pady=12)
        item1.grid_columnconfigure(1, weight=1)
        
        lbl_box1 = ctk.CTkFrame(item1, fg_color="transparent")
        lbl_box1.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(lbl_box1, text="扣减上报地址", font=self.get_font(14, "bold")).pack(anchor="w")
        ctk.CTkLabel(lbl_box1, text="接收 G-code 脚本切片扣减请求", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        self.entry_server_url = ctk.CTkEntry(item1, height=40, corner_radius=10)
        self.entry_server_url.grid(row=0, column=1, padx=(16, 0), sticky="ew")
        self.entry_server_url.insert(0, self.cfg.get("server_url", ""))

        ctk.CTkFrame(card, height=1, fg_color=COLOR_CARD_BORDER).pack(fill="x", padx=20)

        # 耗材台账地址
        item2 = ctk.CTkFrame(card, fg_color="transparent")
        item2.pack(fill="x", padx=20, pady=12)
        item2.grid_columnconfigure(1, weight=1)

        lbl_box2 = ctk.CTkFrame(item2, fg_color="transparent")
        lbl_box2.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(lbl_box2, text="耗材台账地址", font=self.get_font(14, "bold")).pack(anchor="w")
        ctk.CTkLabel(lbl_box2, text="用于实时拉取耗材档案与库存概览", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        self.entry_filaments_url = ctk.CTkEntry(item2, height=40, corner_radius=10)
        self.entry_filaments_url.grid(row=0, column=1, padx=(16, 0), sticky="ew")
        self.entry_filaments_url.insert(0, self.cfg.get("filaments_url", ""))

        ctk.CTkFrame(card, height=1, fg_color=COLOR_CARD_BORDER).pack(fill="x", padx=20)

        # 脚本 API 密钥
        item3 = ctk.CTkFrame(card, fg_color="transparent")
        item3.pack(fill="x", padx=20, pady=12)
        item3.grid_columnconfigure(1, weight=1)

        lbl_box3 = ctk.CTkFrame(item3, fg_color="transparent")
        lbl_box3.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(lbl_box3, text="脚本 API 密钥 (Token)", font=self.get_font(14, "bold")).pack(anchor="w")
        self.lbl_settings_user = ctk.CTkLabel(lbl_box3, text="正在校验认证状态...", font=self.get_font(11), text_color=COLOR_BAMBU_GREEN)
        self.lbl_settings_user.pack(anchor="w")

        key_input_box = ctk.CTkFrame(item3, fg_color="transparent")
        key_input_box.grid(row=0, column=1, padx=(16, 0), sticky="ew")
        key_input_box.grid_columnconfigure(0, weight=1)

        self.entry_api_key = ctk.CTkEntry(key_input_box, height=40, corner_radius=10, show="*")
        self.entry_api_key.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.entry_api_key.insert(0, self.cfg.get("api_key", ""))

        btn_quick_login = ctk.CTkButton(
            key_input_box, text="🔑 一键登录获取", width=120, height=38, corner_radius=10,
            fg_color="#3B82F6", hover_color="#2563EB", font=self.get_font(12, "bold"),
            command=self.open_quick_login_modal
        )
        btn_quick_login.grid(row=0, column=1)

        ctk.CTkFrame(card, height=1, fg_color=COLOR_CARD_BORDER).pack(fill="x", padx=20)

        # 全局字体选择通道
        item_font = ctk.CTkFrame(card, fg_color="transparent")
        item_font.pack(fill="x", padx=20, pady=12)
        item_font.grid_columnconfigure(1, weight=1)

        lbl_box_font = ctk.CTkFrame(item_font, fg_color="transparent")
        lbl_box_font.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(lbl_box_font, text="🎨 界面全局渲染字体", font=self.get_font(14, "bold")).pack(anchor="w")
        ctk.CTkLabel(lbl_box_font, text="支持在小米澎湃圆润字体与微软高清字体之间自由切换", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        self.combo_font = ctk.CTkComboBox(
            item_font, values=["MiSans (小米澎湃)", "Microsoft YaHei UI (微软高清)", "Segoe UI Variable (Win11 字体)"],
            height=36, corner_radius=10, width=220, font=self.get_font(12),
            command=self.on_font_change_live
        )
        self.combo_font.grid(row=0, column=1, padx=(16, 0), sticky="e")
        self.combo_font.set(self.cfg.get("selected_font", "MiSans (小米澎湃)"))

        ctk.CTkFrame(card, height=1, fg_color=COLOR_CARD_BORDER).pack(fill="x", padx=20)

        # 开发者模式 (联动底部运行日志)
        item_dev = ctk.CTkFrame(card, fg_color="transparent")
        item_dev.pack(fill="x", padx=20, pady=12)
        item_dev.grid_columnconfigure(1, weight=1)

        lbl_box_dev = ctk.CTkFrame(item_dev, fg_color="transparent")
        lbl_box_dev.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(lbl_box_dev, text="🛠️ 开发者调试模式", font=self.get_font(14, "bold")).pack(anchor="w")
        ctk.CTkLabel(lbl_box_dev, text="开启后将在底部导航激活 [运行日志] 与调试跟踪面板", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        self.switch_dev = ctk.CTkSwitch(
            item_dev, text="已启用" if self.cfg.get("developer_mode", False) else "已停用",
            font=self.get_font(12, "bold"), progress_color=COLOR_BAMBU_GREEN,
            command=self.toggle_developer_mode
        )
        self.switch_dev.grid(row=0, column=1, sticky="e")
        if self.cfg.get("developer_mode", False):
            self.switch_dev.select()
        else:
            self.switch_dev.deselect()

        ctk.CTkFrame(card, height=1, fg_color=COLOR_CARD_BORDER).pack(fill="x", padx=20)

        # 切片自动监听
        item4 = ctk.CTkFrame(card, fg_color="transparent")
        item4.pack(fill="x", padx=20, pady=12)
        item4.grid_columnconfigure(1, weight=1)

        lbl_box4 = ctk.CTkFrame(item4, fg_color="transparent")
        lbl_box4.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(lbl_box4, text="切片打印自动监听", font=self.get_font(14, "bold")).pack(anchor="w")
        ctk.CTkLabel(lbl_box4, text="开启后切片完成即可自动唤醒扣减", font=self.get_font(11), text_color=COLOR_BAMBU_GREEN).pack(anchor="w")

        self.switch_watcher = ctk.CTkSwitch(
            item4, text="实时监听中", font=self.get_font(12, "bold"),
            progress_color=COLOR_BAMBU_GREEN, command=self.toggle_watcher
        )
        self.switch_watcher.grid(row=0, column=1, sticky="e")
        if self.cfg.get("auto_watcher_enabled", True):
            self.switch_watcher.select()
        else:
            self.switch_watcher.deselect()

        btn_box = ctk.CTkFrame(scroll_view, fg_color="transparent")
        btn_box.pack(fill="x", pady=(8, 14))

        ctk.CTkButton(
            btn_box, text="测试服务器连接", height=42, corner_radius=20,
            fg_color=COLOR_CARD_BG, hover_color=COLOR_CARD_BORDER, border_width=1, border_color=COLOR_CARD_BORDER,
            font=self.get_font(13, "bold"), command=self.test_connection
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_box, text="🔍 立即检查更新", height=42, corner_radius=20,
            fg_color=COLOR_CARD_BG, hover_color=COLOR_CARD_BORDER, border_width=1, border_color=COLOR_CARD_BORDER,
            font=self.get_font(13, "bold"), command=self.manual_check_update
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_box, text="保存设置", height=42, corner_radius=20,
            fg_color=COLOR_BAMBU_GREEN, hover_color="#008F32",
            font=self.get_font(13, "bold"), command=self.save_settings
        ).pack(side="left")

        # 开源卡片
        github_card = ctk.CTkFrame(scroll_view, corner_radius=20, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        github_card.pack(fill="x", pady=(0, 36))

        gh_content = ctk.CTkFrame(github_card, fg_color="transparent")
        gh_content.pack(fill="x", padx=22, pady=16)

        gh_info = ctk.CTkFrame(gh_content, fg_color="transparent")
        gh_info.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(gh_info, text="✨ Bambu Filament Manager (开源联机版)", font=self.get_font(16, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(gh_info, text="专为拓竹 3D 打印机打造的自动化耗材资产与机群成本管理系统。支持切片离线自动扣减、AMS 续料分流与多机位大屏洞察。", font=self.get_font(11), text_color=COLOR_TEXT_MUTED, justify="left", wraplength=520).pack(anchor="w", pady=(4, 6))

        tag_box = ctk.CTkFrame(gh_info, fg_color="transparent")
        tag_box.pack(anchor="w")

        ctk.CTkLabel(tag_box, text=f"{CURRENT_VERSION} 稳定版", font=self.get_font(10, "bold"), text_color=COLOR_BAMBU_GREEN, fg_color="#0D2B1A", corner_radius=6, padx=8, pady=2).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(tag_box, text="MIT License", font=self.get_font(10), text_color=COLOR_TEXT_MUTED, fg_color="#202025", corner_radius=6, padx=8, pady=2).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(tag_box, text="🔐 WinVault Encrypted", font=self.get_font(10), text_color="#3B82F6", fg_color="#1E293B", corner_radius=6, padx=8, pady=2).pack(side="left")

        btn_github = ctk.CTkButton(
            gh_content, text="🌐 GitHub 仓库", height=40, width=130, corner_radius=20,
            fg_color="#24292F", hover_color="#1F2328", border_width=1, border_color="#30363D",
            font=self.get_font(12, "bold"),
            command=lambda: webbrowser.open(f"https://github.com/{GITHUB_REPO}")
        )
        btn_github.pack(side="right", padx=(10, 0))

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
        self.fetch_user_info_async()
        
        if not silent:
            messagebox.showinfo("成功", "设置与凭据已加密保存并即时生效！")

    def test_connection(self):
        self.fetch_user_info_async()
        res = api_request(self.entry_filaments_url.get().strip(), self.entry_api_key.get().strip(), method="GET")
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
        top_row.grid(row=0, column=0, sticky="ew", pady=(0, 14))

        lbl_log_title = ctk.CTkLabel(top_row, text="🛠️ 客户端调试与运行日志", font=self.get_font(22, "bold"), text_color=COLOR_TEXT_PRIMARY)
        lbl_log_title.pack(side="left")
        self.register_widget_font(lbl_log_title, 22, "bold")

        btn_clear = ctk.CTkButton(
            top_row, text="🗑️ 清空日志", width=90, height=32, corner_radius=16,
            fg_color="#DC2626", hover_color="#B91C1C", font=self.get_font(11, "bold"),
            command=self.clear_logs
        )
        btn_clear.pack(side="right")
        self.register_widget_font(btn_clear, 11, "bold")

        self.txt_log = ctk.CTkTextbox(view, corner_radius=18, fg_color=COLOR_CARD_BG, font=ctk.CTkFont(family="Consolas", size=11))
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
        modal.attributes('-topmost', True)
        modal.configure(fg_color=COLOR_BG_MAIN)

        container = ctk.CTkFrame(modal, corner_radius=20, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        header_box = ctk.CTkFrame(container, fg_color="transparent")
        header_box.pack(fill="x", padx=16, pady=(14, 8))

        ctk.CTkLabel(header_box, text=f"耗材: {filament.get('brand')} {filament.get('material')} [{filament.get('color_name')}]", font=self.get_font(15, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(header_box, text="包含所有切片自动扣减与手动调整记录", font=self.get_font(11), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        logs_scroll = ctk.CTkScrollableFrame(container, fg_color="transparent")
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

    def open_add_filament_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("录入耗材档案 (支持批量)")
        modal.geometry("500x560")
        modal.minsize(480, 520)
        modal.attributes('-topmost', True)
        modal.configure(fg_color=COLOR_BG_MAIN)

        container = ctk.CTkFrame(modal, corner_radius=18, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(container, text="录入新耗材档案", font=self.get_font(18, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", padx=18, pady=(16, 12))

        form_scroll = ctk.CTkScrollableFrame(container, fg_color="transparent")
        form_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        fields = {}
        form_defs = [
            ("耗材品牌", "brand", "Bambu"),
            ("耗材材质", "material", "PLA"),
            ("颜色名称", "color_name", "Basic Green"),
            ("单卷初始克重 (g)", "initial_weight_g", "1000"),
            ("单卷买入价格 (¥)", "price", "99.0"),
            ("购买链接 (备选)", "purchase_url", ""),
            ("⚡ 批量入库数量 (卷)", "count", "1")
        ]

        for label, key, default in form_defs:
            f_box = ctk.CTkFrame(form_scroll, fg_color="transparent")
            f_box.pack(fill="x", padx=6, pady=4)
            ctk.CTkLabel(f_box, text=label, font=self.get_font(12, "bold")).pack(anchor="w")
            entry = ctk.CTkEntry(f_box, height=36, corner_radius=8, font=self.get_font(12))
            entry.pack(fill="x", pady=(2, 0))
            entry.insert(0, default)
            fields[key] = entry

        def submit():
            try:
                count = int(fields["count"].get().strip())
                if count < 1: count = 1

                payload_base = {
                    "brand": fields["brand"].get().strip(),
                    "material": fields["material"].get().strip(),
                    "color_name": fields["color_name"].get().strip(),
                    "initial_weight_g": float(fields["initial_weight_g"].get().strip()),
                    "current_weight_g": float(fields["initial_weight_g"].get().strip()),
                    "price": float(fields["price"].get().strip()),
                    "purchase_url": fields["purchase_url"].get().strip()
                }

                base_url = self.cfg['server_url'].replace('/api/ingest/script-report', '')
                if count == 1:
                    api_request(f"{self.cfg['server_url']}-create", self.cfg['api_key'], method="POST", data=payload_base)
                else:
                    batch_list = [payload_base.copy() for _ in range(count)]
                    api_request(f"{base_url}/api/ingest/script-filaments-batch", self.cfg['api_key'], method="POST", data=batch_list)

                messagebox.showinfo("成功", f"成功录入 {count} 卷耗材档案！", parent=modal)
                modal.destroy()
                self.refresh_dashboard()
            except Exception as e:
                messagebox.showerror("错误", f"录入失败，请检查输入格式！\n{e}", parent=modal)

        ctk.CTkButton(
            container, text="✔ 提交入库", height=42, corner_radius=12,
            fg_color=COLOR_BAMBU_GREEN, hover_color="#008F32",
            font=self.get_font(14, "bold"), command=submit
        ).pack(fill="x", padx=18, pady=(0, 16), side="bottom")

    def open_adjust_modal(self, filament):
        modal = ctk.CTkToplevel(self)
        modal.title(f"手动调整克重 - #{filament['id']}")
        modal.geometry("440x480")
        modal.attributes('-topmost', True)
        modal.configure(fg_color=COLOR_BG_MAIN)

        container = ctk.CTkFrame(modal, corner_radius=18, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(container, text=f"耗材: {filament.get('brand')} {filament.get('material')} [{filament.get('color_name')}]", font=self.get_font(15, "bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(12, 2))
        ctk.CTkLabel(container, text=f"当前剩余存量: {filament.get('current_weight_g')} g", font=self.get_font(12), text_color=COLOR_BAMBU_GREEN).pack(anchor="w", padx=16, pady=(0, 10))

        action_box = ctk.CTkFrame(container, fg_color="transparent")
        action_box.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(action_box, text="调整类型:", font=self.get_font(12, "bold")).pack(anchor="w")
        cb_action = ctk.CTkComboBox(action_box, values=["减少 (-)", "增加 (+)"], corner_radius=8, height=36, font=self.get_font(13))
        cb_action.pack(fill="x", pady=(2, 0))
        cb_action.set("减少 (-)")

        w_box = ctk.CTkFrame(container, fg_color="transparent")
        w_box.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(w_box, text="变动克重 (g):", font=self.get_font(12, "bold")).pack(anchor="w")
        entry_weight = ctk.CTkEntry(w_box, height=36, corner_radius=8, placeholder_text="请输入克重 (如 50)", font=self.get_font(13))
        entry_weight.pack(fill="x", pady=(2, 0))

        model_box = ctk.CTkFrame(container, fg_color="transparent")
        model_box.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(model_box, text="模型名称:", font=self.get_font(12, "bold")).pack(anchor="w")
        entry_model = ctk.CTkEntry(model_box, height=36, corner_radius=8, placeholder_text="例如: 手动样品 / 测试件", font=self.get_font(13))
        entry_model.pack(fill="x", pady=(2, 0))

        remark_box = ctk.CTkFrame(container, fg_color="transparent")
        remark_box.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(remark_box, text="备注说明:", font=self.get_font(12, "bold")).pack(anchor="w")
        entry_remark = ctk.CTkEntry(remark_box, height=36, corner_radius=8, placeholder_text="例如: 管道残料清理 / 补充新卷", font=self.get_font(13))
        entry_remark.pack(fill="x", pady=(2, 0))

        def submit():
            try:
                raw_w = float(entry_weight.get().strip())
                if raw_w <= 0:
                    return messagebox.showwarning("提示", "克重请输入大于0的数值！", parent=modal)

                act = cb_action.get()
                model_name = entry_model.get().strip() or "手动调整"
                remark_str = entry_remark.get().strip()

                final_change_g = raw_w if "减少" in act else -raw_w
                act_text = "手动减少" if "减少" in act else "手动增加"
                full_task_name = f"{act_text}（{model_name} - {remark_str}）" if remark_str else f"{act_text}（{model_name}）"

                payload = {
                    "filament_id": filament['id'],
                    "used_weight_g": final_change_g,
                    "task_name": full_task_name
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

        ctk.CTkButton(container, text="确认调整", height=40, corner_radius=12, fg_color=COLOR_BAMBU_GREEN, font=self.get_font(14, "bold"), command=submit).pack(fill="x", padx=16, pady=(16, 10))

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
        view = ctk.CTkFrame(self.content_area, corner_radius=16, fg_color=COLOR_CARD_BG, border_width=1, border_color=COLOR_CARD_BORDER)
        view.grid_columnconfigure(0, weight=1, uniform="col")
        view.grid_columnconfigure(1, weight=1, uniform="col")
        view.grid_rowconfigure(0, weight=1)
        self.views["scale_workbench"] = view
        self._scale_poll_running = False
        self._scale_current_pending = None

        left = ctk.CTkFrame(view, corner_radius=12, fg_color="#0F0F12", border_width=1, border_color=COLOR_CARD_BORDER)
        left.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=16)
        left.grid_columnconfigure(0, weight=1)

        self.scale_status_label = ctk.CTkLabel(left, text="⚪ 秤休眠中", font=self.get_font(16, "bold"), text_color=COLOR_TEXT_MUTED, fg_color="#202025", corner_radius=20, height=40)
        self.scale_status_label.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        self.register_widget_font(self.scale_status_label, 16, "bold")

        self.scale_weight_label = ctk.CTkLabel(left, text="--.- g", font=self.get_font(42, "bold"), text_color="#FFFFFF")
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

        self.scale_refresh_btn = ctk.CTkButton(left, text="🔄 立即刷新", font=self.get_font(13, "bold"), height=36, corner_radius=18, fg_color=COLOR_BAMBU_GREEN, hover_color="#008C36", command=self.refresh_scale_workbench)
        self.scale_refresh_btn.grid(row=5, column=0, sticky="ew", padx=16, pady=(8, 4))
        self.register_widget_font(self.scale_refresh_btn, 13, "bold")

        self.scale_manual_btn = ctk.CTkButton(left, text="✋ 手动称重（无NFC）", font=self.get_font(12, "bold"), height=32, corner_radius=16, fg_color="#6B7280", hover_color="#4B5563", command=self.open_manual_weigh_modal)
        self.scale_manual_btn.grid(row=6, column=0, sticky="ew", padx=16, pady=(0, 8))
        self.register_widget_font(self.scale_manual_btn, 12, "bold")

        # 设备控制区域
        ctk.CTkLabel(left, text="📡 设备远程控制", font=self.get_font(11, "bold"), text_color=COLOR_TEXT_MUTED).grid(row=7, column=0, sticky="w", padx=16, pady=(8, 2))
        self.device_status_label = ctk.CTkLabel(left, text="状态: 未连接", font=self.get_font(10), text_color=COLOR_TEXT_MUTED, anchor="w")
        self.device_status_label.grid(row=8, column=0, sticky="ew", padx=16, pady=(0, 4))
        self.register_widget_font(self.device_status_label, 10)

        dev_btn_frame = ctk.CTkFrame(left, fg_color="transparent")
        dev_btn_frame.grid(row=9, column=0, sticky="ew", padx=16, pady=(0, 4))
        dev_btn_frame.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkButton(dev_btn_frame, text="⚖️称重", font=self.get_font(10), height=26, corner_radius=10, fg_color=COLOR_BAMBU_GREEN, hover_color="#008C36", command=lambda: self.send_device_command("switch_page", {"page": "weighing"})).grid(row=0, column=0, padx=1)
        ctk.CTkButton(dev_btn_frame, text="📱信息", font=self.get_font(10), height=26, corner_radius=10, fg_color="#3B82F6", hover_color="#2563EB", command=lambda: self.send_device_command("switch_page", {"page": "device_info"})).grid(row=0, column=1, padx=1)
        ctk.CTkButton(dev_btn_frame, text="📶WiFi", font=self.get_font(10), height=26, corner_radius=10, fg_color="#F59E0B", hover_color="#D97706", command=lambda: self.send_device_command("switch_page", {"page": "wifi_config"})).grid(row=0, column=2, padx=1)
        ctk.CTkButton(left, text="🔄 重启设备", font=self.get_font(10), height=26, corner_radius=10, fg_color="#6B7280", hover_color="#4B5563", command=lambda: self.send_device_command("reboot", {})).grid(row=10, column=0, sticky="ew", padx=16, pady=(0, 4))

        # 🎯 传感器向导式校准按钮
        ctk.CTkLabel(left, text="🎯 传感器向导式校准", font=self.get_font(11, "bold"), text_color=COLOR_TEXT_MUTED).grid(row=11, column=0, sticky="w", padx=16, pady=(8, 2))
        calib_btn_frame = ctk.CTkFrame(left, fg_color="transparent")
        calib_btn_frame.grid(row=12, column=0, sticky="ew", padx=16, pady=(0, 4))
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

        ctk.CTkButton(calib_btn_frame, text="① 清空并去皮", font=self.get_font(10), height=26, corner_radius=10, fg_color="#F59E0B", command=do_tare).grid(row=0, column=0, padx=1)
        ctk.CTkButton(calib_btn_frame, text="② 标定已知重量", font=self.get_font(10), height=26, corner_radius=10, fg_color="#3B82F6", command=do_calib).grid(row=0, column=1, padx=1)

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

        ctk.CTkButton(left, text="🚀 ESP32 云端固件更新", font=self.get_font(10), height=26, corner_radius=10, fg_color="#8B5CF6", command=trigger_fw_update).grid(row=13, column=0, sticky="ew", padx=16, pady=(6, 4))
        ctk.CTkButton(left, text="🔧 初始化重置配网", font=self.get_font(10), height=26, corner_radius=10, fg_color="#DC2626", hover_color="#B91C1C", command=lambda: self.send_device_command("reset_config", {})).grid(row=14, column=0, sticky="ew", padx=16, pady=(0, 16))

        right = ctk.CTkFrame(view, corner_radius=12, fg_color="#0F0F12", border_width=1, border_color=COLOR_CARD_BORDER)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=16)
        right.grid_columnconfigure(0, weight=1)

        # 未绑定提示区域（默认隐藏）
        self.scale_unbound_frame = ctk.CTkFrame(right, corner_radius=10, fg_color="#2A1F0A", border_width=1, border_color="#8B6914")
        self.scale_unbound_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        self.scale_unbound_frame.grid_columnconfigure(0, weight=1)
        self.scale_unbound_frame.grid_remove()
        ctk.CTkLabel(self.scale_unbound_frame, text="⚠️ NFC 未绑定耗材", font=self.get_font(14, "bold"), text_color="#F59E0B").grid(row=0, column=0, pady=(10, 4))
        self.register_widget_font(self.scale_unbound_frame.winfo_children()[-1], 14, "bold")
        self.scale_unbound_uid_label = ctk.CTkLabel(self.scale_unbound_frame, text="NFC UID: --", font=self.get_font(11), text_color=COLOR_TEXT_MUTED)
        self.scale_unbound_uid_label.grid(row=1, column=0, pady=(0, 2))
        self.register_widget_font(self.scale_unbound_uid_label, 11)
        self.scale_unbound_weight_label = ctk.CTkLabel(self.scale_unbound_frame, text="实测毛重: -- g", font=self.get_font(12, "bold"), text_color=COLOR_TEXT_PRIMARY)
        self.scale_unbound_weight_label.grid(row=2, column=0, pady=(0, 8))
        self.register_widget_font(self.scale_unbound_weight_label, 12, "bold")
        self.scale_bind_btn = ctk.CTkButton(self.scale_unbound_frame, text="🔗 绑定耗材", font=self.get_font(13, "bold"), height=36, corner_radius=18, fg_color=COLOR_BAMBU_GREEN, hover_color="#008C36", command=self.open_scale_bind_modal)
        self.scale_bind_btn.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 12))
        self.register_widget_font(self.scale_bind_btn, 13, "bold")

        ctk.CTkLabel(right, text="📊 账面对比", font=self.get_font(16, "bold"), text_color=COLOR_TEXT_PRIMARY).grid(row=1, column=0, sticky="w", padx=16, pady=(16, 8))
        self.register_widget_font(right.winfo_children()[-1], 16, "bold")

        cmp_frame = ctk.CTkFrame(right, corner_radius=10, fg_color="#16161A", border_width=1, border_color=COLOR_CARD_BORDER)
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

        self.scale_btn_failure = ctk.CTkButton(btn_frame, text="🔴 打印失败纠正", font=self.get_font(11, "bold"), height=44, corner_radius=10, fg_color=COLOR_BADGE_RED, hover_color="#C02828", state="disabled", command=lambda: self.scale_confirm_action("failure_correction"))
        self.scale_btn_failure.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.register_widget_font(self.scale_btn_failure, 11, "bold")

        self.scale_btn_normal = ctk.CTkButton(btn_frame, text="🔵 常规误差同步", font=self.get_font(11, "bold"), height=44, corner_radius=10, fg_color="#007AFF", hover_color="#005FC0", state="disabled", command=lambda: self.scale_confirm_action("normal_sync"))
        self.scale_btn_normal.grid(row=0, column=1, sticky="ew", padx=4)
        self.register_widget_font(self.scale_btn_normal, 11, "bold")

        self.scale_btn_new = ctk.CTkButton(btn_frame, text="🟢 新料盘/重置皮重", font=self.get_font(11, "bold"), height=44, corner_radius=10, fg_color=COLOR_BAMBU_GREEN, hover_color="#008C36", state="disabled", command=self.scale_new_spool)
        self.scale_btn_new.grid(row=0, column=2, sticky="ew", padx=(4, 0))
        self.register_widget_font(self.scale_btn_new, 11, "bold")

        self.scale_hint_label = ctk.CTkLabel(right, text="等待秤端上报数据...", font=self.get_font(11), text_color=COLOR_TEXT_MUTED)
        self.scale_hint_label.grid(row=5, column=0, pady=(8, 8))
        self.register_widget_font(self.scale_hint_label, 11)

        # 历史待确认记录
        ctk.CTkLabel(right, text="📋 历史待确认记录", font=self.get_font(13, "bold"), text_color=COLOR_TEXT_PRIMARY).grid(row=6, column=0, sticky="w", padx=16, pady=(8, 4))
        self.register_widget_font(right.winfo_children()[-1], 13, "bold")
        self.scale_history_frame = ctk.CTkScrollableFrame(right, height=180, fg_color="#0A0A0C", corner_radius=8)
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
            if "scale_workbench" in self.views and self.views["scale_workbench"].winfo_ismapped():
                self.refresh_scale_workbench(silent=True)
                self.refresh_device_status()
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
            self.scale_status_label.configure(text="⚪ 连接服务器失败", text_color=COLOR_BADGE_RED, fg_color="#2A1010")
            return
        items = res.get("items", [])
        if not items:
            self._scale_current_pending = None
            self.scale_status_label.configure(text="⚪ 秤休眠中 / 无待确认", text_color=COLOR_TEXT_MUTED, fg_color="#202025")
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
            self.scale_status_label.configure(text="🟡 等待绑定", text_color="#F59E0B", fg_color="#2A1F0A")
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
        self.scale_status_label.configure(text="🟢 硬件已就绪", text_color="#FFFFFF", fg_color="#0D2B1A")
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
            ctk.CTkButton(btn_frame, text="确认", width=50, height=24, font=self.get_font(10, "bold"), fg_color=COLOR_BAMBU_GREEN, hover_color="#008C36", command=lambda pid=pid: self._scale_history_confirm(pid)).pack(side="left", padx=2)
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
        ctk.CTkButton(btn_frame, text="确认绑定", font=self.get_font(13, "bold"), height=40, corner_radius=10, fg_color=COLOR_BAMBU_GREEN, hover_color="#008C36", command=submit).pack(side="left", expand=True, fill="x", padx=(0, 4))
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

    def refresh_device_status(self):
        base_url = self.cfg.get("server_url", "").replace('/api/ingest/script-report', '')
        api_key = self.cfg.get("api_key", "")
        if not base_url or not api_key: return
        res = api_request(f"{base_url}/api/scale/device/status?device_id=scale_001", api_key=api_key, method="GET")
        if not res or not res.get("online"):
            self.device_status_label.configure(text="状态: 设备离线", text_color=COLOR_TEXT_MUTED)
            return
        self.device_status_label.configure(text=f"在线 | {res.get('current_weight', 0):.1f}g | WiFi{res.get('wifi_bars', 0)}格", text_color=COLOR_BAMBU_GREEN)

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
    ctk.CTkButton(btn_box, text="取消", fg_color="#26262B", command=on_cancel).pack(side="left", padx=10)
    
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
    if len(sys.argv) < 2:
        app = HyperOSFilamentApp()
        app.mainloop()
    else:
        cfg = load_config()
        gcode_path = sys.argv[-1]
        slot_weights = get_bambu_project_info_strict(gcode_path)
        detected_model_name = extract_model_name_from_file(gcode_path)
        if slot_weights and sum(slot_weights) > 0:
            base_url = cfg['server_url'].replace('/api/ingest/script-report', '')
            web_filaments = api_request(cfg["filaments_url"], cfg["api_key"], method="GET") or []
            printers = api_request(f"{base_url}/api/ingest/script-printers", cfg["api_key"], method="GET") or []
            is_confirmed, task_name, slot_map, target_printer_id = ask_user_multi_slot_mapping_modern(
                slot_weights, web_filaments, detected_model_name=detected_model_name, 
                font_family=map_font_family(cfg.get("selected_font", "MiSans")), printers=printers, default_printer_id=cfg.get("selected_printer_id")
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