# SOL-01-A09：Reference Revise Windows 显式写组合

日期：2026-10-09。结果：`SOL_01_A09_REFERENCE_REVISE_WINDOWS_PG_PASS`；仅 `--platform-write` 生产组合接入 PROJECT/GLOBAL 修订路由，默认登录/只读模式不装载该 POST。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-01-A09；输入 Gate2 API-04、CR-SOL-013、A07 Owner/0150 与 A08 可选 HTTP/真实 PG，前置满足。
- 模块/实体/API/权限：Windows Solution Reference 工厂和生产组合根；仍为冻结 PROJECT PM/实施成员及 GLOBAL DeploymentAdmin；无 Schema/Migration、依赖、前端或 `/api/v1` 形状变化。
- 验收：仅显式写模式构造两个真实 Owner/Source/Receipt/Audit Router；缺任一依赖即拒启动；默认/登录专用/只读不开放 POST；Win11 一次性 PG 真 Session/ASGI/来源与全量后端回归。
- 风险：组合根若在只读模式误装写入口将扩大攻击面；工厂必须失败关闭，生产 `include_secret_write` 分支才赋值并传入 `create_app`。

## 实施与验证

新增两个 Windows Revise 工厂，复用已验证的 Source Qualification 组合，严格要求 runtime/Session/Origin/License/Audit/Document/Download/ParseResult；任一缺失/构造失败均抛 `ProductionSolutionReferenceStartupError`。生产组合根只在 `include_secret_write` 下实例化并传入 `create_app`。工厂定向 8 项、生产组合合同 37 项通过。Win11 一次性 PG18.6 PROJECT/GLOBAL 工厂各以实际合成 Session/Document/Evidence/私有文件、201/重放/拒绝链退出 0。

读模式存在同形 `GET /reference-solutions/{id}`，所以向 `:revise` 发送 POST 会由路由器返回 405，表示写路由未装载；完全默认应用没有该 GET 时为 404。写模式匿名/缺 Origin 为 403。以上是已验收的实际 HTTP 行为，不能把读模式 405 误报成 Revise 可执行。新增两个构造失败注入均证明写模式拒启动并释放运行资源、只读模式仍可构建。后端最终全量 `3375 tests OK, skipped=3`。完整目标服务账户/正式信任源生产启动仍未验证。

## 兼容、回滚与后续

不更改冻结合同或数据库历史；撤下生产组合中两个显式写注入可回滚公开写面，原版本/收据/审计保留。TraceLink：API-04 → CR-SOL-013 → A07/0150 → A08 → 本 A09 → UI/浏览器与 Eligibility。正式公钥/Vault/HTTPS、20 并发、Server2025、Gate3/UAT/可用程序包仍未验；Debian13 实机按用户指令暂跳过。
