#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows 无黑框后台启动器 + 原生系统托盘图标（零第三方依赖）。"""

import ctypes
from ctypes import wintypes
import os
import sys
import threading
import urllib.request
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def _run_tray_loop(port_holder):
    if sys.platform != "win32":
        return
    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32
    kernel32 = ctypes.windll.kernel32

    WM_USER = 0x0400
    WM_TRAYICON = WM_USER + 20
    WM_COMMAND = 0x0111
    WM_DESTROY = 0x0002
    WM_LBUTTONDBLCLK = 0x0203
    WM_RBUTTONUP = 0x0205

    NIM_ADD = 0x00000000
    NIM_DELETE = 0x00000002
    NIF_MESSAGE = 0x00000001
    NIF_ICON = 0x00000002
    NIF_TIP = 0x00000004
    MF_STRING = 0x00000000
    TPM_RIGHTBUTTON = 0x0002

    ID_OPEN = 1001
    ID_QUIT = 1002

    class NOTIFYICONDATAW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("hWnd", wintypes.HWND),
            ("uID", wintypes.UINT),
            ("uFlags", wintypes.UINT),
            ("uCallbackMessage", wintypes.UINT),
            ("hIcon", wintypes.HICON),
            ("szTip", wintypes.WCHAR * 128),
            ("dwState", wintypes.DWORD),
            ("dwStateMask", wintypes.DWORD),
            ("szInfo", wintypes.WCHAR * 256),
            ("uTimeoutOrVersion", wintypes.UINT),
            ("szInfoTitle", wintypes.WCHAR * 64),
            ("dwInfoFlags", wintypes.DWORD),
        ]

    WNDPROC = ctypes.WINFUNCTYPE(
        ctypes.c_long, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
    )

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [
            ("style", wintypes.UINT),
            ("lpfnWndProc", WNDPROC),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HICON),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
        ]

    def open_ui():
        port = port_holder[0] or 9600
        webbrowser.open("http://127.0.0.1:%d/" % port)

    def wnd_proc(hwnd, msg, wparam, lparam):
        if msg == WM_TRAYICON:
            if lparam == WM_LBUTTONDBLCLK:
                open_ui()
            elif lparam == WM_RBUTTONUP:
                menu = user32.CreatePopupMenu()
                user32.AppendMenuW(menu, MF_STRING, ID_OPEN, "打开总控台")
                user32.AppendMenuW(menu, MF_STRING, ID_QUIT, "退出总控台")
                pt = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                user32.SetForegroundWindow(hwnd)
                user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON, pt.x, pt.y, 0, hwnd, None)
                user32.DestroyMenu(menu)
            return 0
        if msg == WM_COMMAND:
            cmd_id = wparam & 0xFFFF
            if cmd_id == ID_OPEN:
                open_ui()
            elif cmd_id == ID_QUIT:
                user32.PostQuitMessage(0)
                os._exit(0)
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    proc_ref = WNDPROC(wnd_proc)
    hinst = kernel32.GetModuleHandleW(None)
    cls = WNDCLASSW()
    cls.lpfnWndProc = proc_ref
    cls.hInstance = hinst
    cls.lpszClassName = "LocalOpsTrayWnd"
    user32.RegisterClassW(ctypes.byref(cls))
    hwnd = user32.CreateWindowExW(
        0, cls.lpszClassName, "总控台", 0, 0, 0, 0, 0, None, None, hinst, None
    )

    ico_path = os.path.join(BASE_DIR, "static", "assets", "favicon.ico")
    hicon = None
    if os.path.isfile(ico_path):
        hicon = user32.LoadImageW(None, ico_path, 1, 0, 0, 0x00000010)
    if not hicon:
        hicon = user32.LoadIconW(None, 32512)  # IDI_APPLICATION

    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hWnd = hwnd
    nid.uID = 1
    nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
    nid.uCallbackMessage = WM_TRAYICON
    nid.hIcon = hicon
    nid.szTip = "总控台 (Local Ops)"
    shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

    msg = wintypes.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    finally:
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))


def main():
    import server
    port_holder = [server.PORT_START]
    if sys.platform == "win32":
        threading.Thread(target=_run_tray_loop, args=(port_holder,), daemon=True).start()
    server.main(log_to_file=True)


if __name__ == "__main__":
    main()
