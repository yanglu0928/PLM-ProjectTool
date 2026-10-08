# PRT-01-A09-A04：PrototypePackage 五项 HTTP 合同

日期：2026-10-08。结论：`PRT_01_A09_A04_PACKAGE_HTTP_PASS`。下一项：
`PRT-01-A09-A05` Prototype Identity 六项 HTTP 合同。

## 实现

- 按冻结API-04新增Package LIST、CREATE、GET、PATCH、SET_MEMBERS五个路径；Router只允许显式注入，默认应用
  不挂载并保持404。A09 Windows组合前不改变生产启动模式。
- LIST使用A03 Package专用游标，绑定Session、Project、页长和`updated_at + package_id`位置；GET只返回同项目
  当前成员ID，不展开Prototype或版本内容。所有读取要求可信Host、有效Session并由A02 Owner重证当前成员。
- CREATE与SET_MEMBERS要求严格Origin/CSRF和持久幂等键；PATCH按冻结控制位只要求强`If-Match`，不伪造
  幂等键；SET_MEMBERS同时要求强`If-Match`。请求采用严格JSON、拒绝重复字段/额外字段/非规范UUID/超限正文。
- 成功响应投影显式核验Owner返回的Project/Package身份、状态、ETag和规范成员顺序；授权失败保持404防枚举，
  版本/状态/幂等冲突使用统一安全错误，不回显内部异常。

## 验证

- 新增合同4项，覆盖默认关闭、五个成功操作、续页、强ETag/幂等/CSRF/Origin、重复JSON、查询污染、游标
  跨项目、Owner异常与投影身份漂移；Prototype/Requirement相关定向30项通过。
- 后端全量3190项通过、3项既有环境条件跳过；compileall与`git diff --check`通过。
- 开发wheel共1222项，包含Package Router，SHA-256
  `c37b0dc9edd80f3339e94eee0eda340c3f352eea2a1e8080e73330905387f618`；不是正式发行包。

本项无Migration、依赖、Secret、客户数据或外发；Schema head保持0134。Router合同使用模拟Owner隔离验证，真实
Windows/PostgreSQL 18五操作组合按既定拆分留A09-A09统一验收；Server 2025未外推，Debian 13实机跳过。
