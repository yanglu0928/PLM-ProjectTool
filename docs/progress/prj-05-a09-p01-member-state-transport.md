# PRJ-05-A09-P01：项目成员状态命令私有前端传输

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（仅传输合同，不代表业务响应、页面或浏览器验收）。输入 Gate2 冻结 `PROJECT_MEMBER_SUSPEND/RESUME/REMOVE`、PRJ-04-A12-P03 与 DEC-20260929-446。
- 编码前检查：后端三种状态命令已在 Windows 显式平台组合可用，现有内存 SessionClient/成员历史具备。只改 Auth 前端传输方法及测试，涉及项目/成员双 UUID、强版本、原幂等 Key、私有 CSRF；无实体/Schema/Migration、后端 API、权限或依赖变化。
- Changed：`SessionClient.postProjectMemberState` 固定三条 POST 路径、空请求体、同源 Cookie、no-store、禁重定向与强 If-Match；调用者原 Key 原样传递。401 清本地会话提交证明；503/超时不自动重试、不生成新 Key；共享会话互斥阻止重叠命令。非法目标、动作、版本或 Key 在发网前拒绝。
- Tests：新增 6 个测试（含三动作参数化），覆盖请求路径/头/无 Body、坏输入零网络、只读与 401/503、超时单次和互斥；前端 496/496、typecheck、生产 build PASS。未运行此项真实 HTTP/PG或浏览器状态命令；后端既有验证不替代前端端到端。
- 兼容/升级/回滚：兼容 DB head `20260927_0049` 与冻结 `/api/v1`，前端静态资源更新即可，无数据升级。撤新增方法和测试可回滚。
- Known Issues/Next：状态命令是幂等 Key 绑定的首次结果，首次回执不等于当前状态；P02 必须严格区分已知拒绝/未知结果与首次回执，P03 页面保留原 Key 并让用户明确恢复，P04 才做实际 Windows 11 浏览器/隔离 PG。正式信任/Server2025/Debian/HTTPS、CR-AUT-008 性能、POC-03 质量、Gate3/完整程序包仍待。
