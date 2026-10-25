# SOL-03-A04-P02-P01：当前 Reference 资格与确认账本只读适配器

日期：2026-10-09。结果：`SOL_03_A04_P02_P01_CURRENT_REFERENCE_LEDGER_PASS`；仅 Solution 自有账本现时证明，Document/Evidence 物理来源现时证明和目录版本写仍未开放。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-03-A04-P02-P01。输入：Gate2 DM-05/API-04、CR-SOL-016/DEC-1139、0153 资格事件、P01 最小证明合同。前置已具备，无 Gate3 假设。
- 单一问题：在调用者同一事务中从 Solution 自有表锁定当前 ReferenceRoot/Version、最新资格事件及 GLOBAL 最新脱敏确认，拒绝旧版、跨项目、断裂的固定来源集合。
- 模块/实体/API/权限：Solution infrastructure 的 ReferenceRoot/Version/Event/DocumentRef/EvidenceRef/Confirmation；无新 API/权限策略。只能被未来已授权 Owner 内部注入，不能成为项目用户 GLOBAL 源浏览接口。
- 验收：隔离 PG 真实 PROJECT/GLOBAL 创建及人工资格后读取当前快照；错误目标项目/旧版本、RESTRICTED、确认身份与日期；无正文/定位输出。并发锁语义由 `FOR UPDATE` Root、共享锁 Version/Event/Confirmation 保证，实际竞争计时尚待 Owner 集成证明。
- 风险：账本现时不等于 Document/Evidence 文件现时；该部分留 P02-P02，不将本项称为完整来源验收。

## 实施与验证

`SqlAlchemyCurrentReferenceUseRepository` 锁 Root 并校验当前版本、根 `ELIGIBLE`、最新事件必须为同版本 HUMAN/ELIGIBLE 且锁号等于 Root；固定 Document/Evidence 按连续序号和声明计数闭合。`SqlAlchemyCurrentGlobalConfirmationRepository` 只读并共享锁定相同来源指纹的最新确认行，返回时效/撤回字段供 P01 服务失败关闭，不执行管理员 Session 认证，也不向项目端暴露来源。

`validation/sol-03-a04-p02-p01-reference-current-ledger/verify.py` 在 Windows 11 两个独立临时 PostgreSQL 18.6 库复用现有真实 PROJECT/GLOBAL 来源夹具：创建、人工资格、跨项目/旧版拒绝、RESTRICTED 拒绝、最新 GLOBAL 确认 ID/摘要/时效及既有真实来源夹具负例均退出 0。后端全量 3413 通过/3 跳过/5216 子例（2 条既有警告）。无 DB/Migration、公开 API 或依赖变化；撤掉未接线适配器即可回滚，旧资格历史不动。

下一项 `SOL-03-A04-P02-P02` 必须经 Document/Evidence 自有 Application Interface 实现不提权、不返回正文的现时来源/摘要证明，并与 P01 内部合同及本账本组合，测试撤回、字节变化、GLOBAL 确认过期和并发。未达到该证据前，OutlineVersion CREATE Guard 不开放。Gate3 仍 BLOCKED。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-016 → P01 内部合同 → 本账本适配器 → P02-P02 来源适配器 → OutlineVersion Owner。
