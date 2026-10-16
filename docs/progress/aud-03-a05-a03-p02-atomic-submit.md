# AUD-03-A05-A03-P02：导出原子受理命令

日期：2026-09-26；版本：0.1.0.dev0；结果：INTERNAL_ATOMIC_SUBMIT_PASS。不代表公开接口、Worker、正式 License 或可用程序包验收。

## 编码前检查与实现

前置为 A05-A01 当前提交授权、A02 Jobs 公共队列和 A03-P01 不可变受理 Schema；实施前记录 DEC-20260926-196，沿用 CR-AUD-001。任务仅解决内部提交与重放，不新增 Schema、API、角色、依赖或范围。数据库 head 保持 20260926_0038，原冻结版本及历史迁移保留。

新增 submit_export.py、export_submit_repository.py、8 项单元测试和隔离数据库验证。实际 Session/CSRF/License 检查与 PM 或部署 Admin 授权后，receipt、不可变意图、Jobs 公共 Queue、请求 Audit、不可变 acceptance、receipt 完成在同一 UOW 提交。Audit 目标为真实 jobs/JOB-01，不把 Export ID 冒充审计事件。存储层只访问 Audit owned 表，Job 引用由公共 Port 核验。

重放先重新授权，再核对 Spec 指纹、原受理引用及现存 Job/Event 精确身份；新 trace 不改变首次响应。缺失、替换或旧历史无 acceptance 均失败关闭，不修复或猜测回填，不复活终态任务。只对异常因果链中的实际 DBAPI SQLSTATE 40P01 整 UOW 最多尝试三次，每次重新授权；其他存储错误、未知提交结果不自动重试。

## 验证证据

Windows 11 / Python 3.13 / PostgreSQL 18 隔离库验证通过两轮：真实权限与归档维护规则、双 Scope、同键不同意图拒绝、当前权限拒绝、原 trace 重放、所有写阶段故障全回滚后重试、实际竞争首次提交仅一组引用、终态不复活、缺失或替换 Job/Event 拒绝、旧无受理历史拒绝。实际 PostgreSQL 死锁覆盖 Root 写后和 Auth adapter 内部；两次新事务恢复及连续三次耗尽均通过，失败不留下部分业务记录。没有 capture、Worker 执行或文件产物。

后端 847 项无失败，2 项既有 Windows 符号链接权限跳过；8 项新 unit 覆盖事务编排、原引用重放、安全错误、授权绑定及有限重试。受理 Schema 与 Windows 审计读取组合真实回归通过。License guard 使用合成测试材料，不能证明正式公钥、授权来源或目标运行账户已验证。

开发 wheel 构建通过，SHA-256：`41e706cb16817efafe13f75a19fafd5d11073f72d59540f0f5299a9652c6a764`；仅开发检查产物，不是正式安装包。验证只操作独立临时库，结束清理，无客户数据外发或生产迁移。

## 兼容、升级与已知问题

需要既有 0038，无新升级动作；未开放导出 POST，无冻结 API 破坏性变更。Server 2025 本轮未验，Debian 13 暂缓但正式目标保留。Worker 当前授权、Lease/fencing/取消、Artifact 生成与安全交付、结果访问再授权、性能、正式信任材料、实际业务 Owner、质量复验、Gate 3、UAT 和完整可用包仍未完成。

下一项 AUD-03-A06：先核查 Worker 当前权限与真实 Job 租约/取消边界，再实现 capture、文件产物和发布；不得把提交 metadata 当作跨事务授权凭据。
