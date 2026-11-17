## Purpose / 变更目的

<!-- Explain the problem solved, user scenarios, and why this change is needed. / 说明要解决的问题、用户场景和改动原因。 -->

## Summary of Changes / 主要改动

<!-- Concise list of changes made. Avoid unrelated edits. / 简要说明改动范围，避免夹带无关变更。 -->

## Verification & Tests / 验证与测试

<!-- List commands executed and manual tests performed. / 列出执行过的命令与测试。 -->

- [ ] `python -m unittest discover -s tests -v` (Windows / Cross-platform)
- [ ] `make check` (macOS)
- [ ] UI changes verified across themes (light/dark) and viewport sizes / 界面与明暗主题已验证
- [ ] Process/configuration changes handle failure and upgrade paths / 进程与配置异常路径已覆盖

## Security & Privacy / 安全与隐私

- [ ] No personal tokens, paths, real commands, or sensitive logs submitted / 未夹带个人路径、Token、凭证或真实命令
- [ ] Screenshots, logs, and traces are sanitized / 截图与日志已完成脱敏
- [ ] Loopback binding, user ID/SID isolation, and run token checks preserved / 安全校验未被削弱
- [ ] Zero third-party runtime dependencies maintained / 保持 100% 零第三方运行时依赖
