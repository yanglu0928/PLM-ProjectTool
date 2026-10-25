# CR-SOL-022：SectionVersion 显式 StructuredSpec 固定声明

日期：2026-10-23。状态：`APPROVED_FOR_IMPLEMENTATION`（按用户 `CR-EXEC-001` 持续授权，待逐片客观验收）。原 Gate 2 冻结提交 `64cdf09` 保留，不追改。

## 来源与冲突

冻结 DM-05/API-04 要求 SectionVersion 固定 `structured_spec_refs`，StructuredSpecVersion 固定 `section_refs`。现有 SectionVersion CREATE/ORM 缺前者，Spec 输入却强制引用已有 SectionVersion。若双方均强制在创建时指向同一精确版本，将出现无法通过独立冻结 POST 建立首对不可变版本的循环；把未提供 Spec 字段解释为“无需专项”也会把旧草稿/AI 输出误认为人工作出的业务决定。现有 `CR-SOL-003` 已将 Spec 引用列为 SOL-06 后补任务。

## 方案比较与选择

- A（选择）：有向版本谱系。SectionVersion 在创建时固定结构化 Spec 使用声明：`UNDECLARED`（兼容旧请求/历史、不可通过 Spec 维）、`NONE_REQUIRED`（操作者显式选择并给出理由，待 Review）或 `FIXED_REFS`（非空的既存 SpecVersion 集合）。SpecVersion 仍固定其创建时已有 SectionVersion 来源；不要求两个不可变版本互指同一版本。正式 Solution 输出独立固定已批准 Outline/Section/Spec 集合并校验适用性/Trace。新可选请求字段实现冻结 `structured_spec_refs`，缺字段不推定空集合。
- B（拒绝）：创建 SectionVersion 后原地追加 Spec 关联；破坏不可变快照/内容指纹/首响与审计，升级和回滚风险高。
- C（拒绝）：新增同事务循环批量创建 API 和预分配双 ID；改变冻结业务 API 流程、增加跨 Aggregate 写耦合，Pilot 关键路径更慢。

## 差异、安全与兼容

路径、角色、License、既有请求成功形状和旧版本内容保持。新增请求字段为可选加法；旧客户端仍可创建 DRAFT，但没有声明的版本在 `spec` 维维持 UNAVAILABLE，正式送审前需创建新版本作显式声明，不能静默回填历史。`NONE_REQUIRED` 的理由与操作者/版本/Audit 一起固定，仍需正常客户 Review，不是自动批准；非空 Spec 只能接受受权、同项目、适用 Section 的固定版本，当前资格由后续 Owner 验证。任何已经存在的 Spec 历史不自动关联或改变状态。

## 迁移、回滚与验证计划

- 在当前 Alembic head 后新增 SectionVersion 根的声明状态/有限理由字段与固定 Spec 引用表，复合 FK 约束同项目 SpecVersion 与 SectionVersion、序号/去重及历史 DML/TRUNCATE 防护。旧行默认 `UNDECLARED` 且无引用，不更改旧内容摘要和首响。Schema 先闭锁，不直接开放写口。
- 空库和有数据 PostgreSQL 18 升级、空引用表降级重升、ORM drift、跨项目/错 Spec/重复/顺序/NULL 负例、历史 UPDATE/DELETE/TRUNCATE 拒绝。升级前先备份；有任何新声明/引用历史时主动拒降，回滚优先关闭新入口并向前修复，不删除历史。
- 后续分片分别验收输入规范与新旧客户端兼容、同事务 Owner/指纹/幂等/Audit、现时 Spec 资格/撤销、实际 Win11/PG/浏览器、Review/正式输出。未验真相不写 PASS；不把合成批准当客户确认。

## 剩余风险

非空 Spec 与后续 Section 新版本的适用性需要精确规则；Spec 自身的固定 SectionVersion 来源可能在后续版出现后不再是最新，不能用简单“当前最新”否决永久历史，但也不能忽略实质漂移。该分支须独立设计/测试并保持失败关闭；不阻断明确无需专项的受控章节版本。Section/Outline Review、Plan、正式信任与 Gate 3/Pilot/发行仍未通过。
