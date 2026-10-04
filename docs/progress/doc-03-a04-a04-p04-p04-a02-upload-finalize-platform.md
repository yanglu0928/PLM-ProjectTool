# DOC-03-A04-A04-P04-P04-A02：Windows 显式写模式上传终结组合

日期：2026-09-26；版本：`0.1.0.dev0`；状态：Windows 11/隔离环境合成组合 PASS，正式发行信任源未供给。

依据冻结 API-02 与 `DEC-20260926-119`，仅在既有 Windows `--platform-write` 组合中挂载 Commit/Abort Router，复用真实 Session/CSRF、Project 当前成员与创建者事实、License Guard、PostgreSQL 持久幂等/Audit、LocalFileStorage 和 Job Owner Parse 入队 Port。登录和只读模式仍 404；缺任一原有生产信任源时整个显式写模式失败关闭。Abort 不执行物理删除，仍返回 cleanup_pending。

Windows 11/Python 3.13 后端 507 项无失败（2 项符号链接权限跳过）；隔离 PostgreSQL 18/临时文件的真实 Session/Project 成员与合成 License/上传 Key 组合验证 Create→Content→Commit 产生唯一 DocumentVersion/Parse Job，另一路 Create→Content→Abort 留下 CLEANUP_PENDING，同 Key 重放无重复 Audit，异 Key 冲突、跨用户与 License 拒绝；既有上传平台组合回归及开发 wheel PASS。无 Migration、冻结 API 变化或新依赖。正式发行公钥/目标账户密钥、Server 2025、已登记文件清理停写证明和 Parser Worker 未验；不以本合成测试判定 Gate 3 或最终程序包通过。
