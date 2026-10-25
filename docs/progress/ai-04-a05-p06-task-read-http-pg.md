# AI-04-A05-P06：AI Task 安全读取与项目隔离

- 日期：2026-10-03
- 结果：PASS（Windows 11 / PostgreSQL 18.6；未调用外部 Provider）
- 依据：冻结 API-03 `AI_TASK_GET`、CR-AI-014、DEC-719

实现冻结 `GET /api/v1/projects/{project_id}/ai-tasks/{ai_task_id}` 的可选只读 Router、应用服务、显式 Windows 组合和 PostgreSQL 安全投影。项目经理、客户经理可以读取项目内 Task；其他有效项目成员只能读取自己提交的 Task。未授权、非创建人的普通成员、跨项目引用和不存在资源统一返回 404，避免通过状态差异枚举 Task。

响应仅返回 Task/Project/类型/创建人、不可变 InputRef、Prompt Policy及版本、PromptVersion引用、Output/RAG策略引用、EgressAuthorizationRef、Job/Invocation引用、状态、错误码、时间、Trace与强 ETag。查询没有读取或返回 Task参数、Prompt正文、Input正文、供应商请求/响应、Key或Token；未知 Input Owner 映射失败关闭。登录-only组合继续404，只读和写平台在具备既有正式组合前置时挂载GET。

Windows 11 / PostgreSQL 18.6真实链验证创建人和项目经理200，普通成员及跨项目访问404，带Query拒绝400，并核对响应不含参数或正文。定向43项与后端全量2157项PASS、3项既定跳过；开发wheel SHA-256 `63315024faa0b1d4f5d7776579679b6af5030743257df2b4e0dd7cb2160c6c0e`。无Schema/Migration、新依赖、客户数据外发或真实Provider调用。

Compatibility：只新增冻结GET的实现和可选组合，无Breaking URL或数据库变化。Upgrade：升至本版本并按既有Windows平台组合启动即可；Task POST策略不影响GET安全投影。Rollback：撤只读Router/组合注入即可恢复404，历史Task不变。Known Issues：Worker最终payload构造、每次Invocation、发送前限额/摘要/授权再验、正式Prompt准入与发行信任、Windows Server 2025、Gate 3/UAT/交付包待完成。Next：`AI-04-A06-P01` Worker/Invocation执行边界编码前核查。
