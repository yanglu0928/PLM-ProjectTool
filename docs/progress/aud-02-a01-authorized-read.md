# AUD-02-A01：当前受权内部审计读

日期2026-09-26；Phase2；版本0.1.0.dev0；Result：INTERNAL_AUTHORIZED_READ_PASS，公开API/导出/生产发行未完成。

## 编码前检查 / Changed / Files

输入冻结API-02 Audit角色/Scope/safe view、AUD-01已有查询和追加历史、Auth当前Session/部署管理员只读Port与Project实时授权。仅一个问题：已有抽象AuditReadAccess不等于真实会话/权限，需同事务接线。新增 `application/authorized_read.py` 与6项unit、`validation/aud-02-a01-authorized-read/verify.py`；Project增加AUDIT_PROJECT_LIST/GET当前PM只读锁策略。无Schema/API/新角色/依赖变化。

内部请求明确project_id=None为DEPLOYMENT，绝不从项目授权失败fallback。先License、当前Session/账号/凭据版本，再当前项目PM/成员/部门；Deployment独立当前Admin证明。private能力只由本服务在当前事实检查后创建，绑定同tx/同principal/同Scope供原query使用，不是客户端UUID/bool证明。白名单AuditEventView再验Scope/ID/aware时间、安全code/Actor/ref、分页数量/时间窗口/筛选/排序/唯一/边界；缺事件404语义、异常source失败关闭。不读取正文/Secret值，不复制actor_hint_digest。GET不commit/追加Audit。

## Tests / Result

- Win11/Python3.13后端771项无失败，2项既有符号链接权限环境跳过。unit覆盖项目/部署同事务与无commit、失效会话/错角色前置拒绝、错Scope/ID/unsafe summary、分页/筛选异常、private能力跨事务/主体拒绝、token repr隐藏。
- 独立UUID隔离PostgreSQL：真实Auth Session/credential/User和Project/member/department、PM/Admin、项目3条两页无重漏/详情、Admin仅部署范围、非PM/部署角色无项目旁路、跨项目/部署事件互读拒绝；License合成无效拒绝两范围。
- 并发锁探针验证User/Session/Project/member/department五类当前事实持有到caller UOW结束；归档项目仍可读历史，暂停PM/撤销Session拒绝。Audit全表读取前后完全一致，未追加或改写。隔离库finally只清理own目标。
- Review受权幂等决定撤回/真实40P01恢复回归PASS；开发wheel PASS，SHA256 `e6696c46d7918db3745666c4df33b9b584f1b1911954096a45e2616a250b791d`。非正式安装包。

License是测试Guard，本轮没有真实发行信任锚验证；没有HTTP/导出测试，也不把完整Role×内部操作矩阵当公开路由或性能通过。现有AuditSearch需要caller已验证的after位置，公共cursor尚未形成，不能直接公开。

## Migration / API / Compatibility / Upgrade

无Migration/公开API/新角色/依赖改变，升级无动作；原AUD-01查询合同保留。Project操作策略总数23，现有四角色矩阵继续全覆盖。目标Win11/Server2025/Debian13不变，本轮只Win11，Server未验、Debian暂不验证。Review公开阻塞记录单独保留，不以Audit进展缩减原Scope。

## Known Issues / Next

AUD-02-A02签名分页游标（搜索时间窗口/筛选/Scope/Actor/会话绑定），后续可选公开GET及Windows显式组合、导出用途/快照/Job/权限再验。正式License/三平台/性能/Gate3/UAT/可用程序包仍未完成。无普通人工决策待办，继续批准Scope。
