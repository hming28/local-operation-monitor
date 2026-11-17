# -*- coding: utf-8 -*-
"""POSIX / macOS system operations backend for local-ops."""

import errno
import fcntl
import glob
import os
import re
import shlex
import signal
import subprocess
import sys

IS_WINDOWS = False
SUBPROCESS_TIMEOUT = 5
RUN_TOKEN_ENV = "CONSOLE_RUN_TOKEN"
RUN_TOKEN_ARG_PREFIX = "console-run:"
TASK_CANCELED_EXIT_CODES = {130}
SCRIPT_SUFFIXES = {".py", ".sh", ".bash", ".zsh", ".command"}


def default_data_dir():
    return os.path.expanduser("~/Library/Application Support/总控台")


def default_logs_dir():
    return os.path.expanduser("~/Library/Logs/总控台")


def current_user_id():
    return os.getuid()


def is_same_user(owner_id, self_uid=None):
    target = current_user_id() if self_uid is None else self_uid
    return owner_id == target


def ensure_private_dir(path):
    os.makedirs(path, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)


def set_private_file_mode(path):
    os.chmod(path, 0o600)


def acquire_instance_lock(path, self_pid):
    directory = os.path.dirname(path) or "."
    ensure_private_dir(directory)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    lock_file = os.fdopen(fd, "r+", encoding="ascii")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        lock_file.close()
        if e.errno in (errno.EACCES, errno.EAGAIN):
            return None
        raise
    try:
        os.fchmod(lock_file.fileno(), 0o600)
        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write("%d\n" % self_pid)
        lock_file.flush()
        os.fsync(lock_file.fileno())
    except OSError:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
        raise
    return lock_file


def release_instance_lock(lock_file):
    if lock_file is None:
        return
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    finally:
        lock_file.close()


def run_cmd(args, timeout=SUBPROCESS_TIMEOUT, log=None):
    try:
        r = subprocess.run(
            args, capture_output=True, text=True, errors="replace", timeout=timeout
        )
        return r.stdout or ""
    except Exception:
        if log is not None:
            log.exception("命令执行失败: %r", args)
        return ""


def parse_etime(s):
    try:
        s = s.strip()
        days = 0
        if "-" in s:
            d, s = s.split("-", 1)
            days = int(d)
        parts = [int(p) for p in s.split(":")]
        if len(parts) == 2:
            hours, minutes, secs = 0, parts[0], parts[1]
        elif len(parts) == 3:
            hours, minutes, secs = parts
        else:
            return 0
        return days * 86400 + hours * 3600 + minutes * 60 + secs
    except Exception:
        return 0


def _to_float(tok, default=0.0):
    try:
        return float(tok)
    except (TypeError, ValueError):
        return default


def scan_listeners(log=None):
    out = run_cmd(["lsof", "-iTCP", "-sTCP:LISTEN", "-P", "-n"], log=log)
    found = {}
    for line in out.splitlines():
        if not line or line.startswith("COMMAND"):
            continue
        parts = line.split()
        if len(parts) < 9:
            continue
        try:
            pid = int(parts[1])
        except ValueError:
            continue
        port = None
        bind_host = None
        for tok in reversed(parts):
            m = re.search(r":(\d+)$", tok)
            if m:
                port = int(m.group(1))
                bind_host = tok[: m.start()]
                if bind_host.startswith("[") and bind_host.endswith("]"):
                    bind_host = bind_host[1:-1]
                break
        if port is None:
            continue
        found.setdefault((pid, port), set()).add(bind_host or "")
    return found


def ps_snapshot(pids=None, with_uid=True, log=None):
    base = ["ps"]
    if pids is None:
        base.append("-ax")
    else:
        pids = [int(p) for p in pids]
        if not pids:
            return {}
        base += ["-p", ",".join(str(p) for p in pids)]
    fields = ["pid"] + (["uid"] if with_uid else []) + ["etime", "%cpu", "%mem", "comm"]
    out1 = run_cmd(base + ["-o", ",".join(fields)], log=log)
    out2 = run_cmd(base + ["-o", "pid,args"], log=log)

    snap = {}
    fixed = 5 if with_uid else 4
    for line in out1.splitlines():
        toks = line.split()
        if len(toks) < fixed + 1:
            continue
        try:
            pid = int(toks[0])
        except ValueError:
            continue
        i = 1
        entry = {"args": ""}
        if with_uid:
            try:
                entry["uid"] = int(toks[1])
            except ValueError:
                entry["uid"] = -1
            i = 2
        entry["etime"] = parse_etime(toks[i])
        entry["cpu"] = _to_float(toks[i + 1])
        entry["mem"] = _to_float(toks[i + 2])
        entry["comm"] = " ".join(toks[i + 3 :])
        snap[pid] = entry
    for line in out2.splitlines():
        toks = line.split(None, 1)
        if not toks:
            continue
        try:
            pid = int(toks[0])
        except ValueError:
            continue
        if pid in snap:
            snap[pid]["args"] = toks[1] if len(toks) > 1 else ""
    return snap


def lsof_cwds(pids, log=None):
    pids = [int(p) for p in pids]
    if not pids:
        return {}
    out = run_cmd(
        ["lsof", "-a", "-p", ",".join(str(p) for p in pids), "-d", "cwd", "-Fn"],
        log=log,
    )
    result = {}
    cur = None
    for line in out.splitlines():
        if line.startswith("p"):
            try:
                cur = int(line[1:])
            except ValueError:
                cur = None
        elif line.startswith("n") and cur is not None:
            result[cur] = line[1:]
    return result


def pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return False


def origin_snapshot(log=None):
    table = {}
    for line in run_cmd(["ps", "-axo", "pid=,ppid=,args"], log=log).splitlines():
        toks = line.split(None, 2)
        if len(toks) < 2:
            continue
        try:
            pid, ppid = int(toks[0]), int(toks[1])
        except ValueError:
            continue
        table[pid] = (ppid, toks[2] if len(toks) > 2 else "")
    return table


def pgid_members_map(log=None):
    groups = {}
    for line in run_cmd(["ps", "-axo", "pid=,pgid="], log=log).splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            pid, pgid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        groups.setdefault(pgid, []).append(pid)
    return groups


def process_uid(pid, log=None):
    out = run_cmd(["ps", "-o", "uid=", "-p", str(int(pid))], log=log)
    toks = out.split()
    if not toks:
        return None
    try:
        return int(toks[0])
    except ValueError:
        return None


def process_creation_time(pid):
    return None


def kill_process(pid, force, self_pid=None, self_uid=None, log=None):
    if self_pid is not None and pid == self_pid:
        return False, "不能结束总控台自身进程"
    uid = process_uid(pid, log=log)
    if uid is None:
        return False, "进程不存在"
    if not is_same_user(uid, self_uid):
        return False, "只能结束当前用户的进程"
    sig = signal.SIGKILL if force else signal.SIGTERM
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        return False, "进程不存在"
    except PermissionError:
        return False, "没有权限结束该进程"
    except OSError as e:
        return False, "结束失败: %s" % e
    return True, None


def stop_pid_tree(pid, sig=signal.SIGTERM, force=False):
    if force:
        sig = signal.SIGKILL
    try:
        os.killpg(int(pid), sig)
        return True, None
    except ProcessLookupError:
        return True, None
    except PermissionError:
        return False, "没有权限停止受控进程组"
    except OSError as e:
        return False, "停止受控进程组失败: %s" % e


def stop_single_pid(pid, sig=signal.SIGTERM, force=False):
    if force:
        sig = signal.SIGKILL
    try:
        os.kill(int(pid), sig)
        return True, None
    except ProcessLookupError:
        return True, None
    except PermissionError:
        return False, "没有权限停止受控进程"
    except OSError as e:
        return False, "停止受控进程失败: %s" % e


def group_alive(pgid):
    try:
        os.killpg(int(pgid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True


def build_launch_env(token, environ=None):
    env = dict(os.environ if environ is None else environ)
    home = os.path.expanduser("~")
    preferred = [
        os.path.join(home, ".local", "bin"),
        os.path.join(home, ".volta", "bin"),
        os.path.join(home, ".bun", "bin"),
        os.path.join(home, "Library", "pnpm"),
        os.path.join(home, ".asdf", "shims"),
        "/opt/homebrew/bin",
        "/opt/homebrew/sbin",
        "/usr/local/bin",
        "/usr/local/sbin",
    ]
    preferred.extend(
        sorted(glob.glob(os.path.join(home, ".nvm", "versions", "node", "*", "bin")), reverse=True)
    )
    preferred.extend(
        sorted(
            glob.glob(os.path.join(home, ".fnm", "node-versions", "*", "installation", "bin")),
            reverse=True,
        )
    )
    preferred.extend((env.get("PATH") or "").split(os.pathsep))
    preferred.extend(("/usr/bin", "/bin", "/usr/sbin", "/sbin"))
    seen = set()
    env["PATH"] = os.pathsep.join(
        path for path in preferred if path and not (path in seen or seen.add(path))
    )
    env.setdefault("PNPM_HOME", os.path.join(home, "Library", "pnpm"))
    env[RUN_TOKEN_ENV] = token
    return env


def start_app_process(command, cwd, env, logf, marker):
    outer_script = '/bin/bash -c "$1"\nconsole_status=$?\nexit "$console_status"'
    inner_script = command + '\nconsole_status=$?\nwait\nexit "$console_status"'
    proc = subprocess.Popen(
        ["/bin/bash", "-c", outer_script, marker, inner_script],
        cwd=cwd,
        stdout=logf,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=env,
    )
    return proc, proc.pid, {}


def spawn_detached_helper(args, cwd):
    return subprocess.Popen(args, cwd=cwd, start_new_session=True, close_fds=True)


def pick_path(what):
    if what == "dir":
        script = 'POSIX path of (choose folder with prompt "选择工作目录")'
    else:
        script = 'POSIX path of (choose file with prompt "选择批处理脚本")'
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=180)
    except Exception:
        return None, False
    if r.returncode != 0:
        return None, True
    return r.stdout.strip().rstrip("/") or None, False


def command_for_script(path):
    normalized = os.path.abspath(os.path.expanduser(str(path)))
    quoted = shlex.quote(normalized)
    suffix = os.path.splitext(normalized)[1].lower()
    if suffix == ".py":
        return "python3 -- %s" % quoted
    if suffix == ".zsh":
        return "/bin/zsh -- %s" % quoted
    if suffix in (".sh", ".bash"):
        return "/bin/bash -- %s" % quoted
    if os.access(normalized, os.X_OK):
        return quoted
    return "/bin/bash -- %s" % quoted


def detect_venv_python(workspace_dir):
    for rel in (".venv/bin/python", "venv/bin/python"):
        candidate = os.path.join(workspace_dir, rel)
        if os.path.isfile(candidate):
            return candidate
    return None
