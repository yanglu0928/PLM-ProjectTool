# Windows 中文路径兼容性记录

## 观察

首次将 PostgreSQL 18.6 便携式运行目录放在含中文字符的仓库路径下执行 `initdb --encoding=UTF8 --locale=C` 时，控制台路径发生乱码，服务端返回：

```text
FATAL: invalid byte sequence for encoding "UTF8": 0xb9
```

`initdb` 随后按其失败清理机制删除未完成的数据目录。

## 对照复验

将同一 PostgreSQL 二进制 ZIP 与相同参数迁移到纯 ASCII 路径 `D:\POC-02\postgresql-18.6` 后：

- `initdb` PASS；
- 启动与停止 PASS；
- UTF-8 数据库 SQL PASS；
- pgvector、Migration、10 万向量和备份恢复 PASS。

## 当前约束

Windows 部署时 PostgreSQL 程序、数据和 PoC 临时 SQL 路径使用纯 ASCII 字符。该约束基于本次可重复观察；后续只有在目标 PostgreSQL 小版本完成中文路径回归后才能解除。
