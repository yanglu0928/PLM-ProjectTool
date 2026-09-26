# DOC-01-A04-P04 DocumentVersion HTTP + PostgreSQL 同链路

- 日期：2026-09-26；状态：Windows 11 隔离合成端到端 PASS；正式 Windows 平台尚未装配版本 Router。
- 使用隔离 PostgreSQL 18.6 临时数据库升级至当前 Alembic head；构造真实 Auth User/Credential/Session、Project/Department/Member、Document/FileObject/三代不可变 DocumentVersion。HTTP TestClient 经过真实 `SessionService`、DocumentReadService、SQLAlchemy Owner Port/Repository 和版本专用签名游标；License 为明确的合成 Guard。
- 验证：PROJECT 三版本两页无遗漏、详情摘要及无 FileObject ID/Locator 投影、跨 Document/Project 与非成员隐藏、GLOBAL 管理员读取、游标跨 Session/父文档拒绝、RESTRICTED Version 与 FileObject 即时隐藏、License 拒绝和成员停用后失权。脚本 `validation/doc-01-a04-p04-version-http-db/verify.py` PASS；临时库已删除，测试服务已停止。
- 未使用真实发行公钥/License、目标账户游标密钥或生产文件；不能推断 Windows Server 2025/Debian 13 或受权内容下载可用。下一项为 Windows 显式平台版本读组合与缺专用密钥失败关闭。
