# CR-OUT-004：Output生产Registry接线顺序与编码前核查

- 日期：2026-11-04
- 状态：PRECHECK_IN_PROGRESS
- 来源：CR-EXEC-002纵向链优先级；OUT-01-A01-P03受限验收结果；PLG-01-A08受限完成

## 背景与证据

OUT-01-A01-P03已实现Fail-Closed TrustedOutputContextResolver与四类Port，但结果明确指出它们尚未接入PostgreSQL生产Registry；Requirement/Solution/Plan固定版本Adapter、Template Registry、Policy Registry及Plugin Operation Registry仍缺。PLG-01-A08提供受签名验证门控的Plugin package及operation metadata持久化，但正式publisher key manifest为空，且未建立运行时启用/安装事实。

因此P03只能证明Resolver边界，不能创建真实OutputRequest。A08 smoke中的合成publisher key仅供临时PG18测试，不是生产信任源，也不授权安装或运行插件。

## 决定

- 新增单一前置子任务OUT-01-A01-P04，先审查四类Port对应Owner/ORM/授权、不可变版本和信任/启用事实，再选择一个能以真实已持久化事实安全实现的最小Port。
- 不预先认定四类Registry已有实现；不从AI建议、manifest声明或测试夹具推定正式配置。若关键事实不存在，将记录阻塞与替代顺序，然后转向可独立完成的Source Owner Adapter。
- 当前仅做源码/合同核查，不改冻结API、数据模型或Schema，不新增migration，不写业务代码。

## 影响、风险与回滚

- 对客户运行行为无影响。若直接把VERIFIED当作安装/启用会扩大基线并允许未经配置的代码进入生成路径，因此任何信任/启用语义不明时必须保持Fail Closed。
- 当前无数据迁移；本前置记录可直接撤销，不改变产品数据。
- 用户已授权按CR-EXEC-002自主选择WBS切片；本记录只明确顺序与验收边界，不扩大产品Scope或真实信任授权。

## 验收与下一步

核对源码和冻结契约后，列明四类Port各自可信数据Owner、Project隔离/固定版本/审核检查、缺失事实与候选实现；选择一个单一WBS建立编码前CR，加入定向单测、isolated PG18、后端全量/wheel、Secret检查与托管包验证计划。此核查未完成前不编码，不把Output纵向链、Pilot、Gate或Release标为可用/通过。
