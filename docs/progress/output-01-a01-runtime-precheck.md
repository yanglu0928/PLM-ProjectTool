# OUTPUT-01-A01 Runtime Precheck

## 任务边界

- Phase：2 Platform Core
- WBS：`OUTPUT-01-A01`
- 类型：编码前检查；本任务不修改运行时代码、数据库、冻结合同或生成制品。
- 基线：Gate 2 冻结的 `DATA-MODEL-CANDIDATE-V1`、`DB-SCHEMA-CANDIDATE-V1`、`API-CONTRACT-CANDIDATE-V1`；DM-05 Output 语义与 API-03 Output 路由。
- 目标：核对 OutputRequest/Artifact 物理持久化 Owner、固定来源授权/Trace、下载/交付边界及当前实现，拆出第一个可独立验收的实现切片。

## 编码前检查

|检查项|结果|证据/说明|
|---|---|---|
|冻结语义与接口|PASS|DM-05 定义 OutputRequest、固定 `source_version_refs`、不可变最小 Context、幂等/重新生成及 Artifact 发布条件；API-03 定义 List/Create/Get/Cancel/Regenerate 与 Artifact List/Get/Download/Restrict/Revoke。|
|冻结物理 Root 映射|PASS|SC-01 映射 `OUT-01 → out_requests` 及 context snapshot/source/evidence owned collections，`OUT-02 → out_artifacts` 及 validation results；SC-02 分配 `OUT-01=R-PRJ`、`OUT-02=M-PRJ`；SC-03 有 `Q-OUTPUT-01` 与 generation-live 幂等索引要求。|
|运行时字段映射充分性|LIMITED|DM-05 给出语义字段及状态，但冻结 Schema 仅确定 Root/table/profile/owned collections 和关键查询，不是完整列级 DDL。首个迁移前仍需列级映射、FK/删除语义、状态约束及索引清单；以实现设计记录落实，不改变冻结 Root、Scope 或 API。|
|当前 Owner/ORM/Migration|PASS（缺口已确认）|当前无 `modules/output`，无 `out_requests`、`out_artifacts` ORM/Repository/Owner/API/UI 或 Output migration；Alembic 当前 head 为 `20261026_0210`。|
|Document 发布边界|PASS（需内部 Port）|Document 现有上传 Repository/Commit 对 `GENERATED_ARTIFACT` 做拒绝保护。Output 必须使用受控内部 Document 登记 Port，不能复用/放宽普通上传路径；本 WBS 不实现该 Port。|
|授权、项目隔离与 Trace|PASS（实现前置）|API-03 要求每次请求按 Project Authorization；固定来源版本须在创建时校验同项目、可读且不可变。TraceLink 支持 `owner_module=output` 与 `OUT-02`，须在制品发布事务中建立 GENERATED_FROM 关联；无权下载不得暴露本地路径。|
|异步执行依赖|PASS（边界已识别）|Output 执行链依赖 Job/Outbox、lease/fencing、PluginExecution、暂存结果校验和 Document 内部登记。仅建请求表不能宣称生成可用；缺少任一依赖时 Create 不得返回虚假的可执行/成功状态。|
|当前消费者影响|PASS（隔离）|Solution Structured Spec、Section Input、Plan Input 中已有“Output Owner 未安装”失败关闭分支。不得在本 WBS 顺手放宽消费者或伪造 Artifact。|
|数据库变更验收义务|PASS|正式 ORM/Migration 必须包含 up/down、空库/有数据升级、约束/索引漂移及恢复验证；不允许原地改已发布 revision。|
|Secret/客户数据外发|PASS|只检查本地代码/合同；未访问 Secret 文件、未发送客户资料。|
|工作区保护|PASS|保留既有未跟踪 `.tmp/`；C 盘 Temp 未执行删除或迁移。后续构建临时文件使用 D 盘项目工作区下的专用临时目录。|

## 最小实现切片与依赖

推荐首个编码 WBS：`OUTPUT-01-A02`，仅建立 OutputRequest 及其不可变 Context/source/evidence 持久化骨架（ORM、Repository、Alembic migration、up/down 与 Schema 对照验收）。其列级映射必须在该任务编码前先从冻结语义和现有 Root/Profile 规范逐字段列明；若发现必须改变 Root、Scope、授权含义或 API 行为，则先记录正式 CR，不静默调整。

后续依赖顺序：

1. `OUTPUT-01-A03`：受权 Create/List/Get Owner；固定源版本与 Project 授权、幂等收敛、Audit/Trace、失败关闭；只有 Job/Outbox 实际装配可用时才发布可排队 Request。
2. `OUTPUT-01-A04`：Plugin/Worker 执行、取消/重试及 fencing；不得把子进程隔离宣传为任意代码安全沙箱。
3. `OUTPUT-01-A05`：内部 Document GENERATED_ARTIFACT 登记 Port、完整性校验及不可变 OutputArtifact 发布/Trace。
4. `OUTPUT-01-A06`：项目授权下 Artifact 读取/下载/限制/撤销和浏览器/Windows 组合验收；端到端生成链另行验收。

本分解是实现排序，不改变 Gate 2 冻结的外部合同。当前没有需要调整冻结基线的已识别偏差；列级设计若超出既有语义，按持续授权先记录 Change Request/风险/迁移回滚与验证计划，再实施。

## 风险与验收重点

- R1：跨 Project 固定来源引用可导致越权或串项目；来源读取和创建必须在同一授权上下文中校验，数据库查询必须按 ProjectId 约束。
- R2：幂等键与 live generation 唯一性存在并发竞态；用数据库约束作为最终裁决并做并发负例。
- R3：Document 的公共上传保护被绕过；只允许最小权限的内部登记 Port，且必须校验 FileObject、DocumentVersion、Hash、MediaType、PluginExecution 与 Request 一致。
- R4：状态/API 早于异步依赖装配造成“已受理但永不执行”；请求不得在 job/outbox 原子持久化保证缺失时返回 202。
- R5：失败重试覆盖旧制品；重新生成创建新 generation 和新 Artifact/DocumentVersion，历史不可覆盖。

## 验收结论

`OUTPUT-01-A01 = PASS_SCOPE_LIMITED`。已明确 Output 冻结语义、API 路由、Root/profile/owned-table、Project 授权、Trace、Document 上传隔离与当前代码缺口；未发现必须改动冻结 API/Root/Scope 的事项。由于列级物理映射尚未明确，下一任务必须把列级映射检查作为编码前置，不得直接猜测 ORM/DDL。

本任务未运行代码测试（无代码变更）；未修改 Migration/API；Pilot、Gate 3 和正式 Release 状态不变。
