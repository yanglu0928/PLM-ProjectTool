# SOL-03-A04-P03-P03-P05-A02：OutlineVersion CREATE 真实 ASGI/PG

日期：2026-10-09。结果：`SOL_03_A04_P03_P03_P05_A02_OUTLINE_VERSION_HTTP_PG_PASS`；仅 Win11 隔离 PostgreSQL 18.6 与合成真实文件/Session，Windows 正式组合/UI 未接线。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / 本任务。输入：Gate2 API-04、DEC-1142、P04 双 Scope Owner、P05-A01 可选合同、0156 SQL Guard。
- 单一问题：证明 POST 不是仅 mock 合同，在真实 Session/Project/License/来源证明/PG 下能完成双 Scope 固定版本创建且拒绝路径不写。
- 范围：仅新增可重复运行的验证资产；无产品代码、API/权限/Schema/Migration/依赖变化。默认 App 不挂载路由。
- 验收：PROJECT/GLOBAL 各一套独立临时 PG 与实际 ASGI 请求，201/Location/Trace、原键重放、固定 Requirement/Reference、首响/Audit/收据；客户/跨项目/CSRF/暂停成员/License/篡改/确认到期拒绝与行数闭合；默认 404。风险：Requirement 上游 APPROVED/Review 身份为合成夹具，正式 License/Windows 服务账户未参与。

## 实施与验证

复用前项的真实 Reference/Document/Evidence 文件和 PostgreSQL 夹具，使用真实 `SessionService`、项目写访问、授权服务、`OutlineVersionCreateService` 与可选 Router。PROJECT：项目 PM 发起 v1，实施成员发起 v2，原键重放仍返回 v1，冲突键、客户角色、跨项目、错误 CSRF、暂停成员、拒绝 License 与文件字节篡改均拒；数据库核对版本链、固定 Requirement/PROJECT Reference、首响、收据和 Audit 的总数与序号。GLOBAL：独立项目 PM Session 仅引用已由 GLOBAL 管理员确认/置合格的固定版本，201/重放通过；确认到期后的新 Key 返回安全错误且不增加行，数据库引用 `source_project_id=NULL`。两套一次性 PG18.6 及上游来源夹具回归退出 0，默认应用同一路径 404。运行中仅有既有 Alembic/pgvector 告警，无产品代码修复需求。

兼容/回滚：仅验收脚本，可撤脚本不改业务数据或 Schema；已提交源码/证据须保留可追溯。下一项 Windows 显式装配及缺信任源失败关闭，再前端/UI/浏览器。正式生产公钥、目标账户凭据/ACL、Server 2025 和 UAT/Gate3 仍未通过，Debian13 实机依用户指令跳过。

TraceLink：Gate2 API-04 → DEC-1142/CR-SOL-016/017 → Owner/P04-A03 → P05-A01 Router → 本 ASGI/PG → Windows/UI。
