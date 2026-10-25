# PRJ-05-A07-P03-A05：Windows 11 实际浏览器/PG 成员创建

- 日期/阶段：2026-09-28 / Phase 2；状态：PASS（Windows 11 本机隔离合成信任源）。依据 CR-PRJ-006、DEC-20260928-441、A01～A04 前置。正式发行信任与 Gate 3 不因此通过。
- Changed：扩展自有浏览器 fixture 的独立 `--member-create-api-only` 和 `--member-create-browser` 模式；随机 PostgreSQL 库/角色、Windows Vault 测试凭据、真实 Scrypt 用户、负责人项目、未分配启用候选和 ACTIVE/INACTIVE 两部门；测试结束自动清理。A05 浏览器发现 A03 部门客户端把原生 `fetch` 当对象方法调用，测试替身未显露；改为提取函数后调用并补无接收者回归测试，生产数据/合同不变。
- Files：`validation/prj-05-a04-browser-project/serve.py`、`apps/frontend/src/modules/project/api/projectMemberChoicesClient.ts` 及测试、本进度/状态/CR/决策/版本说明。
- Migration：无；兼容 DB head `20260927_0049`。API/权限/依赖：不变；升级仅部署更新后的前端静态资源，回滚可撤客户端修正与验证模式。
- Tests：首次 API-only 的会话计数断言沿用旧模式失败，修正验收脚本后重跑 exit0：匿名候选 401、负责人精确候选与统一未命中、仅 ACTIVE 部门、成员创建/原 Key 重放 201、异输入冲突 409；SQL 成员/Audit/收据各一。首次实际浏览器部门读取失败揭示原生 fetch receiver 问题；修正后前端 475/475、typecheck/build exit0，重新登录的真实浏览器完成项目→成员→候选→角色/部门确认→提交，页面显示已确认；随机 PG 核对成员/Audit/收据各一、两 Session/两活动成员。既有项目读、成员历史、项目创建三个 API/PG fixture 模式回归 exit0。每轮自有服务/库/角色/Vault 凭据清理确认；本轮启动的 PoC PostgreSQL 恢复为原停止状态。
- Known Issues：合成 License Guard/游标密钥不代表正式目标账户信任；Windows Server 2025/Debian、HTTPS、性能 CR-AUT-008、POC-03 质量、Gate 3/完整发行包仍待。页面未知结果原 Key 分支只经过前端合同测试，未在真实网络故障下注入验证。
- Next：Phase 2 下一独立 WBS 先检查项目成员维护（角色/部门/状态）前端 Scope 和安全前置；不得把本次成员创建 PASS 外推到全部项目功能或可交付程序包。
