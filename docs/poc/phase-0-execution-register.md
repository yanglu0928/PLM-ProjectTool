# Phase 0 执行登记表

## 阶段状态

|字段|值|
|---|---|
|Phase|Phase 0 技术验证|
|状态|IN_PROGRESS|
|启动日期|2026-09-17|
|正式开发 Gate|BLOCKED|
|完成条件|全部 P0 PoC PASS，或失败项具有用户确认的替代方案|

## PoC 登记

|PoC|对应 WBS|验证主题|状态|开始日期|完成日期|结论|证据|
|---|---|---|---|---|---|---|---|
|POC-01|P0.01/P0.01S/P0.02/P0.03/P0.04|Python 3.13 三平台依赖及离线安装|PASS_WITH_EXCEPTION|2026-09-17|2026-09-17|Windows 11、Windows Server 2025 PASS；Debian 13 经用户批准暂缓，不构成兼容性结论|`poc/poc-01-python-313-dependencies/`、`docs/poc/phase-0-exceptions.md`|
|POC-02|P0.05/P0.06/P0.07/P0.08|PostgreSQL 18 + pgvector|PASS_WITH_EXCEPTION|2026-09-17|2026-09-17|Windows 11 功能链 PASS；Windows Server 2025 完全断网功能链 PASS；Windows 11 断网重放与 Debian 13 经用户批准暂缓，不构成对应兼容性结论|`poc/poc-02-postgresql-18-pgvector/`、`docs/poc/phase-0-exceptions.md`|
|POC-03|P0.09/P0.10/P0.12|PLM RAG|FAIL|2026-09-17|-|P03-A11 R5 保护性融合达到 Top-5 114/120（95.00%）并 PASS；Prompt v2 分类为 51/120（42.50%）、引用为 62/120（51.67%）。R7 重新评审包等待人工确认，独立留出集尚未建立，PoC 总体保持 FAIL|`poc/poc-03-plm-rag/`|
|POC-04|P0.11|AI Gateway / DeepSeek|PASS_WITH_EXCEPTION|2026-09-17|2026-09-17|Windows 11、Windows Server 2025 统一网关、11/11 确定性场景及真实文本/流式/结构化/401 PASS；Debian 13 经用户批准暂缓，不构成兼容性结论|`poc/poc-04-ai-gateway/`、`docs/poc/phase-0-exceptions.md`|
|POC-05|P0.04/P0.12|Document + OCR|IN_PROGRESS|2026-09-17|-|Windows 11 六类输入和主辅 OCR 功能链 PASS；Windows Server 2025 完全断网 8/8 PASS；Windows 11 真实资料 26/26 个受支持文件通过并含 5 个扫描 PDF；Windows 11 断网、Debian 13 和真实扫描语义准确率待处理|`poc/poc-05-document-ocr/`|
|POC-06|P0.16/P0.17|Word / PPT|NOT_STARTED|-|-|-|-|
|POC-07|P1|VSDX|DEFERRED_P1|-|-|不阻塞 Phase 0|-|
|POC-08|P0.13|Plugin Host|NOT_STARTED|-|-|-|-|
|POC-09|P0.14/P0.15|License|NOT_STARTED|-|-|-|-|

## 状态定义

- `NOT_STARTED`：尚未开始。
- `IN_PROGRESS`：已有执行活动，但未满足完整验收条件。
- `BLOCKED`：当前缺少必要环境、输入或决策。
- `PASS`：全部必需产物和验收项通过。
- `PASS_WITH_EXCEPTION`：已验证范围通过，未验证范围具有用户明确批准的书面例外；不得把例外范围描述为已验证。
- `FAIL`：已形成完整失败分析，尚无获批替代方案。
- `DEFERRED_P1`：正式降级为 P1，不阻塞 Phase 0。

## 变更记录

