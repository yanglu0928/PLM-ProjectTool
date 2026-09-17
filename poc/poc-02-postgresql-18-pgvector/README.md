# POC-02 PostgreSQL 18 + pgvector

## Status

`IN_PROGRESS`

Windows 11 功能链已通过；Windows Server 2025 完全断网功能链已通过。Windows 11 断网重放与 Debian 13 尚未完成，因此不得判定整个 POC-02 PASS。

## Objective

验证 PostgreSQL 18 与 pgvector 能否在正式目标环境中完成完全离线部署，并通过数据库初始化、SQLAlchemy/Alembic、HNSW、10 万级向量检索、备份和恢复验证。

## Environment

- Windows 11 Home Chinese 10.0.26200，x86-64，32 个逻辑处理器，31.63 GB RAM。
- Windows Server 2025 Datacenter 10.0.26100，x86-64，16 个逻辑处理器，16 GB RAM，VMware 实机虚拟机。
- PostgreSQL 18.6 Windows x86-64 官方二进制 ZIP，隔离运行目录 `D:\POC-02\postgresql-18.6`。
- pgvector 0.8.6，tag commit `8ee86c96f0fd72390f890aa8a336fda6d3ab4c6c`。
- Visual Studio Build Tools 2022 17.14.41，MSVC 14.44 x64。
- Python 3.13.15、SQLAlchemy 2.0.54、Alembic 1.20.0、psycopg 3.3.5、pgvector Python 0.5.0、NumPy 2.3.5。
- 数据库仅监听 `127.0.0.1:55432`；PoC 临时集群使用 `trust`，不得用于生产。

正式目标环境仍为 Windows 11、Windows Server 2025、Debian 13，均为 x86-64/AMD64。

## Input

- PostgreSQL 18.6 Windows 安装器与二进制 ZIP。
- pgvector 0.8.6 官方源码。
- Visual Studio C++ x64 构建工具和 `nmake`。
- POC-01 已验证的 Python 3.13 离线环境。
- 固定种子 `20260917` 生成的 100,000 条 32 维向量。

## Steps

1. 采集操作系统、权限、本机安装状态和官方制品可用性。
2. 下载制品，记录版本、大小和 SHA-256；核验 pgvector tag commit。
3. 将 PostgreSQL 解压到纯 ASCII 路径，执行 `initdb`、启动、SQL 和停止验证。
4. 使用 MSVC x64 / `nmake` 构建 pgvector 并安装到隔离 PostgreSQL 目录。
5. 执行 `CREATE EXTENSION vector`、基础向量 CRUD 和 HNSW 索引检查。
6. 使用 SQLAlchemy 2.x / psycopg 连接；执行 Alembic 空库 up/down 和有数据升级/回退。
7. 导入 100,000 条向量，构建 HNSW，并以精确查询对照 20 组 Top-5 结果。
8. 使用 `pg_dump` / `pg_restore` 恢复到新数据库，核对条数、ID 校验和、扩展与索引。
9. 重启 PostgreSQL 后再次核对源库与恢复库。
10. 将最小运行包复制到 Windows Server 2025，断开唯一物理网卡后在全新目录重复第 3、5～9 步，再恢复网卡。

## Result

|验收域|Windows 11|Windows Server 2025|说明|
|---|---|---|---|
|制品清单与 Hash|PASS|PASS|版本、大小和 SHA-256 已登记|
|完全断网安装|NOT_RUN|PASS|Server 验证时 1 个物理网卡、0 个已连接|
|PostgreSQL init / start / stop|PASS|PASS|18.6，实例结束后无残留监听或进程|
|pgvector 构建与加载|PASS|PASS|Windows 11 构建；两端 `CREATE EXTENSION` 成功|
|基础向量 CRUD / HNSW|PASS|PASS|插入、更新、删除、距离排序与 HNSW 索引通过|
|SQLAlchemy / psycopg|PASS|PASS|Python 3.13.15 连接成功|
|Alembic 空库 up/down|PASS|PASS|升级至 `0002`，回退至 base 后表已删除|
|Alembic 有数据升级|PASS|PASS|升级及回退到 `0001` 后原数据仍在|
|10 万向量 / HNSW|PASS|PASS|100,000 条 32 维向量，执行计划命中 HNSW|
|备份与恢复|PASS|PASS|源库/恢复库各 100,000 条，ID 总和一致|
|重启健康检查|PASS|PASS|重启后源库与恢复库均保持 100,000 条|

