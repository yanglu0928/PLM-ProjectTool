# SOL-05-A04-P11-P04：Spec 声明写 Owner 前置核查

日期：2026-10-23。状态：`SPLIT_RECORDED`；本片只核对实施顺序，不宣称新声明可写。

|检查项|结论|
|---|---|
|Phase/WBS|Phase 2 / `SOL-05-A04-P11-P04`；当前子片 `P04-P01` 为显式 NONE_REQUIRED 同事务写入|
|输入基线|冻结 DM-05/API-04、CR-SOL-022、已验 0178 闭锁 Schema 与 P11-P03 兼容 DTO|
|前置|旧 Section CREATE/读取/VALIDATE、SpecVersion/独立 Review 均存在；Spec 适用性/现时资格规则尚未证明|
|模块/实体|Solution SectionVersion 根、固定 SpecRef、首次响应/幂等收据、Audit、来源证明|
|API/权限|原 `/api/v1` CREATE 路径与 PM/实施成员、Session/CSRF/License 不变；新显式声明仅在同事务证实后开放|
|验收|NONE_REQUIRED 的人工理由进入请求/内容指纹、不可变根和 Audit；同 Key 首次结果重放、失败零写；旧请求/首响不变；Win11隔离 PG/HTTP/负例|
|风险|先开放 FIXED_REFS 会在 Spec 版本虽存在但不适用/已撤销时形成错误业务事实；先改首次结果会破坏旧回放|

核查结论：不能把 `FIXED_REFS` 与 `NONE_REQUIRED` 同时作为一片无条件开放。先在 `P04-P01` 只允许人工明确声明 `NONE_REQUIRED`，不改变旧请求；固定引用仍闭锁。`P04-P02` 在单独的 SpecVersion 适用性、同项目、固定来源/当前 Review 资格证明成立后才开放非空引用并建立闭合子集合。任何 `NONE_REQUIRED` 也只是申请者声明，不是客户 Review 或 AI 可代决策。旧版本 `UNDECLARED` 不能原地补填，须新建版本。

迁移/回滚：下一片只需新增 0179 触发器开放 NONE_REQUIRED 根 INSERT（0160 的现有 Requirement/Evidence/首响闭合仍保留），旧历史不回填；新声明历史存在后不得降回 0178，以关闭入口和前滚修复为先。首次 201 可保持冻结旧形状；GET/DETAIL 已另有只读声明。若后续需新增首次响应字段，必须独立验证旧 Key 逐字节重放及兼容，不得在本片暗改。方案分片已记 `DEC-20261023-1203`，不改 CR-SOL-022 的目标状态。
