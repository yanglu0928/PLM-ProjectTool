# POC-03 Windows 11 候选数据准备证据

## Scope

2026-09-17 在 Windows 11 上只读处理两个本地资料库：历史方案和技术协议/合同。原文件、原文件名、Hash、解析正文、OCR 正文、候选正文和本地映射均未提交 Git。

## Source Corpus

- 历史方案：18 个文件，17 个受支持文件解析通过，1 个旧版 `.doc` 不支持；共 13,710 个内容块。
- 技术协议/合同：18 个文件，4 个 DOCX 和 5 个扫描 PDF 解析通过，9 个旧版 `.doc` 不支持；共 46,720 个内容块。
- 5 个扫描 PDF：105 页，Tesseract 产生 45,145 个 OCR 行，Schema 错误为 0。
- 两个资料库原件不变性：36/36 PASS。
- 合并可用输入：26 个 ParsedDocument，60,430 个内容块。

## Candidate Dataset

- 确定性 Chunk：655 个，全部使用 `PROJECT` scope 和显式 ProjectId。
- 候选评审记录：120 条，覆盖 26/26 个已解析文档。
- 候选状态：全部为 `PENDING_HUMAN_REVIEW`。
- 合同/技术协议资料产生 192 个 Chunk；历史方案产生 463 个 Chunk。
- 候选正文仅保存在 `artifacts/poc-03/candidate-dataset/2026-09-17-r2/`。

## Human Review Workbook

- 已从 120 条候选生成本地 Excel 评审工作簿，包含“评审总览”和“候选评审”两张工作表。
- 工作簿初始状态为 120 条 `PENDING`、0 条 `APPROVED`、0 条可转正式集。
- 3 组下拉规则、完备性公式、冻结窗格、筛选表和条件格式已写入导出文件。
- 已渲染并检查两张工作表；导出后重新载入成功，公式错误扫描为 0。
- 工作簿含候选正文，只保存在 Git 忽略的本地 `artifacts/`；仓库仅提交 `review-workbook-result.json` 的脱敏结论。
- R2 新版本使用完全本地的确定性规则预填 120 条不同查询、答案术语、建议分类和原始引用定位，没有调用外部 AI 服务，也没有覆盖 R1。
- R2 生成时全部 120 行重置为 `PENDING`，审核人和审核时间为空；45 条 `CONTRACT` 可直接映射，75 条 `SOLUTION` 因不在锁定来源类型枚举中保持空白并高亮。
- R2 生成时导入复核为 120 行、0 条 APPROVED、0 个来源一致性问题；用户随后已完成填写，最新复核结果见“Confirmation UX Prototype”。

## Review Import Gate

- 新增本地评审表导入器，逐行核对候选编号、ProjectId、文档/Chunk、来源定位、正文和正文 Hash，不允许人工修改来源证据。
- 只转换 `APPROVED` 且查询、来源类型、分类、答案术语、确认引用、审核人和审核时间完整的记录。
- 确认引用必须来自原候选的来源定位；工作簿公式显示不作为导出依据，导入器独立重算 Gate。
- R1 历史工作簿曾得到 109 条 `APPROVED`、11 条 `PENDING` 和 0 个导入问题，但后续覆盖审计失败，该版本不作为当前评审基线。
- 25/25 单元测试通过；除原有评审导入和覆盖审计外，新增本地建议的来源映射、不可伪造 `SOLUTION` 类型、查询去重和脱敏报告测试。

## Index Binding

- P03-A04 已验证索引身份包含 provider、model、dimension 和 index_version。
- 同一 index_id 重复注册相同绑定是幂等操作；更改模型或维度会被拒绝，必须使用新 index_id。
- 已激活 PoC 绑定：阿里云百炼 OpenAI-compatible `qwen3.7-text-embedding`、1024 维、索引 `v1`。
- 使用固定非客户文本完成真实探测，请求与返回均为 1024 维；Key、输入文本、向量值和厂商响应正文均未提交。
- 安全探测合同通过模拟验证：Key 不写入报告、返回维度必须匹配、HTTP 错误不透传厂商响应正文。
- P03-A05 使用 `text-embedding-v4` 768 维创建独立 `v2` index identity；旧 `v1` 原地换模被拒绝。
- 120 条固定非客户文本通过 12 批真实调用完成 120/120 重建，返回维度均为 768，旧向量复用 0。
- `v2` 仅验证未激活；报告不含 Key、输入文本、向量值或厂商响应正文。

## Project Isolation