|日期|变更|
|---|---|
|2026-09-17|建立 Phase 0 登记表并启动 POC-01。|
|2026-09-17|完成 Windows 11 / Python 3.13.15 在线与 wheelhouse 离线预检；POC-01 保持 IN_PROGRESS。|
|2026-09-17|基线升版：新增 Windows 11，与 Windows Server 2025、Debian 13 并列为正式目标环境。|
|2026-09-17|Windows 11 完成 Tesseract/OCRmyPDF 中文扫描 PDF 主链验证，POC-01 平台覆盖达到 1/3。|
|2026-09-17|Windows 11 完成 Ghostscript 10.08.0 portable 安装、deskew 编码修复及 PDF/A-2b 回归验证。|
|2026-09-17|Windows Server 2025 Datacenter 实机完成 Python 3.13.15 官方嵌入式运行时、109-wheel 完全离线安装、15/15 项检查及中文 OCR/PDF-A-2b/deskew 验证；POC-01 平台覆盖达到 2/3。|
|2026-09-17|用户明确批准 Debian 13 本轮不验证；登记 `EXC-P0-001`，POC-01 以 `PASS_WITH_EXCEPTION` 收口，Debian 兼容性仍为未验证。|
|2026-09-17|启动 POC-02；创建工作区和验收矩阵，完成 Windows 11 PostgreSQL 18.6 / pgvector 0.8.6 官方制品可用性检查。|
|2026-09-17|POC-02 Windows 11 功能链通过：便携式 PostgreSQL 18.6、MSVC x64 构建 pgvector 0.8.6、SQLAlchemy/Alembic、10 万向量 HNSW、备份恢复及重启；登记中文运行路径约束，完全断网与另两平台保持 NOT_RUN。|
|2026-09-17|POC-02 Windows Server 2025 在物理网卡断开状态完成全新离线部署、SQLAlchemy/Alembic、10 万向量 HNSW、备份恢复与重启；修复 Windows PowerShell 5.1 stderr 误判和嵌入式 Python Alembic 路径兼容。|
|2026-09-17|用户批准 `EXC-P0-002`：暂缓 POC-02 Windows 11 完全断网重放与 Debian 13 验证；POC-02 以 `PASS_WITH_EXCEPTION` 收口，未验证范围不形成兼容性结论。|
|2026-09-17|启动 POC-05；创建 Document + OCR 工作区、PoC 统一 ParsedDocument Schema 和三平台验收矩阵，从 Windows 11 六类输入验证开始。|
|2026-09-17|POC-05 Windows 11 六类输入、统一 Schema、来源定位、PaddleOCR/Tesseract/OCRmyPDF 全部通过；PaddlePaddle 3.3.1 Windows CPU 需关闭 oneDNN。|
|2026-09-17|POC-05 Windows Server 2025 在虚拟网卡断开状态完成受控模型与制品全新复跑，六类输入和三条 OCR 链 8/8 PASS；修复 PowerShell 5.1 无 BOM UTF-8 JSON 回读问题。|
|2026-09-17|启动 POC-04；建立 AIService、ModelRouter、DeepSeekAdapter、验收矩阵和官方协议快照。|
|2026-09-17|POC-04 Windows 11 确定性场景 11/11 PASS，DeepSeek 官方端点 401、真实文本、SSE 流式和结构化 JSON 全部通过；修复 JSON/Schema failure 未受控重试的问题。|
|2026-09-17|POC-04 Windows Server 2025 实机完成 11/11 单元测试、11/11 确定性场景及 DeepSeek 官方端点 401、真实文本、SSE 流式和结构化 JSON 验证；临时密钥已删除，脱敏证据扫描无匹配。|
|2026-09-17|用户批准 `EXC-P0-003`：暂缓 POC-04 Debian 13 验证；POC-04 以 `PASS_WITH_EXCEPTION` 收口，Debian 兼容性仍为未验证。|
|2026-09-17|启动 POC-03；建立 Golden Dataset Schema、三平台验收矩阵、确定性 Chunk 和候选评审生成器。|
|2026-09-17|POC-03 Windows 11 只读处理历史方案及技术协议/合同：26 个受支持文件生成 60,430 个块、655 个 Chunk 和 120 条候选记录；全部候选保持 `PENDING_HUMAN_REVIEW`，未冒充正式 Golden Dataset。|
|2026-09-17|修复 POC-05 Tesseract 页面图片句柄未及时关闭导致 Windows 临时目录清理失败，并过滤 macOS `._` 旁车文件；技术协议/合同批次 9/9 个受支持文件通过。|
|2026-09-17|POC-03 生成本地人工评审工作簿：120 条候选、2 张工作表、3 组下拉规则和完备性公式；导出后回读与公式错误扫描通过，候选仍保持 0 条 APPROVED。|
|2026-09-17|POC-03 新增评审表严格导入 Gate：校验不可变来源、人工字段、引用边界和正式 Schema；后续兼容人工“确认全部定位”和 `YYYY.M.D` 本地日期输入。|
|2026-09-17|POC-03 修正后评审表复验通过：120 行中 109 条 APPROVED、11 条 PENDING、0 个导入问题；人工 Gate 已 READY，未通过记录不导出。|
|2026-09-17|进入 P03-A04：单索引单 Embedding 模型的不可变绑定、模型/维度漂移拒绝和向量维度校验已通过；候选百炼模型缺少 live probe 凭据，保持 IN_PROGRESS。|
|2026-09-17|P03-A04 Windows 11 PASS：百炼 `qwen3.7-text-embedding` 使用固定非客户文本真实返回 1024 维，索引 `v1` 绑定激活；Key、输入和向量未提交。|
|2026-09-17|109 条 APPROVED 记录完成 Schema 合法导出，但覆盖审计 FAIL：仅 1 个唯一查询、1 种来源类型和 1 种分类；P03-A02 保持 IN_PROGRESS，不进入质量指标计算。|
|2026-09-17|生成 POC-03 R2 本地预填评审表：120 条不同查询、120 条引用预填，全部重置为 PENDING；45 条 CONTRACT 可明确映射，75 条 SOLUTION 因锁定枚举无对应类型保留待人工确认；未调用外部 AI 服务。|
|2026-09-17|用户完成 R2 填写：120 行均为 APPROVED；独立 Gate 仅认定 45 行完整，75 行仍缺来源类型，状态值不绕过必填验证。|
|2026-09-17|依据用户体验反馈生成 POC-03 R3 人工确认待办原型：主表移除大段正文，增加 120 个证据定位链接、明确维护提示和人工处理选项；R2 技术页原样保留。该原型不是正式项目交接 ActionItem 模块。|
|2026-09-17|POC-03 来源资格审计 PASS：20 条合同、25 条技术协议合格，75 条历史解决方案不得伪造映射；P03-A02 因缺少至少 55 条合格记录及标准能力/调研语料转为 BLOCKED。|
|2026-09-17|P03-A05 Windows 11 PASS：旧 `v1` 原地换模被拒绝；新建 `text-embedding-v4` 768 维 `v2`，以 120 条非客户文本真实调用 12 批完成 120/120 全量重建，旧向量复用 0，v2 未激活。|
|2026-09-17|P03-A06 Windows 11 PASS：PostgreSQL 18.6 + pgvector 0.8.6 上两个项目、40 条合成记录执行 Vector/FTS/Hybrid 6 组 Top-5，30 行结果跨项目泄漏 0；缺失 ProjectId 拒绝，注入式参数返回 0。|
|2026-09-17|P03-A07 Windows 11 PASS：PostgreSQL `simple` + 上游中文术语空格规范化，4 场景/40 条合成记录 Top-5 平均与最低 Recall 100%，GIN 执行计划命中；不形成原生中文分词结论。|
|2026-09-17|P03-A08 Windows 11 PASS：pgvector HNSW cosine 在 1,000 条合成向量、4 组已知近邻上的 Top-5 平均与最低 Recall 100%，执行计划命中 HNSW；不形成真实语料质量结论。|
|2026-09-17|P03-A09 Windows 11 PASS：Vector 0.6 + Full Text 0.4，加大每通道候选池并提高 HNSW 构建/搜索深度后，1,000 条合成记录、4 场景 Top-5 平均与最低 Recall 100%，执行计划同时命中 GIN/HNSW；参数待真实 Gold Set 校准。|
|2026-09-17|P03-A10 Windows 11 PASS：百炼华北 2 `qwen3-rerank` 真实 5→3 重排通过，两个预期相关项位列前二；HTTP 429、超时和无效响应均按原候选顺序降级，证据未保存 Secret 或内容。|
|2026-09-17|P03-A14 Windows 11 PASS：Context Builder 按相关度和字符预算生成可追溯上下文，实际调用统一 `AIService → ModelRouter → ProviderAdapter`，Prompt/Project/Chunk Trace 与结构化输出校验通过，RAG 未直连厂商。|
|2026-09-17|P03-A15 Windows 11 PASS：DB 不可用、空结果、低可靠度、Reranker 不可用、AI 不可用及正常链路共 6 场景通过；空/低可靠度不调用 AI，错误证据保持脱敏。POC-03 转为等待 P03-A02 L3 决策。|
|2026-09-18|P03-A02 Windows 11 PASS：R4 严格导入 120 条 APPROVED、0 个问题；覆盖 29 份文档、120 个唯一查询、四类来源和六类结果。|
|2026-09-18|P03-A11~A13 Windows 11 首轮真实验证完成并判定 FAIL：Top-5 Recall 72/120（60.00%）、分类准确率 17/120（14.17%）、来源引用准确率 61/120（50.83%）；120/120 实时重排、GIN/HNSW 命中、无缺失预测和越界引用。POC-03 转为 `FAIL / BLOCKED_QUALITY_GATE`。|
|2026-09-18|R5 人工批量确认严格导入 120/120，Schema 与覆盖审计 PASS；最终数据集使用五类业务标签，工作流态不作为最终分类。|
|2026-09-18|完成分层诊断、72 组候选扫描与 120/120 次百炼真实重排：扩展候选池 115/120（95.83%），重排 Top-5 89/120（74.17%）。中文 OCR 字间空白规范化检索达到 114/120（95.00%），P03-A11 PASS；P03-A13 当前 Top-5 引用上限 95.00%，按 L3 暂停受影响任务。|
|2026-09-18|用户批准方案 A；生成 R6 六项问题与引用复核包、Top-5 证据定位器和严格导入器。未确认复验为 6 条 PENDING、0 个问题、不输出数据集；其余 114 条及全部 R5 分类保持锁定。|
|2026-09-18|用户确认 R6；严格导入为 120/120、问题 0，覆盖审计 PASS。本地 OCR 规范化 Top-5 为 116/120（96.67%）。完整真实复验因需要把查询/候选片段发送至百炼与 DeepSeek，等待本轮显式数据处理授权；拦截前未发送数据。|
|2026-09-18|用户明确授权 R6 数据外发复验；120/120 次百炼重排和 120/120 次 DeepSeek 预测完成。真实端到端 Top-5、分类、引用分别为 60.00%、47.50%、51.67%，均 FAIL；预测缺失 0、越界引用 0、GIN/HNSW 均命中。分层诊断记录 25 条通道召回缺失、15 条融合丢失、8 条重排丢失和 9 条重排恢复。|
|2026-09-20|P03-A11-R4 完成无外部调用的检索链对齐：按 ProjectId 与来源类型过滤，合并 Vector Top-20、Full Text Top-20、OCR 规范化词法 IDF Top-20，保留 0.6/0.4 权重并版本化缓存。本地候选池精确覆盖 119/120（99.17%）、同文档 120/120、来源越界 0，113/113 测试 PASS；正式 Top-5 等待新百炼重排。|
|2026-09-20|用户明确授权 P03-A11-R4 外发复验；120/120 条百炼 `qwen3-rerank` 真实调用完成，纯语义 Top-5 为 91/120（75.83%）。一次接口超时由新增有限重试与逐条断点恢复处理，数据库正常停止。|
|2026-09-20|P03-A11-R5 采用不读取金标的保护性融合：百炼第 1 名 + OCR 规范化词法前 4 名。复用 120 条真实重排缓存后精确 Top-5 114/120（95.00%）、同文档 118/120（98.33%），GIN/HNSW 命中，117/117 测试 PASS；P03-A11 改判 PASS，P03-A12/A13 保持 FAIL。|
|2026-09-20|P03-A12-R1 Prompt v2 本地准备 PASS：仅保留五类正式标签，按匹配性、充分性、满足程度顺序判断；120/120 条 payload 各含 5 个来源隔离且未截断的 R5 Context，Golden 字段泄漏 0，全部外部调用 0，124/124 测试 PASS。分类准确率等待获批后的 DeepSeek 真实复验。|
|2026-09-20|用户明确授权 P03-A12-R2 仅向 DeepSeek 外发 120 条查询及各 5 个 R5 Context；`--prediction-only` 复用完整本地 Embedding/R5 缓存，Embedding 与当前轮 Reranker 外部调用均为 0。120/120 条预测完成；两个瞬时空/非约束响应由逐条缓存断点续跑恢复，PostgreSQL 每轮均正常停止。|
|2026-09-20|Prompt v2 真实复验 FAIL：Top-5 114/120（95.00%），分类 51/120（42.50%），引用 62/120（51.67%），越界引用 0。诊断显示部分抽取式问题无法从输入推导人工“资料不足/非标”标签，唯一期望 Chunk 口径也缺少等价引用集合；冻结 R6、90%/98% 门槛保持不变，P03-A12/A13 转入 L3 质量 Gate。|
|2026-09-20|用户批准重新评审；保留 R6，新建 R7 全量 120 条语义/分类/引用确认包。工作簿含 836 条证据候选和 120/120 原文定位，AI 建议改分类 73 条、改引用 58 条；合同、技术协议和调研材料缺少标准能力交叉证据时保守建议资料不足。4/4 表渲染、公式错误 0，129/129 测试 PASS；未确认预检为 120 PENDING、0 个问题、不输出数据集。|
|2026-09-20|P03-A12-R5 来源锁 PASS：49 份新增实际客户调研记录本地解析与文件/正文 Hash 去重通过；50 条独立候选按 33/7/8/2 配额锁定，排除历史暴露 Chunk、相邻定位和 13 个仅供参考的调研表单块。调研 2/2 均来自新实际记录；141/141 测试 PASS，外部 AI 调用 0。|
