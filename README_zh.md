# 总控台 (Local Ops) - 中文文档

<div align="center">

**Win & macOS 本地服务与批处理任务的指挥台：一键启动、实时监测、日志与进程溯源**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.12+](https://img.shields.io/badge/Python-3.12%2B-brightgreen.svg)](https://www.python.org/)
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-0%20(Pure%20Stdlib)-orange.svg)](sysops_win32.py)

[English](README.md) • [简体中文](README_zh.md)

</div>

---

## 项目简介

**总控台 (Local Ops)** 是一款专为 **Windows 10/11 与 macOS** 设计的轻量级本地服务与批处理任务指挥中心。它将日常开发常用的项目命令、长期服务和一次性脚本统一集成到一个清爽的本地网页控制台中。

后端基于纯 Python 3 标准库（Windows 下使用原生 `ctypes` 调用 Win32 API，**100% 零第三方 pip 依赖**）；前端采用无打包构建、无 CDN 依赖的原生 HTML/CSS/JavaScript，仅绑定本机回环地址 (`127.0.0.1`)。

> **安全须知**：总控台只服务当前电脑和当前登录用户，并非远程运维或多人管理平台。它会以当前用户的系统权限执行所配置的命令，请勿通过反向代理、SSH 隧道或公网端口映射暴露到不受信任的网络。

---

## 核心亮点

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

## 界面预览

以下截图使用脱敏演示数据，不包含真实用户名、目录、命令或服务信息。

| 启动台 | 服务监控 |
| --- | --- |
| ![Ops 指挥台 · 启动台](docs/screenshots/ops-launchpad.jpg) | ![Ops 指挥台 · 服务监控](docs/screenshots/ops-services.jpg) |

---

## 快速开始

**运行要求**：Windows 10/11 或 macOS 12+，Python 3.12 或更高版本，支持 ES Modules 的现代浏览器。无需安装任何额外依赖。

### Windows 启动方式

| 启动方式 | 操作 | 适用场景 |
| :--- | :--- | :--- |
| **后台托盘常驻（推荐）** | 双击 `总控台.pyw` | 日常使用。无控制台黑框，系统任务栏右下角生成托盘图标 |
| **控制台脚本** | 双击 `start.bat` | 实时查看命令行输出日志与启动信息 |
| **命令行启动** | `python server.py [--no-browser] [--preferred-port 9600]` | 终端或脚本化自定义启动 |

### macOS 启动方式

| 启动方式 | 操作 | 适用场景 |
| :--- | :--- | :--- |
| **双击应用** | 双击 `总控台.app` | 日常使用。后台静默运行，无 Terminal 窗口和 Dock 图标 |
| **双击脚本** | 双击 `start.command` | 在 Terminal 窗口中实时查看输出 |
| **命令行** | `python3 server.py [--no-browser] [--preferred-port 9600]` | 终端或脚本启动 |

*macOS 提示*：首次打开下载的 `总控台.app`，如出现安全隔离提示，执行 `xattr -dr com.apple.quarantine "总控台.app"` 即可。

启动后自动在浏览器中打开 `http://127.0.0.1:9600`（若被占用自动顺延至 9601–9609）。

---

## 使用说明

左侧导航轨切换「启动台 / 服务监控」，右侧信息栏展示实时动态；所有数据每 2 秒自动刷新。

- **启动台**：点「+ 添加服务」选择工作区，自动识别项目并给出候选命令；卡片大按钮启停，支持查看实时日志、运行诊断、重启、编辑与删除，支持卡片拖拽与键盘排序。
- **服务监控**：查看当前用户所有监听端口的进程、资源占用与父进程溯源；发现未知端口可一键认领加入启动台。
- **全局命令面板**：按 `Ctrl+K`（Windows/Linux）或 `⌘K`（macOS）打开命令面板，快速查找和控制服务。
- **日志中心**：按 `Ctrl+J`（Windows/Linux）或 `⌘J`（macOS）集中查看所有服务的输出日志。
- **任务退出码约定**：自然退出 `0` = 成功；用户按 Ctrl+C 主动取消退出 `130` / `0xC000013A`（显示「已取消」）；非零 = 失败。

---

## 安全边界

1. 只添加你已检查且信任的命令和工作目录；总控台能以当前登录用户权限执行保存的命令。
2. HTTP 服务只绑定本地回环地址 `127.0.0.1`，切勿绑定到 `0.0.0.0` 或通过隧道对外暴露。
3. 勿将未脱敏的配置 (`config.json`) 或日志公开上传。

---

## 许可与致谢

- 本项目自有代码与文档采用 [MIT 许可证](LICENSE)。
- 界面素材与字体许可详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 [ASSET_PROVENANCE.md](ASSET_PROVENANCE.md)。
- 感谢原项目 [laogou717/local-ops](https://github.com/laogou717/local-ops) 提供的灵感与基础。
