# WBS 1.04 SQLAlchemy Session Validation

状态：`WINDOWS_11 / POSTGRESQL_18 / SQLALCHEMY_2 / NO_ORM_TABLES / NO_MIGRATION`

验证范围：

- 生产依赖固定为 SQLAlchemy 2.0.54 与 psycopg 3.3.5；
- 仅允许 `postgresql+psycopg`，数据库名称必填；
- Application UnitOfWork Contract 不依赖 SQLAlchemy；
- 每个 UnitOfWork 使用独立 Session/事务，默认回滚、显式提交并始终关闭；
- 日志安全 URL 隐藏密码；
- PostgreSQL 18 实连、连接池双会话、`READ COMMITTED` 和 readiness 检查通过；
- 不创建业务 ORM、表或 Alembic revision。

在项目依赖已安装、PostgreSQL 18 测试实例已启动后运行：

```powershell
python validation/wbs-1.04-sqlalchemy-session/verify.py --host 127.0.0.1 --port 55432 --user poc_admin --database postgres --write
```

结果写入 `evidence/windows-11/result.json`。测试连接只执行只读查询，不创建持久对象。
