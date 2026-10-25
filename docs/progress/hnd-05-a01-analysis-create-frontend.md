# HND-05-A01：交接分析创建前端编码前检查

日期：2026-10-24；状态：`SOURCE_PASS / PACKAGE_EDGE_PG_PENDING`。

|检查项|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `HND-05-A01`：为现有 HND-01 创建合同补用户可操作入口|
|输入基线|Gate 2 冻结 API、CR-EXEC-002、`PKG-PILOT-01-A04-P05` 缺口；后端 `POST /api/v1/projects/{project_id}/handover-analyses` 已在 Windows `--platform-write` 装配，来源须为同项目 ACTIVE 文档的 AVAILABLE 固定版本|
|前置任务|项目/文档列表与版本元数据客户端、Session 写桥接模式、Handover 只读页/后端创建服务均已存在；正式信任仍缺，但不阻断前端编码/合成测试|
|涉及模块|仅前端 Handover 创建客户端、页面、路由/列表入口及 Session 写桥接；复用 DocumentReadClient，不改 Document 后端|
|涉及实体 / API|HandoverAnalysis 逻辑身份与 `source_documents` 固定引用；消费已冻结 POST，无新字段/端点/Schema；成功后由现有读页再确认现时事实|
|涉及权限|仅当前项目负责人/实施成员可提交；Session 原有 CSRF、Origin、Cookie、幂等封装；页面不接收手填 UUID，不展示或传送文档正文；后端再次按项目/版本核验|
|验收标准|选择 1～500 个不重复的当前项目文档及 AVAILABLE 版本，分页选择可用；提交/同 Key 重试与不确定结果保护；拒绝空来源、跨项目/无角色、错误回执；客户端/页面/路由定向及前端全量/typecheck/build；实际 Edge/PG 包内组合另项|
|风险|文档列表是分页现时视图，选择后文档可能归档/版本不可用；服务端最终裁决，UI 不能宣称 AI/客户确认。浏览器 sessionStorage 丢失或损坏须失败关闭；完成后清理原操作号失败也须停止再提交。|

本项不修改冻结基线、License、安全策略或 Scope，无 Migration；若后端现有合同不兼容，先记录偏差再实施。采用独立创建页与元数据选择器的 L2 决定见 `docs/decisions/decision-log.md`。

## 实施与独立验收

- 新增交接分析创建客户端、创建页及列表入口；从项目文档和固定版本的现有只读 API 分页读取元数据。用户不手填内部标识，页面不读取文档正文。仅负责人/实施成员可提交，服务器仍最终复核来源资格。
- 创建请求只含目的和 1～500 个不同文档的固定版本引用；Session 写桥接负责 CSRF 与幂等键。严格核对 201 回执的项目、目的、Location、ETag 等。网络或回执不确定时会话保留原键/内容，用户核对列表后才能同号重试；持久记录损坏则停止提交。
- 定向客户端/页面/列表 16 项通过；前端全量 162 文件、1879 项通过；`pnpm typecheck` 与 `pnpm build` 退出 0。`git diff --check` 通过。测试使用合成身份/文档元数据，未调用客户资料或外部 AI。
- 升级/回滚：无 Schema/API 迁移；更新前端静态资源即可启用。可撤入口及客户端以停止新创建，但已经生成的交接分析和审计不可删除。旧非发行 ZIP 不含本 UI，须从当前清洁源码另建新候选。
- 已知问题：新候选实际 Windows 11 Edge/PG 文档上传→固定版本→分析创建尚未验；后续版本创建/待确认事项直到 Plan 的完整纵向链、正式公钥/服务账户、离线安装升级、Gate/UAT 均未由此通过。Windows Server 2025、Debian 13 不能由 Win11 推定通过。

Result：`HND-05-A01_SOURCE_PASS`。Next：`PKG-PILOT-01-A04-P06`，从已同步清洁提交制作非发行新候选并做合成文档来源与分析创建 Edge/PG 端到端；真实信任阻塞保持独立记录。
