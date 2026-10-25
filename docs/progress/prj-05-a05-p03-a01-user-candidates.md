# PRJ-05-A05-P03-A01 管理员首位负责人候选读取

2026-09-28 / 0.1.0.dev0 / PASS（前端只读客户端合同；选择页面和实际项目创建待后续）。

编码前检查：Phase2，Gate2已批准。输入为冻结`AUTH_USER_LIST`、后端Windows显式User List及`PRJ-05-A05-P02`创建客户端。单一范围是Auth前端管理员用户列表读取，不修改实体/Schema/后端API/角色、权限、依赖或生产配置。冻结读取为`GET /api/v1/admin/users`，仅DeploymentAdmin可读，Session和License仍由服务端实时校验。先登记DEC-409，风险是候选过时、分页未加载全量；回滚删除新增客户端/测试，无迁移。验收同源Cookie/no-store/无CSRF单次GET、50条分页和游标、白名单投影、安全拒绝、超时无重试、前端test/typecheck/build。

实现：仅映射`user_id`、`username_display`、`account_state`；额外邮箱/内部字段不泄漏。启用/停用状态均可展示，后续页面只允许启用候选被选择；列表不含跨项目成员资格，创建时`lock_eligible_manager`/成员唯一约束才是事实。游标仅接受有界`u1.`不透明形式，响应必须有合法trace、完整页/游标一致且ID无重复；不自动翻页。401/403/404及失效游标按状态与错误码固定提示，其余和非JSON/异常统一安全错误。

验证：新增32个参数化场景；`pnpm --dir apps/frontend test`为205/205，`pnpm --dir apps/frontend build`含typecheck与Vite构建通过。初次build遇到测试代码`unknown`收窄问题，修复重跑通过。无本项真实HTTP/浏览器/PG或后端全量、性能验证；不能据此称选择器、写入或Gate3通过。兼容既有0049，无升级动作。下一P03-A02接管理员创建页面并在同账户锁定原输入/原幂等Key恢复未知结果；随后Windows11隔离PG/浏览器写联调。正式发行信任/HTTPS、CR-AUT-008性能FAIL、Gate3/可用包仍待。
