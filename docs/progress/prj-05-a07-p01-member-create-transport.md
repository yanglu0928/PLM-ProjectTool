# PRJ-05-A07-P01 项目成员创建受控前端传输

2026-09-28 / 0.1.0.dev0 / PASS（前端传输合同；安全响应、页面和实际写入另验）。

编码前检查：Phase2、Gate2/Phase1通过；冻结`PROJECT_MEMBER_CREATE`、PRJ-04-A10-P01～P03后端持久幂等/Windows显式写组合、原SessionClient写命令桥为输入。DEC-434先记边界/风险/回滚。仅改前端Auth会话客户端与测试；无后端/实体/权限/API/Schema/Migration/依赖变化。

新增`postProjectMemberCreate(projectId,body,key)`：规范非零Project UUID、非空至8KiB JSON字符串、16～128可打印原幂等Key本地校验；仅固定`POST /api/v1/projects/{projectId}/members`，私有CSRF、同源Cookie、no-store、禁止重定向，沿用会话互斥。401清本地身份/写证明；超时或传输失败不盲重试、不更换Key。方法只返回原始Response，不把201或5xx擅自解释为业务事实。

验证：新增12项固定路径/CSRF/Key、非法输入零网络、只读会话拒绝、401/503证明处理、并发互斥和超时单次测试；全前端430/430、typecheck、生产构建exit0。未运行本项实际浏览器/PG写入、正式TLS/License、Server2025/Debian、性能或全UAT。兼容DB head0049，无升级步骤；回滚撤新增方法/测试。下一PRJ-05-A07-P02负责201安全响应与确定拒绝/不确定结果分类。
