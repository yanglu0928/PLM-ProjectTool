# PLG-01-A01 结果：PluginPackage 不可变元数据持久层

- 日期：2026-11-03
- 状态：PASS_SCOPE_LIMITED
- 分支：feature/p51-a33-launcher-checksum-recovery
- 源码提交：b310488d02322884a1b09f307040553b3d8f2fad
- GitHub hosted 验收：[run 41566771430](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41566771430)，13/13 jobs success

## 实现

- 新增 Plugin 模块 ORM：Plugin package、manifest operation、manifest dependency、package verification 四类持久记录。
- 增加 Alembic revision `20261102_0222`，parent 为 `20261102_0221`；新增约束、索引、写入关闭与防截断保护，不改写 Gate 2 冻结提交 `64cdf09` 或历史 migration。
- 验证记录追加保存；包身份/签名摘要/manifest 元数据不可变；没有增加私钥、API Key、明文口令或客户内容字段。
- 增加 ORM/schema 合同测试与 PG18 hosted 验收脚本；P01 Output migration 的 head 检查同步到 `0222`。

## 云端验收证据

- 后端全量测试与 wheel 构建成功；前端测试/typecheck/build 成功。
- GitHub hosted Windows Server 2025 运行器上的 PostgreSQL 18/pgvector 临时数据库生命周期检查成功；PLG schema verifier 在隔离临时库验证空库迁移、降级/重升、约束和历史数据保护。
- 同一运行中的父包候选组装、A35 有界交接、A17 PlanVersion Edge/HTTPS/PG 与 A34 替换/显式恢复步骤均成功。
- 全部临时验证位于 GitHub hosted runner 的 D 盘临时目录；没有在用户本机/C盘运行代码。

## 首轮失败与修正

Hosted run `41420708454` 后端套件有两项 ORM metadata 预期失败：历史元数据清单没有列出新增四表；新测试把 schema 前缀用于 SQLAlchemy metadata key。先写入本任务前置记录，再修正预期集合与表名筛选。后续修正提交在 run 41566771430 全链通过。

## 限制

本项仅完成 Package 不可变元数据结构及 PostgreSQL 迁移验收。没有实现/验证真实签名、可信发布者信任源、包导入/安装、启停、子进程执行、Plugin API 或 Output registry 对接；数据库写入仍由未安装 Owner 关闭。未验证 Windows 11 实机、Gate 3、Pilot 或正式 Release。该结果不得解释为插件已可信或可执行。
