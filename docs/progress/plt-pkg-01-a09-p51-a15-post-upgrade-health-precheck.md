# PLT-PKG-01-A09-P51-A15：当前应用候选启动与健康检查前置

日期：2026-10-26。状态：`PRECHECK_READY`。

## 编码前检查

| 项目 | 结论 |
|---|---|
| Phase / WBS | Phase 2 / `PLT-PKG-01-A09-P51-A15`；A14已证明文件级升级和显式人工恢复，不证明升级后可运行。 |
| 唯一问题 | 最新Windows 11非发行候选在隔离布局中能否以包内Python启动API和静态前端，经loopback返回Ready/Live健康结果并在退出后停止所有进程。 |
| 固定输入 | P51-A02当前候选SHA `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`；既有完整性报告 `current-app-candidate-96313d4e1215/verification-summary.json`；阶段目录 `D:\PLMToolTemp\plm-current-app-stage-p51a02-96313d4e`。 |
| 先行证据 | `tools/smoke_current_app_packaged_https.py`可对Current App候选运行隔离HTTPS/PG烟测；`tools/smoke_packaged_http_frontend.py`证明包内API `/health/ready`、`/health/live`及前端资源的loopback验收模式，但它绑定旧的Unified PG18包布局，不能直接用于Current App candidate。A15优先复用Current App专用烟测及其既有验证夹具，不混用旧包布局。 |
| 范围 | 仅本轮随机ASCII Temp根、候选包内运行时、一次性PostgreSQL 18和合成License/测试数据。服务仅loopback启动；不得连接既有数据库/Vault，不注册SCM，不使用正式安装根或真实客户资料。 |
| 验收 | 固定非发行候选身份；Edge/HTTPS smoke中的Ready/Live成功；错误Host/Origin及无License业务写入按预期拒绝；服务进程、PG、Caddy、临时目录/Vault均按owner清理；候选文件不变。任何未执行子链不记PASS。 |
| 风险/边界 | 该项验证的是候选包运行性，不是A14升级后磁盘布局本身的应用级Migration验收；数据库升级、正式证书/公钥、服务账户ACL、SCM、正式安装、Gate/Pilot仍独立阻塞。包保持`release_eligible=false`、`legal_clearance=false`。 |
| 预计修改 | 一次性验收脚本/报告、此记录、`STATUS.md`与`CHANGELOG.md`；除非编码前发现真实产品缺陷，否则不改产品功能/API/Schema/Migration。若发现产品缺陷，按独立WBS记录后修复，不在此项跨模块顺手改动。 |

## 验证计划

1. 复核A03～A13在Current App专用 smoke 上的近期证据和可复用的隔离PG/HTTPS启动边界。
2. 编写A15一次性runner前，核对其唯一目标、输入路径、临时所有权/清理、无正式凭据与网络外发约束；固定候选SHA不得覆盖。
3. 先跑runner单测/语法检查，再做Windows 11 loopback实测、候选前后Hash/状态和进程/目录清理审计；保留失败诊断，不把未运行的HTTPS、PG或Edge部分写成通过。

## 下一项

本WBS执行完成后，以客观证据更新 `STATUS.md` 并继续解决受控内部Pilot的真实信任与安装/升级缺口；本检查不通过Gate，也不授权发行。
