# PRT-01-A09-A06：Prototype Template 六项 HTTP 合同

日期：2026-10-08。结论：`PRT_01_A09_A06_TEMPLATE_HTTP_PASS`。下一项：
`PRT-01-A09-A07` Prototype Version/Review 五项 HTTP 合同。

## 实现

- 按冻结 API-04 新增 PROJECT/GLOBAL Template 各自 LIST、CREATE、REVISE 六个路径；Router 仅显式
  注入，默认应用保持 404，A09 Windows 组合前不改变生产启动模式。
- PROJECT LIST 保留既有 Owner 语义，返回同项目 PROJECT 和允许的 GLOBAL 当前版；GLOBAL LIST 仍是
  DeploymentAdmin 管理入口。两者使用同一 Template cursor 类型但强绑定 scope、Project、Session、
  页长及 `updated_at + template_id`，禁止跨 scope/项目重放。
- CREATE 要求 Origin/CSRF 和幂等键；REVISE 另要求强 `If-Match`。请求不允许客户端传 scope、
  Project、Actor 或状态；Layout/Component、适用终端和 ArtifactRef 仍由 A04 Owner 执行非可执行合同、
  规范化、固定 DocumentVersion 证明和不可变版本链。
- 响应在输出前再核验 scope/Project/Template/Version、强 ETag、合同规范形、ArtifactRef 序列和
  内容指纹；Owner 投影漂移或非规范持久事实失败关闭。

## 验证

- 新增合同 4 项，覆盖默认关闭、六个成功操作、PROJECT/GLOBAL 分页、游标跨 scope 拒绝、
  Origin/CSRF/幂等/强 ETag、严格正文、安全错误映射及输出身份/制品漂移失败关闭；相关定向
  20 项通过。
- 后端全量 3196 项通过、3 项既有环境条件跳过；compileall 与 `git diff --check` 通过。
- 开发 wheel 共 1224 项，包含 Template Router，SHA-256
  `bfb931cd9a7bf2e8d8fd33a8feb6b927ae1888172764253a4685cb79972f452d`；不是正式发行包。

本项无 Migration、依赖、Secret、客户数据或外发；Schema head 保持 0134。Router 合同使用模拟 Owner
隔离验证，真实 Windows/PostgreSQL 18 六操作组合留 A09-A09 验收；Server 2025 未外推，Debian 13
实机跳过。
