# Contributing to Local Ops / 参与贡献

[English](#english) • [简体中文](#chinese)

---

<a name="english"></a>
## 🌐 English

Thank you for contributing to Local Ops! The project is currently in the Preview / Alpha phase. We welcome well-scoped, verifiable contributions that maintain our zero-dependency philosophy and strictly preserve security boundaries.

### Before You Begin

1. **Search existing Issues and Pull Requests** to avoid duplicate effort.
2. For large features, configuration schema updates, process management strategy changes, or major UI overhauls, please open an Issue first to discuss user scenarios and compatibility implications.
3. **Do not disclose security vulnerabilities publicly**. Follow [`SECURITY.md`](SECURITY.md) to report them privately.
4. **Never submit** local `data/`, local configuration files, personal absolute paths, authentication tokens, live credentials, or unsanitized log outputs.

### Development Environment

- Windows 10/11 or macOS 12+;
- Python 3.12 or newer;
- Node.js (used solely for JavaScript linting/syntax checks);
- **Zero runtime dependencies**: Pure standard library and native OS APIs only.

### Core Principles

- **Zero Runtime Dependencies**: The backend must remain pure Python standard library + native ctypes. The frontend must remain vanilla ES Modules with no build steps and no CDN dependencies.
- **Strict Security Verification**: Never weaken loopback binding, current user ID/SID isolation, run tokens, process group/Job Object controls, or origin checks.
- **Safe Process Termination**: Never kill arbitrary processes solely by port matching. Always verify ownership and run tokens.
- **Idempotent Configuration**: Any schema change must include a clear `schemaVersion` and idempotent migration tests.

### Running Checks

Before submitting, run:

```bash
# On Windows
python -m unittest discover -s tests -v

# On macOS
make check
```

---

<a name="chinese"></a>
## 🇨🇳 简体中文

感谢你参与改进总控台！项目当前处于 Preview / Alpha 阶段，优先接受范围清晰、可验证且不扩大安全边界的改动。

### 开始之前

1. 先搜索已有 Issue 和 Pull Request，避免重复工作。
2. 较大的功能、配置 schema 变化、进程管理策略或 UI 主题调整，请先开 Issue 说明动机、用户场景和兼容性影响。
3. 安全漏洞切勿公开讨论，请按 [`SECURITY.md`](SECURITY.md) 私下报告。
4. 切勿提交本机 `data/`、个人路径、完整命令、Token、凭证或未脱敏截图。

### 开发环境

- Windows 10/11 或 macOS 12+；
- Python 3.12 或更高版本；
- Node.js（仅用于前端 JS 语法检查）；
- 运行时零第三方 Python 依赖。

### 修改原则

- 后端严格保持 Python 标准库与系统原生 API 实现；前端保持原生 ES Modules，无 CDN，无构建打包。
- 不得削弱回环绑定、当前 UID/SID 隔离、run token、Job Object / 进程组、Host/Origin 等安全校验。
- 不得按端口直接结束未知进程，必须严格校验进程归属。
- 配置变更必须具备明确的 `schemaVersion` 与幂等迁移测试。

### 提交前检查

提交前请运行单元测试：

```bash
# Windows 环境
python -m unittest discover -s tests -v

# macOS 环境
make check
```
