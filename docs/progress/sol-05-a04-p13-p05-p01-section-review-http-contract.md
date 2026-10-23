# SOL-05-A04-P13-P05-P01：Section 送审可选 HTTP 合同

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`HTTP_CONTRACT_PASS / WINDOWS_NOT_MOUNTED`。

编码前检查：Phase 2；输入 Gate 2 冻结 API-04 的 `SOL_SECTION_VERSION_SUBMIT_REVIEW`、CR-SOL-024、P13-P04-P01/P02 内部 Owner 与提交服务，前置满足。涉及 Solution HTTP 和应用组合根的可选路由参数，不改 Section/Review/Receipt 实体、Schema、License 或权限；ProjectManager 限定仍由服务执行。验收为冻结路径、Session Cookie/CSRF/Origin、固定请求字段、1～N Reviewer 服务校验、201 ReviewRef/RoundRef、ETag/no-store、统一错误与默认不挂载。风险为非法来源、额外字段或错误 Subject 响应被当作成功；全部失败关闭。

可选 POST 路由使用 `project_id/section_id/section_version_id` 精确目标，固定 `SOLUTION_SECTION_ALL_V1`，`due_at`/`submission_note` 首版仅允许 null。成功只投影 ReviewId、RoundId、固定 SectionVersion、Reviewer、IN_REVIEW、审计追踪号和 ETag；并不表示客户已批准。默认 `create_app()` 保持 404，只有明确注入该 router 才开放。本片未装配 Windows 生产组合，也未跑真实 HTTP/Session/PG；下一片负责真实环境组合和验收。

验证：可选路由合同 11/11 PASS（含默认404、来源/CSRF、字段、错误映射）；后端全量 3964 通过/3 跳过/6079 子例。

兼容/回滚：路径符合冻结 `/api/v1`，无 Breaking Change、Migration 或历史数据改写；撤可选 router 参数即可回滚未装配入口。正式信任、客户决定、Gate 3、Pilot/Release 均未通过。
