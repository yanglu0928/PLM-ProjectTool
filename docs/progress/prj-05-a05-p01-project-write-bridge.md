# PRJ-05-A05-P01 项目创建受控写传输桥接

2026-09-28 / 0.1.0.dev0 / PASS（前端传输合同；项目创建 DTO/UI/真实网络待后续任务）。

编码前检查：Phase2/PRJ-05-A05-P01；Gate2、冻结PROJECT_CREATE、PRJ-04-A05显式Windows写组合及AUT-05-A09仅内存SessionClient满足前置。Auth前端会话传输为唯一必要修改模块；无实体/Schema/后端API/权限/依赖变化。涉及 `POST /api/v1/projects` 原冻结路径与 DeploymentAdmin/Session/License/CSRF/幂等要求；客户端不授予任何角色，服务端实时重核。验收：仅原固定路径、同源Cookie/no-store/禁止重定向/单次请求、原CSRF不公开、调用方幂等Key原样传递、刷新只读零请求、互斥、超时无重试、401清本地证明、未知结果不宣称失败或成功；前端test/typecheck/build。风险与回滚见DEC-407；撤方法/测试即可，无迁移。

Changed：`SessionClient.postProjectCreate`只封装现有项目创建路径的单次JSON POST，调用方负责构造和解析项目内容；CSRF由私有字段在发送时加头，不提供令牌访问方法。保留本地Session以支持明确同Key恢复，收到401时清除本地身份/CSRF；网络异常变为固定安全错误，不自动重发。该方法不等于项目创建客户端或页面已可使用。

Tests：8新场景、前端147/147、typecheck、build PASS；含请求头与方法/路径/原Key、无CSRF拒绝、畸形Key零请求、503后保留/401清除、并发Auth命令互斥、超时一次且不暴露底层异常。未运行本项实际浏览器/PG/后端全量、coverage/性能；前述A04读取联调不替代写验收。兼容当前0049，无Migration/API/权限/依赖变更。下一 PRJ-05-A05-P02：项目创建 DTO、201 Location/ETag、业务错误和未知结果安全客户端；再做UI/真实Windows合成联调。正式信任/HTTPS/CR-AUT-008性能FAIL/Gate3/包待。
