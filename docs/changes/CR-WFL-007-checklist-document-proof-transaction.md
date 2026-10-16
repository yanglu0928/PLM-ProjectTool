# CR-WFL-007：Checklist 当前事实证明复用调用方事务

- 日期：2026-10-06
- 状态：IMPLEMENTED / VERIFIED
- 触发 WBS：`WFL-01-A07-P07-A05`
- 关联：DEC-890～897、CR-WFL-005/006、HND-03-A04

## 偏差与原因

Windows 生产组合首次真实 HTTP/PostgreSQL 复验中，Checklist 写服务先通过
`SqlAlchemyProjectWriteAccess` 对 Session/User 加排他锁；Handover 当前事实证明随后调用
普通 `PrepareDownloadService`，它经 `DocumentReadService` 另开授权事务并请求同一
Session 的共享锁。第二事务等待第一事务，而第一事务同步等待第二事务，形成单请求
自锁。合同替身和只读资格验证均未覆盖“写事务持有排他锁后再验物理文件”的组合，
因此此前证据不能证明该生产链可运行。

## 采用方案

保留既有普通下载/解析读取行为，同时新增仅供调用方受保护事务使用的路径：

- `DocumentReadService.get_download_source_for_trace` 在既有事务中重验 License、Session、
  Project 与固定版本元数据；
- `PrepareDownloadService.prepare_in_transaction` 在同一事务内进行前后两次来源观测，
  物理快照仍按 size/SHA-256 验证；
- `DocumentParseResultReadService.read_in_transaction` 让原文与解析元数据的两次观测、
  解析字节校验复用同一事务；
- `DocumentFixedSourceProofService` 优先使用事务路径；旧 Port 替身仍保留兼容回退，
  生产组合必须提供事务实现。

不采用“降低 Session 排他锁”“跳过文件复验”或“给锁等待设置超时后重试”，因为这些
方案会削弱写授权/当前事实证明，或只把确定性自锁变成延迟失败。

## 影响、迁移与回滚

- 无 Schema/Migration、冻结 URL/请求 DTO、角色、依赖、Secret、网络或客户数据外发变化。
- 普通 Document 下载/解析 API 保持原入口；新增方法是内部兼容增量。
- 当前事务持有 Document/Project/Session 事实锁直至 Checklist/Audit/receipt 原子提交，
  锁范围符合 HND-03 的既定调用方事务语义。
- 回滚可撤 Windows Checklist Router 和新增事务方法，恢复默认 404；不得在保留该写路由时
  单独回滚事务复用，否则会恢复自锁。已产生的不可变 Checklist/Audit/receipt 保留。

## 风险与验证计划

- 风险：事务时间包含物理文件读取；已有限制 100 MB，且 Handover 资格本就要求固定字节
  复验。后续性能门需继续测量，不据本项推定 20 并发通过。
- 风险：CLOSED Action 仍依赖尚未接入的 Survey/Requirement Trace Owner；生产组合使用空
  Owner 注册表并失败关闭，VERIFIED Action 正例不受影响。
- 验证：事务路径单元正例、Windows 组合/入口合同、全后端回归、开发 wheel，以及 Win11/
  PostgreSQL 18.6 真实 Approved Handover/Review + Document/Evidence/Capability/AI +
  VERIFIED Action 的 HTTP PASS、重放、Audit、receipt 与漂移拒绝。

验证结果：相关定向 58 项、后端 2754 项运行/3 项既有条件跳过、0 失败；真实验证令牌
`WFL_01_A07_P07_A05_WINDOWS_HTTP_PG_PASS`；开发 wheel SHA-256
`5dcda0d86389bfcb71f4b7a783d67537720940d7393b4b91899a403b44d0ae29`。
