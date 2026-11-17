# -*- coding: utf-8 -*-
"""Windows 10/11 native system operations backend (pure Python stdlib + ctypes.windll)."""

import ctypes
from ctypes import wintypes
import errno
import msvcrt
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time

IS_WINDOWS = True
SUBPROCESS_TIMEOUT = 5
RUN_TOKEN_ENV = "CONSOLE_RUN_TOKEN"
RUN_TOKEN_ARG_PREFIX = "console-run:"
TASK_CANCELED_EXIT_CODES = {130, 0xC000013A, -1073741510}
SCRIPT_SUFFIXES = {".py", ".bat", ".cmd", ".ps1"}

CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_TERMINATE = 0x0001
SYNCHRONIZE = 0x00100000
STILL_ACTIVE = 259

TH32CS_SNAPPROCESS = 0x00000002
TCP_TABLE_OWNER_PID_LISTENER = 3
AF_INET = 2
AF_INET6 = 23
JOB_OBJECT_BASIC_PROCESS_ID_LIST = 3
TOKEN_QUERY = 0x0008
TOKEN_USER = 1

_CPU_CACHE_LOCK = threading.Lock()
_CPU_PREV = {}  # pid -> (wall_ns, proc_100ns, ctime_100ns)
_JOB_LOCK = threading.Lock()
_JOB_HANDLES = {}  # root_pid -> job_handle


def _win32_available():
    return sys.platform == "win32" and hasattr(ctypes, "windll")


if _win32_available():
    _kernel32 = ctypes.windll.kernel32
    _advapi32 = ctypes.windll.advapi32
    _iphlpapi = ctypes.windll.iphlpapi
    _psapi = ctypes.windll.psapi
    _ntdll = ctypes.windll.ntdll
else:
    _kernel32 = _advapi32 = _iphlpapi = _psapi = _ntdll = None


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]


class _MIB_TCPROW_OWNER_PID(ctypes.Structure):
    _fields_ = [
        ("dwState", wintypes.DWORD),
        ("dwLocalAddr", wintypes.DWORD),
        ("dwLocalPort", wintypes.DWORD),
        ("dwRemoteAddr", wintypes.DWORD),
        ("dwRemotePort", wintypes.DWORD),
        ("dwOwningPid", wintypes.DWORD),
    ]


class _MIB_TCP6ROW_OWNER_PID(ctypes.Structure):
    _fields_ = [
        ("ucLocalAddr", ctypes.c_ubyte * 16),
        ("dwLocalScopeId", wintypes.DWORD),
        ("dwLocalPort", wintypes.DWORD),
        ("ucRemoteAddr", ctypes.c_ubyte * 16),
        ("dwRemoteScopeId", wintypes.DWORD),
        ("dwRemotePort", wintypes.DWORD),
        ("dwState", wintypes.DWORD),
        ("dwOwningPid", wintypes.DWORD),
    ]


class _PROCESS_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Reserved1", ctypes.c_void_p),
        ("PebBaseAddress", ctypes.c_void_p),
        ("Reserved2", ctypes.c_void_p * 2),
        ("UniqueProcessId", ctypes.c_size_t),
        ("Reserved3", ctypes.c_void_p),
    ]


class _UNICODE_STRING(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", ctypes.c_void_p),
    ]


