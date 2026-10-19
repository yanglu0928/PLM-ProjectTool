# SOL-06-A13-P03：结构化专项固定验证来源 Repository

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_VALIDATION_REPOSITORY_PG_PASS`；仅完成固定来源与系列最新身份读取，不表示现时业务事实、验证命令、HTTP 或送审已实现。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A13-P03`|
|输入基线|0161～0164 不可变专项根/载荷/四类引用，A12 系列 advisory transaction lock，A13-P02 报告合同|
|前置任务|完整 DRAFT 持久化、修订并发锁和验证报告纯合同均已通过，可实现只读固定来源|
|涉及模块/实体|Solution；StructuredSolutionSpec、Payload、Requirement/Section/Evidence/Artifact 固定引用|
|涉及 API / 权限|无；Repository 尚未由受权 Service 或 Router 调用|
|验收标准|按 ProjectId 隐藏对象；同事务稳定重建 v1/v2 输入和快照；给出系列最新版本身份；引用/载荷/版本损坏失败关闭；与修订写锁互斥|
|风险|读到半个版本；首版错误带入已分配 series 导致指纹漂移；历史版本误判最新；跨项目泄漏；验证与修订并发跨越两个状态|

## 实施结果

- 新增应用 DTO `StructuredSpecValidationSource`，绑定 P02 快照、经现有严格输入校验重建的固定正文/引用、系列最新版本 ID/版本号，并从绑定关系只读派生 `is_current_version`；结论不能由调用方伪造。
- 新增 `SqlAlchemyStructuredSpecValidationRepository.lock_source`：先以 `ProjectId + spec_id` 隐藏跨项目对象，再取得与 CREATE/REVISE 同命名空间的共享事务 advisory lock；多个验证可并发，独占修订必须等待当前观察事务结束。
- 同一事务共享锁读请求版本、系列最新版本、payload 及四类有序引用；项目/系列/类型、状态/Review 配对、版本链、顺序、重复、payload 结构与指纹任一不一致均失败关闭。
- v1 按原创建语义重建为 `spec_series_id=None / supersedes=None`，避免将数据库分配的系列 ID 错写进原请求指纹；v2+ 保留固定系列与前驱。Repository 只返回现时输入，不推断 Requirement/Section/Evidence/Artifact/Trace 或类型业务检查。

## 验证证据

- P02/P03 联合定向：40 项通过；P03 新增 7 项覆盖 v1 当前、v2 历史及全部固定引用、零 UUID、跨项目隐藏、payload/顺序/latest 损坏和 DTO 防伪。
- Windows 11 / 可弃 PostgreSQL 18.6：真实完整来源创建同系列 v1/v2；固定正文/Requirement/Section/Evidence 无损重建；v1 历史、v2 当前判定正确；跨项目返回空。第二验证事务在首个共享锁未提交时可完成，修订 Repository 的独占系列锁在提交前被阻塞、提交后恢复；脚本退出 0，临时库/实例按既有夹具清理。
- 后端全量：`3701 passed, 3 skipped, 5791 subtests passed in 80.66s`。
- py_compile：两个生产模块、单元测试和 PostgreSQL 验证脚本通过。
- Python 3.13.15 开发 wheel：1404 个条目，两个新增运行模块各入包 1 份；SHA-256 `ef64d61ef956772da4c6ed77d1c52395a0a25b97b42e0526318430338d33fa47`。
- 无 Migration、外部 AI/网络、客户数据或 Secret 外发。

## 兼容、升级、回滚与遗留

本项只增加未装配的应用 DTO、Repository、测试与验证脚本；无 Schema、冻结 API、权限、License、依赖或旧数据变化，无升级动作。可撤新增模块；任何已存在的不可变版本不得删除。开发 wheel 不是 Pilot 或正式发行包。

受权 Service、首次收据/Audit、HTTP、Windows 平台装配、页面/Edge 尚未实现。当前事实与类型业务检查尚未执行；SOL-06 Trace/Artifact Owner 缺口仍必须显式 `UNAVAILABLE`。正式信任、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 与正式发行状态不变。

Next：`SOL-06-A13-P04` 实现只读当前事实与类型检查评估器：按 Owner 独立形成 PASS/FAIL/UNAVAILABLE，空 Artifact 可证明通过、非空且无 Owner 保持 UNAVAILABLE，Trace 保持 UNAVAILABLE；不接授权、收据、Audit 或 HTTP。
