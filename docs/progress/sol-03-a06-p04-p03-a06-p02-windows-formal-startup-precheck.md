# SOL-03-A06-P04-P03-A06-P02：Windows受控组合正式启动前置核查

日期：2026-10-24。状态：`BLOCKED_BY_OPERATOR_CEREMONY`（仅正式启动验收阻塞；继续独立包任务）。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前Phase/WBS | Phase 2 / `SOL-03-A06-P04-P03-A06-P02` |
| 输入基线 | CR-EXEC-002、正式Ed25519 License信任锚/目标运行账户、Windows受控`--platform-write`组合A06-P01 |
| 前置任务 | A06-P01组合合同及后端全量通过；正式公钥/签发和目标服务账户Vault/备份恢复尚未获客观验收 |
| 涉及模块/实体/API | 本次只核查，不改程序、数据库或`/api/v1`；目标是现有Windows生产启动与停止 |
| 涉及权限 | 不读取、生成或代管私钥/口令，不将合成License、当前交互账户或测试证书作为正式服务信任 |
| 验收标准 | 包内正式公钥校验PASS，目标账户数据库/可信时间/License/Secret及独立备份恢复齐全，生产模式真实启动/停止与端口收回；任一缺失不能标PASS |
| 风险/回滚 | 不能以测试信任源绕过产品公钥缺口；本次无生产变更。继续可独立的非发行包验证，不触动正式服务/客户数据 |

## 当前证据

- `apps/backend/src/plm_assistant/modules/license/trust/product_public_key.json`当前不存在；本机源码`python -m plm_assistant.entrypoints.verify_release_key`仅输出固定拒绝信息`Release product public key unavailable.`，退出码1。
- 既有[正式信任前置核查](plt-02-a07-p05-a09-release-trust-precheck.md)和[操作员交接](../release/CURRENT-APP-FORMAL-TRUST-OPERATOR-HANDOFF.md)已记录交互式工作台签发、独立离线备份、目标账户Vault与恢复的必要证据。此处未读取工作台私钥、密码或任何客户数据，也未运行真实生产入口。
- 结论仅为“缺公钥的正式启动条件未满足”，不推断其他所有运行账户材料仍缺或已齐全。A06-P01的合成组合/Edge证据不代替正式启动。Gate3/Pilot/发行保持未通过。

## 转向

正式启动本片暂停，不伪造PASS；下一独立WBS为Windows 11当前源码非发行候选重建与离线清洁安装预检。候选必须显式`NOT-FOR-RELEASE`，保留发行禁用/法律未放行标志，不含合成私钥、公钥或客户资料。待操作员完成正式仪式后重返本WBS验收。
