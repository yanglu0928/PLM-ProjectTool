# PRJ-05-A06-P02 项目成员历史只读页面

2026-09-28 / 0.1.0.dev0 / PASS（前端页面合同；真实浏览器/PG另验）。

编码前检查：Phase2、Gate2/Phase1通过；输入冻结`PROJECT_MEMBER_LIST`、P01安全只读客户端、现有项目详情路由。DEC-432先记决策/风险/回滚。仅改前端Project页面、路由、入口和测试，无后端/实体/Schema/Migration/API/权限/依赖变化。

新增`/projects/:projectId/members`，从项目详情进入。无内存身份或改密受限时零成员请求；不以Session项目摘要/角色猜测权限，服务端每次GET仍按当前ProjectManager/CustomerManager授权。页面展示成员历史状态/部门/生效与结束时间，服务器文字只作文本渲染；固定50条分页可继续读取。刷新、路由切项目、读失败均清旧成员与cursor；迟到旧项目结果丢弃，跨页重复成员失败关闭。

验证：新增8个页面场景，覆盖无身份/受限、成功与HTML转义、空结果、翻页、拒绝清旧、非法路径、路由迟到回执及跨页重复；前端418/418、typecheck、生产构建 exit0。未运行本项真实浏览器/PG、正式TLS/License、Server2025/Debian、性能/全UAT。兼容DB head0049，无升级步骤；回滚撤页面/路由/入口。下一PRJ-05-A06-P03在Windows11隔离浏览器/PG验当前角色与成员历史页面。
