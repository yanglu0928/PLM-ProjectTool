# RVW-02-A09-P02：受权幂等决定/撤回内部入口

日期2026-09-26；Phase2；版本0.1.0.dev0；Result：INTERNAL_AUTHORIZED_COMMAND_PASS。实际业务Owner/客户批准/公开接口未完成。

## 编码前检查 / Changed / Files

输入AF-02/DM-02/API-02、0035、A08可信事务命令、A09-P01不可变事件Ref与通用receipt。涉及Auth/Project窄应用接口和Review命令，不新增角色/API/数据库/依赖。当前Actor来自共享锁Session/CSRF，当前Project四角色必要资格+assigned reviewer决定，PM撤回；实际Owner必须具体主题政策/资格与版本/锁校验，不拿四角色当具体客户确认权。

新增 `application/transition_command.py`，两类敏感字段不入repr的内部命令。现有Project策略增加REVIEW_DECIDE/REVIEW_WITHDRAW；新增Owner当前固定旧版重放访问Port，基础设施复用仅DBAPI40P01分类。Session/Project/根/轮次/receipt依赖同事务；新命令调用A08/真实Audit后完成200事件收据再commit，重放返回原事件Ref不执行新消费/审计/版本检查。当前访问仍必须通过，未知Owner/错绑定拒绝，bool成功哨兵不接受。DEC-20260926-184。

## Tests / Result

- Windows11/Python3.13后端765项无失败，2项既有符号链接权限环境跳过；新增8项command单位测试，现有完整Role×操作矩阵扩为21项操作。
- `validation/rvw-02-a09-p02-authorized-transition/verify.py` 独立UUID隔离PostgreSQL，真实Session/CSRF、当前Project/member/department、assigned或PM、八表/Audit/receipt；非assigned PM/IM、非PM撤回、部署管理员旁路/跨项目/坏CSRF/无Owner/合成License拒绝，失败不写任何记录。
- 同Key并发决定或撤回只一次owned/Audit/receipt/消费；异comment或reason同Key冲突、新Key不能覆盖已决定；终态与下一轮后旧partial/withdraw Ref相等。Owner当前重放访问拒绝、member暂停/PM撤权/Project归档/Session撤销均阻断重放。其他历史reviewer停用不篡改旧响应，也不触发新批准。
- Audit失败、receipt完成后异常、终态消费写后异常，完整八表/Sources/Audit/receipt/合成消费快照不变。实际Project→User反序竞争制造40P01，整个UOW回滚后二次执行成功，只一次Audit/receipt/消费；不是仅Mock死锁。所有连接/数据库finally只清理own目标，无生产写入。
- 首次故障测试错误重用了已有Actor/Project/操作的Key于另一Review，正确得到CONFLICT_IDEMPOTENCY而非预期审计故障；改独立Key重验全部PASS，未放宽生产冲突规则。
- A09-P01固定历史、A08决定撤回全回滚与A05受权送审/真实死锁回归PASS。开发wheel PASS，SHA256 `d1b0263a9a066d57837224ceaef9872e3a7d32365ccf71910a68a634e15895d2`；不是正式安装包。

Owner为隔离库 `public.synthetic_owner_consumption` 测试事务标记，License为合成Guard；四角色ALL政策也是测试，不证明实际客户资格、Sources合格、真实业务内容锁或正式指针。无公开HTTP/实际业务UAT/正式License装配验收。真实Owner交叉锁序及其他旧命令恢复仍待，不能宣称所有路径无死锁。

## Migration / API / Compatibility / Upgrade

无Migration/API/新角色/依赖改变，需0035，升级无新动作；冻结decide不加If-Match、withdraw沿用根版本。默认应用不注册新写入口。目标Win11/Server2025/Debian13不变，本轮仅Win11，Server未验、Debian暂不验证。

## Known Issues / Next

RVW-02-A10核查Review公开接线与Phase2依赖：实际Owner/完整状态及列表投影/正式业务Sources/公开合同缺口、哪些Platform Core仍可独立推进；不得合成Owner放行业务或跨未满足Gate。当前不标Review总体/Phase2/Gate3通过，完整Scope保留，实际Owner/客户批准/HTTP/Gate/UAT/可用程序包仍未完成。
