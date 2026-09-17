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
|POC-03|P0.09/P0.10/P0.12|PLM RAG|IN_PROGRESS|2026-09-17|-|Windows 11 已生成 655 个可追溯 Chunk、120 条候选和 R2 本地预填评审表；当前 120 条 PENDING、0 条 APPROVED、0 个一致性问题，正式集和质量指标未执行|`poc/poc-03-plm-rag/`|
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
