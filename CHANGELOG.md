# 版本说明

本文件记录 PLM 项目实施辅助工具的可交付变更。正式版本发布时，应将 `Unreleased` 内容归入对应版本，并补充版本号、发布日期、兼容性、安装或升级要求、Migration、已知问题和验证结果。

## Unreleased

### 新增

- 纳入《AI自主执行与最小人工确认规则 V1.0》：新增 `.ai/SKILL.md`、根目录 `STATUS.md` 和 `docs/decisions/decision-log.md`，后续采用 L1 自主执行、L2 记录、L3/Gate 确认模式。
- 新增 Codex/GPT 周额度保护：自动执行开始、WBS 切换前和长任务结束后检查周窗口，剩余低于 20% 时保存检查点并停止新任务；额度重置仍须用户逐次明确确认。
- 用户授权在当前 Scope 和正确分支内使用已绑定 GitHub 身份自动 fetch、commit、push，同时保留禁止 force push、直接提交 main、覆盖未知远端改动和上传敏感数据的约束。
- 建立仓库级 AI 开发约束入口。
- 建立项目开发 Skill，以及架构、技术、开发、测试、PoC 和发行规则。
- 将 GitHub 私有仓库设为唯一代码和版本说明同步目标。
- 启动 Phase 0，建立 PoC 工作区、执行登记表和三平台环境矩阵。
- 建立 POC-01 Python 3.13 依赖分组、环境采集、最小功能验证及三平台在线/离线验证脚本。
- 完成 Windows 11 / Python 3.13.15 Python 包在线与 wheelhouse 离线验证：109 个制品、15/15 项检查通过。
- 基线升版至实施方案 V2.1 / 总控规范 V1.1，新增 Windows 11，与 Windows Server 2025、Debian 13 并列支持。
- 增加 Windows 11 中文扫描 PDF 的 OCRmyPDF/Tesseract 端到端验证脚本，并记录 Ghostscript 安装与许可证风险。
- Windows 11 中文 searchable PDF 主链验证通过：Tesseract 5.4 + OCRmyPDF 17.12.1 + `tessdata_best`，5/5 术语命中。
- 完成 Ghostscript 10.08.0 项目内 portable 安装脚本及 SHA-256 校验，Windows 11 PDF/A-2b 验证通过。
- 修复 OCRmyPDF deskew 在中文 Windows 错误输出上的编码兼容问题，补充 UTF-8/本地编码回退单元测试。
- 新增 ADR-002，采用 Ghostscript AGPL 源码公开策略；仓库公开、项目许可证和第三方声明仍为发行 Gate。
- 完成 Windows Server 2025 Datacenter 10.0.26100 实机验证：Python 3.13.15 官方嵌入式运行时、完整离线依赖、15/15 项检查、Tesseract/OCRmyPDF/Ghostscript PDF/A-2b 与 deskew 中文主链全部通过。
- 增加 Windows Server 2025 非管理员部署脚本；当系统策略拒绝 Python EXE 安装器时，回退到校验过的官方嵌入式包。
- 根据用户决定登记 `EXC-P0-001`，暂缓 Debian 13 的 POC-01 验证；POC-01 以 `PASS_WITH_EXCEPTION` 收口，不形成 Debian 兼容性结论。
- 启动 POC-02，新增 PostgreSQL 18 + pgvector 工作区、三平台验收矩阵和 Windows 可用性检查脚本。
- 完成 Windows 11 首轮可用性检查：PostgreSQL 18.6 官方 Windows x64 安装器/二进制 ZIP 与 pgvector 0.8.6 源码可用；MSVC x64/`nmake` 工具链尚未安装。
- 完成 Windows 11 PostgreSQL 18.6 便携式初始化、启动、SQL 和停止验证；发现含中文字符的数据库运行路径会触发编码失败，当前约束为使用纯 ASCII 路径。
- 安装并验证 Visual Studio Build Tools 2022 17.14.41 / MSVC 14.44 x64，按 pgvector 官方流程构建并加载 pgvector 0.8.6。
- 新增 POC-02 SQLAlchemy/Alembic 验证脚手架；空库 up/down 与有数据升级/回退均通过。
- 完成 Windows 11 100,000 条 32 维向量 HNSW 验证：20 组 Top-5 平均及最低 Recall 均为 100%，并完成 `pg_dump` / `pg_restore` 与重启健康检查。
- 完成 Windows Server 2025 完全断网验证：PostgreSQL 18.6、pgvector 0.8.6、SQLAlchemy/Alembic、100,000 条向量 HNSW、备份恢复及重启全部通过。
- 新增 Windows Server 2025 最小离线包生成与来宾验收脚本；运行包和证据均记录 SHA-256，虚拟网卡在验证结束后恢复。
- 修复 Windows PowerShell 5.1 将 `psql` 普通 stderr/NOTICE 误判为终止错误的问题，并兼容嵌入式 Python 的 Alembic 本地模块路径。
- 根据用户决定登记 `EXC-P0-002`，暂缓 POC-02 的 Windows 11 完全断网重放与 Debian 13 验证；POC-02 以 `PASS_WITH_EXCEPTION` 收口，未验证范围不形成兼容性结论。
- 启动 POC-05，新增 Document + OCR 工作区、六类输入三平台验收矩阵、PoC 统一 ParsedDocument JSON Schema 与验证性解析脚手架。
- 完成 POC-05 Windows 11 六类输入统一解析：DOCX、PPTX、XLSX、CSV、文本 PDF 和扫描 PDF 均输出 PoC ParsedDocument，Schema 与来源定位断言通过。
- 完成 PP-OCRv5 mobile PaddleOCR 主链及 Tesseract/OCRmyPDF 辅助链验证；固定退化扫描样本在 Windows 11 三条链均达到 5/5 术语召回，PDF/A-2b 与中文 `--deskew` 通过。
- 修复 PaddlePaddle 3.3.1 Windows CPU oneDNN 未实现错误，验证性解析器固定 `enable_mkldnn=False`；该约束保留到后续上游版本回归。
- 完成 Windows Server 2025 完全断网 POC-05 复跑：本地 PaddleOCR 模型、离线 JSON Schema wheel、六类输入和三条 OCR 链共 8/8 PASS。
- 修复 Windows PowerShell 5.1 对 Python 无 BOM UTF-8 JSON 的本地代码页误读，Server 驱动显式使用 UTF-8 回读证据。
- 新增 POC-05 真实方案库只读批量验证器：对 18 个、365,328,831 字节的本地方案文件执行隐私隔离、OOXML 完整性、统一解析、Schema 和输入不变性检查。
- 完成 Windows 11 真实方案库复跑：17/17 个受支持的 DOCX、PPTX 和文本 PDF 通过，18/18 原件未改变；1 个旧版 `.doc` 明确记录为 `UNSUPPORTED`。
- 修复 DOCX 无名称段落样式触发的空值异常，并优化文本 PDF 分类，避免仅少量低文本页时错误地对整本启动 OCR。
- 启动 POC-04，新增统一 AIService、ModelRouter、ProviderAdapter 与 DeepSeek Chat Completions 验证实现，不在业务入口硬编码厂商 URL 或 SDK。
- 完成 Windows 11 POC-04 11/11 确定性场景及 11/11 单元测试，覆盖文本、SSE、JSON Schema、timeout、401、429、503、流式中断与厂商隔离。
- 完成 DeepSeek 官方端点真实验证：401 错误映射、文本、SSE 流式和结构化 JSON 全部通过，密钥和响应正文均未写入证据。
- 修复真实 JSON Output 首次返回不可解析内容时不重试的问题；JSON/Schema failure 现纳入最多 3 次受控重试，首次失败证据保留。
- 完成 Windows Server 2025 POC-04 实机验证：11/11 单元测试、11/11 确定性场景及 DeepSeek 真实 401、文本、SSE 流式和结构化 JSON 全部通过。
- 新增 POC-04 Windows Server 2025 验证包生成与来宾机执行脚本；临时密钥执行后删除，提交证据不记录 Secret 或响应正文。
- 根据用户决定登记 `EXC-P0-003`，暂缓 POC-04 的 Debian 13 验证；POC-04 以 `PASS_WITH_EXCEPTION` 收口，不形成 Debian 兼容性结论。
- 启动 POC-03，新增 Golden Dataset JSON Schema、三平台验收矩阵、确定性 Chunk 和候选评审生成器。
- 将本地历史方案与技术协议/合同作为只读 POC-03 输入：26 个受支持文件生成 60,430 个块、655 个 PROJECT Chunk 和 120 条候选评审记录；候选正文不进入 Git。
- 修复 POC-05 Tesseract 页面图片句柄未及时关闭导致的 Windows 临时目录清理失败，并增加句柄关闭回归测试。
- POC-05 真实资料验证新增 4 个 DOCX 和 5 个扫描 PDF，9/9 个受支持文件通过；过滤 macOS `._` 旁车文件，9 个旧版 `.doc` 明确记录为不支持。
- POC-03 新增本地 Golden Dataset 人工评审工作簿：120 条候选、2 张工作表、3 组受控下拉、完备性公式、筛选表和冻结窗格；含客户资料的工作簿继续由 Git 忽略。
- POC-03 新增评审表严格导入器：复核来源字段、人工必填项和引用边界，只允许 100~200 条人工批准记录按锁定 Schema 导出正式 Golden Dataset。
- POC-03 评审导入器兼容人工“确认全部建议定位”和 `YYYY.M.D`/`YYYY/M/D` 本地日期；修正后实际评审表为 109 条 APPROVED、11 条 PENDING、0 个导入问题。
- POC-03 启动 P03-A04，新增不可变索引—Embedding 模型绑定与向量维度保护；同一索引禁止原地更换模型或维度。
- POC-03 新增 OpenAI-compatible Embedding 安全探测入口；API Key 仅从环境变量读取，报告不保存输入文本、向量值或厂商响应正文。
- POC-03 修复 Windows 隔离运行时缺少 `tzdata` 时探测报告无法生成的问题，改用操作系统本地时区时间戳。
- POC-03 P03-A04 实际调用百炼 `qwen3.7-text-embedding`，请求与返回均为 1024 维；索引 `v1` 单模型绑定 PASS。
- POC-03 将 109 条人工 APPROVED 记录完成 Schema 合法导出；覆盖审计发现仅 1 个唯一查询、1 种来源类型和 1 种分类，故质量 Gate 保持未通过。
- POC-03 新增可重复执行的脱敏 Gold Set 覆盖审计，校验查询唯一性、四类来源和六类分类，不保存查询或客户内容。
- POC-03 新增完全本地的评审建议生成器和 R2 工作簿：生成 120 条不同查询及配套建议，全部重置为 PENDING；45 条 CONTRACT 可映射，75 条 SOLUTION 不伪造来源类型并留待人工确认，客户正文未上传外部 AI 服务。
- POC-03 复核用户填写后的 R2：120 行均标记为 APPROVED，45 行满足全部必填 Gate，75 行仍缺来源类型；人工状态值不能绕过正式数据校验。
- POC-03 新增 R3 人工确认待办交互原型：主表不再填充大段原文，提供 120 个本地证据定位链接、逐项维护提示、人工处理下拉和状态提示，并完整保留 R2 技术评审页。
- 新增交接分析 UX 设计边界：AI 发现与正式 ActionItem 分离，经人工确认后才可生成待办；正式产品应使用 Evidence Viewer 按文档版本与来源定位自动跳转和高亮。
- POC-03 新增来源资格审计：确定性识别 20 条合同和 25 条技术协议，发现 25 条需纠正来源类型；75 条历史解决方案不自动伪造为标准能力或调研。当前缺少 55 条合格记录以及两类真实语料，P03-A02 转为 BLOCKED。
- POC-03 P03-A05 完成真实换模重建验证：旧 `qwen3.7-text-embedding` 1024/v1 原地换模被拒绝；新建 `text-embedding-v4` 768/v2，120 条固定非客户文本通过 12 批完成 120/120 重建，旧向量复用 0；v2 保持未激活。
- POC-03 P03-A06 完成 PostgreSQL 18.6/pgvector ProjectId 隔离验证：两个项目、40 条合成记录执行 6 组 Vector/FTS/Hybrid Top-5，30 行结果跨项目泄漏 0；缺失 ProjectId 拒绝，参数注入结果 0。
- POC-03 P03-A07 完成 PostgreSQL Full Text 验证：`simple` 配置结合上游中文术语空格规范化，4 场景/40 条合成记录 Top-5 平均与最低 Recall 100%，表达式 GIN 索引命中；未宣称数据库原生中文分词。
- POC-03 P03-A08 完成 pgvector HNSW Top-5 验证：1,000 条合成三维向量、4 组已知近邻的平均与最低 Recall 100%，执行计划命中 HNSW；不替代真实 Golden Dataset 指标。
- POC-03 P03-A09 完成 Hybrid Retrieval 验证：Vector 0.6 + Full Text 0.4、每通道 4 倍 Top-K 候选池，HNSW `m=32`/`ef_construction=200`/`ef_search=200`；1,000 条合成记录、4 场景 Top-5 平均与最低 Recall 100%，GIN/HNSW 均命中。
- POC-03 P03-A10 完成外部可配置 Reranker：百炼华北 2 `qwen3-rerank` 真实 5→3 重排通过；新增响应完整性校验，以及 HTTP 429、超时、无效响应 fail-open 降级和脱敏记录。
- POC-03 P03-A14 完成 Context Builder → AIService 验证：新增相关度排序、字符预算、Chunk/来源引用、Prompt/Project Trace，并通过 POC-04 `AIService → ModelRouter → ProviderAdapter` 完成结构化输出校验。
- POC-03 P03-A15 完成异常与空结果验证：DB 不可用停止、空/低可靠度禁止 AI、Reranker fail-open、AI 错误脱敏与正常链路共 6 场景通过。

