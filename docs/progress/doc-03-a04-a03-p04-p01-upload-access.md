# DOC-03-A04-A03-P04-P01 上传授权适配

日期：2026-09-26；基线：冻结 API-02 上传角色/控制矩阵，现有 Auth Session/CSRF 与 Project 当前成员事实。

结果：内部适配器在每次 UploadIntent 创建/Content 事务中重新验证当前 Session、CSRF 与 actor_id 一致性；GLOBAL 要求 DeploymentAdmin；PROJECT 要求活动项目中的 ProjectManager、ImplementationMember 或 CustomerManager；Content 还要求当前用户是该 UploadIntent 创建者。授权接口不持有跨流数据库事务；Content 原服务在流前和流后分别调用它。

验证：Windows 11/Python 3.13 后端 482 项无失败，2 项因本机符号链接权限跳过；新增角色矩阵、身份冒用、归档项目、Content 创建者与 GLOBAL 管理员单元测试通过；开发 wheel 构建通过。未运行本适配器的 PostgreSQL 真实 Session/许可/HTTP 组合验证，不将其记为正式公开入口 PASS。

迁移与 API：无 Schema Migration；无公开 API；无新依赖。升级仍以现有 `20260925_0024` 为前置。回退可不装配该适配器，已有内部上传与数据不改变。

下一项：P02 在可选 HTTP 组合中接入当前 License Guard，并以 PostgreSQL 真实 Session/CSRF、角色变更和许可拒绝做端到端验证；正式信任锚仍属发行阻塞。
