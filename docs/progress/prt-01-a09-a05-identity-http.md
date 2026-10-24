# PRT-01-A09-A05：Prototype Identity 六项 HTTP 合同

日期：2026-10-08。结论：`PRT_01_A09_A05_IDENTITY_HTTP_PASS`。下一项：
`PRT-01-A09-A06` Prototype Template 六项 HTTP 合同。

## 实现

- 按冻结 API-04 新增 Prototype LIST、CREATE、GET、PATCH、MARK_NOT_REQUIRED、ARCHIVE 六个路径；
  Router 仅允许显式注入，默认应用不挂载并保持 404。A09 Windows 组合前不改变生产启动模式。
- LIST 使用 A03 Prototype 专用签名游标，绑定 Session、Project、页长及
  `updated_at + prototype_id` 位置；LIST/GET 每次由 A02 Owner 重证项目成员事实。
- CREATE 要求幂等键；PATCH 仅要求强 `If-Match`；MARK_NOT_REQUIRED 要求幂等键与强
  `If-Match`，并要求非空影响 RequirementVersion 集合、理由和影响，可选 Review/Round 必须成对；
  ARCHIVE 要求幂等键、强 `If-Match` 且正文必须为空。
- 所有写入使用严格 Origin/CSRF；请求拒绝重复字段、额外字段、非规范 UUID、超限正文和
  污染查询。成功响应核验 Owner 返回的 Project/Prototype 身份、状态与强 ETag；未授权资源保持
  404 防枚举，内部异常失败关闭且不回显。

## 验证

- 新增合同 2 项，覆盖默认关闭、六个成功操作、续页、读写安全、强 ETag/幂等先决条件、
  Review/Round 成对要求及游标跨项目拒绝；Prototype 相关定向 30 项通过。
- 后端全量 3192 项通过、3 项既有环境条件跳过；compileall 与 `git diff --check` 通过。
- 开发 wheel 共 1223 项，包含 Identity Router，SHA-256
  `d811197de96a2c6a05c247e6b36b5b3d70f29575c792f4189355b979f19e9fbd`；不是正式发行包。

本项无 Migration、依赖、Secret、客户数据或外发；Schema head 保持 0134。Router 合同使用模拟 Owner
隔离验证，真实 Windows/PostgreSQL 18 六操作组合按既定拆分留 A09-A09 统一验收；Server 2025
未外推，Debian 13 实机跳过。
