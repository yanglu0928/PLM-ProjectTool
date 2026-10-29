# CR-EXEC-018：使 Windows hosted 验证证据输出兼容 ASCII 控制台

- 日期：2026-10-29
- 状态：托管验证有效，后续 A17 继续至独立 SourceUnavailable 夹具问题
- 来源与证据：hosted Windows 2025 run 40810209866 已确认 CR-EXEC-017 的 Caddy 路径映射可继续执行，A17 报告 `Packaged Workflow external HTTPS GET/START/replay/CSRF/conflict/Audit PASS`。随后 `validation/sur-07-a08-survey-version-packaged/verify.py` 在 `json.dumps(..., ensure_ascii=False)` 的打印处抛出 `UnicodeEncodeError`：runner stdout 使用 CP1252，无法编码中文字符，导致上层 A17 提前中断。业务探针已执行但完整 A17 尚未通过。
- 问题：托管 Windows 默认控制台编码不能表示含中文的验证 JSON，验证证据打印异常遮断后续集成步骤。
- 方案比较：A. 将该验证证据 JSON 改为 ASCII 转义（`ensure_ascii=True`），保持内容可由 JSON 解码还原；B. 改整个作业环境的 Python/stdout 编码。选择 A，局部调整输出，不影响业务请求、断言或全局环境。
- 基线差异：仅变更验证工具日志的 JSON 序列化选项，不改变产品运行时、API、持久化、合成业务数据或验收含义。
- 影响与风险：日志中的中文以 Unicode 转义显示，机器可读内容与断言数据等价；回滚为恢复 `ensure_ascii=False`。
- 验证计划：托管 Windows 2025 运行 A17 全链；确认不再发生 UnicodeEncodeError，并继续到 Edge、PostgreSQL 状态、服务/临时目录清理和候选完整性结果。未达全链 markers 不关闭 A27。
- 执行边界：只用 GitHub hosted runner，不在用户本机或 C 盘执行项目代码；不外发客户资料或 Secret。

- 托管复验追加（run 40811860032）：ASCII 转义后未再出现 CP1252 UnicodeEncodeError；A17 继续通过 Workflow HTTP/CSRF/Audit 探针并进入 SectionVersion synthetic fixture，随后暴露新的 Document 固定来源路径问题。CR-EXEC-018 修正本身在该 hosted 执行路径中生效，A27 仍未完成。
