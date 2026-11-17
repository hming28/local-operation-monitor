# Local Ops (总控台)

<div align="center">

**Mission control for local services & batch tasks on Windows & macOS**  
**Win & macOS 本地服务与批处理任务的指挥台：一键启动、实时监测、日志与进程溯源**

[![CI](https://github.com/hming28/local-operation-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/hming28/local-operation-monitor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.12+](https://img.shields.io/badge/Python-3.12%2B-brightgreen.svg)](https://www.python.org/)
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-0%20(Pure%20Stdlib)-orange.svg)](sysops_win32.py)

[English](#english) • [简体中文](#chinese) • [README in Chinese (独立中文文档)](README_zh.md)

</div>

---

<a name="english"></a>
## 🌐 English

**Local Ops** is a lightweight, zero-dependency mission control web console for local services and batch tasks on **Windows 10/11 and macOS**. It centralizes everyday project commands, long-running services, and one-off batch scripts into a local web dashboard. 

The backend is built entirely with the Python 3 standard library (using native `ctypes` Win32 API on Windows, zero third-party pip dependencies). The frontend is built with buildless, CDN-free vanilla HTML/CSS/JavaScript and binds strictly to the localhost loopback address.

> **Security Note**: Local Ops is designed exclusively for the current local user on the local machine. It is **not** a remote ops panel or a multi-user management dashboard. It executes commands with your local user privileges. **Do not** expose this service to untrusted networks via reverse proxies, SSH tunnels, or port forwarding.

---

### Highlights

- **Dual-Platform Native Support**: Seamless out-of-the-box experience on both **Windows 10/11** and **macOS 12+**.
- **100% Zero Third-Party Dependencies**: No `pip install` required. Powered purely by Python standard library and native OS APIs (`ctypes.windll` on Windows, POSIX syscalls on macOS).
- **Clean Process Lifecycle (No Orphan Processes)**:
  - **macOS**: Controlled process groups via `killpg`.
  - **Windows**: Kernel-level **Job Objects** tie all parent and spawned child processes together, ensuring `TerminateJobObject` terminates the entire tree with zero leftover zombie ports or orphan processes.
- **PID Reuse Mitigation**: Windows process tracking checks process creation timestamps (`creationTime`) to avoid misidentifying or terminating unrelated processes after rapid PID recycling.
- **Silent Background Tray Runner (`总控台.pyw`)**: Run silently on Windows without a black CMD window. Includes a pure Win32 system tray icon: double-click to open the dashboard, right-click to exit.
- **Adaptive Keyboard Shortcuts**: Keyboard shortcut labels adapt automatically depending on the visitor's OS (`⌘K` / `⌘J` on macOS, `Ctrl+K` / `Ctrl+J` on Windows/Linux).
- **Live Process Monitoring & Provenance**: Inspect CPU, memory, uptime, and **launcher provenance** (AI assistants like Claude/Codex, IDEs like VS Code/Cursor/Trae, terminals, or the console itself) for listening ports every 2 seconds.
- **Read-Only Project Detection**: Select a folder to automatically detect runnable scripts and project types (Node/pnpm, Hexo, FastAPI, Django, Go, Rust, static servers, etc.) without executing unverified code.

---

### UI Preview

The screenshots below use sanitized demo data and contain no sensitive user info, paths, or live tokens.

| Launchpad (启动台) | Service Monitor (服务监控) |
| --- | --- |
| ![Ops Launchpad](docs/screenshots/ops-launchpad.jpg) | ![Ops Service Monitor](docs/screenshots/ops-services.jpg) |

---

### Quick Start

**Prerequisites**: Windows 10/11 or macOS 12+, Python 3.12 or higher, and any modern web browser supporting ES Modules.

#### On Windows

| Method | Action | Use Case |
| :--- | :--- | :--- |
| **System Tray (Recommended)** | Double-click `总控台.pyw` | Everyday use. Runs silently in background with system tray icon. |
| **Console Batch** | Double-click `start.bat` | View live startup logs and console output directly in CMD. |
| **Command Line** | `python server.py [--no-browser] [--preferred-port 9600]` | Terminal automation or custom scripting. |

#### On macOS

| Method | Action | Use Case |
| :--- | :--- | :--- |
| **App Bundle** | Double-click `总控台.app` | Everyday use. Runs in the background without a terminal window. |
| **Command Script** | Double-click `start.command` | View live stdout/stderr in a Terminal window. |
| **Command Line** | `python3 server.py [--no-browser] [--preferred-port 9600]` | Command line debugging or scripting. |

*Note for macOS users*: If downloaded from GitHub and macOS displays a quarantine prompt, run `xattr -dr com.apple.quarantine "总控台.app"` once.

Once launched, Local Ops will automatically open in your default browser at `http://127.0.0.1:9600` (falls back to 9601–9609 if port 9600 is busy).

---

### Usage & Features

- **Launchpad**: Click "+ Add Service" to pick a project workspace folder. The console auto-detects common frameworks and suggests start commands. Cards feature large start/stop buttons, log viewers, diagnostics, restart, and drag-and-drop or keyboard-accessible reordering.
- **Service Monitoring**: Real-time process table showing CPU, memory, uptime, listening ports, and launcher origin. Unrecognized listening ports prompt quick-add or ignore actions.
- **Global Command Palette**: Press `Ctrl+K` (Windows/Linux) or `⌘K` (macOS) to launch commands, search services, or switch views.
- **Live Logs Center**: Press `Ctrl+J` (Windows/Linux) or `⌘J` (macOS) to inspect stdout/stderr logs across all services.
- **Task Exit Code Conventions**: For one-off batch tasks: exit code `0` = Succeeded; non-zero = Failed; user-cancelled via Ctrl+C = `130` / `0xC000013A` (displays as "Canceled").

---

### Security Boundaries

1. Only add commands and working directories you trust. The console runs commands with your full local user permissions.
2. Bind only to `127.0.0.1`. Never bind to `0.0.0.0` or expose the port to untrusted local networks or the public internet.
3. Keep your configuration (`config.json`) and logs private. Sanitize any screenshots or error reports before sharing.

---

<a name="chinese"></a>
## 🇨🇳 简体中文

**总控台 (Local Ops)** 是一款专为 **Windows 10/11 与 macOS** 设计的轻量级本地服务与批处理任务指挥中心。它将日常开发常用的项目命令、长期服务和一次性脚本统一集成到一个清爽的本地网页控制台中。

后端基于纯 Python 3 标准库（Windows 下使用原生 `ctypes` 调用 Win32 API，**100% 零第三方 pip 依赖**）；前端采用无打包构建、无 CDN 依赖的原生 HTML/CSS/JavaScript，仅绑定本机回环地址 (`127.0.0.1`)。

> **安全须知**：总控台只服务当前电脑和当前登录用户，并非远程运维或多人管理平台。它会以当前用户的系统权限执行所配置的命令，请勿通过反向代理、SSH 隧道或公网端口映射暴露到不受信任的网络。

---

### 功能亮点

- **双平台原生支持**：Windows 10/11 与 macOS 双平台开箱即用，**无须安装任何第三方 pip 库**。
- **孤儿进程彻底杜绝**：
  - **macOS**：采用 POSIX 进程组 (`killpg`)；
  - **Windows**：采用内核级 **Job Objects（作业对象）**，停止应用时一键终止整个进程树，彻底杜绝后台残留孤儿进程和占用端口的问题。
- **PID 防复用机制**：Windows 进程快照增加 `creationTime` 进程创建时间戳双重校验，杜绝 PID 快速回收复用带来的误判与误杀风险。
- **系统托盘后台常驻 (`总控台.pyw`)**：Windows 专属纯原生 Win32 托盘启动器，后台静默运行无 CMD 黑窗口，双击托盘打开控制台，右键托盘安全退出。
- **快捷键智能自适应**：前端界面自动识别访客操作系统（Mac 显示 `⌘K` / `⌘J`，Windows 显示 `Ctrl+K` / `Ctrl+J`）。
- **进程监控与来源溯源**：每 2 秒实时刷新所有本地监听服务的 CPU、内存、运行时长，并智能识别启动者来源（VS Code、Cursor、Trae、Claude、终端等）。
- **项目只读智能识别**：选择工作区文件夹后自动识别项目类型并生成启动命令（Node/pnpm、Hexo、FastAPI、Django、Go、Rust 等），不执行任何未受信任的代码。

---

### 快速开始

**运行要求**：Windows 10/11 或 macOS 12+，Python 3.12 或更高版本，支持 ES Modules 的现代浏览器。无需安装任何额外依赖。

#### Windows 启动

| 启动方式 | 操作 | 适用场景 |
| :--- | :--- | :--- |
| **后台托盘常驻（推荐）** | 双击 `总控台.pyw` | 日常使用。无控制台黑框，系统右下角生成托盘图标 |
| **控制台脚本** | 双击 `start.bat` | 实时查看命令行输出日志与启动信息 |
| **命令行启动** | `python server.py [--no-browser] [--preferred-port 9600]` | 终端或脚本化自定义启动 |

#### macOS 启动

| 启动方式 | 操作 | 适用场景 |
| :--- | :--- | :--- |
| **双击应用** | 双击 `总控台.app` | 日常使用。后台静默运行，无 Terminal 窗口和 Dock 图标 |
| **双击脚本** | 双击 `start.command` | 在 Terminal 窗口中实时查看输出 |
| **命令行** | `python3 server.py [--no-browser] [--preferred-port 9600]` | 终端或脚本启动 |

启动后自动在浏览器中打开 `http://127.0.0.1:9600`（若被占用自动顺延至 9601–9609）。

---

### 许可与致谢

- 本项目自有代码与文档采用 [MIT 许可证](LICENSE)。
- 界面图标及素材许可详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 [ASSET_PROVENANCE.md](ASSET_PROVENANCE.md)。
- 感谢原项目 [laogou717/local-ops](https://github.com/laogou717/local-ops) 提供的优秀设计思路。
