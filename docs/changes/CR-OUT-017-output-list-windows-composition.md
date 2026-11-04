# CR-OUT-017：OutputRequest列表HTTP接入Windows只读组合

- 日期：2026-11-04
- 状态：P21编码前检查 PASS_WITH_LIMITATION；实施已授权
- 来源：API-03 OUTPUT_REQUEST_LIST、CR-OUT-011/P14分页Owner、CR-OUT-016/P20只读组合、CR-EXEC-002 Pilot业务链
- 基线：冻结API Contract V1；不修改列表路径/查询契约、Schema或Migration

## 问题与方案

OutputRequest keyset分页Service、SQL Repository、opt-in GET adapter及独立 `OutputRequestListCursorCodec` 已存在，但未接入Windows只读组合。Codec要求专用32-byte密钥；项目中已有当前Windows账户Secret Vault只读Resolver与其他资源专属cursor来源模式。新增Output专属key ref并从当前用户/服务账户Vault解析；缺失或无效时拒绝装配，不生成/写入/重置密钥。仅在 `include_secret_read` 组合挂载列表路由。

## 风险与回滚

- cursor key缺失会导致显式read组合启动失败，必须在错误中不泄露密钥内容；默认应用不受影响。
- 不可复用Plan或Review的cursor key；Output需独立family/key。
- 回滚移除List组合和key resolver；保留P14的Service/Repository/HTTP及P20详情read。
- 不修改冻结角色、分页参数或输出投影；需覆盖三类API-03角色、project/session/page-size绑定cursor与跨项目隔离。

## 验收计划

定向Vault key resolver与路由默认/显式测试；PG18.6合成HTTP验证PM/IM/CustomerManager分页、cursor续页及隔离；完整GitHub hosted后端/前端/父包/A17/A34/A35/A50回归。仅runner D盘临时环境执行。真实vault provisioning与Win11实机不因合成验证标记通过。


## Hosted run 41839890577 finding — 2026-11-04

- Result: backend full suite failed before the PG parent-package jobs. 4,021 tests ran; 31 failures and 6 errors.
- Evidence: newly added read-mode composition resolves the dedicated Output cursor key during platform factory tests. Existing test_production_login.py fixtures injected synthetic cursor sources for prior modules but not the new Output source, so those tests reached the runner's empty Windows credential store and aborted the composed app. The new focused Output cursor tests were not the root issue.
- Scope: validation-fixture omission; production remains fail-closed when the Output key is unavailable. No credential was created or changed.
- Correction plan: add a synthetic OutputRequestListCursorCodec factory patch to the shared production-login test setup, and add an explicit missing-key disposal assertion. Re-run the full hosted workflow and PG18 parent smoke; keep the P21 result incomplete until it passes.
- Recovery: no production migration or data recovery required. Revert the test fixture patch if it changes unrelated expectations; production rollback remains removal of P21 list composition and its dedicated key factory.


## Hosted run 41841051553 finding — 2026-11-04

- Backend full suite/wheel, frontend, package assembly, and A35 handoff passed. The P21 PG18.6 HTTP check returned 404 RESOURCE_NOT_FOUND for the synthetic Project Manager list request before pagination assertions; P21 is incomplete. See run 41841051553 and job 126617682159.
- A17 packaged flow also failed at production startup because the newly required Output list cursor key was absent from its synthetic package test credentials. No customer or production data was used. See job 126618290597. This is a test-fixture compatibility gap; do not weaken the missing-key fail-closed behavior.
- Next: isolate why the seeded authorized Project Manager resolves to 404 (membership/project/department state versus fixture); add the dedicated synthetic cursor key to the hosted A17 fixture only, preserving the read-only current-account Vault contract; rerun full hosted workflow and parent PG smoke. A17 stays unverified until it passes.
- No migration or database recovery needed. P21 rollback still removes only list composition and its key resolver.


## Diagnosis of run 41844332846 — 2026-11-04

- The synthetic Project Manager membership authorization and direct OutputRequestListService page preflight both passed against PostgreSQL 18.6. This localizes the 404 to the ASGI HTTP test adapter.
- Root cause: the verifier supplied the entire URL (including ?page_size=1) as ASGI scope.path while also populating scope.query_string. Starlette therefore routed a path that does not match the frozen route and correctly returned 404.
- Planned correction: split route_path and query_string in the hosted adapter; pass only route_path in scope.path/raw_path. No production route, authorization or contract change.
