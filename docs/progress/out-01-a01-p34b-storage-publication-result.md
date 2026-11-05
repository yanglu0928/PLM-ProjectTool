# OUT-01-A01-P34B Storage发布协调验收结果

- 日期：2026-11-05
- 结论：PASS_SCOPE_LIMITED
- 变更追踪：CR-OUT-030/031
- 运行位置：GitHub hosted Windows Server 2025 runner，D盘临时目录
- 运行： [42051895394](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42051895394)
- 分支提交：fc28777af80f4537ecb259315772cfd0bd1a15ff

## 验收范围和证据

本轮Backend full suite 4,067 tests、wheel、Frontend tests/build、嵌入式Python和Windows父包组装均成功。clean parent PostgreSQL 18/pgvector lifecycle smoke成功，verifier明确输出 `output_generation_completion_validation.status=PASS_SCOPE_LIMITED`，并确认：

- 合成STAGED文件提升至final后，内容Hash和大小复验通过，FileObject发布为AVAILABLE。
- P34A DocumentVersion、source ref和SYSTEM Audit写入成功。
- P33 Output Artifact、四项validation、Job完成及Audit在事务中成功。
- P33 Audit失败时P33自有状态回滚；成功claim精确重放无重复事实，修改后重放被拒绝。
- 无插件执行、无客户数据、无产品Worker/API启动；storage synthetic file仅在runner D盘生成。

新增恢复Owner单测随Backend 4,067项全量通过，覆盖：
- STAGE_ONLY只调用 `publish_verified`；
- FINAL_VERIFIED只调用 `recover_verified_final`；
- LINKED_PAIR只调用 `recover_linked_pair`；
- NONE、BOTH_UNRELATED、FINAL_INVALID、UNSAFE、未知形态失败关闭且不执行提升；
- AVAILABLE final只验证内容；状态/locator不匹配在Storage调用前拒绝。

首次新增测试run 42050570499因fake误用 `publish_verified` 参数而失败，已在CR记录。修正测试替身后，本轮通过；产品Storage逻辑未因该夹具问题修改。

## 独立失败和限制

同一run中独立P25真实Output Create HTTP/Edge作业仍失败；A17 packaged flow在业务链检查后清理临时文件时遇Windows EBUSY锁文件，未影响P34B父包PG18 smoke；A34成功。整个workflow因此不是全绿，P25继续BLOCKED_DIAGNOSTIC。该局部受限结论不代表Output生产装配、客户文件生成、Win11实机、Pilot、Gate 3或Release通过。

无数据库Schema/Migration、冻结API、默认组合、Worker或插件执行变化；无客户数据外发。
