# PRJ-05-A06-P01 项目成员历史只读客户端

2026-09-28 / 0.1.0.dev0 / PASS（前端客户端合同，页面与真实浏览器另验）。

编码前检查：Phase2、Gate2/Phase1通过；冻结`PROJECT_MEMBER_LIST`、后端Windows显式成员列表接口及ProjectReadClient模式为输入。DEC-431先记录范围/风险/回滚。只改前端Project成员只读客户端与测试；无实体、后端API、权限、Schema/Migration或依赖变化。

新增`ProjectMemberReadClient.list(projectId,cursor?)`：固定50条分页，规范UUID与不透明签名cursor输入校验；相对同源Cookie GET、no-store、禁止重定向、超时Abort不重试。对安全MemberView逐字段校验并仅保留白名单投影，强版本、UTC时间、状态与结束时间形状、分页游标、页内重复ID失败关闭。固定中文错误提示不回显服务端正文。授权与cursor签名验证仍由服务端负责，客户端不声称项目访问权。

验证：前端410/410测试、typecheck、生产构建 exit0；新增48个客户端场景覆盖安全投影、分页、非法目标/游标零网络、畸形成员/分页/信封、权限错误和timeout单次。未运行本项实际浏览器/PG页面、正式TLS/License、Server2025/Debian、性能、全UAT。兼容DB head0049，无升级步骤。回滚撤此只读客户端/测试；下一PRJ-05-A06-P02实现成员历史页面，再做Windows11实际浏览器联调。
