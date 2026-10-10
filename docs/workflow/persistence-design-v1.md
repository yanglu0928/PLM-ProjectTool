# WFL-01 持久层设计 V1

日期 2026-09-26；版本 0.1.0.dev0；CR-WFL-002。当前为设计，不是已实现 ORM/Migration。

## 表与归属

|表|主键与归属|核心字段/约束|
|---|---|---|
|wfl_project_workflows|workflow_id UUIDv7；project_id→Project NO ACTION；unique project_id，unique(workflow_id,project_id)|workflow_version int>0；workflow_state 白名单；current_stage_key 可空；lock_version bigint>=0；created/updated_at UTC、created_by User FK；定义 fingerprint SHA256 32 bytes|
|wfl_stages|stage_id UUIDv7；(workflow_id,project_id) 复合 FK；unique(workflow_id,stage_key)、unique(workflow_id,stage_order)、unique(stage_id,workflow_id,project_id)|stage_key、gate_policy_ref ASCII CODE_64；order>0；stage_state 白名单；定义字段初始化后只读|
|wfl_stage_checklists|stage_checklist_id UUIDv7；(stage_id,workflow_id,project_id) 复合 FK；unique(stage_id)、unique(stage_checklist_id,workflow_id,project_id)|一个 Stage 一份 Checklist；实例定义版本/父关系只读；不复制业务正文|
|wfl_checklist_items|checklist_item_id UUIDv7；(stage_checklist_id,workflow_id,project_id) 复合 FK；unique(workflow_id,item_key)|item_key CODE_64；required bool；evidence/review policy refs CODE_64；item_state PENDING/PASS/FAIL/WAIVED；lock_version>=0。当前结果指针及追加事件在独立历史任务设计后接线|

所有跨 Root FK NO ACTION，不 cascade、不依赖 JSON 保存核心 Scope/状态。UUID、timestamptz(6)、text CHECK、bigint 类型与 SC-02 一致。项目授权依 ProjectAuthorizationService，不引入 RLS。未知定义版本必须拒绝，不能由用户自定义清单减项绕过 V1。

## 初始化与事务完整性

1. 一次事务插入 Workflow + 六 Stage + 六 StageChecklist + 十二 Item，引用固定 V1 配置，不插入通过结果。初态 NOT_STARTED/指针空、所有 Stage NOT_STARTED、所有 Item PENDING、锁版本 0。
2. 各实例保存定义 fingerprint 与固定内容；同项目并发初始化以 unique project_id 收敛并通过应用幂等返回同一实例，不创建第二份。
3. 多表完整性采用 PostgreSQL DEFERRABLE INITIALLY DEFERRED constraint trigger：提交时校验定义版本、完整 key/order/required/policy 集合、父关系、状态/指针。事务内部允许分步插入，不能提交半套结构。版本化 SQL 检查须自包含，Migration 不导入会变动的运行 Domain。
4. Workflow、Stage、Checklist 身份/定义不可改，删除拒绝；未来版本迁移另有明确计划，不能每次启动覆盖。支持发布 V2 不代表自动变更已有 V1。
5. 当前阶段解释采用 CR-WFL-002：NOT_STARTED 无 current；ACTIVE 有唯一 ACTIVE 或 BLOCKED 的 current，先前阶段 COMPLETED、后续 NOT_STARTED；COMPLETED 所有阶段完成，current 为 PLAN。不得同时出现 ACTIVE 与 BLOCKED 两个当前阶段。
6. lock_version 每次受控变更加一，非法终态复活拒绝。状态变更必须经过 Application 同事务历史/Gate/Audit；直接更新允许值本身不构成合法业务命令。

## 实施拆分及开放条件

- P02：四表 ORM、Migration `0030` 和结构保护、隔离 PostgreSQL 验证。暂不创建生产实例或开放写 API。
- P03：Project 创建/既有项目初始化的受控事务接线，幂等、权限、历史/审计；既有项目仅 NOT_STARTED，不能凭现有文档推断进度。
- WFL-02：成功 Transition/Gate snapshot 与 Checklist 记录历史持久层；失败 Audit 保留，成功历史追加不可变。
- Gate 应用层：从受权 Owner/Evidence/Review Port 获取固定版本事实，所有 required PASS/已批准 Waiver；没有 Port 不放行。服务原子更新实例与成功记录，不允许单纯客户端 PASS 绕过。
- HTTP：按冻结 If-Match/幂等/CSRF/PM/License 合同逐项接线。最后阶段完成、恢复/退回/定义迁移的未冻结操作另设计，不猜测。

## 验收矩阵

|场景|必要证据|
|---|---|
|空库全量升级/降级/再升|隔离 PostgreSQL 命令结果与版本；不只是离线 SQL|
|既有项目升级|升级前后 Project/成员/历史事实一致，不自动写进度|
|完整初始化/半套拒绝|提交成功及 deferred trigger 提交异常|
|跨项目/父对象漂移|真实复合 FK 拒绝|
|重复项目/阶段/key/order|真实唯一约束拒绝|
|未知版本/策略/required 改写|真实定义校验/只读触发器拒绝|
|状态/指针/乱序/双当前|合法事务成功，非法组合提交拒绝|
|非空降级/历史删除|明确拒绝，不破坏已有 Workflow 数据|
|ORM parity/回归/wheel|实际执行结果及包内内容检查|

所有结果目前待执行；Windows Server 2025 尚未运行，Debian 13 按用户要求暂不验证。纯 Schema PASS 不等于 Workflow、Gate 3 或程序包交付 PASS。
