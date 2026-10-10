# SOL-03-A04-P03-P03-P06-A04：双 Scope 候选与 CREATE 边界收口审计

日期：2026-10-09。结论：PROJECT/GLOBAL 固定引用的 Win11 合成端到端链已连通，但 CR-SOL-018 仍不能关闭；个别失效转移缺项目候选服务的直接负例，正式信任/Server2025/性能属于独立 Gate 3/发行缺口。

## 输入与判定

当前 Phase：Phase 2 Platform Core；当前 WBS：本审计。输入：Gate 2 API-04、CR-SOL-016/017/018、DEC-1148～1159、0157/0158、已提交的 A03～P03 代码/测试/验证脚本。前置：Win11 Edge/隔离PG合成链退出0，前端全量1733项/typecheck/build及后端全量3496项/3跳过/5398子例的最近证据。涉及模块：Solution、Auth、Project、Document/Evidence；本任务只审证据，不改 API/实体/权限。验收：逐项区分直接证据、间接证据与未验证边界，不把合成环境推断成正式发行。

|CR-SOL-018 要求|当前直接证据|结论|
|---|---|---|
|旧 GLOBAL 行默认不可见；管理员显式审定与撤回留痕|0157/0158 迁移、发布 Owner/HTTP/Windows；A02 发布前后及撤回内部 PG|Win11 合成 PASS|
|仅当前项目 PM/IM，客户/暂停/跨项目/归档/License 拒绝|A03 Owner 角色/Session/游标 PG，A04 ASGI，P03 Edge 跨项目隐藏|Win11 合成 PASS|
|项目只读五字段，不泄露原名/来源|A04 HTTP 严格投影与 P01 客户端；P03 Edge 原名不出现|Win11 合成 PASS|
|空可见页仍可签名续页，绑定 Session/Project/页大小|A03 游标/PG，A04 ASGI，P01/P02 前端分页单元|Win11 合成 PASS；浏览器未专门造空首页|
|GLOBAL 当前资格限制/撤回立即隐藏|A02 Catalog/PG 脚本与 P03 上游同轮复验|内部 PG PASS；浏览器未执行撤回交互|
|版本修订、确认过期、物理来源变化使旧发布不可用|发布 Owner 测旧版/文件篡改；A02 复用现时 ReferenceUseProof，来源夹具单独测确认撤销|间接/部分；需项目候选 Owner/HTTP 的直接负例|
|服务端 CREATE 重证，不接受失效的候选或裸 UUID|P05 双 Scope Owner/ASGI 旧版/失效源，P03 Edge 正例固定 GLOBAL 与单 Audit|正例 PASS；候选读取后变更再提交需直接回归|
|默认关闭、缺独立密钥/安全端口失败关闭|A04 默认404、A05 两平台模式/密钥备份恢复|Win11 合成 PASS；正式目标账户未验|
|正式 Windows Server2025、服务账户 Vault/ACL/CA/SCM、20 并发/发行|当前链无对应实测|未通过，不得由 Win11 推定|

## 后续处理

CR-SOL-018 保持实施中。先做 `SOL-03-A04-P03-P03-P06-A04-P01`：项目候选直接负例（版本修订、确认撤销/过期、物理来源变化）与“候选 GET 后失效再 CREATE”拒绝，使用可弃 Win11/PG 和合成来源；如发现真实语义缺口，先登记 CR/DEC 再修。后续独立复验目标服务账户/Server2025 与性能；Gate3 仍 BLOCKED。旧用户数据与本地 `.tmp/` 不触碰，Debian13 实机依用户指令跳过。

TraceLink：Gate 2 API-04 → CR-SOL-018 → 0157/0158 → A03～P03 → 本审计 → A04-P01 直接负例 → Gate 3/Release。
