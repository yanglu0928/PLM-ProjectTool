# AUD-03-A02 / CR-JOB-001：Job/Outbox 部署范围补齐

日期2026-09-26；Phase2；版本0.1.0.dev0；结果SCHEMA_ALIGNMENT_PASS，非审计导出/公开Job/正式发行PASS。

## 编码前检查 / Changed / Files / Migration

正式总控V1.1、V2.1全文与冻结DM-04/API-03核对，V1.1持续授权优先执行流程。AUD-03-A01缺口真实复现；前置满足。只恢复冻结DEPLOYMENT范围，先记录CR-JOB-001再实施。更新JobRow与OutboxEventRow scope CHECK、新0036迁移、迁移head合同及3项unit、隔离验证。原冻结64cdf09及0025～0035不改。

GLOBAL/DEPLOYMENT必须project_id NULL；PROJECT必须有project_id。唯一键仍包含scope，GLOBAL与DEPLOYMENT同Key互不混淆，各自重复拒绝。FK/索引/状态/Lease/幂等不改。Document Parse request及enqueue仍仅GLOBAL/PROJECT；没有新公共或自由Job创建入口。

0036 up只替换两个CHECK，保留所有旧行。down首先ACCESS EXCLUSIVE锁两个表，任一DEPLOYMENT数据存在则拒绝，不删/重标数据或变更revision。离线down拒绝；无DEPLOYMENT历史才恢复旧CHECK。生产仍人工备份/维护/离线迁移流程，不自动回滚。

## Tests / Result

- Win11/Python3.13后端797项无失败，2项既有符号链接权限跳过。新增unit：up两个scope约束、down锁先于历史检查且拒绝时无DDL、offline down无DDL。head为0036并正确连接0035。
- validation/aud-03-a02-job-deployment-scope/verify.py：own UUID PostgreSQL空库up/down/re-up、旧GLOBAL/PROJECT Job/Outbox全字段保留、非法Scope/project组合拒绝、同Key跨Scope独立/各自重复拒绝、Job/Outbox分别存在DEPLOYMENT历史时down拒绝并保持revision/行；无部署数据成功down后旧四行仍在。真实降级LOCK时两个竞争连接ROW EXCLUSIVE写锁均超时，防检查后插入。
- ORM创建部署Job，真实租约领取/finish；部署Outbox领取/确认；ParseJobQueue部署输入被拒绝且repository未调用。测试回调为空仅验证通用租约/投递，不伪称审计业务发布完成。
- 既有Job Schema/lease/outbox三个数据库脚本回归PASS，含ORM parity、旧数据迁移、并发fencing/回滚/消费者去重/限次重试；Alembic已有computed-default warning不代表差异失败。Windows显式审计组合/真实Session与Scope/缺key关闭回归PASS。
- 历史A01缺口脚本改为明确停在0035，不把新head当旧版；实际重跑仍复现旧约束拒绝。所有临时库只清理own目标，无生产操作。
- 开发wheel PASS，SHA256 `fab6e096927a024fd3b8887b7de3c93c4c998495dba9c35bf05fbfa9f6b1a23f`；非可用正式安装包。

## API / Compatibility / Upgrade / Known Issues / Next

无Breaking API/角色/依赖/算法改变；架构和数据模型业务含义不变，以增量实现对齐冻结合同。升级需备份并迁移到0036；运行新版本要求最新Schema。存在DEPLOYMENT历史不能直接down，应保留兼容Schema或由实施团队恢复完整升级前备份，不得自动删除历史。未在真实数据库执行升级。

只Win11实测；Server2025未验、Debian13暂不验证，目标保留。审计导出snapshot/当前授权/Job发布/交付、正式账户密钥和Gate/性能/UAT/可用程序包仍待。下一项AUD-03-A03：导出请求/用途/Scope/归档维护例外与Worker授权Port合同，之后不可变capture Schema单独CR。
