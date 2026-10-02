# AI-01-A05-P03-A01 Provider Test Job/Outbox 原子队列

日期：2026-10-02；状态：内部队列隔离 PG 验证 PASS；来源：冻结 API-03/DM-04、CR-AI-002；决策：DEC-20261002-641。

## 编码前检查

|项目|结论|
|---|---|
|当前Phase|Phase 2 Platform Core；Gate 2 已批准|
|当前WBS|AI-01-A05-P03-A01|
|输入基线|冻结 202 JobRef/Job-Outbox 至少一次；0055 测试结果 Schema；P01 固定探针|
|前置任务|P01/P02 已验证并推送；通用 Job/Outbox 表与 UoW 存在|
|涉及模块|Job application/infrastructure 的 AI Test 原子队列|
|涉及实体|现有 Job/Outbox；无新增 Schema|
|涉及API|无公开 API；A03 才接冻结 202 HTTP|
|涉及权限|队列是仅供已授权 AI Service 调用的内部端口，本项不授予管理员权限或外发|
|验收标准|同事务创建 Job/Outbox 对、同 submission 重放稳定、异绑定/单侧损坏失败关闭、回滚原子性；payload 无 URL/Key/正文；全量后端及 wheel|
|风险|队列本身不验证 Session/License/当前配置/Secret，也不启动 Worker；须待 A02/A03/P04 完成后才能对外开放|

## 执行结果

- Changed/Files：新增 Job application 的强类型 Provider Test 请求/JobRef/Queue Port，以及 Job infrastructure 的 PostgreSQL Job/Outbox 原子对 Repository；三项单元测试和一次性 PG 验证脚本。
- Migration/API：无新 Migration、公开 API 或运行时挂载；只在受信调用者持有的 UoW 中操作，不自行提交事务或启动 Worker。
- Tests：定向 3/3；Win11 隔离 PG18.6 验证同事务成对、同 submission 重放、异绑定/单侧缺失失败关闭、受控异常回滚、双线程并发仅一对及 payload 仅固定引用；后端全量 1941 运行/3 跳过；开发 wheel SHA-256 `748b6c8994d8ddd8e5712572a9a231ecaa7cc4eabf0a181b98009254ed0afd3a`，测试集群恢复停止。
- 兼容/升级/回滚：复用 0055 与既有 Job/Outbox，未改变冻结 API；撤内部队列调用可代码回滚，已提交 Job/Outbox 历史不物理删除。
- Known Issues：队列不证明管理员/License/当前配置/Secret/外发资格；A02 才加入同事务授权、收据、Audit，A03 才接 202 HTTP。P04 Worker、真实连通、三平台/Gate/UAT/可用包仍待。
