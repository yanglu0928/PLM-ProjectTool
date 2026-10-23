# SOL-05-A04-P11-P02：SectionVersion StructuredSpec 闭锁 Schema

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`SCHEMA_PASS`（仅闭锁结构，Owner/API 尚未开放）。

## 编码前检查

|项目|结论|
|---|---|
|Phase / WBS|Phase 2 / `SOL-05-A04-P11-P02`，仅处理数据库契约|
|输入基线|Gate 2 冻结 DM-05/API-04、CR-SOL-022 的 `UNDECLARED/NONE_REQUIRED/FIXED_REFS` 有向版本语义；历史 head 0177|
|前置|SOL-06 固定版本表、SectionVersion 根及复合键存在；P11-P01 已完成冲突与迁移决策|
|模块/实体|solution / SectionVersion 根声明、固定 SpecVersion 引用表|
|API/权限|本项不开放 API 或 Owner；新列与新表先闭锁，旧请求及权限保持|
|验收|ORM/Alembic 一致；空库和有数据升/降/再升；约束、闭锁、跨项目、重复、漂移负例；旧内容指纹/首响不变|
|风险与回滚|旧行只能是 `UNDECLARED`；任何新声明/引用存在时拒绝降级；独立 PG 验证不得使用客户库|

本项不会把新声明变成已确认业务事实；后续 P11-P03/P04 才负责 API 与 Owner 同事务写入。Gate 3、Pilot、Release 维持未通过。

## 实施与验收

- Alembic `0178` 和 ORM 新增三个根字段、封闭状态检查及固定 SpecVersion 引用表；复合 FK 同时固定 SectionVersion/SpecVersion 的 ProjectId，唯一键阻止同版本重复序号或同 SpecSeries 重复固定。
- 旧 SectionVersion 自动为 `UNDECLARED`、零引用；既有内容指纹和冻结首响保持不变。新增根声明及子表 DML/TRUNCATE 均闭锁，不能把旧草稿升级为可送审事实。
- 独立 Win11/PostgreSQL 18.6 临时实例：空库升/降/再升、有旧行升/降/再升、ORM drift、旧指纹/首响、闭锁、空/非法声明、跨项目 FK、序号/重复键、两类新历史拒降均通过；合成夹具并非客户数据或真实 Review。
- 定向 7 项通过；后端完整回归 `3890 passed, 3 skipped, 6023 subtests passed`。数据库验收脚本退出 0；Alembic `check` 无新操作（保留既有 pgvector/operator-class 与计算默认值警告）。

兼容性：旧 CREATE 路径和响应不变。升级不需回填业务判断；回退仅在无任何新声明/固定引用时允许，若后续 Owner 产生新历史应关闭入口并前滚修复，不能删史。下一项 `P11-P03` 处理可选请求/响应契约及旧版本反读，仍不得把 `UNDECLARED` 解释为无需专项。
