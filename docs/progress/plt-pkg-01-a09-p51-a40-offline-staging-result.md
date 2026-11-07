# PLT-PKG-01-A09-P51-A40：Windows 父包云端离线暂存验收结果

- 日期：2026-11-02
- 结果：PASS_LIMITED
- 环境：GitHub hosted Windows Server 2025；所有本轮运行均在托管runner完成，未在用户本机运行。
- Workflow：[P51 A40 offline staging sandbox run 41369734304](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41369734304)
- 证据Artifact：ID `13108667793`，SHA-256 `c3caf121738c27a678d0efc9b25030a12f5bf5f65aee625763f68761513f49aa`，保留至2026-11-16。

## 验收结果

- 19项定向Windows回归全部通过，覆盖A37输入登记、A38就绪报告、A40暂存CLI与A34隔离升级演练。
- 从A35 hosted run 41026213054下载候选ZIP；GitHub Artifact SHA-256为 `3671617ad0acaa0ee9fe83bdd293ade8e193a9f1ff9d9e3ab3f01559dc6dd70a`，包内外验证摘要绑定的ZIP SHA-256为 `94700239dc2218466087fd4beec90f9d34cd4a6c96ceed1049033df58342e2f2`。
- 在D盘 `RUNNER_TEMP` 的新隔离目录校验并暂存20,119个payload文件；回执状态 `HOSTED_WINDOWS_CANDIDATE_STAGING_PASS_LIMITED`。
- 回执中的 `installation_performed`、`services_started`、`release_eligible`、`legal_clearance` 均为false。
- A38报告为 `DIAGNOSTIC_ONLY_NOT_READY`，保留5项启动阻断；包内只读启动诊断返回 `BLOCKED`、exit 2。Actions在断言通过后正常结束。

## 偏差及修正

首轮云端执行记录了三项环境/验收偏差，并在后续运行前修正：

1. A34既有演练约束 `RUNNER_TEMP` 与Python临时目录一致且位于D盘；workflow保留runner原始D盘根，只把 `TEMP/TMP` 指向该根，A40暂存目标使用其直接子目录。
2. Windows hosted 默认Python临时目录落在C盘；A40的合成坏摘要输入改为使用D盘临时根，避免意外写C盘。
3. 包内诊断预期exit 2是安全拒绝，不应令Actions失败；workflow解析JSON并核对BLOCKED后将该预期退出码清零。

专用workflow最终run全部成功；初次失败仍保留在Actions历史，不将其改写为成功。

## 限制

本项证明候选身份校验、非C盘云端暂存、就绪报告和fail-closed诊断行为。它没有安装或启动产品、注册服务、连接数据库/API或读取密钥。GitHub hosted Windows Server 2025结果不推定Windows 11兼容；不构成Pilot、Gate 3或正式Release通过。正式公钥/License信任、数据库凭据身份、服务账户ACL、TLS材料及包外可验证代码信任继续阻塞正式安装路径。