### 兼容性

- 正式目标环境为 Windows 11、Windows Server 2025、Debian 13，均为 x86-64/AMD64。
- 当前仍处于 Phase 0 技术验证执行期，尚无可发布程序版本。

### Migration

- 无正式产品 Migration；POC-02 包含两版验证性 Alembic migration，用于验证空库和有数据 up/down，不进入正式数据模型基线。

### 验证结果

- 项目 Skill 结构校验通过。
- POC-01 本轮要求覆盖 2/2：Windows 11、Windows Server 2025 PASS；Debian 13 为 `DEFERRED_BY_USER`。
- POC-02 Windows 11 除“完全断网”外的功能验收项 PASS。
- POC-02 Windows Server 2025 全部验收项 PASS；20 组 Top-5 平均及最低 Recall 100%，备份恢复条数与 ID 校验和一致。
- POC-02 当前要求覆盖按例外处理完成：Windows 11 功能链 PASS、Windows Server 2025 完全断网功能链 PASS；Windows 11 断网重放与 Debian 13 为 `DEFERRED_BY_USER`。
- POC-05 Windows 11 功能链 PASS；Windows Server 2025 完全断网 8/8 PASS；扫描 PDF 三条 OCR 链在两端均为 5/5 术语召回。
- POC-05 Windows 11 真实方案库批次为 `PARTIAL_PASS`：当前支持格式 17/17 PASS，旧版 `.doc` 1 个不支持；该批次没有真实扫描 PDF，不形成真实扫描件准确率结论。
- POC-04 当前要求覆盖按例外处理完成：Windows 11、Windows Server 2025 功能链 PASS，两端确定性场景均为 11/11，真实 DeepSeek 文本/流式/结构化/401 全部通过；Debian 13 为 `DEFERRED_BY_USER`。
- POC-03 P0.09 候选准备 PASS：120 条候选覆盖 26/26 个可解析文档，全部保持 `PENDING_HUMAN_REVIEW`；正式 Golden Dataset 和三项质量指标尚未执行。
- POC-05 Windows 11 真实技术协议/合同批次为 `PARTIAL_PASS`：当前支持格式 9/9 PASS，含 5 个扫描 PDF、105 页和 45,145 个 OCR 行；9 个旧版 `.doc` 不支持。
- POC-03 人工评审工作簿生成验证通过：两张工作表均完成渲染检查，导出后回读成功，公式错误为 0；初始 120 条全部为 `PENDING`，尚未形成正式 Golden Dataset。
- POC-03 R2 初始生成验证为 25/25 单元测试通过、120 行全部 PENDING、0 个来源一致性问题、明细公式错误扫描为 0；P03-A04 真实 Embedding 探测与索引绑定 PASS。
- POC-03 R3 确认交互原型验证通过：30/30 单元测试通过，R2 技术页逐单元格差异为 0，主表含 120 个相对证据链接，本地定位器含 120 个候选锚点和 120 个原文件入口；状态为 `PASS_FOR_UX_REVIEW`，不代表 P03-A02 或正式交接模块通过。
- POC-03 当前 49/49 单元测试通过；P03-A08 HNSW 与 P03-A09 Hybrid 的 4 组 Top-5 平均/最低 Recall 均为 100%。
- POC-03 P03-A10 完成后 56/56 单元测试通过；Reranker 真实请求与三类降级场景均 PASS。
- POC-03 P03-A14 完成后 62/62 单元测试通过；统一 AIService 调用链和禁止 RAG 直连厂商的边界检查 PASS。
- POC-03 P03-A15 完成后 68/68 单元测试通过；除 P03-A02 及其阻塞的 P03-A11~A13 外，可独立执行的 Windows 11 验收项均已完成。

