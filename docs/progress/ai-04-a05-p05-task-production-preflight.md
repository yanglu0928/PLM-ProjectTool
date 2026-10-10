# AI-04-A05-P05：Task部署策略、Windows组合与执行前置

- 日期：2026-10-03
- 结果：PASS（Windows 11 / PostgreSQL 18.6；未调用外部Provider）
- 依据：CR-AI-014、DEC-715～719、冻结 `AI_TASK_CREATE/GET`

增加严格非敏感 `ai_task_policies` Bootstrap来源，将Task类型、Prompt模板、外发用途、Output/RAG引用和有界标量参数Schema固化为不可变进程快照；生产写平台只有在显式配置有效时才挂载Task创建，否则保持404。Windows组合复用真实Session、Project授权、Document Input Owner、当前Egress Authorization Owner、Prompt Owner、Audit、Receipt和PostgreSQL事务链。

执行前置只读取完整且不可变的Task/Prompt/参数/Job/Egress快照，并在同一数据库事务中重新验证当前Authorization、Provider当前配置和AVAILABLE Model。旧NULL快照、非PENDING Job、参数摘要漂移、过期/撤销授权或路由变化均拒绝。发现0070遗漏Task Policy版本后，按持续授权增加Schema0071 `prompt_policy_version` 并纳入形态/不可变守卫；旧历史不回填、不冒充已知事实。

验证脚本贯通0071空库up/down/re-up与有历史拒降、真实HTTP 201 Egress Preview/Authorize、202 Task创建/重放、执行准入、200撤销和撤销后403/准入拒绝；版本字段数据库不可改，默认App 404。定向50项、后端全量2153项PASS/3项既定跳过；开发wheel SHA-256 `32a3d4b414b2dec7bce36ea2b307f313833c7c62d6ebc9f795ccdc75bbb1b7e0`。

Compatibility：新增0071可空迁移列，不破坏旧Task读取；无依赖或Breaking URL。Upgrade：正式库备份停写后升0071，再配置受审Task Policy并重启写平台。Rollback：无版本化Task历史可降0070；已有历史拒绝物理降级，使用向前修复或受控备份恢复；移除策略并重启可立即关闭新Task入口。Known Issues：冻结Task GET安全投影、Worker最终payload/Invocation/发送前上限与撤销再验、正式Prompt内容准入/发行信任、Server 2025、Gate 3/UAT/交付包待完成。Next：`AI-04-A05-P06`。
