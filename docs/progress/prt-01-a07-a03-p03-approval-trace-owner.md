# PRT-01-A07-A03-P03：Prototype Approval Trace Owner

日期：2026-10-08。结论：`PRT_01_A07_A03_P03_APPROVAL_TRACE_OWNER_PASS`。下一项：
`PRT-01-A07-A04` 原子 `PRT_VERSION_SUBMIT_REVIEW` 业务编排。

## 实施结果

- 新增 `PrototypeApprovalTraceOwner` 与 PostgreSQL Manifest Repository；Owner在Review调用方同一事务重证
  当前Template、Document、Requirement事实，按固定顺序建立合法业务Version TraceLink，并写入0133 Manifest。
- APPROVED终态在Prototype状态结果落库后、Audit与幂等收据完成前接入Trace Owner；任何当前事实、Trace、
  Manifest或后验闭包失败均由统一Review事务整体回滚。RETURNED/WITHDRAWN不生成批准Manifest或TraceLink。
- 当前事实Validator新增严格事实投影，仅在原完整校验无问题时返回精确有序证明；未建立第二套授权或历史快照来源。
- 终态结果改为显式UUIDv7并由仓储返回，APPROVED后验检查同时重读状态结果、正式指针、Manifest和ACTIVE边；
  相同幂等键重放不重复生成边或Manifest。

## 验证证据

- Windows 11 / PostgreSQL 18.6隔离数据库跑通真实PROJECT Review：两次批准、首次批准同Key重放、输入漂移
  拒绝后恢复、旧版SUPERSEDE、撤回保留正式指针；两份Manifest、六条来源和六条ACTIVE边严格匹配。
- 故障注入在APPROVED终态首条Trace持久化处抛错，验证Review/Round仍为IN_REVIEW、PrototypeVersion仍为
  IN_REVIEW、正式指针和Root锁不推进，且终态结果、Manifest、TraceLink、幂等收据和Audit均未留下半提交。
- 定向单元12项、后端全量3153项通过，3项既有条件跳过；`compileall`、Alembic drift和`git diff --check`通过。
- 开发wheel包含1212项，SHA-256
  `343e2067f36ff05bafcfe71d835a7e600810799b33dcb97962fb39a22e77992c`；在锁定依赖运行时中安装并导入
  `PrototypeApprovalTraceOwner`成功。

## 兼容性、偏差与回滚

无新Migration、公开API、依赖、Secret或数据外发；复用0133、现有Trace关系枚举及Review事务。停止注册
Prototype Review Owner可关闭新入口，但已提交的Manifest、TraceLink、Review结果和Audit必须保留并前向修复。
首次wheel隔离导入只安装`--no-deps`包，因预期缺少`cryptography`失败；加入项目锁定依赖运行时后重验通过，
未改产品依赖或降低验证要求。Server 2025未验证且不从Win11外推；Debian 13按指令跳过。原子Submit、HTTP、
Windows生产组合、前端、Gate 3/UAT和正式发行仍待。
