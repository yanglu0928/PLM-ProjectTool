# RVW-02-A03 确认人基础资格

2026-09-26；0.1.0.dev0；WINDOWS_INTERNAL_PROJECT_QUALIFICATION_PASS；不代表具体主题资格/客户批准。

## 编码前检查与 Changed / Files

Phase 2；输入 AF-02/DM-02/API-02/0034、RVW-02-A02 送审前置和现有 Auth/Project 模型。前置真实账户/项目模型已验；本项只解决必要资格，不改变状态、策略或实际业务主题。内部可信调用方事务，Actor/License/PM/主题权限须另验。验收：1～N 唯一非零 ID、真实 ENABLED 账户、同项目活动成员/部门、当前角色子集，状态拒绝与资格锁，无 Assignment/commit。

- `auth/infrastructure/review_user_access.py`：Auth owned UUID 排序共享锁，只返回 ENABLED IDs；无敏感账户投影、不隐式开启事务。
- `project/application/reviewers.py`：窄 Port、固定 reviewer ID/Project/role DTO 与基础资格服务。先所有账户后 Project，当前角色范围只允许服务器传入的非空四角色子集，保留调用方集合顺序。
- `tests/unit/test_review_reviewer_qualification.py`：5 项行为矩阵。
- `validation/rvw-02-a03-reviewers/verify.py`：随机自建 PostgreSQL 隔离库/实际资格保护；只清理自身库。

## Tests / Result

Windows 11/Python 3.13 全部后端 **717 项无失败，2 项既有符号链接环境跳过**。单位验账户先锁/确定顺序/同调用方事务、空集合/重复/畸形 Scope/角色/策略、账户缺失/错误 Port 返回拒绝、归档/非预期 Project facts、无隐式事务与固定安全错误。

PostgreSQL 18.6：真实 ENABLED User、当前活动成员/有效期/部门/Project/角色，两个客户角色必要资格 PASS；未知账户、无成员部署管理员、跨项目、重复 ID、DISABLED、SUSPENDED、REMOVED、未来生效、INACTIVE 部门、ARCHIVED Project、受控策略下 IM 拒绝；恢复后可再次资格核验。Fixture 状态注入只用于自建库，不是正式业务命令或生产变更。

调用方保持事务时，实际账户停用、成员暂停、部门停用、项目归档四类变化均受到已持锁阻断/lock_timeout，结束后账户停用可成功、后续资格拒绝。资格查询前后实际事实投影一致，Assignment 未创建。未运行完整 Session/CSRF/start 与现有成员写的跨路径死锁验证，不声明全链无死锁；具体 Owner 权限/身份锁仍待。

Review 内部创建/真实 Session/Project/Audit/幂等与内部读脚本回归 PASS。开发 wheel 构建 PASS，SHA-256 `c97b0e43d114406ddf8250f7ac54f18ed26c988c6798757411befbcc9fadc3db`；不是可用最终安装包。覆盖率/性能/HTTP/完整送审与 Server 2025 未运行，Debian 13 暂不验证。

## Migration / API / Known Issues / Next

无 Migration/API/角色/依赖/架构变化，升级无动作；不调用新内部组件即可回滚。调用方必须在 Project/Review 锁之前调用基础资格，并独立校验 Session/PM/License/逐人主题资格；不能把基础角色事实当客户确认、赋权或 Gate。实际服务器政策注册/Subject Owner/完整 start 未完成，公共入口仍未接线。

Next：RVW-02-A04 Subject Owner 固定送审快照/逐人资格/真实身份锁 Port 与合同验收；持续交付目标仍未完成。
