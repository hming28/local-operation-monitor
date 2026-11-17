# Security Policy / 安全政策

[English](#english) • [简体中文](#chinese)

---

<a name="english"></a>
## 🌐 English

Local Ops executes user-configured shell commands with the privileges of the currently logged-in OS user and provides APIs to start, monitor, and terminate local processes. Please treat command execution, identity verification, write-endpoint authorization, path traversal prevention, configuration integrity, and data leakage prevention as critical security concerns.

### Supported Versions

The project is currently in the Preview / Alpha stage. Security fixes are applied primarily to the default `main` branch and the latest releases.

### Reporting a Vulnerability

Please report security issues privately via **GitHub Security Advisories (Security → Report a vulnerability)**. 

If private vulnerability reporting is unavailable, please contact the maintainer through the verified contact method on the GitHub profile with a brief message requesting a secure channel. **Do not** disclose vulnerability details in public issues, discussions, or pull requests.

A useful report should include:
- Affected versions or commits;
- OS (Windows / macOS) and Python versions;
- Impact and attack prerequisites;
- Minimal reproduction steps;
- Expected vs. actual behavior;
- Sanitized logs or request traces.

### Required Redactions

Never submit raw sensitive data:
- `config.json` or local configuration paths;
- Log files under `%LOCALAPPDATA%\总控台\Logs` or `~/Library/Logs/总控台/`;
- Full shell commands, personal paths, or usernames;
- PIDs, process run tokens, authentication tokens, or environment variables.

### Project Security Boundaries

- The HTTP server must bind **strictly to `127.0.0.1`** (loopback address only). Never expose it directly or indirectly to the local network or internet.
- This is a single-user local tool, not a multi-tenant or remote administration panel.
- Only trusted local users should add and run commands.

---

<a name="chinese"></a>
## 🇨🇳 简体中文

总控台会以当前操作系统登录用户的权限执行用户配置的命令，并提供启动、监控和结束本地进程的接口。请把命令执行、身份校验、写接口授权、路径处理、配置完整性和敏感信息保护视为高影响安全问题。

### 支持范围

项目处于 Preview / Alpha 阶段，安全修复优先面向默认 `main` 分支和最新发布版本。

### 私下报告漏洞

请优先使用 GitHub 仓库的 **Security → Report a vulnerability** 提交私密安全报告。切勿在公开 Issue、讨论区或 Pull Request 中披露未修复的漏洞细节。

一份有用的安全报告应包含：
- 受影响的版本或 Commit；
- 操作系统版本与 Python 版本；
- 影响范围与复现前提；
- 最小化复现步骤；
- 脱敏后的相关日志。

### 必须脱敏的内容

请勿提交下列包含敏感信息的原始数据：
- `config.json` 配置文件；
- 日志文件；
- 包含个人真实路径、用户名、Token、密钥的环境变量或命令行参数。

### 项目安全边界

- HTTP 服务仅绑定 `127.0.0.1`，严禁直接或间接暴露至局域网或公网。
- 本项目非多用户权限系统，仅供受信任的本机当前用户使用。
