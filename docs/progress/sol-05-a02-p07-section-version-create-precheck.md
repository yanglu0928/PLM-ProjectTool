# SOL-05-A02-P07：SectionVersion 受权 CREATE 与写 Guard 前置核查

日期：2026-10-09。结果：`SECTION_VERSION_CREATE_PRECHECK_PASS`；仅代码/基线审查和 CR 实施计划，非 CREATE 功能 PASS。

## 编码前检查

当前 Phase 2 Platform Core、WBS `SOL-05-A02-P07`。输入 Gate2 冻结 DM-05/API-04、CR-SOL-003、0138 以及 P01～P06 的内部证明；这些足以做受权写入设计，但不足以直接开放写入。涉及 Solution、Project 授权操作、SectionVersion/固定引用/首次响应收据、Audit/Idempotency；冻结 API `SOL_SECTION_VERSION_CREATE` 指定 PM/实施成员，201 DRAFT。此项不改程序、Schema/API 或权限。验收为识别全部未满足前置并形成可验证、可回滚的实施顺序。风险是先开 Guard 再补收据/权限、Artifact 裸 UUID 落库、或把 Document 来源可用误称 Review/Trace 完成。

## 现状证据

- `project.application.authorization.POLICIES` 只列 `SOL_SECTION_CREATE`，没有 `SOL_SECTION_VERSION_CREATE`；不能以邻近操作代替章节版本写授权。
- `20261008_0138` 创建版本及 Requirement/Evidence 固定引用三表，但 `guard_solution_section_version_foundation()` 拒绝全部 DML；无章节版本不可变首次 201 响应表。当前 head 可弃 PG 写拒绝直接断言已由 P06 复核。
- OutlineVersion 的 0155/0156 提供首响应表、原子收据、插入闭环模板，但其 Section/Requirement/Reference 规则不能原样复制给 SectionVersion。后者要核对 DocumentVersion 而非 Reference，并把 Evidence 现时证明留给真实 Owner。
- P06 组合仍只通过单元桩；Document/Requirement/Evidence 各上游和 P05 基底有独立证据，但真实同事务组合、权限、收据、Audit 回滚与并发尚未验证。OutputArtifact/StructuredSpec Owner 缺失，不能用 Artifact UUID 分支开写。
- 旧 0138 全量迁移脚本已不适配当前 0146/0148 的首响应闭环与不可降级历史。当前 head 要有独立 Guard/迁移验证，不能因旧脚本复跑失败而弱化正式约束。

## 执行顺序与门禁

1. `P08` 增补 Project-owned `SOL_SECTION_VERSION_CREATE` PM/实施成员操作及角色×项目负例，不开放入口。
2. `P09` 新增不可变 SectionVersion 首响应结果表、复合 FK/字段一致形状及闭锁 Guard；ORM+Alembic，空库/含既有 Section 数据升级、空表降级重升、drift 与非空拒降。
3. `P10` 仅在现存 SectionVersion/子表/首响应均空或经过独立审计迁移时开放三表 INSERT-only：父 Outline→Section 锁序、ACTIVE/同项目、DRAFT/无 Review、DocumentVersion 分支限定、连续版本/前驱、引用上限/ordinal 与延迟提交闭环、首响应匹配；UPDATE/DELETE/TRUNCATE 继续拒绝。回滚仅空表可逆，有历史时禁止丢数据；旧 0138 Guard 保留历史，不改写冻结提交。
4. `P11` 在真实 Session/CSRF、License、Project 授权及同事务 P06 来源证明后，预留持久幂等收据并原子写版本/固定引用/首响应/Audit；重放仅从不可变首响应取回。验证角色/错项目/撤权、Document 漂移、Requirement/Evidence 失效、并发同/异 Key、失败回滚与无孤儿引用。
5. `P12` 后再加可选 HTTP 与 Windows 显式装配、真实 PG/ASGI/浏览器回归；后续 VALIDATE、Review、Trace、Spec/Artifact 独立实现。201 DRAFT 不等于批准章节、覆盖或 Gate3。

以上为 CR-SOL-003 的后续实施切片，不改变冻结 API 路径/响应语义。生产数据若已通过异常途径存在 SectionVersion 行，必须先停受影响迁移、审计并制定保留历史的专门迁移；不得用 `TRUNCATE` 或手工删除绕过。即使 P08～P11 完成，正式目标账户/Server2025、质量/性能、UAT 与发行仍分别验收，Debian13 实机依用户指令跳过。

验证：静态逐项对照冻结 API、0138/0155/0156、Project 授权矩阵、P01～P06 代码与当前 head Guard PG 记录；本 P07 未运行新动态测试、不标功能 PASS。回滚为撤本次实施计划修订，保留前述历史证据。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-003/0138 → P01～P06 → DEC-1173 → 本前置 → P08～P12 → VALIDATE/Review/Trace → Gate3。