def _setup_win32_signatures():
    if not _win32_available():
        return
    _advapi32.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    _advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    _advapi32.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_uint, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    _advapi32.GetTokenInformation.restype = wintypes.BOOL
    _advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    _advapi32.OpenProcessToken.restype = wintypes.BOOL

    _iphlpapi.GetExtendedTcpTable.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL, wintypes.ULONG, ctypes.c_uint, wintypes.DWORD]
    _iphlpapi.GetExtendedTcpTable.restype = wintypes.DWORD

    _kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _kernel32.GetCurrentProcess.argtypes = []
    _kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    _kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    _kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    _kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(_FILETIME), ctypes.POINTER(_FILETIME), ctypes.POINTER(_FILETIME), ctypes.POINTER(_FILETIME)]
    _kernel32.GetProcessTimes.restype = wintypes.BOOL
    _kernel32.GetSystemTimeAsFileTime.argtypes = [ctypes.POINTER(_FILETIME)]
    _kernel32.GetSystemTimeAsFileTime.restype = None
    _kernel32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(_MEMORYSTATUSEX)]
    _kernel32.GlobalMemoryStatusEx.restype = wintypes.BOOL
    _kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    _kernel32.LocalFree.restype = ctypes.c_void_p
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
    _kernel32.Process32FirstW.restype = wintypes.BOOL
    _kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
    _kernel32.Process32NextW.restype = wintypes.BOOL
    _kernel32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_uint, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    _kernel32.QueryInformationJobObject.restype = wintypes.BOOL
    _kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    _kernel32.ReadProcessMemory.restype = wintypes.BOOL
    _kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _kernel32.TerminateJobObject.restype = wintypes.BOOL
    _kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _kernel32.TerminateProcess.restype = wintypes.BOOL

    _ntdll.NtQueryInformationProcess.argtypes = [wintypes.HANDLE, ctypes.c_uint, ctypes.c_void_p, wintypes.ULONG, ctypes.POINTER(wintypes.ULONG)]
    _ntdll.NtQueryInformationProcess.restype = ctypes.c_long

    _psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
    _psapi.GetProcessMemoryInfo.restype = wintypes.BOOL


_setup_win32_signatures()


def _ft_to_int(ft):
    return (int(ft.dwHighDateTime) << 32) | int(ft.dwLowDateTime)


def default_data_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "local-ops")


def default_logs_dir():
    return os.path.join(default_data_dir(), "logs")


def _process_sid(handle):
    if not _win32_available() or not handle:
        return None
    token = wintypes.HANDLE()
    if not _advapi32.OpenProcessToken(handle, TOKEN_QUERY, ctypes.byref(token)):
        return None
    try:
        needed = wintypes.DWORD(0)
        _advapi32.GetTokenInformation(token, TOKEN_USER, None, 0, ctypes.byref(needed))
        if needed.value == 0:
            return None
        buf = ctypes.create_string_buffer(needed.value)
        if not _advapi32.GetTokenInformation(
            token, TOKEN_USER, buf, needed.value, ctypes.byref(needed)
        ):
            return None
        sid_ptr = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
        str_ptr = wintypes.LPWSTR()
        if not _advapi32.ConvertSidToStringSidW(sid_ptr, ctypes.byref(str_ptr)):
            return None
        try:
            return str(str_ptr.value)
        finally:
            _kernel32.LocalFree(str_ptr)
    finally:
        _kernel32.CloseHandle(token)


def current_user_id():
    if _win32_available():
        handle = _kernel32.GetCurrentProcess()
        sid = _process_sid(handle)
        if sid:
            return sid
    return os.environ.get("USERNAME") or "win-user"


def is_same_user(owner_id, self_uid=None):
    target = current_user_id() if self_uid is None else self_uid
    return owner_id is not None and owner_id == target


def ensure_private_dir(path):
    os.makedirs(path, exist_ok=True)


def set_private_file_mode(path):
    return None


def acquire_instance_lock(path, self_pid):
    directory = os.path.dirname(path) or "."
    ensure_private_dir(directory)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    lock_file = os.fdopen(fd, "r+", encoding="ascii")
    try:
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as e:
        lock_file.close()
        if e.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
            return None
        raise
    try:
        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write("%d\n" % self_pid)
        lock_file.flush()
    except OSError:
        try:
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        lock_file.close()
        raise
    return lock_file


def release_instance_lock(lock_file):
    if lock_file is None:
        return
    try:
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    finally:
        lock_file.close()


def run_cmd(args, timeout=SUBPROCESS_TIMEOUT, log=None):
    try:
        kwargs = {
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "timeout": timeout,
        }
        if _win32_available():
            kwargs["creationflags"] = CREATE_NO_WINDOW
        r = subprocess.run(args, **kwargs)
        return r.stdout or ""
    except Exception:
        if log is not None:
            log.exception("命令执行失败: %r", args)
        return ""


def _scan_listeners_netstat(log=None):
    out = run_cmd(["netstat", "-ano", "-p", "tcp"], log=log)
    found = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        state = parts[3].upper()
        if state != "LISTENING":
            continue
        local = parts[1]
        m = re.search(r":(\d+)$", local)
        if not m:
            continue
        port = int(m.group(1))
        bind_host = local[: m.start()]
        if bind_host.startswith("[") and bind_host.endswith("]"):
            bind_host = bind_host[1:-1]
        try:
            pid = int(parts[4])
        except ValueError:
            continue
        found.setdefault((pid, port), set()).add(bind_host or "")
    return found


