# PLT-MAINT-01 维护模式停写栅栏

日期：2026-09-30；Phase 2；A01 设计与编码前检查。

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A01 可靠停写栅栏设计；后续 A02 Schema、A03 Platform Port、A04 生产 API、A05 双 Worker、A06 跨进程验收。
输入基线：ADR-007/008、Gate2 原冻结 `64cdf09`、DOC-03-A03-P04-P04 阻塞证据、现有 Windows 生产组合、Audit/Parser Worker。
前置任务：Parser 独立进程合成 OCR 内部验证已通过；正式维护停写之前不得执行生产清理/升级。涉及模块：Platform、Audit/Parser Worker、Document 上传窗口和生产入口；设计阶段不改代码。
涉及实体：拟新增单行维护状态与 Audit 操作历史，须正式 Migration。涉及 API：不破坏 `/api/v1`；生产请求外层 admission，普通业务响应合同保持。涉及权限：仅受控部署账户启停维护；普通用户不能切换。
验收标准：CR 记录证据、方案比较、完整覆盖矩阵、迁移/回滚与真实并发验收门槛；任何未覆盖入口保持 BLOCKED。风险：会话级共享锁跨长 OCR/上传窗口增加数据库连接占用，需容量/超时测试；部分旧进程绕过门禁会使证明无效。

结果：A01 设计已登记 `CR-PLT-004`，尚无代码、Migration 或并发证据；A02 及整体 PLT-MAINT-01 均未通过。下一步先做 Schema 及最小状态源，不能用本设计文档解开 DOC-03 停写前置。

## A02 编码前检查：持久维护状态 Schema

当前 Phase：Phase 2 Platform Core。当前 WBS：PLT-MAINT-01-A02。输入基线：`CR-PLT-004`、Gate2 原0050增量链、Platform 现有 Base/Alembic。前置 A01 设计已登记；真实 admission 尚未实现。
涉及模块：Platform ORM 与 PostgreSQL18 Migration 0051；只新增一个系统单行状态表。涉及实体：维护状态/版本/数据库时间，不复制业务 Job、Upload 或 Audit。涉及 API/权限：无 `/api/v1` 与角色变化；写状态的正式命令属后续 A03。
验收标准：空库及含既有业务数据从0050升至0051，单行 RUNNING/v0；ORM parity、约束/不可删除和合法单步状态版本转换；原始数据不变；全新未使用状态可 down/re-up，有维护历史时 down 拒绝且原状态保留；Python3.13 全量回归、wheel。
风险：此表单独不能阻止并发请求/Worker，直到共享/排他锁与所有生产入口挂载后才可作为停写证明。只改 Schema，迁移前需人工备份并停写；回滚仅无历史的隔离环境可测试，生产不承诺自动降级。

结果：A02 Windows11 隔离 PostgreSQL18 Schema PASS。新 `20260930_0051` 增量只增单行 `plm.plt_maintenance_state`，默认 RUNNING/v0；数据库约束及触发器拒绝第二行、跳版/同态更新、DELETE/TRUNCATE，允许 RUNNING→MAINTENANCE→RUNNING 每次版本+1；有历史的 downgrade 拒绝且状态/迁移版本保留。空库 head→0050→head、有原 Auth 数据0050→head、ORM parity、后端全量1657（3既有跳过）、wheel 含 ORM/Migration PASS。隔离数据库删除、PoC PG 恢复停止；未迁移生产库。没有 admission Port、生产路由或 Worker 接线，此单行状态绝非维护静止证明，整体 PLT-MAINT-01/DOC-03 前置/Gate3仍未通过。
