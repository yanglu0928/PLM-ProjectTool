# CR-PLT-003：Secret 管理 API 与生产装配时序调整

日期：2026-09-25；状态：AUTHORIZED_BY_CR-EXEC-001 / PREREQUISITES_IN_PROGRESS。

来源：上一任务暂定 PLT-02-A07 为 Secret 管理 API 接线，但当前应用仅暴露健康路由；冻结 API-01/API-02 要求登录安全、Session、CSRF、License、If-Match、幂等、Audit 和 write-only Secret。冻结架构将跨平台 SecretKeyProvider 与恢复放在 Release 安全设计；这会阻止提前公开可使用的 Secret 管理 API。

方案比较：A 先开放路由并使用合成 License/Key Provider，仅能得到测试表象，存在真实密钥误入与安全边界绕过风险；B 保留端点合同，先实现 Auth HTTP 与幂等/版本基础，并将生产 Key Provider 安全设计、备份恢复提前作为装配前置，再恢复 Secret API。选择 B。

差异与影响：只重排任务时序，不改冻结 `/api/v1` 路径、权限、Schema、产品 Scope 或三平台目标。生产 Secret 相关密钥来源和恢复比原 Release 时点提前设计/验证；尚未选择具体 OS 技术，不把 Windows 验证外推到 Debian。Auth/License/API 仍各自按模块任务实施，不在本 CR 中静默合并。

迁移与回滚：无数据库迁移。若前置设计失败，Secret 路由保持未公开；已实现的内部密文历史不可删除或改写。后续 Key Provider 方案必须另记选择依据、保护/恢复和失密失败关闭结果。

验证计划：AUT-03 登录 Origin/Host/限流/Cookie/CSRF 测试；正式 Key Provider 的 Windows 11、Windows Server 2025 与独立备份恢复测试；Debian 13 保持兼容目标，但按用户既有“暂不验证”指令登记未验证风险，不借 Windows 结果推定通过。另需 License 生产装配及 A07 端到端权限、幂等、If-Match、错误脱敏、审计与真实安装测试。缺项时不得虚报 A07/Gate 3/Release 通过。