def scan_listeners(log=None):
    if not _win32_available():
        return _scan_listeners_netstat(log=log)
    found = {}
    for family, row_cls in (
        (AF_INET, _MIB_TCPROW_OWNER_PID),
        (AF_INET6, _MIB_TCP6ROW_OWNER_PID),
    ):
        size = wintypes.DWORD(0)
        _iphlpapi.GetExtendedTcpTable(
            None, ctypes.byref(size), False, family, TCP_TABLE_OWNER_PID_LISTENER, 0
        )
        if size.value <= 0:
            continue
        buf = ctypes.create_string_buffer(size.value)
        ret = _iphlpapi.GetExtendedTcpTable(
            buf, ctypes.byref(size), False, family, TCP_TABLE_OWNER_PID_LISTENER, 0
        )
        if ret != 0:
            continue
        num_entries = ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0]
        row_offset = ctypes.sizeof(wintypes.DWORD)
        row_size = ctypes.sizeof(row_cls)
        for i in range(num_entries):
            offset = row_offset + i * row_size
            if offset + row_size > size.value:
                break
            row = row_cls.from_buffer_copy(buf, offset)
            pid = int(row.dwOwningPid)
            raw_port = int(row.dwLocalPort)
            port = ((raw_port & 0xFF) << 8) | ((raw_port >> 8) & 0xFF)
            if family == AF_INET:
                ip_bytes = int(row.dwLocalAddr).to_bytes(4, "little")
                bind_host = socket.inet_ntop(socket.AF_INET, ip_bytes)
            else:
                ip_bytes = bytes(row.ucLocalAddr)
                bind_host = socket.inet_ntop(socket.AF_INET6, ip_bytes)
            found.setdefault((pid, port), set()).add(bind_host)
    if not found:
        return _scan_listeners_netstat(log=log)
    return found


def _toolhelp_processes():
    if not _win32_available():
        return {}
    snap = _kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == wintypes.HANDLE(-1).value:
        return {}
    procs = {}
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        if _kernel32.Process32FirstW(snap, ctypes.byref(entry)):
            while True:
                procs[int(entry.th32ProcessID)] = (
                    int(entry.th32ParentProcessID),
                    str(entry.szExeFile),
                )
                if not _kernel32.Process32NextW(snap, ctypes.byref(entry)):
                    break
    finally:
        _kernel32.CloseHandle(snap)
    return procs


def _total_phys_memory():
    if not _win32_available():
        return 1
    ms = _MEMORYSTATUSEX()
    ms.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
    if _kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)) and ms.ullTotalPhys > 0:
        return int(ms.ullTotalPhys)
    return 1


def _read_remote_unicode_string(handle, ustr_addr):
    if not ustr_addr:
        return ""
    ustr = _UNICODE_STRING()
    read = ctypes.c_size_t(0)
    if not _kernel32.ReadProcessMemory(
        handle, ctypes.c_void_p(ustr_addr), ctypes.byref(ustr), ctypes.sizeof(ustr), ctypes.byref(read)
    ):
        return ""
    length = int(ustr.Length)
    if length <= 0 or length > 32768 or not ustr.Buffer:
        return ""
    buf = ctypes.create_string_buffer(length)
    if not _kernel32.ReadProcessMemory(
        handle, ctypes.c_void_p(ustr.Buffer), buf, length, ctypes.byref(read)
    ):
        return ""
    return buf.raw[: read.value].decode("utf-16-le", errors="replace")


