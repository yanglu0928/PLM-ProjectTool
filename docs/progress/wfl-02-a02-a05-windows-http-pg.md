# WFL-02-A02-A05：Windows显式写组合与真实HTTP/PostgreSQL闭环

日期：2026-10-06
状态：`WFL_02_A02_A05_WINDOWS_HTTP_PG_PASS`

## 范围与实现

本项只解决已验证Stage Transition Router的Windows生产组合和真实边界验收。新增组合工厂将
Session/CSRF、ProjectManager、License、Handover双Owner、Transition仓储、Audit和持久幂等
接入同一生产图；仅`--platform-write`模式挂载。默认App、登录模式和只读平台模式保持关闭。

没有修改Schema/Migration、冻结DTO、角色、依赖、Secret或外发策略。回滚为撤销生产组合的
Router注入；已经提交的不可变Transition历史不得删除或改写。

## 验证结果

- 组合与生产入口定向`38`项通过，覆盖缺依赖失败关闭、只读不构造和显式写模式构造。
- Windows 11/PostgreSQL 18.6独立临时库以真实Session、完整Handover/Review/Document/
  Evidence/Capability/AI/Action事实及两项当前Checklist PASS运行HTTP。
- 默认路由`404`、错误Origin`403`、客户端非空Gate`422`、首次迁移`200`、同Key原结果
  重放`200`；强ETag从`v3`推进到`v4`。
- 数据库后验为唯一Transition、两个固定Gate、一次`WORKFLOW_STAGE_TRANSITIONED`审计和
  一条完成回执，Workflow为`SURVEY/v4`，HANDOVER完成且SURVEY激活；隔离资源已清理。
- 后端全量`2779`项通过、`3`项既有条件跳过。开发wheel`1013`项，包含组合及HTTP模块，
  SHA-256 `5bfc9fac85fedb89d1a85d2cc7fb1728693fbe3c0cb1510a89d3ccd90aa1bc38`。

首次真实脚本运行使用的既有测试venv未包含`pgvector`，迁移导入前即退出，未形成通过证据；
补入项目正式Python 3.13依赖路径后，以新临时数据库完整重跑并取得上述结果，未新增依赖。

## 边界与下一项

本项不代表前端、浏览器、其余阶段Owner、WAIVED、20并发、正式信任、Gate 3、UAT或发行通过。
下一项`WFL-02-A02-A06`实现Stage Transition安全前端客户端与显式确认页面：使用服务端空Gate
语义、当前Workflow ETag和单一持久操作身份，不在浏览器生成或展示可信Gate UUID。
