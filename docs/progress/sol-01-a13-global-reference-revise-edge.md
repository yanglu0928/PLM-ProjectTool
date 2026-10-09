# SOL-01-A13-P03：GLOBAL Reference Revise Win11 Edge/隔离 PG 验收

日期：2026-10-09。结果：`SOL_01_A13_P03_GLOBAL_REVISE_EDGE_PG_PASS`；仅合成用户、文件、Windows 11、临时 PostgreSQL 18 与真实 Edge，不等于正式目标账户或完整 UAT。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-01-A13-P03；输入冻结 API-04、A13-P02 页面与 A07～A11 后端/Windows 组合，前置满足。
- 模块/实体/API/权限：只扩展一次性 GLOBAL Reference 浏览器验收夹具，兼修联测暴露的回执展示缺陷；DeploymentAdmin 可修订、非管理员不可读写。无 DB Schema/Migration、后端业务、公开 API 或依赖变化。
- 验收：真实登录与多来源创建基准根；新来源顺序/分类重新预览、逐项打开与人工确认；首次修订 201 丢失后保存原 body/If-Match/Key，整页重载/重新登录同号恢复；历史回执与当前 GET 分离；非管理员入口隐藏/直 POST404；数据库单根第 2 版、两历史版本、单条修订 Audit；临时 Edge/HTTP/PG 清理。
- 风险：浏览器脚本只模拟合成来源和管理员确认动作，不是实际客户脱敏签署；正式 License、目标账户、HTTPS、Server2025/性能/Gate3 仍待。

## 实施与证据

新增 `validation/sol-01-a13-p03-global-reference-revise-browser/serve.py` 与 `run-edge-browser.mjs`，复用既有 GLOBAL 合成真实 Document/Evidence 来源、登录和多来源确认环境，仅在本夹具显式装入 GLOBAL Revise Router。脚本以真实浏览器创建参考根，再反向选择两来源并将脱敏分类改为 `REDACTED`，重新确认后提交。DevTools 在首次 201 响应阶段模拟网络丢失；会话存储保留原 Key、If-Match 和正文，重新登录后只用原请求恢复。网络记录证明两次请求三者逐字一致；当前 GET 指向第 2 版。SQL 核对根 `lock_version=1`、当前 `version_no=2`、两条版本、单条 `SOL_REFERENCE_REVISED` Audit。非管理员详情与修订页面拒绝，另用其真实 Session 直 POST 得 404。

联测发现 A13-P02 页面把修订回执放在内存中人工确认区下：整页重载后确认状态不复原，虽服务端同号恢复成功，回执却不显示。已把回执移至独立修订结果区，并增加“无内存确认仍显示恢复回执”的单元回归。初始脚本也先后有网络拦截异步等待与重载后按钮不存在的断言误判，均按实际状态修复；失败轮次不计 PASS。最终夹具退出 0，前端 119 文件/1695 测试、typecheck/build通过，旧 GLOBAL 多/单来源 Edge/PG 创建夹具回归退出 0。临时库、服务及 Edge profile 由夹具清理。

## 兼容、回滚与后续

仅验证夹具与前端回执显示修复；可撤回夹具/页面修复，不触及冻结合同或历史版本，但回滚前应核对未决操作。GLOBAL 文档-only 来源仍缺 UI（服务端允许），A14 需对账双 Scope 权限、来源与历史回执边界，并规划覆盖此缺口。正式目标账户/信任源、20 并发、Server 2025、Gate 3/UAT/发行未验；Debian 13 实机依用户指令暂跳过。
