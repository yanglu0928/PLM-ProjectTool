# PRT-01-A09-A07-P02-A02：Version VALIDATE 持久幂等

日期：2026-10-08。结论：`PRT_01_A09_A07_P02_A02_VALIDATION_IDEMPOTENCY_PASS`。
下一项：`PRT-01-A09-A07-P03` Version/Review 五项 HTTP。

## 实现

- VALIDATE现在要求规范幂等键，请求指纹固定Project、Prototype和PrototypeVersion；相同Key不能换目标。
- 首次验证重证Template、Requirement和Artifact当前事实，把受控、有序issue集合与Version原状态写入
  不可变AuditEvent，并由通用幂等receipt引用该AuditEventId；Audit、receipt和业务事务原子提交。
- 同Key同载荷重放通过Actor、Project、Version、Action、Owner、对象类型和状态不变条件精确读取首次
  Audit证明，不重新计算漂移后的结果，也不重复Audit；新Key才重新观察当前事实。
- 严格解析`PRT_VALIDATION_PASSED`或`PRT_VALIDATION_FAILED_TRA`子集；缺失、错绑、重复/乱序或未知
  issue编码均失败关闭。

## 偏差、兼容与回滚

DEC-1057原计划新增Schema0135保存ValidationResult。实施前对账发现Capability、Requirement、Survey等
模块已经使用并验证“不可变AuditEvent + 通用receipt”的同类模式。DEC-1058据此取消重复结果表，避免
Audit与新表双写同一事实；冻结HTTP路径、控制位和业务语义不变，Schema head保持0134。

本项无Migration、公开API、依赖、Secret或外发。停止A07-P03 Router装配即可关闭外部入口；已有
Audit/receipt作为不可变历史保留，不执行破坏性回滚。

## 验证

- 定向13项覆盖首次成功、证明漂移后的原结果重放、新Key重算、Key跨Version冲突、畸形Audit失败关闭、
  缺CSRF和读取分页；全部通过。
- Windows 11 / Python 3.13后端全量3199项通过、3项按既有环境条件跳过；compileall和
  `git diff --check`通过。
- 开发wheel含1225项，SHA-256
  `ab75ed0f68f07e45dd61a04918aef0a5479cda4ab1dbccc2c990d9b07b86f1c5`，包含新的Prototype验证
  Audit source。真实PostgreSQL 18 HTTP组合留A09-A09统一验收。