def _read_peb_details(pid):
    """Best-effort read of (cmdline, cwd) for same-user processes via PEB."""
    if not _win32_available():
        return "", ""
    handle = _kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, int(pid))
    if not handle:
        return "", ""
    try:
        pbi = _PROCESS_BASIC_INFORMATION()
        ret_len = wintypes.ULONG(0)
        status = _ntdll.NtQueryInformationProcess(
            handle, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), ctypes.byref(ret_len)
        )
        if status != 0 or not pbi.PebBaseAddress:
            return "", ""
        ptr_size = ctypes.sizeof(ctypes.c_void_p)
        # ProcessParameters offset in PEB: 0x20 on 64-bit, 0x10 on 32-bit
        pp_offset = 0x20 if ptr_size == 8 else 0x10
        pp_ptr = ctypes.c_void_p()
        read = ctypes.c_size_t(0)
        if not _kernel32.ReadProcessMemory(
            handle,
            ctypes.c_void_p(pbi.PebBaseAddress + pp_offset),
            ctypes.byref(pp_ptr),
            ptr_size,
            ctypes.byref(read),
        ) or not pp_ptr.value:
            return "", ""
        # Offsets inside RTL_USER_PROCESS_PARAMETERS:
        # 64-bit: CurrentDirectory.DosPath at 0x38, CommandLine at 0x70
        # 32-bit: CurrentDirectory.DosPath at 0x24, CommandLine at 0x40
        cwd_offset = 0x38 if ptr_size == 8 else 0x24
        cmd_offset = 0x70 if ptr_size == 8 else 0x40
        cwd = _read_remote_unicode_string(handle, pp_ptr.value + cwd_offset).rstrip("\\")
        cmdline = _read_remote_unicode_string(handle, pp_ptr.value + cmd_offset)
        return cmdline, cwd
    except Exception:
        return "", ""
    finally:
        _kernel32.CloseHandle(handle)


def process_creation_time(pid):
    if not _win32_available():
        return None
    handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return None
    try:
        ct, et, kt, ut = _FILETIME(), _FILETIME(), _FILETIME(), _FILETIME()
        if not _kernel32.GetProcessTimes(
            handle, ctypes.byref(ct), ctypes.byref(et), ctypes.byref(kt), ctypes.byref(ut)
        ):
            return None
        return _ft_to_int(ct)
    finally:
        _kernel32.CloseHandle(handle)


