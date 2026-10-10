# PRJ-05-A07-P03-A04：项目成员创建页面

- 日期/阶段：2026-09-28 / Phase 2；状态：PASS（前端页面合同，不是浏览器/数据库写验收）。依据 CR-PRJ-006、DEC-20260928-440，A01～A03 前置 PASS。
- Changed：新增项目成员创建页与路由/成员历史入口。当前项目负责人且可提交的会话才展示流程，实时权限仍以后端为准；按准确用户名查候选、仅选 ACTIVE 部门、显式选择角色并确认。用户名变化清除旧候选；未知提交结果保留原输入和幂等 Key 于页面内存、人工确认后原样重试，幂等冲突/会话或项目变化阻止页面重试。成功仅展示经原创建客户端验证的服务端结果。
- Files：`apps/frontend/src/modules/project/views/ProjectMemberCreateView.vue` 及测试、`apps/frontend/src/app/router.ts`、`ProjectMemberListView.vue`、本进度/决策/状态/CR/版本说明。
- Migration：无；DB head `20260927_0049` 兼容。API：消费现有候选POST、部门GET、冻结成员创建POST，无合同/权限变更。依赖/升级：无。回滚撤页面、路由和入口，A01～A03 保留。
- Tests：全前端 474/474 PASS，typecheck、生产 build PASS；页面权限、明确确认、陈旧候选失效、原 Key 未知结果重试、明确拒绝与冲突阻断通过。首轮 3 测试因选择器命中部门刷新按钮而失败，修正测试定位后全量重跑通过。
- Known Issues：尚未执行实际浏览器/隔离 PostgreSQL 创建与 Audit 验证；正式目标账户 License/HTTPS、Server 2025/Debian、性能/POC-03 质量/Gate 3/完整发行包待。
- Next：`PRJ-05-A07-P03-A05` 独立实际浏览器/PG 成员创建写链与安全回归。
