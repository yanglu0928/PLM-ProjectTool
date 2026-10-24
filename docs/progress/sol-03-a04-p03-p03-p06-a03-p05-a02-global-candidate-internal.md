# SOL-03-A04-P03-P03-P06-A03-P05-A02：GLOBAL 候选内部最小扫描与现时证明

日期：2026-10-09。结果：仅内部组件和 Win11 隔离 PG18.6 验证通过；项目成员 HTTP/授权 Owner 尚未开放，不能标记完整 P05 或 Gate PASS。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / 本任务；输入 Gate 2 API-04、CR-SOL-018、DEC-1152/1153、0158 发布账本、已验 ReferenceUseProof。
- 前置：管理员发布/撤回 Owner、HTTP 及 Windows 显式写组合均已在隔离环境验证；旧 GLOBAL 数据未回填发布。
- 单一问题：在不复用管理员读投影的条件下，从原始 GLOBAL 根有界扫描，只交付同版已发布且当前可用的最小候选。
- 模块/实体/API/权限：仅 Solution application/repository 与测试；读取现有 Root、Version、Publication；不新增 API、权限策略、Schema/Migration 或依赖。项目授权及签名游标留 A03。
- 验收：未发布/撤回不可见，发布同版最小标签可见，现时 Reference/Document/Evidence/确认按既有证明端口重证；过滤后空页仍保留原始根游标；不输出原名/来源指纹。
- 风险：过期来源、历史修订、空页分页及证明失败。仓储只返回最小投影，证明失败逐项隐藏；仓储异常整体拒绝，内部层不独立授权，后续 Owner 先验 Session/License/项目资格后才能调用。

## 实施与验证

新增 `GlobalReferenceCandidateCatalog` 和 `SqlAlchemyGlobalReferenceCandidateRepository`。仓储每页最多扫描 100 个原始 GLOBAL 根并按根 ID 前进；仅根当前 `ELIGIBLE`、最新同版 `PUBLISH`、有效固定版本进入待证候选。Catalog 在调用者事务内以 `ReferenceUseProofService` 重证固定版本、人工资格、Document/Evidence 与有效脱敏确认；输出 DTO 只有根/版本 ID、管理员审定标签、版本号和资格状态。证明失败的候选不出现在项目页；即使可见项为零，仍按扫描过的根推进。无管理员会话复用、原始名称或客户来源投影。

定向单元 3 通过/3 子例；Win11 隔离 PostgreSQL 18.6、真实合成文件/Document/Evidence/确认与管理员发布 Owner 脚本退出 0：未发布不可见、发布后仅标签可见、当前人工资格限制后立即不可见、撤回后仍不可见，第一页未发布根导致空结果但可继续到第二页已发布根。验证源夹具之后另自测物理文件篡改、Evidence 撤权和确认撤销；本项未把这些夹具结果扩称为候选服务的独立负例。Alembic `command.check` 无新升级操作，保留既有索引表达式/计算默认值警告。后端全量 3486 通过、3 跳过、5362 子例通过。

兼容/升级/回滚：无 Migration/API/角色/依赖变化；内部组件未挂载，删除该组件可回滚，发布事件/Audit/收据历史保留。下一项 A03 必须先实现项目 Session/License/PM-IM 授权与签名游标，再考虑外部 HTTP。正式目标服务账户、Server2025、浏览器/性能/Gate3 均未验证；Debian13 实机依用户指令跳过。

TraceLink：Gate 2 API-04 → CR-SOL-018 → DEC-1152/1153 → 0158 发布事件 → 本内部只读扫描 → A03 授权 Owner/游标 → A04 HTTP。
