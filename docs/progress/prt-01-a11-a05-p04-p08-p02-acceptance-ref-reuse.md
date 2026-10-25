# PRT-01-A11-A05-P04-P08-P02：同源锁定快照复用验收稳定ID

2026-10-08 / 状态：`IMPLEMENTATION_PASS_PERFORMANCE_FAIL`。

编码前检查：Phase 2；冻结Requirement/Prototype当前事实规则及CR-PRT-005为输入，P08前置已确认两次验收行读取；仅涉及Requirement快照仓储、内部Workflow锁、Prototype资格Owner及测试。实体持久化、公开API、权限、Schema和文件物理校验不变。验收为同事务/同锁序/同当前性、无ID错配、真实PG减少SQL且正反例与全量回归通过；20并发网络P95仍以≤500ms单独判断。

实现：Requirement `lock_snapshot`仍保留原返回；新增内部`lock_snapshot_and_acceptance_refs`，从同一`FOR SHARE`验收行序列构造带数量、连续序号、UUID唯一性校验的稳定ID证明。Requirement完整范围锁仅可选附带Proof并强校验项目/需求/版本/数量；正式仓储填充它，Prototype消费有效Proof，不再对同一版本调用独立Proof Port。没有Proof的测试/替代Owner仍走原Port，不能跳过证明。项目、根、最新版本、Review引用、快照当前性及Audit/文件检查保持原流程。

Windows11隔离PostgreSQL18.6/pgvector同一Approved Prototype夹具：每项资格经预热及三轮20并发，共122次请求，Requirement首FROM计数由1952降至1708，少244条，即2条/请求；总SQL由7686降至7442，约63→61条/请求。SQL诊断只用于计数，计时不能作为网络验收。真实Uvicorn loopback/20并发P95本次`PROTOTYPE_SCOPE_DECISIONS`约593.788ms、`PROTOTYPE_COVERAGE`约596.738ms，均返回正确但仍超500ms。跨项目Link、PM撤权/恢复、缺Checklist副作用、混合Approved/NOT_REQUIRED、文件损坏、双重认领隔离PG/HTTP回归退出0。全量后端pytest为3250通过、3跳过、4795子测试通过；新增单测覆盖同源ID正常、数量/序号/重复/零UUID拒绝，以及锁Proof身份/数量错配和旧Port兼容回退。此前prj05a05测试环境没有pytest，`unittest discover`虽运行3230项但两个pytest文件导入失败；改用已有pytest环境全量通过，不把前者记为通过。

兼容性/迁移/回滚：无Schema、公开API、依赖、配置或数据迁移；部署同步代码即可。若生产等价性问题，保持Prototype入口关闭，恢复始终调用独立Proof Port并撤内部侧带Proof；原冻结版本与业务历史不动。未达性能门槛，正常生产入口继续关闭，Gate3/UAT/可用程序包未通过。下一项需定位余下约61条SQL或其他瓶颈；不得用放宽500ms、缓存批准事实、跳过Review/物理文件证明替代。
