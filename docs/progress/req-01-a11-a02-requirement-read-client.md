# REQ-01-A11-A02：Requirement 严格只读客户端

日期：2026-10-08。结论：`REQ_01_A11_A02_READ_CLIENT_PASS`。下一项：
`REQ-01-A11-A03` Requirement 列表、详情与来源定位页面。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A11-A02
输入基线：A11-A01、A10四个只读HTTP、统一响应envelope/安全错误
前置任务：A11-A01 PASS
涉及模块：frontend requirementReadClient
涉及实体：Requirement、RequirementVersion及其固定owned集合
涉及API：REQ_LIST/GET、REQ_VERSION_LIST/GET
涉及权限：客户端不缓存授权结论；服务端每次读取重证
验收标准：精确路径/父级、独立opaque cursor、强ETag、严格DTO/计数/ordinal/错误/超时
风险：多余字段泄漏；错Project/Requirement父级；断裂ordinal；列表乱序；首次摘要冒充详情
```

## 结果

- 新增 `RequirementReadClient`，实现Requirement list/get及Version list/get四个读取；游标只作为
  opaque token回传，不解析或跨资源族复用，所有GET固定same-origin/no-store/redirect error。
- Requirement详情同时校验响应体强ETag与响应头；列表核验`updated_at + id`降序，Version列表核验
  version_no降序、身份唯一、cursor不回放。
- Version详情严格接收固定Source、验收五要素、Capability人工判断、假设/排除/依赖和AI Task引用；
  声明计数必须与数组长度一致，所有ordinal从0连续，错父级、未知/多余字段和Review引用半对均失败关闭。
- 定向26项通过；本轮完整前端89个测试文件、1508项通过，typecheck/build通过。该客户端尚未进入路由或
  构建页面，A03前生产UI仍不可见。
- 无Schema/Migration、后端API、依赖、Secret、客户数据或外发变化；删除客户端文件即可回滚，
  不影响后端或历史数据。
