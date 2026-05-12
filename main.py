#!/usr/bin/env python3
"""禅道BUG分析工具 — 原生窗口入口"""
import atexit
import ctypes
import os
import socket
import sys
import threading
import time
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ERROR_LOG = os.path.join(BASE_DIR, "logs", "error.log")
PORT = 8765
URL = f"http://127.0.0.1:{PORT}"

# 必须在 WebView2 初始化前设置，确保 localStorage 跨会话持久化
os.environ['WEBVIEW2_USER_DATA_FOLDER'] = os.path.join(BASE_DIR, '.webview2_profile')


def _hide_console():
    """隐藏控制台窗口（使用 python.exe 而非 pythonw.exe 时）"""
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        pass


def _ensure_single_instance():
    """通过 Windows 命名 Mutex 确保单实例（进程退出自动释放，重启无残留）"""
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, "ZentaoBugAnalyzer_Mutex")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.user32.MessageBoxW(0, "禅道BUG分析工具已在运行中", "提示", 0x40)
        sys.exit(0)
    # 保持 handle 存活直到进程退出
    atexit.register(lambda: ctypes.windll.kernel32.CloseHandle(handle))


def _show_error(title, msg):
    """弹窗 + 写日志"""
    try:
        os.makedirs(os.path.dirname(ERROR_LOG), exist_ok=True)
        with open(ERROR_LOG, 'a', encoding='utf-8') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {title}: {msg}\n")
    except Exception:
        pass
    ctypes.windll.user32.MessageBoxW(0, msg[:500], title, 0x10)


def _is_port_in_use(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(('127.0.0.1', port))
        s.close()
        return True
    except socket.error:
        return False


def _start_server():
    os.chdir(BASE_DIR)
    import uvicorn
    uvicorn.run("app.server:app", host="127.0.0.1", port=PORT, log_level="info", reload=False)


def _wait_for_server():
    import urllib.request
    for _ in range(30):
        try:
            urllib.request.urlopen(URL + "/api/health", timeout=0.5)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def _set_window_icon():
    icon_path = os.path.join(BASE_DIR, "static", "favicon.ico")
    if not os.path.exists(icon_path):
        return
    for _ in range(20):
        hwnd = ctypes.windll.user32.FindWindowW(None, "禅道BUG分析工具")
        if hwnd:
            break
        time.sleep(0.1)
    else:
        return
    hicon = ctypes.windll.user32.LoadImageW(0, icon_path, 1, 0, 0, 0x00000010)
    if hicon:
        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon)
        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon)


def main():
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ZentaoBugAnalysis")
    except Exception:
        pass

    if not _is_port_in_use(PORT):
        server_thread = threading.Thread(target=_start_server, daemon=True)
        server_thread.start()
        if not _wait_for_server():
            _show_error("启动失败", "服务启动超时，请查看 logs/error.log")
            sys.exit(1)

    icon_thread = threading.Thread(target=_set_window_icon, daemon=True)
    icon_thread.start()

    import webview
    webview.create_window(
        title="禅道BUG分析工具",
        url=URL,
        width=1400,
        height=900,
        min_size=(1024, 680),
    )
    webview.start()
    sys.exit(0)


if __name__ == "__main__":
    _hide_console()
    _ensure_single_instance()
    try:
        main()
    except Exception as e:
        _show_error("启动失败", f"{e}\n\n{traceback.format_exc()}")
        sys.exit(1)