### 已知问题

- Phase 0 阻塞 PoC 尚未全部通过，禁止进入大规模正式业务开发。
- Debian 13 尚无可用验收环境，兼容性保持未验证；恢复 Debian 验证或发行时必须重新开启相关 Gate。
- POC-02 Windows 11 完全断网与 Debian 13 尚未验证；虽已按批准例外收口，仍不能宣称三平台全部 PASS。
- PostgreSQL 18.6 在 Windows 中文运行路径存在 `initdb` 编码失败；当前部署路径必须为纯 ASCII。
- POC-05 Windows 11 物理断网、Debian 13 和真实脱敏扫描件尚未验证，当前状态保持 `IN_PROGRESS`。
- 当前工作区依赖未提供打包 LibreOffice，POC-05 DOCX 样本未完成 DOCX 转 PNG 视觉检查；OOXML 结构解析已通过，Office 打开性留在 POC-06。
- POC-05 当前不支持旧版二进制 `.doc`；真实方案库中的 1 个文件未转换、未解析，是否纳入 P0 需单独确认。
- POC-04 Debian 13 尚未验证；虽已依据 `EXC-P0-003` 收口，仍不得声明 Debian 兼容或通过 Debian Release Gate。
- POC-03 旧 R1 的 109 条批准记录覆盖审计失败；当前 R2 虽有 120 条不同查询且用户已全部标记 APPROVED，但 75 条 SOLUTION 来源无锁定枚举映射，在通过完整 Gate 前不得运行或宣称 Top-5 Recall、分类准确率和引用准确率。
- POC-03 R2 已由用户将 120 行标记为 APPROVED，但 75 条 SOLUTION 仍无锁定来源类型；R3 仅改善人工确认体验，不能替代正式来源决策或 Golden Dataset Gate。
- 两个本地资料库共 10 个旧版二进制 `.doc` 不受当前统一解析器支持，未自动转换或改写。
