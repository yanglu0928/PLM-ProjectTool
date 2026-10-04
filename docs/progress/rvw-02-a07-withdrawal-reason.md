# RVW-02-A07：撤回原因历史

日期：2026-09-26；Phase2；版本0.1.0.dev0；Result：OWNED_SCHEMA_PASS。完整业务命令/Owner未完成。

## 编码前检查 / Changed / Files

输入AF-02 withdraw(reason)、0034、先登记CR-RVW-002和RVW-02-A06。仅Review事件/ORM/查询/0035及验收，权限与API不变。新增 `migrations/versions/20260926_0035_review_withdrawal_reason.py`、`validation/rvw-02-a07-withdrawal-reason/verify.py`；修改Review ORM/read_repository、相关unit与四个既有head verifier版本断言，历史测试保留，0034不改。

旧NULL不猜测，原因TEXT仅撤回可非NULL且需实质非空白；NUL由PostgreSQL TEXT/Domain拒绝。原事件不可变和完整性触发器保留。down同事务排他表锁检查，存在原因拒绝，offline down禁止。

## Tests / Result

- Win11/Python3.13后端743项无失败，2项既有符号链接权限环境跳过。
- 独立UUID隔离PostgreSQL：空up/check/down、旧0034有数据up/旧字段保持/NULL读回/安全down/re-up，中文原因读回、空白/非撤回拒绝全回滚、不可变、含原因down拒绝且数据/0035保持、ORM check无新增差异。finally只清理own数据库，无生产写入。
- Review完整结构/固定查询/受权幂等送审/真实40P01恢复，以及Workflow0031/0032/0033关联回归PASS。Subject/License/Review业务批准合成，不是实际Owner或Gate证明。
- 开发wheel PASS，SHA256 `8811c63eca3a0054a11e55a4d33774627ee8451c259f13ecd1a3211f4651f5d3`；非正式安装包。Alembic computed列提示为已有观测警告，原generated定义不改，command.check无新增差异。

## Migration / API / Compatibility / Upgrade

新版ORM/查询要求先备份升级0035；不能声明旧0034兼容。含原因down拒绝，保留列或关新入口回滚程序，不删除历史。API/角色/依赖不变。目标Win11/Server2025/Debian13不变，当前仅Win11，Server未验、Debian暂不验。

## Known Issues / Next

RVW-02-A08：可信调用方事务完整决定/撤回写/Audit/Owner终态消费，再接受权幂等。原因重放/异原因同Key冲突及消费失败全回滚仍待；真实客户资格/Source重验/身份锁编辑和替代Draft保护、正式批准未验。无Owner不挂载HTTP，Gate3/UAT/正式可用程序包未完成，完整目标继续。
