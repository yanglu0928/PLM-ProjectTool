# PRT-01-A07-A02-P01：PrototypeVersion Review 生命周期窄门

日期：2026-10-08。结论：`PRT_01_A07_A02_P01_REVIEW_LIFECYCLE_SCHEMA_PASS`。下一项：
`PRT-01-A07-A02-P02` Review Subject Owner 与终态消费。

## 实施结果

- 新增 Migration `20261008_0132` 与 `prt_version_review_state_results` 不可变结果表，固定
  `START / APPROVED / RETURNED / WITHDRAWN`、Review/Round、Actor、Root 强版本和批准指针前后值。
- 版本状态只开放 Review 所需窄迁移；`IN_REVIEW` 时禁止创建后续版本。`APPROVED` 必须把正式指针推进到
  该版本，可同时将旧批准版改为 `SUPERSEDED`；`RETURNED/WITHDRAWN` 必须保留原正式指针。
- 延迟提交闭包把 Version、Prototype Root、Review Kernel 的 `PRT-03 + PROTOTYPE_ALL_V1` Subject 与结果行
  联合验证，缺少任一组成、伪造锁版本、错项目/错版本/错Review或裸状态更新均拒绝。
- Migration 降级只允许无 Review 状态历史的库回退到0131；已有历史拒绝降级，保留向前修复路径。

## 验证与偏差

- Windows 11 / PostgreSQL 18.6 实测空库升级、0132→0131→0132、v1送审与批准、评审中创建拒绝、v2批准并
  SUPERSEDE v1、v3退回且继续指向v2、历史降级拒绝及 Alembic drift 无新增操作，标记PASS。
- 实施复核发现最初Root窄门未覆盖同名同指针的START/RETURNED锁推进，且Review闭包缺少Scope Decision
  指纹检查；均在首次正式实库验收前修正并补入联合闭包。未放宽业务规则，完整实库脚本一次通过。
- 定向22项/21 subtests；后端全量3137项通过、3项既有条件跳过、4684 subtests；compileall PASS。
- 开发wheel共1206项，SHA-256 `0464c7e03435da714325614111908415d4db76d49b5fa18dc88ff2528d802952`。

## 兼容、迁移与回滚

这是前向Schema增量，不修改冻结公开API、不增加依赖、无AI外发。升级前应备份并停写；无本项历史可降0131，
有历史时禁止破坏性降级，应继续前向修复。Server 2025未验证，不能由Windows 11结果外推；Debian 13按用户
指令跳过。P02前尚无Review Subject业务Owner，HTTP/前端、批准Trace、原子送审、Gate 3/UAT/正式发行仍待。
