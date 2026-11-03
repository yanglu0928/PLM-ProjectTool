# OUT-01-A01-P04：Output 生产 Registry 接线编码前检查

- 日期：2026-11-04
- 状态：PRECHECK_IN_PROGRESS（本文件只登记问题与证据；尚未允许编码）
- 阶段：Phase 2 / Windows 11内部Pilot纵向链
- 依据：CR-EXEC-002、冻结API-03/DM-04、OUT-01-A01-P01/P02/P03与当前STATUS

## 目标

核实并打通 TrustedOutputContextResolver 所依赖的真实Source、Template、Policy及Plugin Operation Owner/Registry。一次只处理一个明确Port；禁止以合成Registry、current/latest或未验证的enabled/trusted布尔值冒充生产业务事实。优先选择有现存持久来源且能在隔离PG18验证的Port，以增量任务逐项推进。

## 已知证据

- OUT-01-A01-P03已完成Fail-Closed application resolver，但其结果文档明确指出Resolver尚未接入PG注册数据；Requirement/Solution/Plan固定版本Adapter及生产Template/Policy/Plugin Operation Registry仍缺。
- apps/backend/src/plm_assistant/modules/output/application/resolve_context.py定义四类明确Port，缺依赖时拒绝构造；resolver读取精确UUID版本，不猜测current/latest。
- PLG-01-A08已PASS_SCOPE_LIMITED并可形成VERIFIED package与operation metadata，但正式包内publisher trust manifest为空；插件元数据验证不代表被启用、可执行或可供客户使用。
- 本核查的目标是选择一个存在可核验生产数据源的最小Port，不新增Schema/API，不运行插件，也不连接客户数据。

## 编码前必须完成

1. 读取各Owner真实ORM/authorization查询及冻结DTO；确定Source版本、Project隔离、review状态如何可信读取。
2. 检查Template、Policy、Plugin Operation是否有已冻结持久事实与版本/信任/启用状态。缺少事实时不得从manifest或AI建议推定为正式配置。
3. 选定一个单一Port作为下一WBS实现；建立对应CR，记录差异/风险/回滚/PG18及单测验收。若无安全可信来源，明确阻塞该Port并转到独立且可验证的Source Adapter。
4. 同步测试计划、Secret检查和GitHub hosted验证计划；不在用户本机或C盘运行。

## 安全与回滚

- 不外发客户正文、秘钥、真实插件包或客户数据库；使用合成身份、PG18 disposable库及托管runner临时目录。
- 冻结API/Schema若需变化，先做CR与兼容/迁移分析；此预检查本身不修改冻结合同或数据库。
- 当前结论：未选定唯一Port，不编码；不影响PLG-01-A08受限关闭。
