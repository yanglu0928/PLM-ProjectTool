# SOL-01-A04-P08-P06-P03：GLOBAL Reference Create 隔离实库验收

日期：2026-10-09。结果：`GLOBAL_CREATE_HTTP_PG_PASS`，限定 Windows 11 一次性 PostgreSQL 18.6/pgvector、真实 Session 仓储、ASGI 和合成私有 Document/Evidence/文件；不是客户资料人工脱敏核查、正式 License 或生产部署验收。

编码前检查：依 P06-P01/P02、冻结 API-04、CR-SOL-006/007/009/010 和现有 GLOBAL 确认 Owner；本项只增加验证脚本及追溯，无生产代码、Schema、权限、依赖、公开合同或迁移变化。临时 PG、文件及测试身份均一次性创建，结束后停止与清理；不触碰客户方案库。

验收：无确认时 Create 404 且零写入；合成管理员经 Preview→显式 Confirm 后 Create 201，`GLOBAL/REFERENCE_ONLY/DRAFT`，安全响应、ETag/Location/Trace、版本绑定同源指纹与确认 ID、1 Root/1 Version/1 DocumentRef/2 EvidenceRef/1 Create Audit；原 Key 重放仍 201 且无重复写入，变更名称 409。错误 Origin/CSRF 403，错误来源类别 404，物理文件字节篡改 503，确认到期或撤回后新 Key 404，License 拒绝 403；失败均未增加 Reference 行。已有真实来源夹具随后继续通过 Document/Evidence 撤销/漂移回归。

首次执行的测试预期将无确认写成 503，实测现有合同按 `RESOURCE_NOT_FOUND` 返回 404；仅修正脚本预期并复验退出 0。该差异不改变生产错误映射，也不将合成声明称为真人确认。

兼容/升级/回滚：仅验证资产，无数据升级。可移除脚本回滚，不删除产品中的确认/Reference/Audit/收据历史。P06-P04 仍需 Windows 显式生产组合及开关审计，P06-P05 前端入口另验；正式账户/License、真人核查、Server 2025、20 并发、Gate 3/UAT/发行仍未通过，Debian 13 按用户指令跳过。

TraceLink：冻结 API-04 → CR-SOL-006/007/009/010 → P06-P01/P02 → 本 P06-P03 → P06-P04/P05。
