# SOL-01-A16-P05：Windows 显式 Reference Eligibility 组合

日期：2026-10-09。结果：`SOL_01_A16_P05_REFERENCE_ELIGIBILITY_WINDOWS_PG_PASS`（仅 Windows 11 合成信任源/隔离 PostgreSQL 18.6）。

## 编码前检查

- 当前 Phase/WBS：Phase 2 / SOL-01-A16-P05；输入为冻结 API-04、CR-SOL-014、A16-P03 内部 Owner 与 A16-P04 可选 HTTP，前置均已满足。
- 单一问题：在 Windows 生产装配中仅对显式 `--platform-write` 模式开放 PROJECT/GLOBAL 资格写；默认及只读模式仍关闭。涉及 Solution Windows 工厂和生产组合，不改变 Schema、ORM、Migration、冻结 API 或前端。
- 实体/API/权限：ReferenceSolution 根/不可变资格事件；既有双 Scope `:set-eligibility`；PROJECT ProjectManager、GLOBAL DeploymentAdmin，以及 Session/Origin/CSRF/License/来源现时证明。
- 验收标准：两路由真实 ASGI/隔离 PG 命令及历史重放通过；安全依赖缺失失败关闭；默认/只读组合不构造写路由；后端回归通过。
- 风险：合成信任源不等于正式目标账户/License/HTTPS 验收；历史回执不是当前资格。未对此作生产可用推断。

## Changed / Files / Migration / API

- Windows Solution Reference 工厂复用现有来源资格服务，装配受控资格 Owner 与双 Scope 路由；空安全 Port 抛出无敏感细节的启动错误。
- 生产组合只在 `include_secret_write` 分支构造并注入两个路由；默认/只读不构造。
- 文件：`apps/backend/src/plm_assistant/entrypoints/windows_solution_reference.py`、`production_login.py`、`apps/backend/tests/contract/test_production_login.py`、`validation/sol-01-a16-p04-reference-eligibility-http/verify_{project,global}.py` 与新增 `validation/sol-01-a16-p05-reference-eligibility-windows/verify_{project,global}.py`。
- Migration：无新增；目标库仍需既有 `0153`。API：仅装配已冻结路径，无字段/角色/错误码变更。

## Tests / Result

- Win11 双 Scope Windows 工厂/真实 Session/ASGI/临时 PG18.6：PROJECT/GLOBAL 各脚本退出 0，沿用 P04 的资格转换、重放、权限/锁/Origin 与事件/Audit SQL 验收；脚本还证明缺安全 Port 拒绝装配。
- 生产入口定向合同 `38 passed, 12 subtests passed`：默认/只读不调用新工厂，显式写模式工厂异常时启动失败关闭并清理 runtime。
- 加入生产入口新用例后，后端全量 `3405 passed, 3 skipped, 5199 subtests passed`。

## Known Issues / Next

无新依赖/Secret/客户数据外发。回滚为撤下可选生产组合路由并重启，资格事件及审计历史保留，不执行历史数据回滚。A16-P06 需前端现时资格读取、人工理由/确认与 Edge 真实浏览器验收。真人确认、正式 License/账户/HTTPS、Server 2025、20 并发、Gate 3/UAT/发行尚未验证；Debian 13 实机依用户指令跳过。

TraceLink：Gate 2 API-04 → CR-SOL-014 → A16-P01～P04 → 本 P05 → P06 → Gate 3。
