# RVW-02-A08：可信调用方事务决定/撤回

日期：2026-09-26；Phase2；版本0.1.0.dev0。Result：INTERNAL_PERSISTENCE_PASS，完整受权命令/实际业务审批 INCOMPLETE。

## 编码前检查

输入冻结 AF-02/DM-02/API-02、0034/0035、CR-RVW-001/002、RVW-02-A06/07。仅 Review application/infrastructure 完整 owned 决定/撤回、Audit和Owner窄Port同事务交接。Actor/Project/License/assigned reviewer或PM当前授权由后续入口负责，本服务不能公开。验收：首RETURN保持锁、完整集合汇总、撤回历史/pending/原因保留，故障整事务回滚与竞争单终态。风险：实际Owner不存在，合成标记不证明真实业务身份锁/客户资格。

## Changed / Files

- `application/persist_transition.py`：可信调用方事务入口和不可变首次结果Ref；固定ID/Scope/Actor核对，重复决定、RETURN实质意见、根If-Match撤回、UTC/时序、完整单步交接；Owner access/锁前后重核、终态consume和消费后独立assert、真实Audit。禁止True成功哨兵，不自建UOW/commit/幂等收据。
- `infrastructure/transition_repository.py`：先根独占锁、固定完整轮次查询，写前再次对比；决定/Assignment/Round/根/Review锁/事件原子写。撤回不制造DECIDED；所有人完成才终态。无外部Owner表SQL。
- `application/subject_transition.py`：新增消费后独立实际结果/正式指针/身份锁释放重核Port；真实实现仍缺。
- `tests/unit/test_review_transition_persistence.py`：8项拒绝/同事务/终态/无commit/故障测试；`validation/rvw-02-a08-persist-transition/verify.py`：隔离真实owned/Audit/合成消费事务回滚。
- DEC-20260926-182和前置设计记录实际读锁序及未完成真实Owner并发。公开API不改变。

## Tests / Result

Windows11/Python3.13后端751项无失败，2项既有符号链接环境跳过。隔离PostgreSQL：两人全APPROVE/先RETURN最后处理、首条不consume/解锁、重复/非assigned/跨项目拒绝；撤回旧决定/pending/中文原因保留；权限/第一及第二锁核验/消费写后故障/bool哨兵/消费后重核/Audit故障全数据库快照不变（八表、Sources、Audit、合成消费记录）；最终决定与撤回并发只有一个终态、一条成功Audit和一次消费。回滚后的最后决定不存在，锁仍持有。仅own UUID数据库并finally清理。

消费记录是 `public.synthetic_owner_consumption` 测试标记，只存在隔离库，不是生产业务表/实际资格/内容锁/正式批准指针。本轮未接Session/License/Project授权和receipt，不声称实际客户批准或完整业务锁证明。无新HTTP验收。

0035历史迁移/原因回归、真实Session受权送审/幂等/真实40P01恢复回归PASS。开发wheel PASS，SHA256 `002a594626b8130c10202ecdcf85f0a53089fc20353d3d715583838ddfd485f2`，不是正式安装包。

## Migration / API / Compatibility / Upgrade

无新增Migration/API/角色/依赖变化，运行需0035，升级无新动作。保留全部历史，未挂HTTP。目标Win11/Server2025/Debian13不变，本轮只Win11，Server未验、Debian暂不验。真实Owner跨路径锁序须独立验证，不能从合成竞争宣称无死锁。

## Known Issues / Next

RVW-02-A09接当前Session/CSRF/License/Project、assigned reviewer具体Owner权或PM撤回、持久幂等首次结果/当前旧版访问重核/故障全回滚及死锁整事务恢复。实际Owner必须重验必要Sources/内容和资格、阻止编辑与替代Draft、同事务消费正式状态及释放真实锁；未具备前不公开路由。原Scope不删，Gate3/UAT/最终可用程序包未完成。
