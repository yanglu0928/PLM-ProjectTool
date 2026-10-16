# Windows Server 2025 验证证据

执行日期：2026-09-17。

## 环境

- Microsoft Windows Server 2025 Datacenter 10.0.26100，x86-64。
- 16 个逻辑处理器，16 GB RAM。
- PostgreSQL 18.6、pgvector 0.8.6、Python 3.13.15。
- VMware Workstation Pro 虚拟机，验证时唯一物理网卡已断开。

## 完全离线证明

1. 在宿主机生成最小运行包并记录 SHA-256。
2. 验证开始前将运行包复制到虚拟机。
3. 通过 VMware 断开 `ethernet0`；来宾系统检测到 1 个物理网卡、0 个处于连接状态。
4. 在全新的 `run-03` 目录内完成解压、`initdb`、pgvector、Migration、10 万向量、备份恢复和重启。
5. 验证进程退出后恢复虚拟网卡；VMware Tools 再次返回来宾 IP，确认连接动作完成。

离线包 SHA-256：`79acfd9c050676189b3030ede5b63353f6ec2922c9989c4655519c4e80ade03f`。

PostgreSQL + pgvector 运行时 ZIP SHA-256：`67869cf66d6395cf9395b5ac2b640a5af00d6980911dacbfcead409f5f5f3d0d`。

## 结果

- PostgreSQL 18.6 初始化、启动、SQL 与停止：PASS。
- pgvector 0.8.6 加载、CRUD、距离排序与 HNSW：PASS。
- SQLAlchemy 2.x / psycopg：PASS。
- Alembic 空库 up/down 与有数据升级/回退：PASS。
- 100,000 条 32 维向量：PASS。
- 20 组 Top-5 平均和最低 Recall：100%。
- HNSW 查询 P50 / P95：2.642 ms / 15.473 ms。
- 备份恢复、100,000 条及 ID 总和校验、扩展与索引恢复：PASS。
- PostgreSQL 重启后源库与恢复库健康检查：PASS。

## 证据边界

- pgvector DLL 在 Windows 11 的同版本 PostgreSQL 18.6 / MSVC x64 环境构建，本次验证证明其在 Windows Server 2025 上的离线部署和运行兼容性，不表示在 Server 内重复编译。
- `trust` 认证只用于断网虚拟机内的 `127.0.0.1` PoC，不是生产配置。
- 性能值只代表该虚拟机，不是生产容量承诺。
- 初次兼容性运行暴露并修复了 Windows PowerShell 5.1 对原生 stderr 的误判，以及嵌入式 Python 的 Alembic 模块路径问题；最终结论以全新 `run-03` 结果为准。
