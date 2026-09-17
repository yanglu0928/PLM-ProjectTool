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

### 兼容性

- 正式目标环境为 Windows 11、Windows Server 2025、Debian 13，均为 x86-64/AMD64。
- 当前仍处于 Phase 0 技术验证执行期，尚无可发布程序版本。

### Migration

- 无正式产品 Migration；POC-02 包含两版验证性 Alembic migration，用于验证空库和有数据 up/down，不进入正式数据模型基线。

### 验证结果

- 项目 Skill 结构校验通过。
- POC-01 本轮要求覆盖 2/2：Windows 11、Windows Server 2025 PASS；Debian 13 为 `DEFERRED_BY_USER`。
- POC-02 Windows 11 除“完全断网”外的功能验收项 PASS；Windows Server 2025、Debian 13 仍为 NOT_RUN。

### 已知问题

- Phase 0 阻塞 PoC 尚未全部通过，禁止进入大规模正式业务开发。
- Debian 13 尚无可用验收环境，兼容性保持未验证；恢复 Debian 验证或发行时必须重新开启相关 Gate。
- POC-02 完全断网、Windows Server 2025 与 Debian 13 尚未验证，不能形成跨平台 PASS 结论。
- PostgreSQL 18.6 在 Windows 中文运行路径存在 `initdb` 编码失败；当前部署路径必须为纯 ASCII。
