# PLT-PKG-01-A09-P51-A17 Caddy 启动诊断编码前检查

- 日期：2026-11-06
- 基线检查：PASS_WITH_LIMITATION；遵循 CR-PKG-012/013 和项目 Release/Testing Rules。当前限制是 Hosted synthetic candidate only，不触碰正式信任。
- WBS：PLT-PKG-01-A09-P51-A17，仅补足本次 A17 验收 Harness 对 Caddy 子进程提前退出时的诊断。
- 输入证据：Hosted run 42243433283 A17 失败；日志指出 `/health/ready` 前子进程退出、`stderr unavailable`。源码当前把 Caddy stderr 指向 `DEVNULL`。之前 hosted run 42220874670 曾通过。
- 前置：P40、P39、P24、A50、P25、A34 与本轮前后端构建/测试均有 hosted success。
- 涉及模块/实体/API/权限：测试工具 `tools/smoke_packaged_platform_write_https.py` 的 Caddy subprocess 启动诊断；产品模块、实体、API、权限均不改。
- 编码前决策：按 CR-PKG-014 采用 B，在 owned临时run根捕获有限 stderr、退出码及白名单错误类别；原始stderr不输出/不上传。
- 验收：GitHub Hosted Windows D: 上A17 Edge HTTPS/PG18 required markers通过；cleanup无残留；diagnostic不包含原始 stderr、凭据、headers、正文或客户数据。
- 回滚：Harness stderr 恢复 DEVNULL，移除仅诊断代码；不影响候选包。
- 风险：如果失败不匹配已知错误类别，只显示不可逆的短 hash，可能需要额外一次受限诊断；结果不等同于真实 Win11 或正式发行。
- 状态：编码前完成；尚未实现、尚未运行本次更新后的 Hosted 验证。
