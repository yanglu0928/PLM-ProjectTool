# CR-TRC-002：Trace HTTP Owner 解析前置与实施时序

日期：2026-09-26。来源：TRC-01-A05-P03 编码前核查。状态：按持续授权调整实施时序；冻结 HTTP 契约未修改。

## 冲突与证据

冻结 API-02 的 `ResourceVersionRef` 只含 `resource_type/resource_id/version_id`，路径提供 ProjectId；内部已验证的 Trace Owner Port 则接收明确 Scope/Project 并须由所属模块证明固定版本。当前仅 `document/DOC-02` Owner 注册，且项目用户路径已通过 P02；其余 Capability/Handover/Survey/Requirement/Prototype/Solution/Plan/Output Owner 尚未具备正式持久版本与解析 Port。直接从 HTTP 输入猜 Scope、接受额外必填字段或让未注册类型进入写服务，分别会破坏冻结合同、暴露资源范围或伪造目标证明。

## 方案与选择

- A：现在仅对 DOC-02 开放同名通用 POST，其他冻结类型返回未找到。虽然安全失败关闭，但会把不完整的通用能力暴露为正式 API，不采用。
- B：保持 `/api/v1/projects/{project_id}/trace-links` 写入口未挂载；后续为各 Owner 增加内部 `ResourceVersionRef → Scope/Project/固定版本` 受权解析，明确注册和发行验收，再接 HTTP。选择 B；其间转向 Phase 2 独立的 Workflow/Review 基础任务。

## 基线差异、影响与回滚

原冻结 `ResourceVersionRef`、路径、权限及 Gate 2 提交 `64cdf09` 保持不变；仅调整实现时序。内部 P02 服务保留，但没有生产 HTTP 挂载。无 Schema、Migration、正式数据迁移或新依赖。若全部 Owner 解析与前置证明先于预期完成，可直接恢复 P03；不得通过新增未冻结必填 Scope 字段绕过。已存在的 TraceLink 历史不删除。

## 验证与剩余风险

本轮仅完成静态前置核查：冻结 API-02 与代码 Owner 注册清单核对；未声称 HTTP 验收通过。后续逐 Owner 验证 Scope/Project、固定版本、权限/状态、不可枚举错误，并以真实 Session/License/CSRF/幂等/并发/Audit 测试完整路由。当前 Gate 3 和可用程序包未通过。
