# PRT-01-A11-A05-P04-P09：Requirement同事务Evidence证明复用

2026-10-08 / 状态：`IMPLEMENTATION_PASS_PERFORMANCE_FAIL`。

编码前检查：Phase2；依据冻结Requirement当前性与Prototype资格规则、CR-PRT-005和P08后每资格约61条SQL。仅改Requirement Validator与Workflow Owner内部交接及单元测试，不改Evidence仓储、公开API、Schema、权限、文件字节证明或项目锁。验收为同一调用内可复用已共享锁定Evidence Owner Proof、跨调用重新读取、字段/项目不匹配失败关闭、真实PG减少往返并通过正反例/全量测试；20并发网络仍以P95≤500ms单独判定。

实施：`current_issues_and_project_evidence`在Validator一次检查内按EvidenceId缓存Evidence Owner当前Proof，来源、能力及证据可用性检查继续执行；有任何Issue时不返回Proof。原`current_issues`接口只返回Issue，行为保留。Workflow Owner取得该次已检查Proof后仍严格核对项目、EvidenceId、DocumentId/VersionId、锁版本及32字节指纹，再生成Checklist证据；Decision Evidence或旧Validator缺Proof时继续调用原独立Port。缓存不跨事务、请求或两次Validator调用。

Windows11隔离PostgreSQL18.6/pgvector：122次资格GET的SQL诊断由7442降至7076条（每请求61→58）；`evd`首FROM由610降至244，`evd_evidence_records`单一模板由488降至122。计时器环境下SQL耗时总和不是端到端P95。单元新增同次只调用一次、再次调用重新读取、无效Proof不外传、Workflow Owner复用但Decision仍独立读取、错项目拒绝；后端pytest3253通过、3跳过、4795子测试通过。隔离PG/HTTP跨项目Link、PM撤权、混合Approved/NOT_REQUIRED、文件损坏和双重认领负例脚本退出0。真实Uvicorn loopback20并发两项P95本轮约584.504/575.858ms，仍超500ms；与前次约594/597ms不能据单轮差异确证性能改善幅度。

兼容性/迁移/回滚：无Schema、API、权限、依赖、配置或数据迁移；同步部署代码即可。失败时恢复原Validator各处Evidence读取及Workflow Owner再读，保持Prototype入口关闭，既有历史不变。性能结论仍FAIL，Gate3、UAT与可使用发行包未通过；下一独立项需测剩余约58条SQL之外的请求调度/线程等待及锁竞争，不得放宽目标或删证明。
