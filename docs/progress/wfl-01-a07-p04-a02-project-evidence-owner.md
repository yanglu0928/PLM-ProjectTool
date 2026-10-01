# WFL-01-A07-P04-A02：PROJECT Evidence 固定来源内部 Owner

日期：2026-10-02；Phase 2；基线：Gate 2 冻结提交 `64cdf09`，偏差 `CR-WFL-005`，决策 `DEC-20261002-605`。状态：**PROJECT 内部来源证明 PASS；未装配 Workflow/Checklist**。

Evidence Application 新增 `EvidenceFixedProjectSourceService`：调用方提供当前事务、Session 与目标 ProjectId。服务先检查当前用户为 ACTIVE 项目经理，再在同一事务锁定目标项目当前 ELIGIBLE Evidence；随后通过 Document 固定来源 Port 验证 DocumentVersion、实际私有文件和可选 ParseRecord/ResultRef。整文档要求无 ParseRecord，指纹等于源文件 SHA；解析节点要求固定 ParseRecord，并对 Document 已验证的解析字节执行现有节点/locator 证明，最终与 Evidence 中的固定 locator、fingerprint 比对。模板、旧缺固定解析身份、跨项目、失效或篡改均失败关闭。返回仅最小观测事实，不含原文、解析字节或存储路径。

验证：新增 Owner 单元 6/6、原节点证明回归合计 15/15；隔离 PostgreSQL 18 的合成 PROJECT 节点与整文档通过，Owner 持 Evidence、Document、Version、File、ParseRecord、ResultRef 六行共享锁，第二连接 `FOR UPDATE NOWAIT` 均返回 `55P03`；跨项目、撤销、源文件与解析结果篡改拒绝。后端全量 1846 通过/3 跳过；本地开发 wheel SHA-256 `9813b797836e8759e52f6b67c82737a0a9cd829ea4edf7fe45395f731ba482f9`。

兼容/升级/回滚：无公开 API、Schema/Migration 或依赖变化，无旧 Evidence 自动回填；可不装配下游 Workflow 而保持历史原状。隔离 PG18 的会话/项目角色由受检假 Port 提供，尚未在实际 Workflow 写链中验证真实 Session/CSRF/License；GLOBAL 标准引用、Review/例外 Owner、Checklist/Gate、正式信任/法律及三平台/UAT 均未通过。下一任务处理窄 GLOBAL 标准引用，普通 GLOBAL 列表/下载权限保持不变。
