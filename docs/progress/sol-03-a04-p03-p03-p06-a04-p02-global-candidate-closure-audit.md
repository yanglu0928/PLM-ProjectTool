# SOL-03-A04-P03-P03-P06-A04-P02：GLOBAL 候选 Win11 证据收口审计

日期：2026-10-09。结论：CR-SOL-018 所需的 GLOBAL 发布、最小项目候选读面、页面选择及候选失效后 CREATE 拒绝，在 Windows 11 合成环境具备直接证据；这是**功能子集验证完成**，不是正式环境、Gate 3 或发行 PASS。CR 保持开放。

## 基线和范围

Phase 2 Platform Core；输入为 Gate 2 API-04、CR-SOL-016/017/018、DEC-1148～1164、0157/0158 迁移及已提交的进展/验证脚本。前置：A03～P03 正链和 A04-P01 四种失效负例均已有独立退出 0 记录。本项只重审证据，不变更应用代码、Schema、API、权限或历史数据。验收标准是每项结论可回指直接脚本，未实测边界继续列为阻塞。

|要求|直接证据|Win11 判定|
|---|---|---|
|旧 GLOBAL 默认不可见、显式发布/撤回及历史审计|A03-P01～P04 的 0157/0158、管理员 Owner/HTTP/Windows；A03-P05-A02 发布前后与撤回 PG|合成 PASS|
|PM/IM 项目授权、跨项目/暂停/License 拒绝与最小五字段|A03-P05-A03 Owner/PG、A04 HTTP、A05 Windows、A06-P03 Edge/PG|合成 PASS|
|签名游标、空可见页续页及缺安全端口失败关闭|A03-P05-A03～A05 的 Owner/HTTP/Windows 和 A06-P01/P02 前端合同|合成 PASS；浏览器空首页专门场景未执行|
|GLOBAL 固定版本选择、DRAFT 创建、重证与单次 Audit|A06-P03 Edge/PG 正链及 P05 双 Scope 服务端验证|合成 PASS|
|候选 GET 后物理来源漂移，CREATE 拒绝且无写副作用|A04-P01-P01 Edge/PG 直接负例|合成 PASS|
|最新确认撤销，旧候选隐藏且 CREATE 拒绝|A04-P01-P02-P01 真实撤销 Owner/PG/项目 HTTP 直接负例|合成 PASS|
|确认精确到期，旧候选隐藏且 CREATE 拒绝|A04-P01-P02-P02 受控服务时钟/PG/项目 HTTP 边界负例|合成 PASS；不证明正式可信时间|
|同根 v2 修订使 v1 旧发布失效|A04-P01-P03 真实 ReferenceRevise Owner/PG/项目 HTTP 直接负例|合成 PASS|
|正式发行信任源、目标服务账户、Server 2025、20 并发|无该目标环境实测证据；现有性能 P95 超目标|未通过，独立阻塞|

直接记录分别见 `docs/progress/sol-03-a04-p03-p03-p06-a03-p05-a06-p03-global-candidate-browser.md`、`...-a04-p01-p01-global-candidate-source-drift.md`、`...-a04-p01-p02-p01-confirmation-revoke.md`、`...-a04-p01-p02-p02-confirmation-expiry.md` 和 `...-a04-p01-p03-version-revise.md`（同目录）。没有重复运行上述脚本，结论依据其已提交的退出码及断言范围；本审计不增加新的运行结果。

## 偏差、遗留和转序

与先前 A04 审计相比，来源漂移、确认撤销/到期和版本修订的项目入口直接负例已补齐。空可见首页在 Owner/HTTP/前端合同层已验证，但不称 Edge 专门场景 PASS。真实业务人工审定、正式 License 公钥/服务账户 Vault/ACL/CA/SCM、Server 2025 当前组合、20 并发与 P95、POC-03 质量复验及完整 UAT 仍未通过。Debian 13 实机依用户指令跳过，不推定兼容验收。

下一独立任务先核查 Windows Server 2025 可用测试环境与正式信任前置，能安全复用现有合成脚本时进行该环境实测；若正式凭据或仪式需要真人操作，记录客观阻塞并继续质量/性能与业务链工作。CR-SOL-018 保持 `IMPLEMENTED_WIN11_SYNTHETIC_VERIFIED / FORMAL_ACCEPTANCE_OPEN`，Gate 3 保持 BLOCKED。历史审计和发布记录不删除；本项仅文档，回滚为撤回本次审计判定，不改变应用数据。

TraceLink：Gate 2 API-04 → CR-SOL-018 → A03～P03 → A04-P01-P01/P02-P01/P02-P02/P03 → 本审计 → 正式环境/质量/性能 → Gate 3/Release。
