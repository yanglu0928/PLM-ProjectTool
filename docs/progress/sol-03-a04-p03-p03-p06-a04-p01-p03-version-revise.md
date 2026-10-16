# SOL-03-A04-P03-P03-P06-A04-P01-P03：GLOBAL 当前版本修订使旧发布失效

日期：2026-10-09。结果：Win11 可弃 PostgreSQL 18.6/真实项目 HTTP 与正式 GLOBAL ReferenceRevise Owner 通过；仅为合成环境，不代表正式发行。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / 本项；输入 Gate2 API-04、CR-SOL-018、DEC-1160/1164、已验项目候选/OutlineVersion CREATE 与 GLOBAL 修订 Owner。
- 单一问题：旧固定版本已发布且项目可见时，同根修订为 v2 后，旧标签不得继续展示，旧固定引用不得继续创建 DRAFT。
- 模块/实体/API/权限：仅验证资产；复用真实 ReferenceRevise、项目候选 GET、OutlineVersion CREATE、PG/Audit/收据，不改应用实体/API/角色或 ORM/Migration。
- 验收：修订前项目 GET 返回旧版，真实修订后根当前指针指向 v2 且旧版 GET 空项，旧固定引用 CREATE 拒绝；无目录版本/创建 Audit/创建收据，修订 Audit 单条；可弃环境完全清理。
- 风险：直接改写版本指针绕过业务 Owner，或上游夹具后来限制旧版资格造成误归因。此脚本使用正式修订 Owner，在其余条件有效时验证并以成功哨兵结束上游后续状态变更。

## 验证

新增 `validation/sol-03-a04-p03-p03-p06-a04-p01-p03-version-revise/verify.py`。在未撤确认、真实 Document/Evidence 与活动项目 PM 上，旧已发布 v1 项目 GET 200 可见；调用 `ReferenceReviseService` 生成同根 v2 后，旧项目候选 GET 200 `items=[]`，旧固定 v1 的 OutlineVersion CREATE 503。SQL 确认根当前指针为 v2、该目录 0 版本/0 创建 Audit/0 创建收据，修订 Audit 恰一条。脚本退出码 0，输出 `GLOBAL_CANDIDATE_VERSION_REVISE_PASS` 与本 WBS PASS；上游夹具在本项成功哨兵后停止，不计其后续来源验证。

兼容/升级/回滚：只增验证资产，无运行 Schema/Migration、API/权限/依赖变化；删脚本可回滚，历史保留。CR-SOL-018 的 Win11 合成语义缺口本轮直接负例已覆盖，下一项重审 CR 收口边界；正式账户 Vault/ACL/CA/SCM、Server2025、20 并发、质量/Gate3/Release 仍未通过；Debian13 实机依用户指令跳过。

TraceLink：Gate2 API-04 → CR-SOL-018 → DEC-1160/1164 → GLOBAL Revise Owner → 项目候选/CREATE 旧版直接负例 → CR 收口审计 → Gate3/Release。
