# DOC-01-A03-P03 Document HTTP + PostgreSQL 同链路验证

- 日期：2026-09-26；状态：Windows 11 隔离合成端到端 PASS；正式平台仍未挂载。
- 使用隔离 PostgreSQL 18.6 临时数据库执行当前 Alembic head；构造真实 Auth User/Credential/Session、Project/Department/Member、PROJECT/GLOBAL/RESTRICTED Document；HTTP TestClient 使用真实 `SessionService`、Document 读 Service、SQLAlchemy Owner Port/Repository，License 为明确标识的合成 Guard，游标密钥为测试专用常量。
- 证据：PROJECT 两页 keyset 无遗漏、强 ETag、响应无 Locator/物理路径；RESTRICTED/跨项目/非成员/非管理员 GLOBAL 隐藏；GLOBAL 管理员可读；游标跨 Session/Project 拒绝；License 拒绝；归档项目当前成员仍可读、停用成员随即失权。脚本 `validation/doc-01-a03-p03-document-read-http-db/verify.py` PASS，退出时删除临时数据库并停止测试服务。
- 不把合成 License 当作真实发行验证；不装配正式 Windows 路由，也不声称 Server 2025 或 Debian 13 已验证。下一项为 Windows 显式只读组合与目标账户独立游标密钥失败关闭。
