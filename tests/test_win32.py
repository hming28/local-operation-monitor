# -*- coding: utf-8 -*-
"""Windows 10/11 porting unit tests (runs on both Windows and POSIX via mocks)."""

import os
import sys
import tempfile
import types
import unittest
from unittest import mock

# Provide a stub msvcrt on POSIX hosts so sysops_win32 can be imported and tested everywhere
if "msvcrt" not in sys.modules:
    _msvcrt_stub = types.ModuleType("msvcrt")
    _msvcrt_stub.LK_NBLCK = 2
    _msvcrt_stub.LK_UNLCK = 0
    _msvcrt_stub.locking = lambda fd, mode, nbytes: None
    sys.modules["msvcrt"] = _msvcrt_stub

import server
import sysops_win32


class Win32BackendTests(unittest.TestCase):
    def test_task_canceled_exit_codes(self):
        self.assertEqual(server.classify_task_exit(0), "succeeded")
        self.assertEqual(server.classify_task_exit(130), "canceled")
        with mock.patch.object(server.sysops, "TASK_CANCELED_EXIT_CODES", sysops_win32.TASK_CANCELED_EXIT_CODES):
            self.assertEqual(server.classify_task_exit(0xC000013A), "canceled")
            self.assertEqual(server.classify_task_exit(-1073741510), "canceled")
            self.assertEqual(server.classify_task_exit(1), "failed")

    def test_netstat_listener_fallback_parses_ipv4_and_ipv6(self):
        sample = (
            "Active Connections\n"
            "  Proto  Local Address          Foreign Address        State           PID\n"
            "  TCP    127.0.0.1:9600         0.0.0.0:0              LISTENING       4120\n"
            "  TCP    [::1]:3000             [::]:0                 LISTENING       5180\n"
            "  TCP    127.0.0.1:5000         127.0.0.1:51234        ESTABLISHED     4120\n"
        )
        with mock.patch.object(sysops_win32, "run_cmd", return_value=sample):
            found = sysops_win32._scan_listeners_netstat()
        self.assertEqual(found.get((4120, 9600)), {"127.0.0.1"})
        self.assertEqual(found.get((5180, 3000)), {"::1"})
        self.assertNotIn((4120, 5000), found)

    def test_command_for_script_windows_extensions(self):
        self.assertIn("python ", sysops_win32.command_for_script(r"C:\proj\job.py"))
        self.assertIn("powershell.exe -NoProfile -ExecutionPolicy Bypass -File", sysops_win32.command_for_script(r"C:\proj\run.ps1"))
        self.assertTrue(sysops_win32.command_for_script(r"C:\proj\build.bat").startswith("call "))
        self.assertTrue(sysops_win32.command_for_script(r"C:\proj\build.cmd").startswith("call "))

    def test_detect_venv_python_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            scripts = os.path.join(tmp, ".venv", "Scripts")
            os.makedirs(scripts)
            py = os.path.join(scripts, "python.exe")
            open(py, "w").close()
            self.assertEqual(sysops_win32.detect_venv_python(tmp), py)

    def test_build_launch_env_sets_utf8_and_token(self):
        env = sysops_win32.build_launch_env("tok-xyz", environ={"PATH": r"C:\Windows\System32"})
        self.assertEqual(env["PYTHONUTF8"], "1")
        self.assertEqual(env["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(env[sysops_win32.RUN_TOKEN_ENV], "tok-xyz")

    def test_pid_reuse_blocked_by_creation_time_mismatch(self):
        app = {
            "id": "abcd1234",
            "runToken": "tok-1",
            "lastPid": 7777,
            "lastPgid": 7777,
            "creationTime": 133000000000000000,
        }
        fake_groups = {7777: [7777]}
        fake_snap = {
            7777: {
                "uid": server.SELF_UID,
                "args": "cmd.exe /c rem console-run:tok-1",
                "ctime": 133999999999999999,  # Different creationTime => reused PID!
            }
        }
        with mock.patch.object(server, "ps_snapshot", return_value=fake_snap):
            idx, _, _ = server.managed_process_index([app], groups=fake_groups)
        self.assertEqual(idx["abcd1234"], [])

    def test_windows_exe_provenance_attribution(self):
        table = {
            100: (10, r'"C:\Program Files\cursor\Cursor.exe" --type=renderer'),
            200: (100, r'C:\Windows\System32\cmd.exe /c npm run dev'),
            300: (200, "node.exe vite"),
        }
        res = server.attribute_origin(300, table)
        self.assertEqual(res, {"label": "Cursor", "icon": "code"})

    def test_launcher_files_exist(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assertTrue(os.path.isfile(os.path.join(base, "start.bat")))
        self.assertTrue(os.path.isfile(os.path.join(base, "总控台.pyw")))
        self.assertTrue(os.path.isfile(os.path.join(base, "sysops.py")))
        self.assertTrue(os.path.isfile(os.path.join(base, "sysops_win32.py")))
        self.assertTrue(os.path.isfile(os.path.join(base, "sysops_posix.py")))


if __name__ == "__main__":
    unittest.main()
