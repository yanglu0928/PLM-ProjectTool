# PRT-01-A07-A04：PrototypeVersion 原子送审

日期：2026-10-08。结论：`PRT_01_A07_A04_SUBMIT_REVIEW_PASS`。下一项：
`PRT-01-A08-A01` RequirementPrototypeLink 前置核查。

## 实施结果

- 新增 `PrototypeReviewSubmissionService`，固定 `PRT-03 + PROTOTYPE_ALL_V1` 与
  `PRT_VERSION_SUBMIT_REVIEW` ProjectManager策略；Reviewer集合规范排序、先锁用户并由Subject Owner逐人重证。
- 在一个调用方UOW中完成Review创建、首Round启动、PrototypeVersion `IN_REVIEW`绑定、SubjectSnapshot、
  Review/Prototype Audit及持久幂等收据；请求前后都重验License，数据库死锁最多重试三次。
- 同Key同载荷从持久收据恢复首次Review/Round，并重新执行当前Subject访问校验；同Key异载荷冲突，不创建
  第二个Review。客户端不能以通用Review create/start两次调用替代该原子业务命令。
- 本项仅实现内部业务编排；冻结HTTP路径、请求DTO、Windows组合和前端仍按A09/A10实施，默认应用没有新入口。

## 验证证据

- Windows 11 / PostgreSQL 18.6隔离数据库：Document当前事实漂移时返回业务不合格，Review和收据均为零；
  恢复后原Key成功创建唯一Review/Round并绑定Version，重放返回同一身份，异载荷冲突。
- CustomerManager送审被资源隔离拒绝，失效License在事务前拒绝；Review/round/Prototype绑定、两条Review Audit、
  完成态收据和Alembic drift均通过，临时数据库已删除。
- 定向application/authorization 10项、后端全量3156项通过，3项既有条件跳过；`compileall`和
  `git diff --check`通过。
- 开发wheel包含1213项，SHA-256
  `fe215815e7ffaa372fa08b42035a39819918e6077e5c041aa19b92618745e557`；在锁定依赖运行时中安装并导入
  `PrototypeReviewSubmissionService`成功。

## 兼容性、偏差与回滚

无新Migration、公开API、依赖、Secret或数据外发；仅增加已冻结Operation的ProjectManager授权策略和内部
Application编排。停止装配该Service可关闭新送审，已提交Review/Version状态/Audit/收据必须保留。实库验收
首轮把既有Review审计动作误写为`REVIEW_ROUND_STARTED`，实际合同为`REVIEW_STARTED`；仅修正验收断言并用
新数据库全量重跑，产品代码未因此改变。Server 2025未验证且不从Win11外推；Debian 13按指令跳过。
Prototype A07完成；Link、HTTP/Windows组合、前端、Workflow、Gate 3/UAT和正式发行仍待。