## Metrics

|指标|Windows 11|Windows Server 2025|
|---|---|---|
|向量数 / 维度|100,000 / 32|100,000 / 32|
|数据生成 SHA-256|`8d4c...c2500`|`8d4c...c2500`|
|导入耗时|1.970 s|2.521 s|
|HNSW 构建耗时|17.586 s|20.476 s|
|查询数 / Top-K|20 / 5|20 / 5|
|平均 / 最低 Top-5 Recall|100% / 100%|100% / 100%|
|精确查询 P50 / P95|26.744 / 31.954 ms|50.869 / 62.206 ms|
|HNSW 查询 P50 / P95|1.781 / 4.645 ms|2.642 / 15.473 ms|
|备份文件大小|15,687,652 bytes|15,687,652 bytes|
|备份 SHA-256|`3faaa5...7ddcd`|`ca3d7d...54c1f`|

以上性能数据仅代表对应 PoC 主机，不是生产容量承诺。

## Logs

- 制品清单：`evidence/windows-11/asset-manifest.json`
- PostgreSQL 初始化：`evidence/windows-11/postgresql-smoke.json`
- 构建工具：`evidence/windows-11/toolchain.json`
- pgvector 构建：`evidence/windows-11/pgvector-build.json`
- pgvector 基础功能：`evidence/windows-11/pgvector-smoke.json`
- Python、Migration 与 10 万向量：`evidence/windows-11/python-validation.json`
- 备份、恢复与重启：`evidence/windows-11/backup-restore.json`
- 中文路径问题：`evidence/windows-11/path-compatibility.md`
- Windows Server 2025 总结与断网证据：`evidence/windows-server-2025/README.md`、`overall-result.json`
- Windows Server 2025 组件结果：`evidence/windows-server-2025/postgresql-smoke.json`、`pgvector-smoke.json`、`python-validation.json`、`backup-restore.json`

原始日志、数据库目录、下载制品和 dump 位于被 Git 忽略的 `artifacts/poc-02/` 与 `D:\POC-02`，仓库只提交脱敏摘要。

## Known Issues

1. PostgreSQL 18.6 `initdb` 在包含中文字符的运行路径中出现路径乱码和 `invalid byte sequence for encoding "UTF8": 0xb9`；改用纯 ASCII 运行路径后通过。Windows 正式部署目录必须限制为纯 ASCII 路径，除非后续上游版本复验解除。
2. Windows 11 虽从已下载的本地制品完成解压、构建和运行，但执行时网络未隔离；Windows Server 2025 已完成物理网卡断开验证。
3. `trust` 认证只用于隔离、回环地址 PoC；生产配置必须使用口令或更强认证并实施最小权限。
4. Debian 13 尚未执行本 PoC；两个 Windows 平台的结果不能替代 Debian 兼容性结论。
5. Debian 13 的 `EXC-P0-001` 只适用于 POC-01，不自动扩展到 POC-02。
6. Windows PowerShell 5.1 会把原生程序写入 stderr 的普通 `NOTICE` 包装为错误记录；验证脚本已改为保留日志并仅以进程退出码判断成败。

## Conclusion

PostgreSQL 18.6 + pgvector 0.8.6 已在 Windows 11 与 Windows Server 2025 x86-64 通过初始化、扩展加载、ORM/Migration、10 万向量 HNSW、备份恢复和重启验证；Windows Server 2025 还通过完全断网安装与执行。Debian 13 仍未验证，因此 POC-02 尚未跨平台完成。

## PASS / FAIL

`IN_PROGRESS`：Windows 11 功能验收 PASS、断网重放 NOT_RUN；Windows Server 2025 全部验收项 PASS；Debian 13 为 NOT_RUN。

## Alternative

- 若 EDB 服务安装器受权限或策略影响，继续使用同版本官方二进制 ZIP 的便携式部署路径，不更换 PostgreSQL 18 基线。
- 若目标环境无法在本机构建 pgvector，可在同 OS/架构的受控构建机生成并校验二进制制品，但必须重新验证 PostgreSQL 小版本、编译器 ABI 和完整离线安装。
- 若纯 ASCII 安装路径约束不可接受，须形成独立上游兼容性调查和方案评审，不得直接宣称中文路径受支持。
