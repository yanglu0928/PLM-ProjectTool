# PRJ-05-A07-P02 项目成员创建安全响应客户端

2026-09-28 / 0.1.0.dev0 / PASS（前端安全响应合同；页面和实际写链另验）。

编码前检查：Phase2，Gate2/Phase1通过；冻结`PROJECT_MEMBER_CREATE`、PRJ-04-A10-P01～P03后端持久幂等与P01前端单次传输为输入。涉及Project前端客户端与只读成员投影函数；实体ProjectMember仅作响应投影，无Schema/API/权限变更。验收为请求安全白名单、201完整匹配、明确拒绝/未知结果分离、无盲重试。风险与回滚见DEC-435。

Changed：新增`ProjectMemberCreateClient`，规范UUID、角色、可选UTC生效时间、原幂等Key，白名单构造请求；201严格绑定MemberView八字段/初始ACTIVE、无结束时间、初始强ETag、响应头Location/ETag及请求User/Role/Department/生效时间。复用只读成员安全投影，额外字段不进入UI。已知状态/错误码给出固定中文提示；所有未知结果标记uncertain，单次提交且不旋转Key。微秒生效时间按六位比较，避免JS毫秒精度遗漏。无Migration、后端API、生产依赖或版本破坏；兼容DB head0049，无升级步骤。

Tests：新增32项前端测试；全前端462/462、typecheck、生产build exit0。合成HTTP响应/前端契约验证，不是实际浏览器、PG写入或生产信任验证。Known Issues：创建页面、真实浏览器/PG链、正式TLS/License、Server2025/Debian、性能/质量Gate3及完整程序包仍待。Next：PRJ-05-A07-P03成员创建页面；不把未验证项标PASS。