def ps_snapshot(pids=None, with_uid=True, log=None):
    if not _win32_available():
        return {}
    th_procs = _toolhelp_processes()
    target_pids = list(th_procs.keys()) if pids is None else [int(p) for p in pids]
    if not target_pids:
        return {}
    now_ft = _FILETIME()
    _kernel32.GetSystemTimeAsFileTime(ctypes.byref(now_ft))
    now_100ns = _ft_to_int(now_ft)
    wall_ns = time.monotonic_ns()
    ncpu = max(1, os.cpu_count() or 1)
    total_mem = _total_phys_memory()
    self_sid = current_user_id()

    snap = {}
    for pid in target_pids:
        if pid not in th_procs:
            continue
        _, exe_name = th_procs[pid]
        handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            continue
        try:
            sid = _process_sid(handle) if with_uid else None
            ct, et, kt, ut = _FILETIME(), _FILETIME(), _FILETIME(), _FILETIME()
            ctime = 0
            etime = 0
            cpu_pct = 0.0
            if _kernel32.GetProcessTimes(
                handle, ctypes.byref(ct), ctypes.byref(et), ctypes.byref(kt), ctypes.byref(ut)
            ):
                ctime = _ft_to_int(ct)
                etime = max(0, int((now_100ns - ctime) // 10_000_000))
                proc_100ns = _ft_to_int(kt) + _ft_to_int(ut)
                with _CPU_CACHE_LOCK:
                    prev = _CPU_PREV.get(pid)
                    _CPU_PREV[pid] = (wall_ns, proc_100ns, ctime)
                if prev and prev[2] == ctime and wall_ns > prev[0]:
                    d_wall_100ns = (wall_ns - prev[0]) / 100.0
                    d_proc_100ns = max(0, proc_100ns - prev[1])
                    cpu_pct = round(min(100.0 * ncpu, (d_proc_100ns / d_wall_100ns) * 100.0 / ncpu), 1)

            mem_pct = 0.0
            pmc = _PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(_PROCESS_MEMORY_COUNTERS)
            if _psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
                mem_pct = round((pmc.WorkingSetSize / total_mem) * 100.0, 2)

            args = exe_name
            if (not with_uid) or sid == self_sid:
                cmdline, _ = _read_peb_details(pid)
                if cmdline:
                    args = cmdline

            entry = {
                "comm": exe_name,
                "args": args,
                "cpu": cpu_pct,
                "mem": mem_pct,
                "etime": etime,
                "ctime": ctime,
            }
            if with_uid:
                entry["uid"] = sid
            snap[pid] = entry
        finally:
            _kernel32.CloseHandle(handle)
    return snap


def lsof_cwds(pids, log=None):
    if not _win32_available():
        return {}
    result = {}
    for pid in pids:
        _, cwd = _read_peb_details(int(pid))
        if cwd:
            result[int(pid)] = cwd
    return result


def pid_alive(pid):
    if not _win32_available():
        return False
    handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, int(pid))
    if not handle:
        return False
    try:
        code = wintypes.DWORD(0)
        if not _kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE
    finally:
        _kernel32.CloseHandle(handle)


def origin_snapshot(log=None):
    th_procs = _toolhelp_processes()
    self_sid = current_user_id()
    table = {}
    for pid, (ppid, exe_name) in th_procs.items():
        args = exe_name
        handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            try:
                if _process_sid(handle) == self_sid:
                    cmdline, _ = _read_peb_details(pid)
                    if cmdline:
                        args = cmdline
            finally:
                _kernel32.CloseHandle(handle)
        table[pid] = (ppid, args)
    return table


def _query_job_pids(job_handle):
    if not _win32_available() or not job_handle:
        return []
    buf_size = ctypes.sizeof(wintypes.DWORD) * 2 + ctypes.sizeof(ctypes.c_size_t) * 256
    buf = ctypes.create_string_buffer(buf_size)
    ret_len = wintypes.DWORD(0)
    ok = _kernel32.QueryInformationJobObject(
        job_handle, JOB_OBJECT_BASIC_PROCESS_ID_LIST, buf, buf_size, ctypes.byref(ret_len)
    )
    if not ok:
        return []
    count = ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[1]
    offset = ctypes.sizeof(wintypes.DWORD) * 2
    ptr_size = ctypes.sizeof(ctypes.c_size_t)
    pids = []
    for i in range(count):
        val = ctypes.c_size_t.from_buffer_copy(buf, offset + i * ptr_size).value
        if val > 0:
            pids.append(int(val))
    return pids


def pgid_members_map(log=None):
    """Map root_pid -> [member_pids...] using active Job Objects + PPID descendants."""
    th_procs = _toolhelp_processes()
    children = {}
    for pid, (ppid, _) in th_procs.items():
        children.setdefault(ppid, []).append(pid)

    groups = {}
    with _JOB_LOCK:
        job_items = list(_JOB_HANDLES.items())
    for root_pid, job_handle in job_items:
        members = set(_query_job_pids(job_handle))
        if root_pid in th_procs:
            members.add(root_pid)
        if members:
            groups[root_pid] = sorted(members)

    # Also include PPID-tree descendants for every active process as fallback after restart
    for root_pid in th_procs:
        if root_pid in groups:
            continue
        desc = []
        stack = [root_pid]
        seen = set()
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            desc.append(cur)
            stack.extend(children.get(cur, ()))
        if desc:
            groups[root_pid] = desc
    return groups


def process_uid(pid, log=None):
    if not _win32_available():
        return None
    handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return None
    try:
        return _process_sid(handle)
    finally:
        _kernel32.CloseHandle(handle)


def kill_process(pid, force, self_pid=None, self_uid=None, log=None):
    if self_pid is not None and pid == self_pid:
        return False, "不能结束总控台自身进程"
    uid = process_uid(pid, log=log)
    if uid is None:
        return False, "进程不存在"
    if not is_same_user(uid, self_uid):
        return False, "只能结束当前用户的进程"
    if not force:
        try:
            os.kill(int(pid), signal.CTRL_BREAK_EVENT)
            return True, None
        except OSError:
            pass
    handle = _kernel32.OpenProcess(PROCESS_TERMINATE, False, int(pid))
    if not handle:
        return False, "没有权限结束该进程"
    try:
        if not _kernel32.TerminateProcess(handle, 1):
            return False, "结束失败"
    finally:
        _kernel32.CloseHandle(handle)
    return True, None


def stop_pid_tree(pid, sig=None, force=False):
    root_pid = int(pid)
    if not force:
        try:
            os.kill(root_pid, signal.CTRL_BREAK_EVENT)
            return True, None
        except OSError:
            pass
    with _JOB_LOCK:
        job_handle = _JOB_HANDLES.get(root_pid)
    if job_handle and _win32_available():
        if _kernel32.TerminateJobObject(job_handle, 1):
            return True, None
    run_cmd(["taskkill", "/T", "/F", "/PID", str(root_pid)])
    return True, None


def stop_single_pid(pid, sig=None, force=False):
    ok, err = kill_process(int(pid), force=force)
    if err == "进程不存在":
        return True, None
    return ok, err


def group_alive(pgid):
    root_pid = int(pgid)
    with _JOB_LOCK:
        job_handle = _JOB_HANDLES.get(root_pid)
    if job_handle and _query_job_pids(job_handle):
        return True
    return pid_alive(root_pid)


def build_launch_env(token, environ=None):
    env = dict(os.environ if environ is None else environ)
    home = os.path.expanduser("~")
    local_app = env.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
    app_data = env.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
    preferred = [
        os.path.join(home, ".local", "bin"),
        os.path.join(local_app, "pnpm"),
        os.path.join(app_data, "npm"),
        os.path.join(home, ".bun", "bin"),
        os.path.join(home, ".cargo", "bin"),
    ]
    preferred.extend((env.get("PATH") or "").split(os.pathsep))
    seen = set()
    env["PATH"] = os.pathsep.join(
        path for path in preferred if path and not (path in seen or seen.add(path))
    )
    env.setdefault("PNPM_HOME", os.path.join(local_app, "pnpm"))
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env[RUN_TOKEN_ENV] = token
    return env


def start_app_process(command, cwd, env, logf, marker):
    # Inject run marker into cmd.exe title/subshell args so PEB CommandLine carries it
    cmd_line = f'cmd.exe /d /s /c "rem {marker} & chcp 65001 >NUL & {command}"'
    flags = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    proc = subprocess.Popen(
        cmd_line,
        cwd=cwd,
        stdout=logf,
        stderr=subprocess.STDOUT,
        creationflags=flags,
        env=env,
    )
    extra = {}
    if _win32_available():
        job = _kernel32.CreateJobObjectW(None, None)
        if job:
            proc_handle = _kernel32.OpenProcess(0x1F0FFF, False, proc.pid)
            if proc_handle:
                try:
                    if _kernel32.AssignProcessToJobObject(job, proc_handle):
                        with _JOB_LOCK:
                            _JOB_HANDLES[proc.pid] = job
                finally:
                    _kernel32.CloseHandle(proc_handle)
        ctime = process_creation_time(proc.pid)
        if ctime:
            extra["creationTime"] = ctime
    return proc, proc.pid, extra


def spawn_detached_helper(args, cwd):
    return subprocess.Popen(
        args,
        cwd=cwd,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
        close_fds=True,
    )


def pick_path(what):
    if not _win32_available():
        return None, False
    if what == "dir":
        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
            "$d.Description = '选择工作目录';"
            "if ($d.ShowDialog() -eq 'OK') { Write-Output $d.SelectedPath } else { exit 1 }"
        )
    else:
        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$d = New-Object System.Windows.Forms.OpenFileDialog;"
            "$d.Title = '选择批处理脚本';"
            "if ($d.ShowDialog() -eq 'OK') { Write-Output $d.FileName } else { exit 1 }"
        )
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-STA", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW,
            timeout=180,
        )
    except Exception:
        return None, False
    if r.returncode != 0:
        return None, True
    return r.stdout.strip().rstrip("\\/") or None, False


def command_for_script(path):
    normalized = os.path.abspath(os.path.expanduser(str(path)))
    quoted = '"%s"' % normalized.replace('"', '\\"')
    suffix = os.path.splitext(normalized)[1].lower()
    if suffix == ".py":
        return "python %s" % quoted
    if suffix == ".ps1":
        return "powershell.exe -NoProfile -ExecutionPolicy Bypass -File %s" % quoted
    if suffix in (".bat", ".cmd"):
        return "call %s" % quoted
    return quoted


def detect_venv_python(workspace_dir):
    for rel in (
        os.path.join(".venv", "Scripts", "python.exe"),
        os.path.join("venv", "Scripts", "python.exe"),
        os.path.join(".venv", "bin", "python"),
        os.path.join("venv", "bin", "python"),
    ):
        candidate = os.path.join(workspace_dir, rel)
        if os.path.isfile(candidate):
            return candidate
    return None