- Windows 11 本地 PostgreSQL 18.6 + pgvector 0.8.6 建立临时隔离 Schema，写入两个项目共 40 条合成记录。
- PROJECT 请求必须包含非空 ProjectId；缺失值在进入数据库前被拒绝。
- Vector、Full Text、Hybrid 对两个项目各执行 Top-5，共 6 个场景、30 行结果，跨项目泄漏为 0。
- 所有 SQL 使用参数化 ProjectId；注入式字符串返回 0 行，没有扩大结果范围。
- 验证结束后临时 Schema 删除，未保留合成行，也未使用客户内容。

## PostgreSQL Full Text

- PostgreSQL 18.6 使用 `simple` text search configuration；中文术语由上游以空格完成确定性规范化。
- 4 组中文合成查询、40 条记录分别执行 Top-5；平均及最低 Recall 均为 100%。
- `EXPLAIN` 确认命中表达式 GIN 索引。
- 该 PoC 不宣称 PostgreSQL 原生具备中文分词能力；不带上游术语规范化的中文检索尚未验证。
- 临时 Schema 已删除，查询文本和合成行未提交。

## Dataset Export and Coverage

- 109 条 APPROVED 记录已按 `poc-03.golden.v1` 完成 Schema 合法导出；数据集只保存在 Git 忽略的本地 `artifacts/`。
- 脱敏覆盖审计：109 条记录、1 个唯一查询、26 个文档、109 个 Chunk、1 个项目。
- 来源类型全部为 `SURVEY`，分类全部为 `STANDARD_SATISFIED`；质量覆盖判定为 `FAIL`，不得计算或宣称 Recall/分类准确率通过。

## Privacy

- `方案库/`、`技术协议&合同/` 和 `artifacts/` 均由 Git 忽略。
- 提交证据不含原文件名、客户名称、原始 Hash、解析正文、OCR 正文或候选正文。
- 仓库只保存脱敏文档编号、数量、类型、状态和质量边界。

## Confirmation UX Prototype

- 用户已在 R2 填写 120 行 `APPROVED`、审核人和日期；原值在 R3 技术审计页逐单元格保留，差异为 0。
- 严格 Gate 重新计算后，45 行字段完整，75 行仍缺锁定来源类型；“已批准”不能绕过必填规则。
- R3 主清单移除大段候选正文，生成 120 个“打开证据”链接和 120 条逐项维护提示。
- 本地证据定位器包含 120 个候选锚点和 120 个原文件入口；PDF 链接携带页码，Office 文件显示精确段落、表格或幻灯片定位。
- 浏览器实测 `#GD-C-0010` 可直接跳到对应证据卡；工作簿公式回读为 120 个相对 `HYPERLINK`。
- 当前 POC-03 全量单元测试 30/30 通过，包含“APPROVED 状态不得绕过其他必填字段”的回归用例。
- 该结果仅为 `PASS_FOR_UX_REVIEW`，不代表正式交接 ActionItem 模块或 P03-A02 通过。

## Source Type Eligibility Audit

- 审计脚本按原文件标题的显式“合同”或“技术协议”标识进行确定性分类，不读取 AI 推断作为正式来源类型。
- 120 条候选中，20 条合同已验证，25 条需从 `CONTRACT` 纠正为 `TECHNICAL_AGREEMENT`。
- 75 条来自历史解决方案，均不属于锁定的 `STANDARD_CAPABILITY`、`CONTRACT`、`TECHNICAL_AGREEMENT`、`SURVEY`，已标记排除而非伪造映射。
- 当前只有 45 条合格来源，距最低 100 条差 55 条，并缺少标准能力和调研两类真实语料。
- 审计本身 PASS；P03-A02 状态为 `BLOCKED_MISSING_SOURCE_CORPORA`。

## Result

候选集、工作簿、严格导入、确认交互原型、来源资格审计和 P03-A04 Embedding 绑定已验证。R2 的 120 行虽均由用户填为 `APPROVED`，但只有 45 条来源合格；75 条历史解决方案不能进入锁定四类。P03-A02 现为 `BLOCKED`，不能计算或宣称 Top-5 Recall、分类准确率和引用准确率通过。

## Known Issues

1. 两个资料库共 10 个旧版二进制 `.doc` 尚不支持。
2. 当前来源覆盖历史方案以及合同/技术协议，仍缺少独立的标准能力和调研样本确认。
3. Tesseract 扫描件结果尚未完成语义准确率人工标注。
4. R2 虽有 120 条不同查询且人工状态均为 `APPROVED`，但 75 条 `SOLUTION` 缺少锁定枚举映射，且分类仍需人工语义确认，不得用状态值制造真值。
5. R3 的本地证据定位器是 PoC；Office 文件尚不能从浏览器自动跳到精确段落并高亮，正式产品需由内置 Evidence Viewer 实现。
