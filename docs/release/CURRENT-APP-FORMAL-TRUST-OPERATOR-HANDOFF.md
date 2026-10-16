# 当前应用发行信任材料：操作员交接与验收输入

日期：2026-10-02；对象：Windows 11 当前应用**非发行**候选 SHA-256 `eb2494be5de85b64a7ac64ce02112ed52454d0423d2a7e8406f120a126e14ed7`。本文件只说明正式信任缺口与安全交接，不含私钥、口令、API Key、证书私钥或客户数据，也不授权安装/发行。

## 当前可复核状态

- 仓库 `apps/backend/src/plm_assistant/modules/license/trust/product_public_key.json` 不存在；工作台 `tools/developer-workbench/private/license-signing-v1.pem` 不存在。当前候选内公钥资源也不存在。
- 以已哈希清洁解包的当前候选中 `payload/runtime/python.exe -I -B -m plm_assistant.entrypoints.verify_release_key` 运行，输出 `Release product public key unavailable.`、退出码1。按设计失败关闭，不能以 P47 的合成公钥/Vault 烟测代替。
- 正式服务账户、证书/DNS、离线备份、目标账户 Vault/ACL/SCM 恢复及真实 License 签发/导入没有与此候选绑定的验收记录。`C:\PLMTool` 正式根不存在，未进行正式安装。

## 需要操作员提供的证据，而不是让 AI 代保管的秘密

1. 由能独立保管强口令的开发者工作台操作员在交互终端执行现有 `tools/developer-workbench/license_key_ceremony.py create`；它只允许独占创建加密 Ed25519 私钥与本产品公钥清单。已有身份不得覆盖。私钥留在开发者工作台，**不提交 Git、不进客户包**。
2. 将加密私钥和口令分别离线备份，核实独立副本可由同一工具的 `verify` 模式与公钥匹配；记录执行人、日期、备份介质标识及校验结果，不在仓库记录口令或私钥正文。
3. 仅对公开的 `product_public_key.json` 做 Schema/本产品 `key_ref`/Ed25519 格式核验与安全扫描，然后依 CR-PKG-008 的新来源构建流程重新构建 wheel、前端及**新的唯一**候选；不得修改 P47 固定 ZIP 或把公钥后贴到旧包而沿用旧 SHA。
4. 在不外发秘密的前提下，用新候选包内 `verify_release_key` 和真实签发 License 的验签/机器指纹/可信时间链做目标账户验证；另核对 TLS 证书/DNS/信任链、服务账户 Vault/ACL、断电/重启与备份恢复。任何一步缺证据继续拒绝正式启动。
5. 产品级 LICENSE/NOTICE、Windows 11 正式新装/升级、Windows Server 2025、Debian 13、AI 质量、UAT及 Release Gate 仍需独立关闭；真实公钥存在也不自动使 `release_eligible` 变为 true。

当前项目可继续不依赖上述私钥/正式目标环境的业务开发及本地验证。需要对外发给操作员的只是本交接说明；不得在聊天、日志或 GitHub 收集口令/私钥。
