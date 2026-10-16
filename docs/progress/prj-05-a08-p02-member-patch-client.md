# PRJ-05-A08-P02：成员 PATCH 安全业务客户端

- 日期/阶段：2026-09-28 / Phase 2；状态：PASS（前端客户端合同，不代表页面或真实浏览器/PG验收）。依据 Gate 2 冻结 `PROJECT_MEMBER_PATCH`、P01 传输桥及 DEC-20260928-443。
- 编码前检查：前置后端 PATCH、成员安全只读投影和固定前端传输均已具备。本项仅涉及 Project 前端业务 DTO/响应分类，不改后端 API、权限、实体、Schema/Migration、架构或依赖。验收为请求字段收敛、身份/状态/版本绑定、已知拒绝与未知结果隔离。
- Changed/Files：`projectMemberPatchClient.ts` 对角色/部门变更只接受明确字段、有效项目/成员/强 ETag 和非 REMOVED 历史；按原成员 UUID、User、状态/起止时间、期望角色/部门及 ETag vN→vN 或 vN+1 验证 200 成功，返回既有安全投影；`projectMemberPatchClient.spec.ts` 覆盖角色/部门/no-op、坏输入零网络、已知拒绝、响应伪造和超时不确定结果。
- 不确定语义：未知失败、非 JSON、响应身份或版本不吻合均标 `PROJECT_MEMBER_PATCH_UNCERTAIN`，不自动重试。后续页面须重读成员历史再判断，不能复用旧版本盲改。
- Migration/兼容：无；兼容 DB head `20260927_0049` 与现有 `/api/v1`；前端静态资源更新即可。回滚撤 Project 客户端与测试，既有传输及服务端保持不变。
- Tests：前端 485/485 PASS、typecheck、生产 build PASS。首轮 UUID 校验少一组导致 5 个新用例失败；修正后测试通过，随后类型检查发现 `record(input)` 收窄冲突并修正，最终全量重跑通过。未作本项真实浏览器/PG、跨平台或性能验收。
- Known Issues/Next：P03 页面须展示目标角色/部门和强版本确认；P04 再作 Windows 11 真实浏览器/隔离 PG 写链。正式信任/Server 2025/Debian/HTTPS、CR-AUT-008 性能、POC-03 质量、Gate 3/可用程序包仍待。
