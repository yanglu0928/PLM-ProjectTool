# AI-04-A06-P06-P05-P02 Claim 租约窗口与 SendProof 截止

日期：2026-10-03；状态：`INTERNAL_PASS`；依据 CR-AI-017、DEC-749/750、P05-P01。

`AITaskExecutionClaim`现在必须携带由同一Jobs短事务取得的数据库`observed_at`和当前`lease_expires_at`，两者必须为有时区有限时间且观察严格早于截止。PostgreSQL Claim Repository在原current Job/Lease/Attempt锁定后读取数据库时钟，并拒绝已经不足为有效Claim的Lease。

pre-send在解析出受信Route后，要求数据库观察时剩余Lease严格大于`route.total_timeout_seconds + 2秒`；SendProof的最迟发送开始时间取Authorization截止与`lease_expires_at-total_timeout-2秒`的较早值。Adapter仍在实际网络前用当前时间复核Proof，因此开始得足够早的有界调用才可进入网络；该窗口不是后台续租，也不宣称远端结果已知。

Tests：新增/调整Claim与pre-send边界测试，相关定向16项通过；Windows 11/PostgreSQL 18.6真实Claim→Envelope→Begin→pre-send链将Job/Lease同时缩至21秒，确认无法覆盖20秒Route+2秒余量而失败，续至120秒后成功。后端全量 **2231项通过、3项既有条件跳过、无失败**；开发wheel SHA-256 `930d37c319def3c3cbf928738f80e535cac2b924f75ff4aec4ad5eda26a8fc74`。首次合成夹具用两次数据库表达式更新产生微秒不一致，被Jobs守卫拒绝；改为同一显式截止时间写两行后新资源完整重跑，生产规则未放宽。

Changed/Files：AI Task Claim合同/PG Repository、pre-send proof窗口、单元及PG验证。Migration/API/Dependencies：无。Compatibility/Rollback：内部构造方需补两个时间字段；未装配Worker，无外部兼容影响或历史数据修改。Known Issues：安全余量固定2秒，后续Worker需用足够长Lease并在发送前双pre-send；Task专用Secret Audit与发送编排、响应Schema/终态、Server2025/Gate3/UAT/可用包仍待。Next：`AI-04-A06-P06-P05-P03` AI Task专用Secret访问审计作用域。
