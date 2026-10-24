# PRT-01-A09-A07-P03：Prototype Version/Review 五项 HTTP

日期：2026-10-08。结论：`PRT_01_A09_A07_P03_VERSION_REVIEW_HTTP_PASS`。
下一项：`PRT-01-A09-A08` RequirementPrototypeLink HTTP。

## 实现

- 新增冻结路径的Version LIST、CREATE、GET、VALIDATE可选Router和独立SUBMIT_REVIEW Router；
  `create_app`只在显式注入时挂载，默认应用五项均保持404。
- LIST使用PrototypeVersion专属签名cursor，绑定Session、Project、Prototype和page size，上限100；GET和
  LIST只投影Owner返回的不可变Template、Artifact、Requirement、Interaction、Coverage与内容指纹。
- CREATE严格接收六字段正文，要求可信Origin、Session、CSRF、Idempotency-Key和强If-Match；完整命令交给
  Owner，成功返回201、Location及Owner原子推进后的Root ETag。
- VALIDATE要求空正文及幂等键，把首次不可变Audit proof投影为`valid/blocking_issues/warnings/
  coverage_summary/checked_at`，重放时响应信封仍使用当前HTTP trace。
- SUBMIT_REVIEW只接受非空Reviewer候选、`PROTOTYPE_ALL_V1`及空due/note；Review创建、资格、状态推进、
  Audit和receipt全部继续由A07 Owner负责。

## 验证

- 6项合同测试覆盖默认关闭、五项成功、分页/游标跨Prototype拒绝、101页长拒绝、严格JSON、空验证正文、
  缺幂等/If-Match、Origin/Session/CSRF、Owner错误映射及畸形输出失败关闭。
- Windows 11 / Python 3.13后端全量3205项通过、3项按既有环境条件跳过；compileall和
  `git diff --check`通过。
- 开发wheel含1227项，SHA-256
  `8760faebb6ed13e0432e3d20f816e1f4a29e8b09741aa49f0aad5815ca2f23ed`，包含两个新Router。

本项无Schema/Migration、依赖、Secret或外发；Schema head保持0134。真实Windows 11/PostgreSQL 18组合
留A09-A09统一验收，Server 2025不据此外推，Debian 13按用户指令跳过实机。
