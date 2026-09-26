# RVW-02-A05-P01 完整轮次内部事务持久化

2026-09-26；0.1.0.dev0；WINDOWS_INTERNAL_PERSISTENCE_PASS；可信调用方、Subject Owner 合成，不代表完整受权送审。

## 编码前检查 / Changed / Files

Phase 2；输入 0034/CR-RVW-001、A02 送审前置、A03 基础资格、A04 固定 Subject 合同。完整 start 拆 P01（本任务）与 P02（真实 Session/CSRF/PM/资格/幂等入口）；原 Scope/验收保留。P01 调用方已经受权并持事务，服务不自行创建事务或 commit，不承担 License/交互授权、不装配公开路径。

- `review/application/persist_round.py`：稳定 StartedReviewRoundRef、内部事务编排；当前 Scope/版本/活动状态拒绝、绑定准备结果、Owner 锁前后复核、真实 REVIEW_STARTED Audit，不允许 bool 充当锁复核。
- `review/infrastructure/start_repository.py`：Review→Round 锁序，Core 当前根/预分配数据库 UUIDv7、完整 Round/Assignment/固定 Snapshot/refs/Review owned subject lock/STARTED 与根投影，根版本+1，当前值再次比较，无业务 Owner SQL。
- `tests/unit/test_review_round_persistence.py`：5 项单位矩阵。
- `validation/rvw-02-a05-p01-persistence/verify.py`：随机隔离库，真实 Sources/Audit/0034 持久化与合成 Owner 故障注入；仅清理脚本自建库。

验收：完整结构与 Audit 同事务；缺 Owner、过时根/活动轮、跨项目或错绑定拒绝；准备前后实际 Owner 重核和 Audit/来源失败全回滚。风险：无真实 Subject Owner，不能由数据形状/Review owned 锁推定真实业务锁；完整授权/幂等入口未完成。

## Tests / Result

Windows 11/Python 3.13 后端 **728 项无失败，2 项既有符号链接权限环境跳过**。新增 5 项验证同 tx/不 commit、两次锁复核、缺 Owner/版本冲突/活动根拒绝、错准备绑定或 bool 锁标志拒绝、第二次锁失败不写 Audit、外国根/错误结果拒绝。首轮测试替身将 `assert_...` 当成 Mock 断言方法而报错，改为精确 Protocol spec 后全部重跑通过；不是生产行为失败，也不把首轮报错算通过。

PostgreSQL 18.6 隔离验收 PASS：完整 PROJECT 新 Round，2 Assignment PENDING、Snapshot/真实 Evidence 固定观测、ACTIVE Review owned 主题锁、根 IN_REVIEW/版本+1、STARTED、真实 Audit。读取完整快照核对固定 Version/来源和完整 reviewer；活动根再次 start 明确拒绝，完整数据不变。

合成 Owner 第一次复核失败、插入后第二次失败、真实 Audit 适配前故障注入、真实 Evidence 锁版本错误（明确 SQLSTATE P0001）、错误准备 version 绑定均拒绝，八表/Sources 与完整 Audit 行快照全部回滚。测试 Owner 是绑定/故障注入替身，不是真实主题身份锁，不证明阻断业务编辑或替代 Draft。

0034 Schema/空与已有数据 up/down/re-up/metadata/拒绝并发、内部创建/幂等/Audit、真实账户/Project 基础资格回归 PASS。开发 wheel SHA-256 `ad1466f3bd356e300f1ce2af3623ce7e4700dd86534eedbd956f70343331af21`；不是可用安装包。

## Migration / API / Known Issues / Next

无新 Migration/API/角色/依赖/架构变化；需 0034，升级无数据库动作。停用内部服务回滚，保留不可变历史。Caller 必须按规定锁序先完成真实身份/PM/License/资格；必须在同事务写收据并 commit，失败全部 rollback，不得直接暴露本服务。

无真实业务 Owner/来源权限、客户资格/送审锁、完整受权 start/持久幂等与公共 HTTP，未跑完整送审锁序/性能/覆盖率/Server 2025，Debian 13 暂不验证。Next RVW-02-A05-P02 真实 Session/CSRF/PM/基础资格与幂等 start 入口；总体可用程序包/Gate 3 未完成。
