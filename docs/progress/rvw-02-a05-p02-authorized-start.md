# RVW-02-A05-P02 受权幂等送审内部入口

2026-09-26；0.1.0.dev0；WINDOWS_INTERNAL_AUTHORIZED_START_PASS；Subject/License 合成，无公开 HTTP/实际客户审批。

## 编码前检查 / Changed / Files

Phase 2；输入 AF-02/DM-02/API-02、0034/CR-RVW-001、基础资格/A04 Subject 合同及 P01 原子持久化。仅完成内部受权入口，真实 Session/CSRF/ACTIVE PM/Project/账户成员事实，Owner 缺失拒绝；无 Migration/API/新增角色/依赖/架构改变。验收完整权限、幂等/原始响应、当前撤权、原子 Audit/receipt/故障回滚和已知死锁完整重试。风险实际业务主题/身份锁缺失，不能公开；旧反序 User 写路径并不天然无死锁。

- `auth/infrastructure/review_start_access.py`：实际 Session/User/credential/有效期与恒时 CSRF，共享锁保持到事务结束。
- `project/application/reviewers.py`：账户预锁观测与当前成员资格分离，必须同 tx/同集合；原一次性方法保留兼容，不公开临时观测或当授权证明。
- `project/application/authorization.py`：REVIEW_START_ROUND 仅 PM/ACTIVE。
- `review/application/start_round.py`：规范完整 reviewer 集合指纹、当前 PM 后才报告资格错误、Owner/P01/成功收据同事务、固定旧 Ref 重放、已知死锁最多三次完整事务执行；应用不依赖驱动异常类型，基础设施分类。
- `review/infrastructure/start_repository.py`：固定轮次 Ref/原始 Assignment 读取和真实 DBAPI 40P01 分类；Owner replay Port 补当前固定旧版权限，拒绝类型固定 RESOURCE_NOT_FOUND。
- 单位测试 8 项 start + 1 项两步资格跨事务拒绝；隔离 `validation/rvw-02-a05-p02-authorized-start/verify.py` 仅自建库。

## Tests / Result

Windows 11/Python 3.13 全后端 **737 项无失败，2 项既有符号链接权限环境跳过**。单位矩阵同事务/commit、当前权限先于资格错误、缺 Owner、新失格、非法/错投影/Owner replay 拒绝、原始成功 Ref 在后来根版本和 reviewer 停用后仍可受权重放、仅已知死锁重新 UOW 与最多 3 次界限、输入/Session/token repr。

PostgreSQL 18.6 隔离验收：真实 Session/CSRF/User/PM/Project/当前 reviewer 账户/成员/部门/角色、完整 Round/Audit/receipt。非 PM 三角色、无成员部署管理员、非 PM 请求未知 reviewer（不泄露资格）、跨项目、错 CSRF、失格 reviewer、过时根、缺 Owner、合成 License、归档与撤销拒绝，失败完整数据快照不变。

同 Key 两并发收敛为一 Round/一 REVIEW_STARTED Audit/一 COMPLETED receipt；只重排 reviewer 集合返回同 Ref，不同 version 同 Key 冲突。合成 Owner 撤权重放拒绝；新 Key 使用当前版本号时活动轮明确拒绝。后来用 Schema helper 完成合成 APPROVED，停用原 reviewer 后仍能受权重放原 Ref，但新的送审资格拒绝，不重复或改变旧批准。此 APPROVED 不是实际客户确认。

Audit 故障及已完成 receipt 后故障，Round/八表/Sources/完整 Audit/receipt 全回滚。真实竞争构造：送审共享 actor User 后等待 reviewer User，旧反序竞争方锁 reviewer 再等待 actor；由隔离连接实际 PostgreSQL 40P01（本次 start deadlock_timeout 50ms 仅测试）触发第一 UOW rollback，第二 UOW 成功，认证适配调用 2 次，最终只有一 Round/一次 Audit。竞争方只锁自建库 rows，不改生产或全局配置。不把模拟错误当真实死锁、不宣称全部旧写路径已无死锁或有重试。

首轮验收新 Key 活动轮拒绝的断言沿用旧 expected_version=0，因此实际正确优先 CONFLICT_VERSION；改为当前版本 1 后才验 REVIEW_SUBJECT_LOCKED，重跑通过。P01 完整持久化、A03 基础资格、A07 创建/幂等回归 PASS。

开发 wheel SHA-256 `01531bbdd964d31b8b6e14639ef47c09a5bff93a059803b490b0f103b289fa8a`，不是可用安装程序。没有 HTTP/实际 Owner/业务版本锁/覆盖率/性能/Server 2025 验收，Debian 13 暂不验证。

## Migration / API / Compatibility / Known Issues / Next

无新 Migration/API/角色/依赖/总体架构变化，需 0034，升级无新数据库动作。停用内部入口回滚，保留历史/Audit/收据。当前资格四角色只是必要集合；服务器实际 Owner 仍需逐人政策/具体版本来源与真实身份锁，不因 P02 基础授权通过而开放生产。

真实 Owner/终态消费释放/决定撤回、公开投影/HTTP/拒绝审计策略与完整业务链仍待；所有旧命令全并发恢复未完成。Next RVW-02-A06 决定/撤回与 Owner 终态消费前置，持续完成 Review 核心，不跨 Phase 编造业务实体，不提前关闭 Gate 3/整体交付。
