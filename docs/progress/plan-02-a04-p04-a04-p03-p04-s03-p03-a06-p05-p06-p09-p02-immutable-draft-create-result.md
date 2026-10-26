# A06-P05-P06-P09-P02 PlanVersion 不可变草稿创建结果

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P02`
- 结果：`PASS_SCOPE_LIMITED`

## 实施

- 增加 PlanVersion 创建页：受限选择项目内当前已批准的 Solution Outline 固定版本，严格读取固定来源，填写 WBS 根任务、准入条件、验收标准、排期及风险，并显示完整不可变快照预览。
- 创建前重新读取来源并校验其身份/固定引用；为不确定网络结果保存原始内容与幂等键，仅允许原内容原操作号重试；成功后按响应中的固定版本 ID 读取并核验完整快照。
- Plan Detail 增加受授权用户入口；增加 Create 路由。
- 将 PlanVersion Create router 接入显式 Windows 写组合，提供现有 Session/CSRF、License、审计、文档/解析来源服务；默认/Login-only/只读组合不装载该写路由。
- 未改变冻结 API Contract、ORM、Schema、Migration；不包含 Validate/Review UI，不把创建 DRAFT 解释为批准或交付。

## 验证

- 前端定向：Solution 候选与 Create 页面 2 文件/4 测试通过。
- 前端全量：Vitest 197 files / 2057 tests 通过；`typecheck` 和生产构建通过。默认并发首次运行触发 Node OOM；Vitest 5 不支持 `--minWorkers`，改用 `--maxWorkers=1` 串行全量运行成功。构建仍有既有 >500KB 主 chunk 提示。
- 后端定向写组合/API测试通过；完整 pytest `4190 passed, 3 skipped, 6219 subtests passed`。首次全量测试在并发资源压力下有一条 Windows trace launcher 偶发失败，单项复验通过；串行环境下完整后端回归复跑全绿。
- Windows 11 + PostgreSQL 18.6 隔离库：migration upgrade/check、合成 Outline/Section 固定版本夹具、真实 PlanVersion SQL 创建及 HTTP 201、固定版本 HTTP 200 和快照字段核对通过，隔离库清理。Session、License、Project 授权及 Approved Solution source proof 为合成替身；这不是正式信任、真实批准状态或客户 UAT 验证。
- 首次 PG 夹具未满足 Outline Version 数据库基础约束而被拒绝；按既有 `ACTIVE` Outline、至少一个 Section 及闭合版本集合规则修正后复验通过。数据库约束本身未改动。
- `git diff --check` 通过。未使用客户数据或 Secret；本任务临时目录/数据库位于 D 盘。

## 限制与后续

- 本任务只证明创建表单与显式 Windows 写组合在合成条件下可用；正式信任材料/目标账户密钥、真实批准方案、Server 2025、Debian 13、完整业务 UAT、Gate/Pilot/正式 Release 仍未通过。
- 下一项：为固定 PlanVersion 增加独立 Validate 页面/结果消费前置核查；保持 Validate 与 Review 分离，先核对冻结合同、Owner、写组合和现有前端 Client，再开始编码。
