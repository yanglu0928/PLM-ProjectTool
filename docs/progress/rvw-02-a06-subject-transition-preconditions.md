# RVW-02-A06：决定/撤回终态交接前置

日期：2026-09-26；Phase 2；版本 0.1.0.dev0。Result：INTERNAL_CONTRACT_PASS；完整决定/撤回业务能力 INCOMPLETE。

## 编码前检查与范围

输入 AF-02/DM-02/API-02、0034、CR-RVW-001、已完成 RVW-02-A05。仅 Review application 内部交接 DTO/Owner Port、unit tests 与设计/CR；实体为固定 Round/Progress/Withdrawal。无公开 API、授权策略或数据库变更；必须由实际 Session Actor、assigned reviewer/PM 当前权限和 Owner 资格独立核验。风险：没有真实业务 Owner，不能凭合成快照批准或解锁。

## Changed / Files

`application/subject_transition.py` 及 `tests/unit/test_review_subject_transition.py`：严格检查一次追加或撤回、旧决定不改写、确认人/轮次固定、Actor/UTC 时间绑定、终态禁止、计数溢出、冻结值与全维绑定。DTO 不代表真实来源/资格/锁证明。前置设计见 `docs/review/review-decision-withdraw-preconditions-v1.md`；缺口与迁移计划见 CR-RVW-002；决策 DEC-20260926-180。

## Tests / Result

Windows 11/Python 3.13：后端 742 项无失败（2 项既有符号链接权限环境跳过），其中新增 5 项交接合同测试。开发 wheel 成功，新增模块已检查入包；不是安装包/生产发行证明。本轮未运行新数据库或 HTTP 验收，没有实际 Owner 实现或客户批准。

## Migration / API / Compatibility / Upgrade

无已实施 Migration、公开 API、依赖、权限或架构改变；现有 0034 保留，升级无新动作。CR-RVW-002 nullable reason 迁移下一任务才实施并验收，旧值 NULL 不臆造。目标 Win11/Server2025/Debian13 不变，本轮仅 Win11，后两者未验/暂不验。

## Known Issues / Next

RVW-02-A07 完成原因 ORM/migration/读回、空库与有数据 up/down/历史不变验收；随后可信事务决定/撤回与真实 Audit/收据/Owner 消费，再接真实受权幂等入口。实际 Sources/客户资格/身份锁编辑及替代 Draft 保护与释放需实际 Owner 测试，Gate 3/UAT/正式可用程序包仍未完成。完整 Scope 不删除，不用合成 Port 放行业务。
