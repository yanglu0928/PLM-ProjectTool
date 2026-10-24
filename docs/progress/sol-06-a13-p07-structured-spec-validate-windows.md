# SOL-06-A13-P07：Windows 结构化专项 VALIDATE 装配与真实 HTTP/PG

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_VALIDATE_WINDOWS_HTTP_PG_PASS`；完成 Windows 11 显式读写模式装配与真实 ASGI/PostgreSQL 验证，不表示 UI、正式信任或其他平台验收已完成。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A13-P07`|
|输入基线|A13-P03～P05 Repository/评估器/Service，A13-P06 默认关闭 HTTP；既有 Windows Solution 组合与正式登录模式开关|
|前置任务|完整后端验证链与可选 Router 均已通过，可复用现有 Document/Evidence/Requirement/Section 生产适配器|
|涉及模块/实体|Windows Solution composition、production login composition；无 Schema 变化|
|涉及 API / 权限|仅 `include_secret_write` 显式读写模式装配 `SOL_SPEC_VALIDATE`；默认/登录专用/只读模式不注入|
|验收标准|依赖缺失拒启动；真实 Session/CSRF/License/项目角色/来源/PG 下首报、重放、漂移、历史版本、隔离和错误映射成立；收据/Audit 一一对应|
|风险|只读模式误开放写入口；组合漏接某个 Owner；恢复 Evidence 后忽略 lock version 漂移；测试 200 被误报为 ready；正式环境依赖不全仍启动|

## 实施与验证

- 新增 `create_windows_structured_spec_validate_router`，使用真实写 Session、License、项目授权、Requirement、Section/SectionVersion、Document、Evidence、共享锁验证 Repository、当前事实评估器、通用收据与 Audit；任一依赖缺失或构造异常统一拒绝启动。
- `production_login` 仅在显式写模式创建并传入 Router；默认、登录专用与只读组合变量保持 `None`。现有 create/revise/list/get、Section VALIDATE 和其他路由不变。
- Windows factory/生产组合/HTTP 合同定向：58 项、94 子例通过；首轮定向命令引用了不存在的测试文件，改为仓库实际 production login 合同路径后完整运行，未修改产品逻辑或验收项。
- Windows 11 / 可弃 PostgreSQL 18.6：真实 Session、License、Project、Requirement、Section/Document、Evidence 与 SOL-06 v1/v2；默认应用 404，显式 Router 首次 200 且 `valid=true/ready=false`，同 Key 保留首次观察、不同本次 Trace。正文/查询/Origin/CSRF/跨项目被拒；Evidence 撤回后新 Key 为 `UNAVAILABLE`，恢复后因 lock version 漂移 integrity 仍 `FAIL`；实施成员和历史版本报告准确；失效 License 返回 403。四条成功首次观察对应四条收据和四条 Audit，脚本退出 0，临时库/实例清理。
- 后端全量：`3725 passed, 3 skipped, 5817 subtests passed in 65.92s`。
- py_compile、`git diff --check` 通过。Python 3.13.15 开发 wheel：1408 个条目，Windows 与 production composition 各入包 1 份；SHA-256 `20720690b589155da4ab3ad6e1acbb14bc0c29315490c32104a3bfc4029852dd`。
- 无 Migration、外部 AI/网络、客户数据或 Secret 外发。

## 兼容、升级、回滚与遗留

本项只扩展 Windows 显式读写组合；无 Schema、冻结 API、角色、License 权益、依赖或旧数据变化。关闭显式写模式或撤 Router 传入即可停止新验证写入，既有 Audit/收据保留。开发 wheel 和合成 License/账户不代表 Pilot 或正式发行信任。

前端客户端、页面和 Edge 操作尚未实现。Trace、非空 Artifact 及非结构类型 Owner 缺口仍使 `ready_for_review=false`；正式服务账户、公钥、HTTPS/Vault/ACL/CA、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 与正式发行状态不变。

Next：`SOL-06-A13-P08` 实现前端 Session/CSRF/幂等客户端与固定版本详情验证入口，显示八维事实、类型检查和维护提示；不把 200、valid 或 DRAFT 表述为批准。
