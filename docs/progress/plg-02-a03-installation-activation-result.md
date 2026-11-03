# PLG-02-A03：按操作启用与Installation版本切换Owner验收结果

- 日期：2026-11-04
- 结论：`PASS_SCOPE_LIMITED`
- WBS：PLG-02-A03
- 变更记录：CR-PLG-008
- 业务代码提交：`df98f9b9258708c7c5d7168d0f3762299d2471ca`
- 最终验收提交：`d37a9eb4fbeefc0ba3650238173a41c83dea1832`
- 云端验收：[GitHub Actions run 41728983860](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41728983860)，13/13 jobs 成功

## 实现

- 新增内部 PluginActivationOwner 与 PostgreSQL Repository：只接受已安装、包 VERIFIED、最新兼容性证据仍匹配的 Installation；启用集合必须非空且为精确 Manifest 子集。
- 插件级事务锁、Installation/Package/操作行锁和 lock_version 共同保护同一 plugin 的版本切换；将冲突操作从旧 Installation 原子转给目标 Installation，旧 Installation 仍有其它操作时保持 ENABLED，否则变为 DISABLED。
- 对精确状态重放作无写入幂等处理；过期 lock_version、未声明操作、runtime snapshot不匹配或状态冲突均拒绝。
- 状态、owned EnabledOperation 现态、逐操作 Audit 和 history 同一 Unit of Work。0227新增只追加的 `plg_enabled_operation_history`，记录 operation、Installation/Package、动作、actor、trace、UTC及Audit FK；禁止 UPDATE/DELETE/TRUNCATE。
- 本项不增加公开API/默认服务组合，不做物理安装、不改变签名信任、不启动插件子进程，也不使Output Create可用。

## 托管验收

- GitHub hosted Windows runner；临时工作区位于 D:。全量后端3,937项测试、frontend tests/typecheck/build、backend wheel、Python embedded backend、Windows parent candidate均通过。
- 同run父包 PostgreSQL/pgvector smoke通过；空库/既有合成PLG事实迁移、0227 Owner守卫、关系约束、追加历史和安全降级边界由父包数据库流程验收。Evidence artifact `plm-parent-pg-smoke-4e0fd5920bc74bed9d4b55fe5d4afa90edc43e65`（ID 13277205559）。
- A17 packaged PlanVersion HTTPS/Edge/PostgreSQL flow为 `PASS_LIMITED`，验证包内20,161项清单并以D:临时环境执行；合成身份，不是Windows 11设备验收。Evidence artifact ID 13277375572。
- A34离线候选替换及显式人工恢复演练为 `PLT_PKG_01_A09_P51_A34_PASS_LIMITED`；失败候选隔离及手动恢复标记通过。Evidence artifact ID 13277525431。
- A35候选分片交接与A50 hosted Edge导航通过。
- 客户数据0、外部API调用0、生产数据库false、产品API/listener false、正式License trust未使用、正式安装false。

## 偏差与限制

- 首次hosted run 41726736924暴露父包PG验证器仍期待0226的17个总守卫；0227增加三个历史守卫，实际读回20。随后复核发现Owner写守卫数也从3变为4。两项断言先登记到CR-PLG-008，再修正并重跑。
- 最终run 41728983860对修正后的父包PostgreSQL冒烟、A17、A34及完整验证链全部通过。产品实现没有因该偏差而变更。
- 仅PASS_SCOPE_LIMITED：Owner未接入HTTP或默认组合；无真实安装适配器/目标服务账户DB身份，未验证PluginExecution、Windows 11实机、Gate、Pilot或正式Release。

## 下一项

PLG-02-A04：运行环境变化后的重验证、失败关闭及Installation生命周期Owner编码前检查。
