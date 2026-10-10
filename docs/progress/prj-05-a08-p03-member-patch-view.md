# PRJ-05-A08-P03：项目成员角色/部门修改页面

- 日期/阶段：2026-09-28 / Phase 2；状态：PASS（前端页面合同，真实浏览器/PG待 P04）。依据 Gate2 冻结 `PROJECT_MEMBER_PATCH`、P01/P02 和 DEC-20260928-444。
- 编码前检查：成员历史、安全 PATCH 客户端和 ACTIVE 部门客户端已具备。冻结 API 无单成员 GET，故从当前已读取列表中选精确成员快照，不添加新端点或凭路由 ID 盲查。本项仅 Project 前端页面与测试，无实体/Schema/Migration、后端 API/权限、依赖变更。
- Changed/Files：`ProjectMemberListView.vue` 对当前项目负责人、可提交会话及非 REMOVED 成员展示编辑入口；打开时重新取 ACTIVE 部门，明确展示目标 User/旧角色/部门/状态/强版本，选择新值并勾选后单次 PATCH。成功回执与重新读取的当前历史分离；已知拒绝清旧编辑并刷新；未知结果锁住本页后续写入，刷新仅供对账，提示核审计后重入，不自动重试。导航/身份变化丢弃迟到回执。对应 spec 补授权、确认、冲突、未知和跨项目迟到场景。
- Validation：前端 490/490 PASS、typecheck、生产 build PASS。首轮类型检查暴露测试 fixture 字面类型问题；新增冲突测试发现刷新会清错误提示、以及复用已消费 Response 的测试夹具问题，修正后全量复验通过。尚无真实浏览器/PG 写链证据。
- Compatibility/rollback：兼容 DB head `20260927_0049` 和冻结 `/api/v1`；更新前端静态资源即可，无数据升级。撤列表编辑入口与测试即可回滚，P01/P02及后端保留。
- Known Issues/Next：强版本冲突需重读后重新决定；超时/未知结果仅靠当前列表不能证明本次请求是否执行，须审计核对。P04 做 Windows 11 真实浏览器/隔离 PG 端到端；正式信任/Server2025/Debian/HTTPS、CR-AUT-008 性能、POC-03 质量、Gate3/完整程序包仍待。
