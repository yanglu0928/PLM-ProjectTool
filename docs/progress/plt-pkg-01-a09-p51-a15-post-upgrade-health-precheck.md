# PLT-PKG-01-A09-P51-A15：当前应用候选启动与健康检查前置

日期：2026-10-26。状态：`PASS_SCOPE_LIMITED`。

## 编码前检查

| 项目 | 结论 |
|---|---|
| Phase / WBS | Phase 2 / `PLT-PKG-01-A09-P51-A15`；A14已证明文件级升级和显式人工恢复，不证明升级后可运行。 |
| 唯一问题 | 最新Windows 11非发行候选在隔离布局中能否以包内Python启动API和静态前端，经loopback HTTPS返回Ready/Live健康结果并在退出后停止所有进程。 |
| 固定输入 | P51-A02当前候选SHA `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`；既有完整性报告 `current-app-candidate-96313d4e1215/verification-summary.json`；阶段目录 `D:\PLMToolTemp\plm-current-app-stage-p51a02-96313d4e`。 |
| 先行证据 | `tools/smoke_current_app_packaged_https.py`可对Current App候选运行隔离HTTPS/PG烟测；`tools/smoke_packaged_http_frontend.py`证明包内API `/health/ready`、`/health/live`及前端资源的loopback验收模式，但它绑定旧的Unified PG18包布局，不能直接用于Current App candidate。A15优先复用Current App专用烟测及其既有验证夹具，不混用旧包布局。 |
| 范围 | 仅本轮随机ASCII Temp根、候选包内运行时、一次性PostgreSQL 18和合成License/测试数据。服务仅loopback启动；不得连接既有数据库/Vault，不注册SCM，不使用正式安装根或真实客户资料。 |
| 验收 | 固定非发行候选身份；包内API与HTTPS Ready/Live=200；首页及JS/CSS静态资源HTTPS返回与包内文件一致；错误Host/Origin及无License业务写入按预期拒绝；API、Caddy、PG、临时目录/Vault按owner清理；候选文件不变。此项使用HTTP客户端，不声称真实Edge浏览器验收。 |
| 风险/边界 | 该项验证的是当前候选新建隔离布局的运行性，不是A14升级后磁盘布局本身的应用级Migration验收；数据库升级、正式证书/公钥、服务账户ACL、SCM、正式安装、Gate/Pilot仍独立阻塞。包保持`release_eligible=false`、`legal_clearance=false`。 |
| 预计修改 | 现有非发行HTTPS smoke增加Live/静态资源断言及可选既有SHA报告复用；新增一次性验收脚本、测试与进度材料。不改产品功能/API/Schema/Migration。若发现产品缺陷，按独立WBS记录后修复，不在此项跨模块顺手改动。 |

## 验证计划

1. 复核A03～A13在Current App专用 smoke 上的近期证据和可复用的隔离PG/HTTPS启动边界。
2. 编写A15一次性runner前，核对其唯一目标、输入路径、临时所有权/清理、无正式凭据与网络外发约束；固定候选SHA不得覆盖。
3. 先跑runner单测/语法检查，再做Windows 11 loopback实测、候选前后Hash/状态和进程/目录清理审计；保留失败诊断，不把未运行的HTTPS、PG或Edge部分写成通过。

## 最终验收结果（2026-10-26）

- `tools/smoke_current_app_packaged_https.py` 增加可选既有完整性报告绑定（摘要状态、固定SHA、归档大小、路径后缀及非发行标志必须匹配；测试期间再核对大小/mtime未变），并为现有HTTPS smoke 输出是否复用报告。Fast reuse仅复用此前P51-A02完整验证的不可变stage；本轮布局映射、元数据/manifest/清单和文件路径边界仍核对。
- `tools/smoke_packaged_platform_write_https.py` 增加包内API直连及HTTPS代理上的`/health/ready`、`/health/live`状态码/响应体断言；验证首页及2个JS/CSS资源HTTPS返回与隔离包内文件逐字节一致。
- Windows11实测输出 `PLT_PKG_01_A09_P51_A15_PASS_SCOPE_LIMITED`：API Ready/Live及HTTPS Ready/Live均200；前端JS/CSS 2项相符；合成登录200、Session 200、未授权项目403、错误Host 421/错误Origin 403。一次性PG18、API/Caddy均由既有Current App smoke启动并停止；测试Vault目标不存在，临时运行文件与安装布局清理完成。候选SHA固定为`3cbd68aa…f2326f455`，非发行/非法律放行标志保留。
- 候选归档SHA复用P51-A02既有完整性报告，本轮未重新读取约655MB ZIP计算SHA；报告摘要和当前文件大小匹配，执行前后大小/mtime不变，包内stage按原记录复用。该偏差不声称本轮重新校验归档SHA；P51-A02完整清洁stage哈希证据仍是stage来源。
- 标准库定向测试：Current App HTTPS边界2/2、平台写HTTPS smoke 8/8；使用候选包Python运行（系统Python缺少`httpx`）。`py_compile`、runner集成验收及`git diff --check`通过。没有Edge浏览器验收、正式License/信任或正式安装。
- 仅改验收工具/测试/报告，无产品API/Schema/Migration/依赖变化。A15不等于A14升级后布局的应用级迁移启动，不通过Gate、Pilot或Release。

## 下一项

本WBS执行完成后，以客观证据更新 `STATUS.md` 并继续解决受控内部Pilot的真实信任与安装/升级缺口；本检查不通过Gate，也不授权发行。
