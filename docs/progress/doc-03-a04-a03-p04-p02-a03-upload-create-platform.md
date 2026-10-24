# DOC-03-A04-A03-P04-P02-A03 Windows 显式上传创建组合

日期：2026-09-26；追溯：冻结 API-02、DEC-20260926-112、P04-P01/P02-A01/A02。

结果：Windows `--platform-write` 显式装配 UploadIntent 创建路由。当前账户独立上传 Token Key 预检失败则整个应用构造失败并释放数据库运行时。每个请求使用真实 Session/CSRF、DeploymentAdmin 或 Project 成员事实、License Guard、PostgreSQL UploadIntent/幂等收据与 Audit。默认登录和平台只读模式维持 404。

验证：Windows 11/Python 3.13 后端 490 项无失败（2 项符号链接权限跳过），开发 wheel 构建通过。PostgreSQL 18 独立合成库使用真实 Auth Session 行验证 PM/IM/CustomerManager 201，CustomerMember/非成员/跨项目 404，GLOBAL 仅 DeploymentAdmin，Key 重放仅一条 Intent/Audit，许可拒绝 403，成员降权 404，会话撤销 401；合成启动缺上传 Key 时整个写模式失败关闭。临时数据库已删除，服务已停止。

已知边界：License 服务和上传密钥在组合验证中为合成信任源；正式发行公钥、目标账户独立密钥与备份仪式未完成。没有 Content HTTP、Commit/Abort 或 Parser Job，因此上传尚不能完成为正式 DocumentVersion。无新 Migration、API Contract 破坏或依赖；回退为不装配该 Router，旧 Intent 按过期/终止处理。
