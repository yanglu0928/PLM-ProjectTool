# CR-EVD-001 DOCX 标题来源的 SECTION 定位

日期：2026-10-01。状态：Parser V2 来源节点与 Evidence 内部证明已实现；隔离 PostgreSQL 版本共存及升级排空验收待后续 WBS。来源：Gate 2 冻结的数据模型要求 `SECTION` 指向可重放的章节路径或标题锚点；`EVD-01-A03-P02-A02-P03-P04-A02` 前置核查发现当前 Parser 只发出 DOCX 段落/表格节点，Evidence 对 SECTION 一律拒绝。冻结提交 `64cdf09` 保留，不追写。

## 冲突与证据

`extract_office.py` 对 DOCX 段落只保存正文和序号，不读取段落样式；`structured_result.py` 的节点类型没有 SECTION，解析版本为 1；`parsed_node_proof.py` 不接受 SECTION 来源。一个普通段落即使文字像标题，也没有证据证明它是标题。将 `PARAGRAPH` 序号或全文 Hash 直接包装成 SECTION 会违反冻结的来源可重放规则。

## 方案比较与选择

- 方案 A：从现有段落文字推断标题并直接出具 SECTION。无需版本升级，但会把普通段落误判为章节，无法证明样式来源；不采用。
- 方案 B：对 DOCX 使用解析版本 2，仅当原文段落样式为内置 Heading 1～9 且正文非空时，额外发出稳定标题节点；节点定位携带按段落序号构造的 `word/heading/<index>` 锚点，Evidence 对固定 ParseRecord 的该节点证明 SECTION。保留原段落节点，旧版本 1 结果不修改；采用。
- 方案 C：Evidence 直接重开 Document 原字节检查标题样式。会跨越 Document 受权读取边界，重复文件解析并扩大权限面；不采用。

## 差异、影响与风险

这是已冻结 SECTION 能力的来源证明补齐，不增加公开 `/api/v1` 字段或新 Scope。内部 DOCX Parser 结果新增一个节点类型，DOCX 解析版本由 1 升至 2；其他格式仍为版本 1。旧 ParseRecord、ResultRef 与 Evidence 历史保留，不能用版本 2 结果覆盖旧字节。当前数据库 `parser_version` 为文本且唯一约束包含该列，预计无需 ORM/Alembic 迁移；实施时必须再次以测试确认。只有明确内置 Heading 1～9 样式产生 SECTION，普通/自定义/空标题不自动推断。跨格式章节来源仍未实现，不宣称九种定位全面通过。

## 迁移、回滚与验证计划

升级不改现有记录；新 DOCX 作业按版本 2 生成独立尝试/结果。现有 Jobs payload 不预先存 Parser 版本，尚未开始的队列项会在准备输入时选择新版本；已经 RUNNING 的 V1 尝试不能在新代码中直接续跑，部署前须停止入队并让旧 Worker 静止/排空，未收尾项按现有恢复流程显式处理，不能悄悄改版。回滚为停用新 DOCX V2 入队/发行并部署旧代码，保留 V2 已发布历史只读，不删除证据；回滚前同样需要静止/排空新 V2 作业。测试覆盖：真实 DOCX 内置标题与普通段落独立重开位置、重名标题/空标题/自定义样式、旧版本结果兼容、跨版本伪装拒绝、当前权限/固定 ResultRef 的 Evidence 证明、全后端回归及 wheel。若需要数据库变化另建迁移子项，先做空库和有数据 up/down 验证。

## 未关闭事项

Parser V2 标题节点已通过合成落盘 DOCX 回查、定向 10 项、后端全量 1,745 项（3 既有跳过）和开发 wheel；Evidence SECTION 内部证明经落盘 DOCX、定向 9 项、全后端 1,746 项（3 既有跳过）及 wheel 通过。隔离 PostgreSQL V1/V2 共存与旧作业升级排空、正式客户文档、复杂章节层级、其他格式 SECTION、Windows Server 2025/Debian 13、正式信任与 Gate 3 仍待各自证据。本 CR 整体尚未关闭。
