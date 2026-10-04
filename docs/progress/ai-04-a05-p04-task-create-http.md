# AI-04-A05-P04：AI Task创建HTTP合同

- 日期：2026-10-03
- 结果：PASS（可选Router合同；未装生产组合）
- 依据：冻结API-03 `AI_TASK_CREATE`、CR-AI-014、Schema0070、DEC-718

实现 `POST /api/v1/projects/{project_id}/ai-tasks` 可选Router，严格接收task type、不可变input refs、Prompt/Output/RAG策略引用、最小标量参数和EgressAuthorizationRef。入口执行可信Origin、Session/CSRF、Idempotency及严格JSON/UUID/字段校验，调用P03内部原子服务，并只返回202 TaskRef+JobRef、trace、no-store与Location。新增冻结 `AI_PROMPT_VERSION_INVALID` 和 `AI_EGRESS_AUTHORIZATION_REQUIRED` 公共安全错误。

合同测试覆盖默认404、显式202、安全投影、禁止额外敏感字段、重复JSON键/嵌套参数/非法UUID/query、Origin/Session/CSRF/Idempotency，以及Project/License/幂等/Prompt/Egress/系统错误映射。首轮唯一失败为测试误期望缺Idempotency-Key返回400；平台既有解析器实际稳定返回422，保持公共行为并修正断言后全量重跑。

定向14项PASS，后端2145项PASS、3项既定跳过；wheel SHA-256 `6f854dd6386108a0ad01c2f4b2aa8fe694af5bf0ec734be05d0f586889922ee7`。Changed：Router、可选App工厂槽、两项冻结错误码与合同测试。Compatibility：无Schema/依赖/Breaking URL；默认及当前生产仍404。Upgrade/Rollback：须先升0070并完成P05正式策略/信任组合后才可挂载；撤Router注入恢复404，历史Task不删除。Known Issues：P05部署Task Policy、Windows真实HTTP/PG组合、Task读取与旧NULL执行前置、Worker发送前撤销/payload重验、正式信任、Server2025、Gate3/UAT/交付包待完成。Next：`AI-04-A05-P05`。
