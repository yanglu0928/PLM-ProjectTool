# POC-02 PostgreSQL 18 + pgvector

## Status

`IN_PROGRESS`

Windows 11 可用性检查已完成；尚未安装、初始化或执行数据库功能验证，不得判定 POC-02 PASS。

## Objective

验证 PostgreSQL 18 与 pgvector 能否在正式目标环境中完成完全离线部署，并通过数据库初始化、SQLAlchemy/Alembic、HNSW、10 万级向量检索、备份和恢复验证。

## Environment

正式目标环境：

- Windows 11 x86-64/AMD64。
- Windows Server 2025 x86-64/AMD64。
- Debian 13 x86-64/AMD64。

当前执行环境：Windows 11 Home 10.0.26200 x86-64，32 个逻辑处理器，31.63 GB RAM，D 盘约 435.29 GB 可用。当前账号不是管理员。

## Input

- PostgreSQL 18.6 Windows x86-64 安装器或官方二进制 ZIP。
- pgvector 0.8.6 源码，Git tag `v0.8.6`，commit `8ee86c96f0fd72390f890aa8a336fda6d3ab4c6c`。
- Visual Studio C++ x64 构建工具和 `nmake`。
- Python 3.13、SQLAlchemy 2.x、Alembic、psycopg 3.x、pgvector Python client。
- 10 万条可重复生成的测试向量。

## Steps

1. 执行 `scripts/windows/check-availability.ps1`，记录操作系统、权限、本机 PostgreSQL 和 C++ 工具链状态，并检查官方制品 URL。
2. 下载并校验 PostgreSQL 18.6、pgvector 0.8.6 及离线构建依赖。
3. 在无管理员服务安装依赖的隔离目录中初始化 PostgreSQL 18 数据目录并启动实例。
4. 使用 x64 MSVC 工具链构建 pgvector，安装到隔离 PostgreSQL 目录。
5. 执行 `CREATE EXTENSION vector`、基础向量 SQL 和 HNSW 验证。
6. 执行 SQLAlchemy/Alembic up/down、空库和有数据升级验证。
7. 导入 10 万条测试向量，记录构建时间、查询延迟和 Recall 指标。
8. 执行 `pg_dump` / `pg_restore`，核对数据量、扩展和索引。
9. 在 Windows Server 2025 重复执行并保留独立证据。

## Result

### Windows 11 可用性检查

|检查项|结果|证据/说明|
|---|---|---|
|PostgreSQL 18 当前稳定维护版本|AVAILABLE|PostgreSQL 官方页面显示 18.6|
|Windows x86-64 安装器|AVAILABLE_ONLINE|HTTP 200，375,833,688 bytes|
|Windows x86-64 二进制 ZIP|AVAILABLE_ONLINE|HTTP 200，343,808,005 bytes|
|PostgreSQL 18 Windows 平台支持|AVAILABLE|官方页面列出 Windows Server 2025/2022；桌面 Windows 属可比平台，仍须本机实测|
|pgvector PostgreSQL 18 支持|AVAILABLE|pgvector 0.8.6 官方文档以 `PGROOT=...\PostgreSQL\18` 给出 Windows 构建命令|
|pgvector 0.8.6 tag|AVAILABLE|远端 tag commit `8ee86c96f0fd72390f890aa8a336fda6d3ab4c6c`|
|本机 PostgreSQL|NOT_INSTALLED|未发现命令、服务、注册表安装项或标准安装目录|
|Visual Studio C++ / `nmake`|NOT_AVAILABLE|未发现 Visual Studio Installer、`cl.exe` 或 `nmake.exe`|
|本机管理员令牌|NO|优先验证便携式 PostgreSQL；安装构建工具可能需要管理员操作|

官方来源：

- <https://www.postgresql.org/download/windows/>
- <https://www.enterprisedb.com/download-postgresql-binaries>
- <https://github.com/pgvector/pgvector>
- <https://github.com/pgvector/pgvector/blob/v0.8.6/CHANGELOG.md>

## Metrics

|指标|目标|当前值|
|---|---|---|
|官方 PostgreSQL Windows 制品可访问性|100%|2/2 URL HTTP 200|
|pgvector PostgreSQL 18 官方支持证据|存在|PASS（0.8.6）|
|本机 PostgreSQL 18 安装与初始化|PASS|NOT_RUN|
|pgvector 构建与 `CREATE EXTENSION`|PASS|BLOCKED_TOOLCHAIN|
|Alembic up/down 与升级|PASS|NOT_RUN|
|10 万级 HNSW|PASS|NOT_RUN|
|备份恢复|PASS|NOT_RUN|
|Windows 平台覆盖|2/2|0/2 功能验证；Windows 11 仅完成可用性检查|

## Logs

- Windows 11 可用性摘要：`evidence/windows-11/availability.json`
- Windows 11 可用性说明：`evidence/windows-11/README.md`
- 总体验收矩阵：`acceptance-matrix.md`

日志和原始下载制品必须保存在被 Git 忽略的 `artifacts/poc-02/`，脱敏摘要才可提交。

## Known Issues

1. Windows 官方 pgvector 安装方式需要 Visual Studio C++ x64 工具链和 `nmake`，当前本机未安装。
2. 当前账号没有管理员令牌；不能假设 EDB 服务安装器和 Visual Studio Build Tools 可静默安装成功。
3. PostgreSQL 18.6 Windows 安装器存在近期已关闭的[上游问题记录](https://github.com/EnterpriseDB/edb-installers/issues/658)，因此本 PoC 同时准备官方二进制 ZIP 作为隔离验证路径；两种路径均尚未执行安装。
4. Windows 11 不是 PostgreSQL 下载页列出的服务器认证平台；官方仅说明可比桌面版本通常可运行，必须以本机执行证据确认。
5. Debian 13 本轮尚未开始；`EXC-P0-001` 只适用于 POC-01，不自动扩展到 POC-02。

## Conclusion

PostgreSQL 18.6 和 pgvector 0.8.6 均存在官方 Windows 18 路径，Windows 11 具备继续准备离线制品的基础条件。当前只能判定“制品来源可用”，不能判定“PostgreSQL 18 + pgvector 已兼容 Windows 11”。下一阻塞项是补齐 MSVC x64/`nmake` 构建能力并完成首次隔离安装。

## PASS / FAIL

`IN_PROGRESS`：可用性检查 PASS；功能链尚未执行。

## Alternative

若 EDB 安装器受权限或上游缺陷影响，优先使用同版本官方二进制 ZIP 在项目隔离目录执行 `initdb`，不更换 PostgreSQL 18 基线。若 pgvector 0.8.6 无法在官方 Windows 构建流程中编译，必须先形成 Failure Analysis、Root Cause、Impact、Option A、Option B 和 Recommendation，再由用户决定方案。
