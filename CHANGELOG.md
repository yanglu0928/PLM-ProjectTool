# 版本说明

本文件记录 PLM 项目实施辅助工具的可交付变更。正式版本发布时，应将 `Unreleased` 内容归入对应版本，并补充版本号、发布日期、兼容性、安装或升级要求、Migration、已知问题和验证结果。

## Unreleased

### 新增

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
- POC-03 19/19 单元测试通过；人工评审 Gate 为 READY，P03-A04 本地绑定与安全探测合同通过，但 live provider probe 尚未运行。

### 已知问题

- Phase 0 阻塞 PoC 尚未全部通过，禁止进入大规模正式业务开发。
- Debian 13 尚无可用验收环境，兼容性保持未验证；恢复 Debian 验证或发行时必须重新开启相关 Gate。
- POC-02 Windows 11 完全断网与 Debian 13 尚未验证；虽已按批准例外收口，仍不能宣称三平台全部 PASS。
- PostgreSQL 18.6 在 Windows 中文运行路径存在 `initdb` 编码失败；当前部署路径必须为纯 ASCII。
- POC-05 Windows 11 物理断网、Debian 13 和真实脱敏扫描件尚未验证，当前状态保持 `IN_PROGRESS`。
- 当前工作区依赖未提供打包 LibreOffice，POC-05 DOCX 样本未完成 DOCX 转 PNG 视觉检查；OOXML 结构解析已通过，Office 打开性留在 POC-06。
- POC-05 当前不支持旧版二进制 `.doc`；真实方案库中的 1 个文件未转换、未解析，是否纳入 P0 需单独确认。
- POC-04 Debian 13 尚未验证；虽已依据 `EXC-P0-003` 收口，仍不得声明 Debian 兼容或通过 Debian Release Gate。
- POC-03 已有 109 条人工批准记录，但正式 Golden Dataset 尚待 P03-A04 实际 Embedding 绑定激活后导出；Top-5 Recall、分类准确率和引用准确率仍未运行。
- POC-03 候选 Embedding 服务缺少对应凭据和 live dimension probe；当前候选不得描述为已激活或已冻结。
- 两个本地资料库共 10 个旧版二进制 `.doc` 不受当前统一解析器支持，未自动转换或改写。
