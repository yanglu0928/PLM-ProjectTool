# SOL-01-A04-P08-P03-P02：GLOBAL Reference 人工确认只读预览 Owner

日期：2026-10-09；结果：`GLOBAL_REFERENCE_PREVIEW_OWNER_PG_PASS`，内部受权预览/隔离 PG 合成验证；公开 Preview HTTP/真实人工操作仍未开放。

编码前检查：Phase 2；输入冻结 API-04、CR-SOL-006/007/009 与 P08-P02 合同；前置 P03-P01 写时指纹栅栏通过。仅涉及 Solution 预览应用服务，不新增 Schema、公开 API、权限或依赖。验收为当前 DeploymentAdmin Session/CSRF/License 与真实 GLOBAL 来源 Proof、最小有序 Document 根/版本和 Evidence 身份/来源指纹投影、只读不提交；异常/跨 Scope 失败关闭。

新增 `ReferenceDeidentificationPreviewService`，在同一只读事务中先检查管理员，再检查 License 和当前 Document/Evidence 来源 Proof。仅返回服务端计算的 32 字节来源指纹、有序 Document 根/版本、有序 EvidenceId、UTC 预览时刻；不返回正文/路径，也不调用确认、Audit、幂等或事务提交端口。该指纹是后续 Confirm 的旧预览栅栏，不是可由客户端授权的来源证明。

验证：定向单元 4 通过/3 子例，覆盖无写入、越权/License/畸形/投影错配；Win11 隔离 PG18.6/真实 Auth/Document/Evidence/私有文件证明预览与直接来源指纹一致，确认表行数不变，既有确认/物理篡改/撤销回归通过；后端全量 `3327 passed, 3 skipped, 4909 subtests passed`。首轮 PG 验证脚本把预览断言误置于故意篡改文件之后，来源按设计拒绝；移至篡改前复验通过，生产行为未因该修正改变。

无数据迁移或部署动作；回滚可移除未挂载的预览服务。公开 HTTP、Windows 显式组合、前端人工点击、正式 License/目标账户、Server 2025、20 并发/Gate3/发行未验；Debian 13 依用户指令跳过。TraceLink：CR-SOL-009/P08-P02 → P03-P01 写时栅栏 → P03-P02 Owner/单元/PG/全量 → P03-P03 HTTP。
