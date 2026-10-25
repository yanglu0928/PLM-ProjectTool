# CR-SOL-020：SectionVersion 历史读取生产游标密钥升级前置

日期：2026-10-12。状态：P04 Windows 组合时识别运行兼容性差异并补记；未虚称此 CR 先于代码。依据用户 `CR-EXEC-001` 持续授权实施，不追写 Gate2 冻结提交 `64cdf09`。TraceLink：Gate2 API-04 → CR-SOL-003 → A03-P02/P03 → DEC-1184 → 本 CR → P04 → Pilot/Release 部署验证。

## 差异、证据与方案

原显式 `--platform` / `--platform-write` 不需要 `project-section-version-list-cursor-v1`。新增历史 GET/LIST 要求独立 HMAC-SHA256 密钥；当前 Windows 组合缺此密钥即拒绝启动并释放 Runtime，直接升级旧部署会增加启动前置。登录专用模式和默认应用不挂此路由。选用目标服务账户 Windows Credential Manager 中独立 32 字节 key，不复用 OutlineVersion、Section、Reference 或其他资源族密钥；生产代码只读取，不自动生成、覆盖或打印密钥。冻结路径/角色、Schema、历史数据和依赖不变。

## 风险、升级与回滚

升级前以目标服务账户安全供给密钥，建立独立加密备份，在离线测试中验证丢失/恢复旧游标；确认 Vault ACL、服务身份和恢复责任后再启用新版显式平台。密钥缺失、长度错误或错误账户会造成启动失败；轮换时丢失旧密钥会使既有游标失效，用户需重新从首页列表查询。失败时停止升级并恢复旧程序/配置，或撤除新增可选 Router 组合；不删除 SectionVersion 历史，也不以其他密钥顶替。密钥备份口令不得写入仓库。

## 验证门禁

P04 验证独立引用缺失失败关闭/Runtime 释放、当前账户临时密钥备份恢复、Win11 一次性 PG18.6 的真实会话/项目隔离/分页/详情/License/错误与后端回归。正式服务账户 Vault/ACL、HTTPS、公钥和 Server2025、离线升级仍未验证，不能因此判 Pilot 或 Release 可用；Debian13 实机按用户指令跳过。
