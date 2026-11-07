# OUT-01-A01-P05：Requirement固定版本Output Source读取前置

- 日期：2026-11-04
- 状态：PASS_SCOPE_LIMITED（实现及云端验收完成）
- WBS：OUT-01-A01-P05
- 依据：CR-OUT-005、冻结API-03/DM-04、OUT-01-A01-P04结果

## 编码前检查

- 阶段：Phase 2；输出纵向链仍是Pilot关键缺口。
- Owner数据：RequirementVersionRow按project_id和requirement_version_id存不可变版本，version_state与内容字段在Owner模块内读取；version read repository已有project scoped查询，但常规接口要求requirement_id。
- 授权：ProjectAuthorizationService定义REQ_VERSION_GET当前成员策略。新内部Owner调用须用调用方actor_id及project_id同事务重新授权，不信任Output层传来的authorized布尔。
- Output契约：TrustedOutputContextResolver当前要求返回精确FixedSourceVersion DTO；Requirement不可直接依赖Output。组合根负责把RequirementOwner DTO映射为Output DTO。
- 数据：不新增表、不新增migration、不传出客户正文；ProjectId/VersionId必须在SQL查询同时限定；审查状态原样输出，不推断审批。
- 验收：单测覆盖授权、固定版本/Project隔离与状态保真；PG18验证跨Project/未知Version拒绝及合法读取；A17 packaged flow运行同步Owner smoke。全部仅synthetic、hosted runner。
- 不包含：Output模板、Policy、Plugin启用/执行、Output worker/Artifact或用户界面。本项通过不代表OutputRequest可以生产生成。

## 剩余编码前事项

实现具体Owner DTO字段白名单与错误码时保持Source Owner语义；先实现Requirement内部Port，再由entrypoint组合根做适配，禁止跨业务模块引用对方ORM。实现后再更新本文件验收结果。


## 实现与验收结果（2026-11-04）

- 增加RequirementVersionReadService内部读取方法，按ProjectId+固定RequirementVersionId查询；Owner重新执行REQ_VERSION_GET授权并保留版本审核状态。
- 新增SQL repository受控字段投影以及EntryPoint组合适配器，Requirement模块不依赖Output模块。未新增ORM表或migration。
- 新增Owner读取单测、组合适配单测及A17 packaged PG18烟测。提交188a2ca0036acedfeb95b77883446a2315c90255的hosted run [41684956861](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41684956861)全13/13 jobs通过；A17结果包含专项PG18 marker，校验精确版本/Project、APPROVED状态及非成员拒绝。无Migration/API改动，仅synthetic hosted Windows Server 2025；本项PASS_SCOPE_LIMITED，不是Win11设备验收，也不代表Output模板/Policy/Plugin或Output Create已可用。
