# AUT05A08-P01 改密客户端合同

2026-09-28 / 0.1.0.dev0 / PASS（仅前端改密客户端合同）。

编码前检查：Phase2；WBS AUT05A08-P01；输入冻结API02、`password-change-v1-increment.md`、现有SessionClient及Windows `platform-write` 后端验证；前置Gate2/A07和后端可选改密接口已满足。模块仅前端Auth客户端；实体只读SessionView与返回credential_version；API使用现有POST `/api/v1/auth/password:change`，不改路由/字段；权限仍由服务端现有Session/CSRF/Origin/本人实时校验。验收：同源一次请求、两个只写密码/幂等键、严格输入、已知错误安全映射、响应仅采信安全版本；成功及不确定失败均清本地CSRF/身份，绝不自动重试；旧Cookie实际注销由后端负责。风险：503可能已提交，不能用新Key盲重试；调用方须保留本次Key并在重新登录后按原两密码决定恢复，页面交互另列P02。不存储密码、Token或CSRF于浏览器持久存储。无Migration/API变化；回滚撤客户端方法与测试。

L2设计决定：`SessionClient.changePassword(current,new,key)`由调用方持有幂等键，不在Client内自动新建或重试；客户端只返回正整数credential_version，不把后端响应当新会话。输入长度按UTF-8字节（1～1024）、NUL拒绝，不trim/normalize。请求结果不确定时本方法将会话本地能力清空并返回固定安全错误，交互层须让用户重新登录再以同Key/原两密码恢复；不能谎称服务端已撤销。

Changed：客户端新增改密方法，沿用唯一同源Cookie/no-store/无跳转传输及已有互斥；校验密码UTF-8字节上限、NUL、可打印16～128字符幂等键，发送原合同双密码字段与私有CSRF；仅采信安全正整数`credential_version>=2`。409/422映射固定安全提示；503/无效响应/网络故障统一安全拒绝，不自动重试，不将响应中的其他字段或任何Token保存为新会话。成功后本地身份与CSRF均空；失败请求后亦清空，不把本地清空描述成服务器撤会话。无后端/Schema/API/依赖变更。

Tests：新增14项测试覆盖普通/受限会话、请求合同、密码多字节长度/NUL、坏Key不发送且不丢既有Session、刷新只读拒绝、409/422/503一次请求、坏响应安全关闭。前端80/80测试、类型检查和生产构建通过。首轮80测试通过但TypeScript测试变量为`unknown`而构建失败；补明确类型收窄后复验通过，初始失败不冒充PASS。没有本轮真实浏览器/真实PG改密；后端既有Windows工厂验证不能替代前端端到端证明。

Next：A08-P02将页面呈现、密码清空、显式重新登录/未知结果恢复提示接入，并核浏览器/真实后端链。全量发行、正式信任/HTTPS/CR008性能FAIL/Gate3仍待。
