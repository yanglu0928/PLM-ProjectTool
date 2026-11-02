# CR-OUT-001：Output 持久层增量扩展

- 日期：2026-11-02
- 状态：记录完成 / 按持续授权实施 / 待托管验收
- 工作分支：`feature/p51-a33-launcher-checksum-recovery`
- 关联 WBS：`OUT-01-A01-P01`
- 依据：Gate 2 冻结 API-03、DM-04、DB Schema V1；CR-EXEC-002；用户持续自主执行授权

## 问题与原因

当前仓库已有冻结的 OutputRequest、OutputContextSnapshot 与 OutputArtifact 语义/API 契约，但数据库迁移止于 `20261026_0210`，未有 Output 模块或 Output 持久表，Pilot 纵向链在计划输出阶段中断。为按冻结契约推进，需在冻结 DB Schema V1 后追加 OUT-01 物理结构增量，不覆盖原冻结提交 `64cdf09`。

初始编码前检查将其误分类为“计划内物理落地”而判定无须 CR。提交代码后再次按 AGENTS 基线规则审查，确认新增物理表仍是冻结 DB Schema 的增量变更。本 CR 明确记录这一流程偏差；代码尚未部署、未写入任何业务数据库，修正工作继续留在功能分支。后续任务均先记录正式变更，再实施。

## 变更范围

本次只新增：
- `plm.out_context_snapshots`：Project 归属、固定来源引用、最小上下文快照与 SHA-256 指纹；
- `plm.out_output_requests`：固定模板/来源/策略/插件操作/上下文引用、输出类型、生成代次、幂等键和请求状态；
- 递增 Alembic revision `20261102_0220`、ORM 注册及相应 schema/迁移契约测试。

新表默认由数据库关闭写入，直到后续 OutputRequest Owner WBS 安全接管。当前不添加 Artifact 表或公开接口，不接入 Job、Plugin、Document、Trace 或 AI 运行流程；不更改冻结 API、业务角色、Scope、License 或既有数据。

## 兼容与影响

- 既有表与数据不重写；从 `20261026_0210` 追加迁移。
- 公开 `/api/v1` 无变化；没有现有应用代码消费新表。
- 输出格式缩写采用 `DOCX/PPTX/PNG/JPEG`，与 Phase 9 及 API-03 输出格式验收措辞对齐。
- 请求和快照间使用 Project 复合外键；输出代次和项目内幂等键具有唯一约束。
- 新表闭锁写入，因此本代码切片不开放尚未完成授权、同事务审计和业务幂等的路径。

## 风险及缓解

|风险|缓解|
|---|---|
|固定引用 JSON 与 Context 不一致|写 Owner 在同事务校验并绑定指纹；目前表不可写，Owner 未完成不能开放|
|后续 Job/Plugin Owner 未就绪|关联仅保存冻结契约引用，本 WBS 不启动 Job/Plugin；后续按各自 Owner 接线|
|回滚误删正式制品/来源|当前禁止降级离线执行，检测到任何请求/快照即拒绝降级；已部署后必须先核对引用及保留策略|
|新约束与既有元数据清单不一致|更新严格 ORM metadata inventory，并运行后端/托管 PostgreSQL迁移验证|

## 验证与首次发现

GitHub Actions hosted run [41399398488](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41399398488)：
- 后端运行 3,853 项测试，仅 `test_platform_audit_auth_and_license_tables_are_registered` 失败；失败原因是其显式历史表白名单未包括本次新增的 `out_context_snapshots` 与 `out_output_requests`。
- 前端测试/构建、Python 基础环境、PG18 sidecar、A50 Edge job 均成功；依赖后端通过的父包与 A17 后续 jobs 按工作流规则跳过。
- 该失败是测试清单遗漏的客观证据，不代表数据库迁移已经完成 PostgreSQL 升降级验收；该验收仍须由后续通过的托管完整链证明。
- 无客户数据、无外部 API、无本机运行、无生产数据库操作。

## 回滚与恢复

功能分支尚未合并/部署时，回退本 CR 关联提交即可恢复先前分支状态。迁移 `downgrade` 会检查两表无历史数据后才删除本 CR 新建的表、索引与触发器；存在数据则失败关闭，不做自动清理。原 DB Schema V1 内容和 Gate 2 冻结提交始终保留。

## 执行与关闭条件

按用户 2026-09-24 的持续授权自动实施，无需逐项确认。CR 只有在严格 metadata inventory、定向测试、全量后端回归、托管 PostgreSQL 空库/现有库升级、降级/再升级以及安全扫描均有证据后，才能关闭为 `VERIFIED`；未完成前保持 `IN_PROGRESS`。不构成 Gate、Pilot 或正式 Release 放行。
