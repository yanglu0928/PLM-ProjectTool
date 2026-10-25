# PLAN-02-A04-P04-A04-P03-P04-S03-P03-A04：PlanVersion 固定快照读取

日期：2026-10-26。状态：`PASS_INTERNAL_WIN11_PG18_SYNTHETIC`；非Gate结论。

## 编码前检查

- 当前Phase：Phase 2 Platform Core。
- 当前WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A04`。
- 输入基线：Gate 2冻结 API-04 `PLAN_VERSION_GET`、`PlanVersionInput`及API-01成功/错误Envelope；A02原子写Owner和0188；A03 DRAFT创建HTTP。
- 前置任务：PlanVersion Schema、授权策略、Owner及A03创建路径在Win11隔离PG18合成环境已通过。
- 涉及模块：Plan Application/Infrastructure/API与Windows组合；不跨写Owner或Review状态命令。
- 涉及实体：固定PlanVersion、WBS、角色/条件、固定Requirement/Solution/Prototype/Evidence refs、FS Dependency、Milestone及Exclusion快照。
- 涉及API：冻结 `GET /api/v1/projects/{project_id}/plans/{plan_id}/versions/{plan_version_id}`；WBS独立列表页API留后续WBS。
- 涉及权限：有效Session、Origin host校验、License以及Project成员只读授权在数据库事务内复验；跨项目统一404；默认应用不挂载。
- 验收标准：固定三元组查询且不走current/latest；复原全部持久化的业务字段与固定版本ref；不输出数据库列、Storage Locator或路径；错误响应无内部细节；Win11/PG18实际HTTP复验默认关闭、成功快照及Project隔离。
- 风险：DB Schema没有Dependency/Milestone原始排序字段；为避免伪造写入顺序，读取端按固定的稳定键排序并记录L2决定。其他有ordinal的Owned refs按ordinal输出。`PLAN_VERSION_WBS_LIST`后续提供分页消费者入口。
- 迁移/回滚：无Migration。回滚只需从可选Windows组合中撤掉只读Router；不会改写数据。

## 实施结果

- 新增只读PlanVersion聚合Service/SQLAlchemy Repository，事务中完成Session用户、Project成员只读权限、License及固定Project/Plan/Version身份复验；只读快照包含状态/创建/Review/Supersedes身份及完整持久化输入快照。
- 明确投影 Approved Solution refs、WBS/条件/支持角色、Requirement/Solution/Prototype/Evidence refs、Dependency、Milestone和Exclusion；Storage Locator/内部FK/SQL没有进入HTTP DTO。查询按Project+Plan+Version三重限定，不因Plan归档删除历史可读性。
- 依冻结API新增可选GET及Windows显式组合；默认应用保持404。为ProjectVersion读取建立专属`PLAN_VERSION_GET`全项目成员只读锁策略。
- WBS按ordinal；其他原始关系缺少数据库序号的Dependency和Milestone稳定排序，不宣称恢复客户端提交顺序。Decision Log记录了该限制。
- Milestone-item关联批量查询，无每个Milestone额外SQL往返。

## 验证

- 定向Contract/权限测试：21 passed、875 subtests passed。
- Win11/隔离PG18真实HTTP创建+读取链和上游依赖脚本exit 0；固定版本完整字段读取、成员授权和跨Project 404通过。
- 全量后端回归：4131 passed、3 skipped、6183 subtests passed（66.77s）；`compileall`、`git diff --check`通过，变更文件Secret模式扫描无命中。
- 测试pgvector Windows二进制为非官方构建，仅存在项目外隔离运行时，不进入源码、安装包或客户运行环境。

## 交付边界

- 无Migration、无Breaking API、无写入/Audit状态变化。
- WBS分页列表、版本列表/比较/验证/Review、前端用户界面和OutputArtifact仍需独立任务。
- Win11隔离PG合成证据不代表真实客户/正式信任/Server2025/Debian13/Gate3/Pilot或正式Release。

## 文件

- `apps/backend/src/plm_assistant/modules/plan/application/read_plan_version.py`
- `apps/backend/src/plm_assistant/modules/plan/infrastructure/plan_version_read_repository.py`
- `apps/backend/src/plm_assistant/modules/plan/api/read_plan_version.py`
- `apps/backend/src/plm_assistant/entrypoints/windows_plan_version.py`
- `apps/backend/src/plm_assistant/entrypoints/api.py`
- `apps/backend/src/plm_assistant/modules/project/application/authorization.py`
- `apps/backend/tests/contract/test_plan_version_read_api.py`
- `apps/backend/tests/unit/test_project_authorization.py`
- `validation/plan-02-a04-p03-owner-transaction-pg/verify.py`
- `STATUS.md`
- `CHANGELOG.md`
