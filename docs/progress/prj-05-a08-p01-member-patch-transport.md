# PRJ-05-A08-P01：成员 PATCH 受控前端传输

- 日期/阶段：2026-09-28 / Phase 2；状态：PASS（传输合同，不是业务响应或真实浏览器验收）。依据 Gate2 冻结 `PROJECT_MEMBER_PATCH`、PRJ-04-A11-P01/P02 和 DEC-20260928-442。
- 编码前检查：前置 Gate2、后端 PATCH/Windows 显式组合、现有内存 SessionClient 均已满足。涉及前端 Auth 传输与 ProjectMember ID/ETag，不改实体、服务端 API、权限、Schema/Migration 或依赖。验收为固定同源路径、私有 CSRF、强 If-Match、单次 PATCH、互斥和未知结果不自动重试；风险为无幂等 Key 的重复变更。
- Changed/Files：`apps/frontend/src/modules/auth/api/sessionClient.ts` 增固定成员 PATCH 方法，`sessionClient.spec.ts` 增请求、非法输入、会话、并发/超时测试；本进度、决策、状态与版本说明。只校验目标/版本/请求体边界，业务 DTO 和成功投影留 P02。
- Migration：无；兼容 DB head `20260927_0049`。API：只消费冻结 `PATCH /api/v1/projects/{project_id}/members/{project_member_id}`，没有新增或破坏合同。Architecture/依赖：无变化；升级无需数据操作，更新前端静态资源即可。回滚撤方法及测试。
- Tests：前端 479/479 PASS、typecheck、生产 build PASS；本项未运行真实 HTTP/PG、浏览器、覆盖率或性能，不以既有后端 PG 证据替代本项集成验证。
- Known Issues：PATCH 无幂等 Key，503/超时后可能已提交；后续客户端必须重读当前成员历史再判断，不能盲目复用旧 ETag。正式信任/Server2025/Debian/HTTPS、CR-AUT-008 性能、POC-03 质量、Gate3/完整程序包仍待。
- Next：`PRJ-05-A08-P02` 成员 PATCH 请求/响应安全客户端与明确拒绝/未知结果分类，再做页面和实际浏览器/PG 验证。
