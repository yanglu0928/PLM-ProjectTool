# 技术基线

除非用户明确要求“修改已锁定方案”，以下选型不得替换。

|领域|锁定方案|
|---|---|
|主语言|Python 3.13.x|
|Web|Vue 3 + TypeScript + Vite|
|API|FastAPI + Uvicorn，REST/JSON，`/api/v1`，AI 流式使用 SSE|
|数据库|PostgreSQL 18|
|ORM/Migration|SQLAlchemy 2.x + Alembic|
|向量|pgvector|
|PDF|PyMuPDF 主、pdfplumber 辅|
|OCR|PaddleOCR 主、Tesseract/OCRmyPDF 辅|
|Word/PPT|python-docx、python-pptx|
|VSDX|P1；模板驱动或 Aspose.Diagram|
|配置|YAML/.env + 数据库配置 + 加密 Secret|
|认证|内置用户名密码；Server Session + HttpOnly Cookie|
|缓存|进程内缓存|
|后台任务|PostgreSQL Job Table + Worker Process|
|插件|Python 独立子进程 + JSON-RPC over stdio|
|License|MAC 规范化 → SHA-256；Ed25519 签名|
|目标环境|Windows 11、Windows Server 2025、Debian 13；x86-64/AMD64|
|最低资源|4 Core / 8 GB RAM / 100 GB SSD；不运行本地模型|

## AI Provider

首批实际验收使用 DeepSeek；架构同时保留 OpenAI-compatible、Anthropic Messages、Gemini Native 和 Custom Provider Adapter。业务模块不得直接依赖任何厂商 SDK。

Reranker 使用外部可配置 API，服务器不做本地推理。

## 文件与部署

第一版本地文件系统保存文件，PostgreSQL 保存元数据。文件必须经 API 权限检查，不能暴露为可直接访问的静态目录。

第一版为单服务器部署，包含 Web、FastAPI、Worker、PostgreSQL/pgvector、文件存储和 Plugin Host。

## 明确禁止引入

- 微服务、Redis、Kafka、RabbitMQ、独立向量数据库。
- 本地大模型、SSO、手机 App、第三方插件市场。
- 客户自开发插件、AI 原型执行沙箱、自动代码提交。
- WebSocket、FTP、COM、ActiveX、自定义 TCP。
- 自行实现完整 Visio OOXML。
