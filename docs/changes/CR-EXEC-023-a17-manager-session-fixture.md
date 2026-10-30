# CR-EXEC-023：向 A17 nested Requirement fixture 传递匹配的 Manager Session

- 日期：2026-10-29
- 状态：已实施，待托管验收
- 来源与证据：hosted run 40819285914 第二次 attempt 的基础全量测试通过；A17 已越过此前 Caddy、stdout、Document、Review 合同、CUSTOMER_MEMBER 角色及旧来源数量夹具，并输出 `P51_A17_SYNTHETIC_SECTION_OWNER_REVIEW_PASS`。继续到 `_approved_requirement_v2` 的真实 RequirementVersionCreateService 时，返回 `AUTH_ACCESS_DENIED`。A17 上游 Handover browser callback 刻意保留 unrelated observer client；A17 Section fixture 已单独通过生产 Login HTTP 建立匹配的 synthetic Manager token/CSRF，但该函数未返回凭据，调用处继续取用了遗留 `context['client']` 的 Session。
- 问题：nested Requirement 创建用错 authenticated ProjectMember Session，而不是当前 synthetic ProjectManager。
- 方案比较：A. 由 A17 Section fixture 返回其已验证的 manager token/CSRF，并将这对凭据用于 nested Requirement 写命令；B. 在 fixture 中伪造授权上下文或放宽 Requirement 服务角色检查。选择 A，沿用真实 production Login HTTP 产生的 Session，不改变产品授权。
- 基线差异：仅修复 A17 hosted验证中 Session 传递；不改产品授权、API、Schema、License 或安全配置。
- 影响与风险：复用的是本次 disposable database 的 synthetic manager Session；token 不写日志或文档，仅在进程内传递，session按数据库临时生命周期清理。
- 回滚：恢复调用上游 observer token；只影响 synthetic validation。
- 验证计划：hosted Windows 2025 全量复跑；确认 RequirementVersion 创建、Review、Outline/Section/PlanVersion Edge 与 PostgreSQL 状态通过，并满足进程停止、临时目录删除和候选 Hash 完整性 markers。否则 A27 不通过。
- 执行边界：只使用 GitHub hosted runner；不在用户本机或 C 盘运行项目代码，不外发客户数据或 Secret。
